"""上传接口 - 处理图片/语音/文本上传"""

from __future__ import annotations

import asyncio
import logging
import tempfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from pydantic import BaseModel

from ..agent.session import SessionManager, SessionState
from ..agent.workflow import AutoEntryWorkflow
from ..multimodal.audio import transcribe_audio
from ..storage.user_storage import UserStorage
from .auth import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()

# 全局存储实例
user_storage = UserStorage()

# 全局会话管理器（确保所有请求共享同一个会话管理器）
session_manager = SessionManager()

# 文件大小限制（5MB）
MAX_FILE_SIZE = 5 * 1024 * 1024


class UploadResponse(BaseModel):
    """上传响应"""
    success: bool
    sessionId: Optional[str] = None
    documentId: Optional[str] = None
    state: Optional[str] = None
    error: Optional[str] = None
    recognition: Optional[dict] = None
    classification: Optional[dict] = None


class ConfirmRequest(BaseModel):
    """确认请求"""
    sessionId: str
    modifications: Optional[dict] = None


class ConfirmResponse(BaseModel):
    """确认响应"""
    success: bool
    documentId: Optional[str] = None
    error: Optional[str] = None


class TranscribeResponse(BaseModel):
    """音频转文本响应"""
    success: bool
    text: Optional[str] = None
    error: Optional[str] = None


def validate_file(file: UploadFile, field_name: str, max_size: int = MAX_FILE_SIZE) -> None:
    """验证文件大小和类型"""
    if file.size and file.size > max_size:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name}文件过大，最大允许{max_size / 1024 / 1024:.1f}MB（当前：{file.size / 1024 / 1024:.2f}MB）"
        )
    
    # 验证文件类型（基本检查）
    if field_name == "image" and file.content_type:
        allowed_image_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp", "application/pdf"]
        if file.content_type not in allowed_image_types:
            logger.warning(f"图片文件类型可能不受支持: {file.content_type}")
    
    if field_name == "audio" and file.content_type:
        allowed_audio_types = ["audio/mpeg", "audio/mp3", "audio/wav", "audio/ogg", "audio/webm"]
        if file.content_type not in allowed_audio_types:
            logger.warning(f"音频文件类型可能不受支持: {file.content_type}")


