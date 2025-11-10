"""文档和用户数据接口 - 提供文档列表和用户摘要"""

from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional
import re

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from ..models import BaseDocument, DocumentStatus, DocumentType, UserCategory
from ..storage import UserStorage
from .auth import get_current_user
from ..agent.workflow import ProfileOptimizationWorkflow

router = APIRouter()

# pyright: reportMissingImports=false

# 全局存储实例
user_storage = UserStorage()


def _normalize_amount(value) -> Optional[float]:
    """将金额值规范化为浮点数"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("￥", "").replace(",", "").strip()
        if not cleaned:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None
    return None


def _format_date(value: Any) -> Optional[str]:
    """将日期格式化为 YYYY/MM/DD"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y/%m/%d")
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        patterns = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y/%m/%dT%H:%M:%S",
            "%Y/%m/%dT%H:%M:%S.%f",
        ]
        for pattern in patterns:
            try:
                parsed = datetime.strptime(cleaned, pattern)
                return parsed.strftime("%Y/%m/%d")
            except ValueError:
                continue
        digits_match = re.search(r"(20\d{2})(?:[-/年]?)(\d{1,2})(?:[-/月]?)(\d{1,2})", cleaned)
        if digits_match:
            year, month, day = digits_match.groups()
            return f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
    return None


class DocumentSummary(BaseModel):
    """文档摘要"""
    documentId: str
    documentType: str
    userCategory: Optional[str] = None
    tags: List[str] = []
    uploadTime: str
    status: Optional[str] = None
    sourceImage: str
    amount: Optional[float] = None
    issuedDate: Optional[str] = None


class UserSummaryResponse(BaseModel):
    """用户摘要响应"""
    user_id: str
    document_count: int
    total_amount: float
    category_stats: dict
    recent_documents: List[DocumentSummary]


class DocumentsResponse(BaseModel):
    """文档列表响应"""
    documents: List[DocumentSummary]
    total: int


class UpdateDocumentRequest(BaseModel):
    """更新文档请求"""
    document_type: Optional[str] = None
    user_category: Optional[str] = None
    tags: Optional[List[str]] = None
    amount: Optional[float] = None
    status: Optional[str] = None


class UpdateDocumentResponse(BaseModel):
    """更新文档响应"""
    success: bool
    message: str


class DeleteDocumentResponse(BaseModel):
    """删除文档响应"""
    success: bool
    message: str


class BatchConfirmRequest(BaseModel):
    """批量确认请求"""
    document_ids: List[str]


class BatchConfirmResponse(BaseModel):
    """批量确认响应"""
    success: bool
    confirmed_count: int
    failed_count: int
    message: str


class ConfirmDocumentRequest(BaseModel):
    """确认单个票据请求"""
    document_id: str


class ConfirmDocumentResponse(BaseModel):
    """确认单个票据响应"""
    success: bool
    message: str


class BatchDeleteRequest(BaseModel):
    """批量删除请求"""
    document_ids: List[str]


class BatchDeleteResponse(BaseModel):
    """批量删除响应"""
    success: bool
    deleted_count: int
    failed_count: int
    message: str


def _document_to_summary(doc: BaseDocument) -> DocumentSummary:
    """将文档对象转换为摘要"""
    # 优先使用统一金额字段
    total_amount = doc.amount
    if total_amount is None:
        # 回退到结构化数据
        structured_data = getattr(doc, "structured_data", {})
        if isinstance(structured_data, dict):
            for key in (
                "total_amount",
                "total_amount_including_tax",
                "total_amount_excluding_tax",
                "amount_in_digits",
            ):
                total_amount = _normalize_amount(structured_data.get(key))
                if total_amount is not None:
                    break
    
    # 将中文状态值转换为英文状态值（前端期望的格式）
    status_mapping = {
        DocumentStatus.PENDING: "pending",
        DocumentStatus.VERIFIED: "verified",
        DocumentStatus.VOIDED: "cancelled",
    }
    status_value = None
    if doc.status:
        status_value = status_mapping.get(doc.status, doc.status.value.lower() if hasattr(doc.status, 'value') else None)
    
    issued_date = _format_date(doc.issued_date)
    if not issued_date:
        issued_date = _format_date(doc.upload_time)

    return DocumentSummary(
        documentId=doc.document_id,
        documentType=doc.document_type.value if doc.document_type else "",
        userCategory=doc.user_category.value if doc.user_category else None,
        tags=doc.tags,
        uploadTime=doc.upload_time.isoformat() if doc.upload_time else "",
        status=status_value,
        sourceImage=doc.source_image,
        amount=total_amount,
        issuedDate=issued_date
    )


