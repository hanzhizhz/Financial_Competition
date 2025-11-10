"""Agent API - 统一的Agent调用接口"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from ..models.user import User, create_new_user
from ..storage import UserStorage
from .session import SessionManager
from .workflow import AutoEntryWorkflow, FeedbackWorkflow, ProfileOptimizationWorkflow

logger = logging.getLogger(__name__)


class AgentAPI:
    """Agent统一API
    
    提供简洁的接口调用Agent的各项功能。
    """
    
    def __init__(self, storage_dir: str = "data"):
        """初始化API
        
        Args:
            storage_dir: 数据存储目录
        """
        self.storage = UserStorage(base_dir=storage_dir)
        self.session_manager = SessionManager()
        self.logger = logging.getLogger(__name__)
    
    def get_or_create_user(
        self,
        user_id: str,
        profile_items: Optional[list[str]] = None
    ) -> User:
        """获取或创建用户
        
        Args:
            user_id: 用户ID
            profile_items: 初始画像条目
            
        Returns:
            用户对象
        """
        # 尝试加载现有用户
        user = self.storage.load_user(user_id)
        
        if user:
            self.logger.info(f"加载现有用户: {user_id}")
            return user
        
        # 创建新用户
        self.logger.info(f"创建新用户: {user_id}")
        user = create_new_user(user_id, profile_items)
        self.storage.save_user(user)
        
        return user
    
    async def upload_document(
        self,
        user_id: str,
        image_path: Union[str, Path],
        text: Optional[str] = None,
        audio_path: Optional[Union[str, Path]] = None
    ) -> dict:
        """上传票据（功能一：自动入账）
        
        Args:
            user_id: 用户ID
            image_path: 图片路径
            text: 用户文本
            audio_path: 音频路径
            
        Returns:
            处理结果
        """
        try:
            # 获取用户
            user = self.get_or_create_user(user_id)
            
            # 创建工作流
            workflow = AutoEntryWorkflow(user, self.storage, self.session_manager)
            
            # 执行
            session = await workflow.execute(
                image_path=image_path,
                text=text,
                audio_path=audio_path
            )
            
            # 返回结果
            return {
                "success": session.state.value != "error",
                "session_id": session.session_id,
                "document_id": session.document_id,
                "state": session.state.value,
                "error": session.error,
                "summary": session.get_summary()
            }
            
        except Exception as e:
            self.logger.error(f"上传票据失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def confirm_document(
        self,
        session_id: str,
        modifications: Optional[dict] = None
    ) -> dict:
        """确认票据
        
        Args:
            session_id: 会话ID
            modifications: 用户修改
            
        Returns:
            确认结果
        """
        try:
            session = self.session_manager.get_session(session_id)
            if not session:
                return {
                    "success": False,
                    "error": "会话不存在"
                }
            
            user = self.storage.load_user(session.user_id)
            if not user:
                return {
                    "success": False,
                    "error": "用户不存在"
                }
            
            workflow = AutoEntryWorkflow(user, self.storage, self.session_manager)
            success = await workflow.confirm_document(session_id, modifications)
            
            # 不再自动触发反馈学习，改为手动触发
            
            return {
                "success": success,
                "document_id": session.document_id
            }
            
        except Exception as e:
            self.logger.error(f"确认票据失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def trigger_feedback_learning(
        self,
        user_id: str,
        max_feedbacks: int = 50,
        batch_size: int = 10
    ) -> dict:
        """触发反馈学习（功能二）
        
        Args:
            user_id: 用户ID
            max_feedbacks: 最多分析的反馈数量，默认50
            batch_size: 每批处理的反馈数量，默认10
            
        Returns:
            学习结果
        """
        try:
            user = self.storage.load_user(user_id)
            if not user:
                return {
                    "success": False,
                    "error": "用户不存在"
                }
            
            workflow = FeedbackWorkflow(user, self.storage)
            result = await workflow.execute(max_feedbacks=max_feedbacks, batch_size=batch_size)
            
            return {
                "success": result.get('triggered', False),
                **result
            }
            
        except Exception as e:
            self.logger.error(f"反馈学习失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def optimize_profile(
        self,
        user_id: str,
        manual: bool = False
    ) -> dict:
        """优化用户画像（功能三）
        
        Args:
            user_id: 用户ID
            manual: 是否手动触发
            
        Returns:
            优化结果
        """
        try:
            user = self.storage.load_user(user_id)
            if not user:
                return {
                    "success": False,
                    "error": "用户不存在"
                }
            
            workflow = ProfileOptimizationWorkflow(user, self.storage)
            result = await workflow.execute(manual=manual)
            
            return {
                "success": result.get('triggered', False),
                **result
            }
            
        except Exception as e:
            self.logger.error(f"画像优化失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    def get_user_summary(self, user_id: str) -> dict:
        """获取用户摘要
        
        Args:
            user_id: 用户ID
            
        Returns:
            用户摘要
        """
        try:
            user = self.storage.load_user(user_id)
            if not user:
                return {"error": "用户不存在"}
            
            return {
                "user_id": user.user_id,
                "profile": user.profile.profile_text,
                "document_count": user.get_document_count(),
                "feedback_count": user.get_feedback_count(),
                "created_at": user.created_at.isoformat(),
                "learning_summary": user.learning_history.get_learning_summary(days=30)
            }
            
        except Exception as e:
            self.logger.error(f"获取用户摘要失败: {e}")
            return {"error": str(e)}


__all__ = ["AgentAPI"]