@router.post("/upload", response_model=UploadResponse)
async def upload_document(
    image: UploadFile = File(...),
    audio: Optional[UploadFile] = File(None),
    text: Optional[str] = Form(None),
    remarks: Optional[str] = Form(None),
    current_user: dict = Depends(get_current_user),
):
    """上传票据图片和可选的语音/文本说明
    
    Args:
        image: 票据图片文件（必需）
        audio: 可选的语音文件
        text: 可选的文本说明
        remarks: 可选的备注
        current_user: 当前登录用户
        
    Returns:
        上传响应，包含会话ID和识别结果
    """
    user_id = current_user.get("user_id")
    
    logger.info(f"[上传接口] 收到上传请求: user_id={user_id}")
    logger.info(f"[上传接口] 文件信息: image={image.filename}, size={image.size}, type={image.content_type}")
    logger.info(f"[上传接口] 可选字段: audio={audio.filename if audio else None}, text={'有' if text else '无'}, remarks={'有' if remarks else '无'}")
    
    try:
        # 验证用户
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        # 验证图片文件
        if not image.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="图片文件名为空"
            )
        
        # 验证文件大小（注意：UploadFile.size 可能为 None，需要读取后检查）
        try:
            # 先读取图片内容以获取实际大小
            image_content = await image.read()
            image_size = len(image_content)
            
            logger.info(f"[上传接口] 图片文件实际大小: {image_size} bytes ({image_size / 1024 / 1024:.2f} MB)")
            
            if image_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"图片文件过大，最大允许{MAX_FILE_SIZE / 1024 / 1024:.1f}MB（当前：{image_size / 1024 / 1024:.2f}MB）"
                )
            
            if image_size == 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="图片文件为空"
                )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"[上传接口] 读取图片文件失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"读取图片文件失败: {str(e)}"
            )
        
        # 确保用户存在
        user = user_storage.create_user_if_not_exists(user_id)
        logger.info(f"[上传接口] 用户已确认/创建: {user_id}")
        
        # 保存图片到用户目录
        upload_dir = user_storage.get_user_upload_dir(user_id)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # 清理文件名，避免路径问题
        safe_filename = "".join(c for c in image.filename if c.isalnum() or c in "._-")
        image_filename = f"{timestamp}_{safe_filename}"
        image_path = upload_dir / image_filename
        
        logger.info(f"[上传接口] 保存图片到: {image_path}")
        
        # 写入图片文件
        try:
            with image_path.open("wb") as f:
                f.write(image_content)
            logger.info(f"[上传接口] 图片文件保存成功: {image_path}")
        except Exception as e:
            logger.error(f"[上传接口] 保存图片文件失败: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"保存图片文件失败: {str(e)}"
            )
        
        # 处理音频（如果有）
        audio_path = None
        if audio and audio.filename:
            try:
                audio_content = await audio.read()
                audio_size = len(audio_content)
                
                logger.info(f"[上传接口] 音频文件大小: {audio_size} bytes ({audio_size / 1024 / 1024:.2f} MB)")
                
                if audio_size > MAX_FILE_SIZE:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"音频文件过大，最大允许{MAX_FILE_SIZE / 1024 / 1024:.1f}MB（当前：{audio_size / 1024 / 1024:.2f}MB）"
                    )
                
                safe_audio_filename = "".join(c for c in audio.filename if c.isalnum() or c in "._-")
                audio_filename = f"{timestamp}_{safe_audio_filename}"
                audio_path = upload_dir / audio_filename
                
                with audio_path.open("wb") as f:
                    f.write(audio_content)
                
                logger.info(f"[上传接口] 音频文件保存成功: {audio_path}")
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"[上传接口] 处理音频文件失败: {e}")
                # 音频文件失败不影响主流程，只记录警告
                logger.warning(f"[上传接口] 音频文件处理失败，继续处理图片: {e}")
        
        # 合并文本和备注
        combined_text = text
        if remarks:
            combined_text = f"{text}\n备注：{remarks}" if text else remarks
        
        logger.info(f"[上传接口] 准备调用工作流处理，文本长度: {len(combined_text) if combined_text else 0}")
        
        # 调用 Agent 工作流处理（使用全局会话管理器）
        workflow = AutoEntryWorkflow(user=user, storage=user_storage, session_manager=session_manager)
        
        # 执行自动入账流程
        logger.info(f"[上传接口] 开始执行工作流...")
        session = await workflow.execute(
            image_path=str(image_path),
            text=combined_text,
            audio_path=str(audio_path) if audio_path else None,
        )
        
        logger.info(f"[上传接口] 工作流执行完成，会话状态: {session.state.value}, session_id: {session.session_id}")
        
        # 构建响应
        if session.state == SessionState.ERROR:
            error_msg = session.error or "处理失败"
            logger.error(f"[上传接口] 工作流执行失败: {error_msg}")
            return UploadResponse(
                success=False,
                error=error_msg,
            )
        
        # 提取识别数据
        recognition_data = None
        if session.recognition:
            recognition_data = {
                "markdown_content": session.recognition.markdown_content,
                "document_type": session.recognition.document_type,
            }
            logger.info(f"[上传接口] 识别结果: document_type={session.recognition.document_type}")
        
        # 提取分类数据
        classification_data = None
        if session.classification:
            classification_data = {
                "professional_category": session.classification.professional_category,
                "user_category": session.classification.user_category,
                "tags": session.classification.tags,
                "reasoning": session.classification.reasoning or "",  # 添加推理说明字段
            }
            logger.info(f"[上传接口] 分类结果: user_category={session.classification.user_category}, tags={session.classification.tags}, reasoning={session.classification.reasoning[:50] if session.classification.reasoning else '无'}")
        
        response = UploadResponse(
            success=True,
            sessionId=session.session_id,
            documentId=session.document_id,
            state=session.state.value,
            recognition=recognition_data,
            classification=classification_data,
        )
        
        logger.info(f"[上传接口] 上传处理成功，返回响应")
        return response
    
    except HTTPException:
        # 重新抛出HTTP异常
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"[上传接口] 处理异常: {error_msg}\n{error_trace}")
        traceback.print_exc()
        
        return UploadResponse(
            success=False,
            error=f"服务器内部错误: {error_msg}",
        )