@router.get("/user_summary", response_model=UserSummaryResponse)
async def get_user_summary(
    current_user: dict = Depends(get_current_user)
):
    """获取用户摘要
    
    Returns:
        用户摘要信息，包括票据数量、总金额、分类统计等
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 加载所有文档
        documents = []
        for doc_id in user.document_ids:
            doc = user_storage.load_document(user_id, doc_id)
            if doc:
                documents.append(doc)
        
        # 计算总金额
        total_amount = 0.0
        for doc in documents:
            amount_value = doc.amount
            if amount_value is None:
                structured_data = getattr(doc, "structured_data", {})
                if isinstance(structured_data, dict):
                    for key in (
                        "total_amount",
                        "total_amount_including_tax",
                        "total_amount_excluding_tax",
                        "amount_in_digits",
                    ):
                        amount_value = _normalize_amount(structured_data.get(key))
                        if amount_value is not None:
                            break
            if amount_value is not None:
                total_amount += amount_value
        
        # 统计分类
        category_stats = {}
        for doc in documents:
            cat = doc.user_category.value if doc.user_category else "其他"
            category_stats[cat] = category_stats.get(cat, 0) + 1
        
        # 获取最近的文档（按上传时间排序，最多10个）
        recent_docs = sorted(
            documents,
            key=lambda d: d.upload_time if d.upload_time else datetime.min,
            reverse=True
        )[:10]
        
        return UserSummaryResponse(
            user_id=user_id,
            document_count=len(documents),
            total_amount=total_amount,
            category_stats=category_stats,
            recent_documents=[_document_to_summary(doc) for doc in recent_docs]
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/documents", response_model=DocumentsResponse)
async def get_documents(
    current_user: dict = Depends(get_current_user),
    limit: Optional[int] = 50,
    offset: Optional[int] = 0
):
    """获取用户的所有文档列表
    
    Args:
        limit: 返回数量限制
        offset: 偏移量
        
    Returns:
        文档列表
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 加载所有文档
        documents = []
        for doc_id in user.document_ids:
            doc = user_storage.load_document(user_id, doc_id)
            if doc:
                documents.append(doc)
        
        # 按上传时间排序（最新的在前）
        documents.sort(
            key=lambda d: d.upload_time if d.upload_time else datetime.min,
            reverse=True
        )
        
        # 分页
        total = len(documents)
        offset_value = offset or 0
        if limit is None:
            paginated_docs = documents[offset_value:]
        else:
            paginated_docs = documents[offset_value:offset_value + limit]
        
        return DocumentsResponse(
            documents=[_document_to_summary(doc) for doc in paginated_docs],
            total=total
        )
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.put("/documents/{document_id}", response_model=UpdateDocumentResponse)
async def update_document(
    document_id: str,
    request: UpdateDocumentRequest,
    current_user: dict = Depends(get_current_user),
):
    """修改票据信息
    
    Args:
        document_id: 票据ID
        request: 更新请求
        current_user: 当前登录用户
        
    Returns:
        更新响应
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 检查票据是否存在且属于当前用户
        if document_id not in user.document_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在或不属于当前用户"
            )
        
        # 加载票据
        document = user_storage.load_document(user_id, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在"
            )
        
        # 记录原始值用于反馈学习
        original_category = document.user_category.value if document.user_category else None
        original_tags = document.tags.copy()
        original_document_type = document.document_type.value if document.document_type else None
        
        # 保留原有的reasoning字段（这些字段不在更新请求中，需要保留）
        original_document_type_reasoning = document.document_type_reasoning
        original_tag_classification_reasoning = document.tag_classification_reasoning
        
        # 应用修改
        if request.document_type is not None:
            try:
                document.document_type = DocumentType(request.document_type)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的票据类型: {request.document_type}"
                )
        
        if request.user_category is not None:
            try:
                document.user_category = UserCategory(request.user_category)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的用户分类: {request.user_category}"
                )
        
        if request.tags is not None:
            document.tags = request.tags
        
        if request.amount is not None:
            # 更新结构化数据中的金额
            if not hasattr(document, 'structured_data'):
                setattr(document, 'structured_data', {})
            structured_data = getattr(document, 'structured_data', {})
            if isinstance(structured_data, dict):
                structured_data['total_amount'] = f"￥{request.amount:.2f}"
                structured_data['total_amount_including_tax'] = f"￥{request.amount:.2f}"
                setattr(document, 'structured_data', structured_data)
            document.amount = float(request.amount)
        
        if request.status is not None:
            try:
                # 前端传递的是英文状态值，需要转换为中文枚举值
                status_mapping = {
                    "pending": "待确认",
                    "verified": "已验证",
                    "cancelled": "已作废",
                }
                chinese_status = status_mapping.get(request.status, request.status)
                document.status = DocumentStatus(chinese_status)
            except (ValueError, KeyError):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"无效的状态: {request.status}"
                )
        
        # 确保reasoning字段被保留（如果原本存在）
        if original_document_type_reasoning is not None:
            document.document_type_reasoning = original_document_type_reasoning
        if original_tag_classification_reasoning is not None:
            document.tag_classification_reasoning = original_tag_classification_reasoning
        
        # 记录分类变更（用于反馈学习）
        if request.document_type is not None or request.user_category is not None or request.tags is not None:
            user.record_classification_change(
                document_id=document.document_id,
                original_category=original_document_type or document.document_type.value,
                original_user_category=original_category,
                original_tags=original_tags,
                new_category=document.document_type.value,
                new_user_category=document.user_category.value if document.user_category else None,
                new_tags=document.tags,
                modification_source="用户手动修改"
            )
        
        # 保存票据和用户
        user_storage.save_document(user_id, document)
        user_storage.save_user(user)
        
        return UpdateDocumentResponse(
            success=True,
            message="票据修改成功"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"修改票据失败: {str(e)}"
        )


@router.delete("/documents/{document_id}", response_model=DeleteDocumentResponse)
async def delete_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """删除票据
    
    Args:
        document_id: 票据ID
        current_user: 当前登录用户
        
    Returns:
        删除响应
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 检查票据是否存在且属于当前用户
        if document_id not in user.document_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在或不属于当前用户"
            )
        
        # 从用户文档列表中移除
        user.remove_document(document_id)
        
        # 删除文档文件
        user_docs_dir = user_storage.get_user_documents_dir(user_id)
        doc_file = user_docs_dir / f"{document_id}.json"
        if doc_file.exists():
            doc_file.unlink()
        
        # 保存用户
        user_storage.save_user(user)
        
        return DeleteDocumentResponse(
            success=True,
            message="票据删除成功"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除票据失败: {str(e)}"
        )


