"""工作流编排 - 编排三大核心工作流"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional, Union

from ..models import BaseDocument, DocumentStatus
from ..models.user import User
from ..storage import UserStorage
from .core import DocumentAgent, ProcessResult
from .learning import FeedbackLearner
from .profile_optimizer import ProfileOptimizer
from .session import Session, SessionManager, SessionState

logger = logging.getLogger(__name__)


class AutoEntryWorkflow:
    """自动入账工作流
    
    处理完整的上传、识别、分类、入账流程。
    """
    
    def __init__(
        self,
        user: User,
        storage: UserStorage,
        session_manager: Optional[SessionManager] = None
    ):
        """初始化工作流
        
        Args:
            user: 用户对象
            storage: 存储管理器
            session_manager: 会话管理器（可选）
        """
        self.user = user
        self.storage = storage
        self.session_manager = session_manager or SessionManager()
        self.agent = DocumentAgent(user)
        self.logger = logging.getLogger(f"{__name__}.AutoEntry.{user.user_id}")
    
    async def execute(
        self,
        image_path: Union[str, Path],
        text: Optional[str] = None,
        audio_path: Optional[Union[str, Path]] = None
    ) -> Session:
        """执行自动入账流程
        
        Args:
            image_path: 图片路径
            text: 用户文本
            audio_path: 音频路径
            
        Returns:
            会话对象
        """
        # 创建会话
        session = self.session_manager.create_session(
            user_id=self.user.user_id,
            image_path=str(image_path),
            user_text=text,
            audio_path=str(audio_path) if audio_path else None
        )
        
        try:
            self.logger.info(f"开始自动入账流程，会话ID: {session.session_id}")
            
            # 调用Agent处理
            result: ProcessResult = await self.agent.process_upload(
                image_path=image_path,
                text=text,
                audio_path=audio_path
            )
            
            if not result.success:
                session.set_error(result.error or "处理失败")
                return session
            
            # 设置为待确认状态
            session.set_pending(
                document=result.document,
                recognition=result.recognition,
                classification=result.classification,
                intent=result.intent
            )
            
            # 保存票据（待确认状态）
            self.storage.save_document(self.user.user_id, result.document)
            
            # 添加到用户票据列表
            self.user.add_document(result.document.document_id)
            
            # 保存用户
            self.storage.save_user(self.user)
            
            self.logger.info(f"自动入账完成，票据ID: {result.document_id}，状态: 待确认")
            
            return session
            
        except Exception as e:
            self.logger.error(f"自动入账失败: {e}", exc_info=True)
            session.set_error(str(e))
            return session
    
    async def confirm_document(
        self,
        session_id: str,
        modifications: Optional[dict] = None
    ) -> bool:
        """确认票据
        
        Args:
            session_id: 会话ID
            modifications: 用户修改（可选）
            
        Returns:
            True如果确认成功
        """
        try:
            session = self.session_manager.get_session(session_id)
            if not session or not session.document:
                self.logger.error(f"会话不存在或无票据: {session_id}")
                return False
            
            document = session.document
            
            # 如果有修改，应用修改并记录反馈
            if modifications:
                original_category = document.user_category.value if document.user_category else None
                original_tags = document.tags.copy()
                
                # 应用修改
                if 'user_category' in modifications:
                    # 这里需要转换为枚举
                    pass  # 简化实现
                
                if 'tags' in modifications:
                    document.tags = modifications['tags']
                
                # 记录反馈
                self.user.record_classification_change(
                    document_id=document.document_id,
                    original_category=document.document_type.value,
                    original_user_category=original_category,
                    original_tags=original_tags,
                    new_category=document.document_type.value,
                    new_user_category=document.user_category.value if document.user_category else None,
                    new_tags=document.tags,
                    modification_source="用户手动"
                )
            
            # 更新状态为已验证
            document.status = DocumentStatus.VERIFIED
            
            # 保存
            self.storage.save_document(self.user.user_id, document)
            self.storage.save_user(self.user)
            
            # 确认会话
            session.confirm()
            
            self.logger.info(f"票据已确认: {document.document_id}")
            
            return True
            
        except Exception as e:
            self.logger.error(f"确认票据失败: {e}", exc_info=True)
            return False


class FeedbackWorkflow:
    """反馈学习工作流
    
    手动触发，基于用户修改历史生成分类规则。
    """
    
    def __init__(self, user: User, storage: UserStorage):
        """初始化工作流
        
        Args:
            user: 用户对象
            storage: 存储管理器
        """
        self.user = user
        self.storage = storage
        self.learner = FeedbackLearner(user, user_storage=storage)
        self.logger = logging.getLogger(f"{__name__}.Feedback.{user.user_id}")
    
    async def execute(self, max_feedbacks: int = 50, batch_size: int = 10) -> dict:
        """执行反馈学习流程（手动触发）
        
        Args:
            max_feedbacks: 最多分析的反馈数量，默认50
            batch_size: 每批处理的反馈数量，默认10
            
        Returns:
            学习结果
        """
        try:
            self.logger.info("开始反馈学习流程（手动触发）...")
            
            # 生成规则（不再检查自动触发条件）
            result = await self.learner.generate_rules(max_feedbacks=max_feedbacks, batch_size=batch_size)
            
            # 保存用户（规则已更新到settings中）
            self.storage.save_user(self.user)
            
            self.logger.info(f"反馈学习完成，生成{len(result.rules)}条规则")
            
            return {
                "triggered": True,
                "rules_count": len(result.rules),
                "rules": [r.rule_text for r in result.rules],
                "summary": result.summary,
                "feedback_count": result.feedback_count
            }
            
        except Exception as e:
            self.logger.error(f"反馈学习失败: {e}", exc_info=True)
            return {
                "triggered": False,
                "error": str(e)
            }


class ProfileOptimizationWorkflow:
    """用户画像优化工作流
    
    根据触发条件优化用户画像。
    """
    
    def __init__(self, user: User, storage: UserStorage):
        """初始化工作流
        
        Args:
            user: 用户对象
            storage: 存储管理器
        """
        self.user = user
        self.storage = storage
        self.optimizer = ProfileOptimizer(user, storage)
        self.logger = logging.getLogger(f"{__name__}.ProfileOpt.{user.user_id}")
    
    async def execute(self, manual: bool = False) -> dict:
        """执行画像优化流程
        
        Args:
            manual: 是否手动触发
            
        Returns:
            优化结果
        """
        try:
            self.logger.info(f"开始画像优化流程，手动触发: {manual}")
            
            # 检查触发条件
            trigger = self.optimizer.should_trigger(manual=manual)
            
            if not any([trigger.manual, trigger.continuous_modifications, trigger.time_based]):
                self.logger.info(f"不满足触发条件: {trigger.reason}")
                return {
                    "triggered": False,
                    "reason": trigger.reason
                }
            
            self.logger.info(f"触发条件满足: {trigger.reason}")
            
            # 执行优化
            result = await self.optimizer.optimize_profile()
            
            if result.get('success'):
                # 保存用户
                self.storage.save_user(self.user)
                
                self.logger.info(f"画像优化完成，变更{len(result.get('changes', []))}处")
            
            return {
                "triggered": True,
                "trigger_reason": trigger.reason,
                **result
            }
            
        except Exception as e:
            self.logger.error(f"画像优化失败: {e}", exc_info=True)
            return {
                "triggered": False,
                "error": str(e)
            }


__all__ = [
    "AutoEntryWorkflow",
    "FeedbackWorkflow",
    "ProfileOptimizationWorkflow",
]