@router.post("/confirm", response_model=ConfirmResponse)
async def confirm_document(
    request: ConfirmRequest,
    current_user: dict = Depends(get_current_user),
):
    """确认票据入账
    
    Args:
        request: 确认请求
        current_user: 当前登录用户
        
    Returns:
        确认响应
    """
    user_id = current_user.get("user_id")
    
    logger.info(f"[确认接口] 收到确认请求: user_id={user_id}, sessionId={request.sessionId}")
    
    try:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        # 确保用户存在
        user = user_storage.create_user_if_not_exists(user_id)
        
        # 调用工作流确认（使用全局会话管理器）
        workflow = AutoEntryWorkflow(user=user, storage=user_storage, session_manager=session_manager)
        success = await workflow.confirm_document(
            session_id=request.sessionId,
            modifications=request.modifications,
        )
        
        if success:
            # 从工作流的会话管理器获取会话以获取文档ID
            session = workflow.session_manager.get_session(request.sessionId)
            document_id = session.document_id if session else None
            
            logger.info(f"[确认接口] 确认成功: documentId={document_id}")
            
            return ConfirmResponse(
                success=True,
                documentId=document_id,
            )
        else:
            logger.warning(f"[确认接口] 确认失败: sessionId={request.sessionId}")
            return ConfirmResponse(
                success=False,
                error="确认失败",
            )
    
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"[确认接口] 处理异常: {error_msg}\n{error_trace}")
        traceback.print_exc()
        
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"确认失败: {error_msg}",
        )