@router.post("/documents/batch_confirm", response_model=BatchConfirmResponse)
async def batch_confirm_documents(
    request: BatchConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    """批量确认票据
    
    Args:
        request: 批量确认请求
        current_user: 当前登录用户
        
    Returns:
        批量确认响应
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        confirmed_count = 0
        failed_count = 0
        
        for document_id in request.document_ids:
            try:
                # 检查票据是否存在且属于当前用户
                if document_id not in user.document_ids:
                    failed_count += 1
                    continue
                
                # 加载票据
                document = user_storage.load_document(user_id, document_id)
                if not document:
                    failed_count += 1
                    continue
                
                # 只确认待确认状态的票据
                if document.status != DocumentStatus.PENDING:
                    failed_count += 1
                    continue
                
                # 更新状态为已验证
                document.status = DocumentStatus.VERIFIED
                
                # 保存票据
                user_storage.save_document(user_id, document)
                
                confirmed_count += 1
                
            except Exception as e:
                failed_count += 1
                continue
        
        # 保存用户
        user_storage.save_user(user)
        
        return BatchConfirmResponse(
            success=True,
            confirmed_count=confirmed_count,
            failed_count=failed_count,
            message=f"成功确认 {confirmed_count} 条票据，失败 {failed_count} 条"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量确认失败: {str(e)}"
        )


@router.post("/documents/{document_id}/confirm", response_model=ConfirmDocumentResponse)
async def confirm_single_document(
    document_id: str,
    current_user: dict = Depends(get_current_user),
):
    """确认单个票据
    
    Args:
        document_id: 票据ID
        current_user: 当前登录用户
        
    Returns:
        确认响应
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 检查票据是否存在且属于当前用户
        if document_id not in user.document_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在或不属于当前用户"
            )
        
        # 加载票据
        document = user_storage.load_document(user_id, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在"
            )
        
        # 只确认待确认状态的票据
        if document.status != DocumentStatus.PENDING:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="只能确认待确认状态的票据"
            )
        
        # 更新状态为已验证
        document.status = DocumentStatus.VERIFIED
        
        # 保存票据
        user_storage.save_document(user_id, document)
        user_storage.save_user(user)
        
        return ConfirmDocumentResponse(
            success=True,
            message="票据确认成功"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认票据失败: {str(e)}"
        )


