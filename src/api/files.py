"""文件访问接口 - 提供票据图片等文件的访问"""

from pathlib import Path
from typing import Optional
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import FileResponse

from .auth import SESSION_TOKENS
from ..storage import UserStorage

router = APIRouter()

# 全局存储实例
user_storage = UserStorage()


@router.get("/files/{document_id}/{filename}")
async def get_document_file(
    document_id: str,
    filename: str,
    token: Optional[str] = Query(None, description="认证token"),
):
    """获取票据文件（图片等）
    
    由于浏览器img标签不会发送Authorization header，
    这里使用查询参数传递token
    
    Args:
        document_id: 票据ID
        filename: 文件名
        token: 认证token（查询参数）
        
    Returns:
        文件响应
    """
    try:
        # 验证 token
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="缺少认证token"
            )
        
        user_info = SESSION_TOKENS.get(token)
        if not user_info:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="无效的token"
            )
        
        user_id = user_info["user_id"]
        
        # 加载用户
        user = user_storage.load_user(user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="用户不存在"
            )
        
        # 检查票据是否属于当前用户
        if document_id not in user.document_ids:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在或不属于当前用户"
            )
        
        # 加载票据以获取文件路径
        document = user_storage.load_document(user_id, document_id)
        if not document:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据不存在"
            )
        
        # 从 source_image 路径中查找文件
        if not document.source_image:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="票据没有关联的图片文件"
            )
        
        # 转换为 Path 对象
        source_path = Path(document.source_image)
        
        # 验证文件存在
        if not source_path.exists():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"文件不存在: {filename}"
            )
        
        # 验证文件名匹配（安全检查）
        if source_path.name != filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="文件名不匹配"
            )
        
        # 根据文件扩展名判断 MIME 类型
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.bmp': 'image/bmp',
            '.webp': 'image/webp',
            '.svg': 'image/svg+xml',
        }
        file_ext = source_path.suffix.lower()
        media_type = mime_types.get(file_ext, 'application/octet-stream')
        
        # 返回文件
        return FileResponse(
            path=source_path,
            media_type=media_type,
            filename=filename
        )
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取文件失败: {str(e)}"
        )