@router.post("/transcribe", response_model=TranscribeResponse)
async def transcribe_audio_file(
    audio: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """将音频文件转换为文本
    
    Args:
        audio: 音频文件
        current_user: 当前登录用户
        
    Returns:
        转文本响应，包含转换后的文本
    """
    user_id = current_user.get("user_id")
    
    logger.info(f"[转文本接口] 收到转文本请求: user_id={user_id}, audio={audio.filename}")
    
    try:
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="用户未认证"
            )
        
        if not audio.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="音频文件名为空"
            )
        
        # 读取音频内容
        audio_content = await audio.read()
        audio_size = len(audio_content)
        
        logger.info(f"[转文本接口] 音频文件大小: {audio_size} bytes ({audio_size / 1024 / 1024:.2f} MB)")
        
        if audio_size > MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"音频文件过大，最大允许{MAX_FILE_SIZE / 1024 / 1024:.1f}MB（当前：{audio_size / 1024 / 1024:.2f}MB）"
            )
        
        if audio_size == 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="音频文件为空"
            )
        
        # 确定文件扩展名和MIME类型
        mime_type = audio.content_type or "audio/wav"
        original_filename = audio.filename or "audio.wav"
        
        # 根据MIME类型确定文件扩展名
        if "webm" in mime_type.lower():
            file_extension = "webm"
        elif "mp4" in mime_type.lower() or "m4a" in mime_type.lower():
            file_extension = "mp4"
        elif "ogg" in mime_type.lower():
            file_extension = "ogg"
        else:
            file_extension = "wav"
        
        # 创建临时文件保存音频
        temp_file = None
        temp_file_path = None
        
        try:
            # 创建临时文件
            with tempfile.NamedTemporaryFile(
                mode='wb',
                suffix=f'.{file_extension}',
                delete=False,
                prefix='audio_transcribe_'
            ) as temp_file:
                temp_file.write(audio_content)
                temp_file_path = Path(temp_file.name)
                logger.info(f"[转文本接口] 音频已保存到临时文件: {temp_file_path}")
            
            # 如果需要转换格式（webm/ogg -> wav）
            final_file_path = temp_file_path
            if file_extension in ['webm', 'ogg']:
                logger.info(f"[转文本接口] 检测到不支持的格式 {mime_type}，尝试转换为wav格式")
                try:
                    from pydub import AudioSegment
                    from pydub.utils import which
                    
                    if not which("ffmpeg"):
                        raise ImportError("ffmpeg not found")
                    
                    # 读取原始音频
                    audio_segment = AudioSegment.from_file(str(temp_file_path), format=file_extension)
                    
                    # 创建新的临时wav文件
                    with tempfile.NamedTemporaryFile(
                        mode='wb',
                        suffix='.wav',
                        delete=False,
                        prefix='audio_transcribe_'
                    ) as wav_temp_file:
                        wav_file_path = Path(wav_temp_file.name)
                    
                    # 导出为wav格式
                    audio_segment.export(str(wav_file_path), format="wav")
                    
                    # 删除原始临时文件
                    if temp_file_path.exists():
                        temp_file_path.unlink()
                        logger.info(f"[转文本接口] 已删除原始临时文件: {temp_file_path}")
                    
                    final_file_path = wav_file_path
                    mime_type = "audio/wav"
                    logger.info(f"[转文本接口] 成功转换为wav格式，文件: {final_file_path}, 大小: {final_file_path.stat().st_size} bytes")
                    
                except ImportError:
                    logger.warning("[转文本接口] pydub或ffmpeg未安装，无法转换音频格式")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"音频格式 {mime_type} 不支持。请安装 pydub 和 ffmpeg 以支持格式转换，或使用 wav/mp3 格式。"
                    )
                except Exception as convert_error:
                    logger.error(f"[转文本接口] 音频格式转换失败: {convert_error}")
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail=f"音频格式转换失败: {str(convert_error)}。请使用 wav 或 mp3 格式。"
                    )
            
            # 调用转文本API（使用文件路径）
            logger.info(f"[转文本接口] 开始转文本，文件: {final_file_path}, 格式: {mime_type}, 大小: {final_file_path.stat().st_size} bytes")
            result = await transcribe_audio(
                audio=str(final_file_path),
                filename=final_file_path.name,
                mime_type=mime_type
            )
            
            # 提取文本内容
            text = result.get("text", "")
            
            if not text:
                logger.warning(f"[转文本接口] 转文本结果为空")
                return TranscribeResponse(
                    success=False,
                    error="转文本结果为空，请检查音频文件"
                )
            
            logger.info(f"[转文本接口] 转文本成功，文本长度: {len(text)}")
            
            return TranscribeResponse(
                success=True,
                text=text
            )
        
        finally:
            # 清理临时文件
            if temp_file_path and temp_file_path.exists():
                try:
                    temp_file_path.unlink()
                    logger.info(f"[转文本接口] 已删除临时文件: {temp_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[转文本接口] 删除临时文件失败: {cleanup_error}")
            
            if 'final_file_path' in locals() and final_file_path != temp_file_path and final_file_path.exists():
                try:
                    final_file_path.unlink()
                    logger.info(f"[转文本接口] 已删除转换后的临时文件: {final_file_path}")
                except Exception as cleanup_error:
                    logger.warning(f"[转文本接口] 删除转换后的临时文件失败: {cleanup_error}")
    
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_msg = str(e)
        error_trace = traceback.format_exc()
        logger.error(f"[转文本接口] 处理异常: {error_msg}\n{error_trace}")
        traceback.print_exc()
        
        # 确保临时文件被清理
        if 'temp_file_path' in locals() and temp_file_path and temp_file_path.exists():
            try:
                temp_file_path.unlink()
                logger.info(f"[转文本接口] 异常处理：已删除临时文件: {temp_file_path}")
            except:
                pass
        
        if 'final_file_path' in locals() and final_file_path and final_file_path.exists() and final_file_path != temp_file_path:
            try:
                final_file_path.unlink()
                logger.info(f"[转文本接口] 异常处理：已删除转换后的临时文件: {final_file_path}")
            except:
                pass
        
        return TranscribeResponse(
            success=False,
            error=f"转文本失败: {error_msg}",
        )