@router.post("/documents/batch_delete", response_model=BatchDeleteResponse)
async def batch_delete_documents(
    request: BatchDeleteRequest,
    current_user: dict = Depends(get_current_user),
):
    """批量删除票据
    
    Args:
        request: 批量删除请求
        current_user: 当前登录用户
        
    Returns:
        批量删除响应
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        deleted_count = 0
        failed_count = 0
        
        for document_id in request.document_ids:
            try:
                # 检查票据是否存在且属于当前用户
                if document_id not in user.document_ids:
                    failed_count += 1
                    continue
                
                # 从用户文档列表中移除
                user.remove_document(document_id)
                
                # 删除文档文件
                user_docs_dir = user_storage.get_user_documents_dir(user_id)
                doc_file = user_docs_dir / f"{document_id}.json"
                if doc_file.exists():
                    doc_file.unlink()
                
                deleted_count += 1
                
            except Exception as e:
                failed_count += 1
                continue
        
        # 保存用户
        user_storage.save_user(user)
        
        return BatchDeleteResponse(
            success=True,
            deleted_count=deleted_count,
            failed_count=failed_count,
            message=f"成功删除 {deleted_count} 条票据，失败 {failed_count} 条"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"批量删除失败: {str(e)}"
        )


class OptimizeProfileRequest(BaseModel):
    """画像优化请求"""
    manual: bool = True


class ProfileOptimizationResponse(BaseModel):
    """画像优化响应"""
    success: bool
    triggered: Optional[bool] = None
    updated_profile: Optional[List[str]] = None
    operations_count: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None


@router.post("/optimize_profile", response_model=ProfileOptimizationResponse)
async def optimize_profile(
    request: OptimizeProfileRequest,
    current_user: dict = Depends(get_current_user)
) -> ProfileOptimizationResponse:
    """手动触发用户画像优化
    
    基于画像更新后的历史票据数据，优化用户画像。
    
    Args:
        request: 优化请求（manual=True表示手动触发）
        current_user: 当前登录用户
        
    Returns:
        画像优化响应
    """
    try:
        user_id = current_user["user_id"]
        user = user_storage.load_user(user_id)
        
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 执行画像优化
        workflow = ProfileOptimizationWorkflow(user, user_storage)
        result = await workflow.execute(manual=request.manual)
        
        return ProfileOptimizationResponse(
            success=result.get('success', False),
            triggered=result.get('triggered', False),
            updated_profile=result.get('updated_profile'),
            operations_count=result.get('operations_count', 0),
            message=result.get('message'),
            error=result.get('error')
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        return ProfileOptimizationResponse(
            success=False,
            triggered=False,
            error=str(e)
        )

