"""会话管理 - 管理用户上传和确认的会话状态"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional
from uuid import uuid4

from ..models import BaseDocument
from .core import ClassificationResult, IntentResult, RecognitionResult


class SessionState(str, Enum):
    """会话状态"""
    UPLOADING = "uploading"  # 正在上传处理
    PENDING = "pending"  # 等待用户确认
    CONFIRMED = "confirmed"  # 用户已确认
    CANCELLED = "cancelled"  # 已取消
    ERROR = "error"  # 处理出错


@dataclass
class Session:
    """会话对象
    
    维护单次上传的上下文信息，支持用户确认/修改流程。
    """
    
    session_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    state: SessionState = SessionState.UPLOADING
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    # 上传信息
    image_path: Optional[str] = None
    user_text: Optional[str] = None
    audio_path: Optional[str] = None
    
    # 处理结果
    recognition: Optional[RecognitionResult] = None
    classification: Optional[ClassificationResult] = None
    intent: Optional[IntentResult] = None
    
    # 票据对象
    document: Optional[BaseDocument] = None
    document_id: Optional[str] = None
    
    # 错误信息
    error: Optional[str] = None
    
    # 额外数据
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def update_state(self, new_state: SessionState) -> None:
        """更新会话状态
        
        Args:
            new_state: 新状态
        """
        self.state = new_state
        self.updated_at = datetime.now()
    
    def set_error(self, error: str) -> None:
        """设置错误状态
        
        Args:
            error: 错误信息
        """
        self.error = error
        self.update_state(SessionState.ERROR)
    
    def set_pending(
        self,
        document: BaseDocument,
        recognition: RecognitionResult,
        classification: ClassificationResult,
        intent: Optional[IntentResult] = None
    ) -> None:
        """设置为待确认状态
        
        Args:
            document: 票据对象
            recognition: 识别结果
            classification: 分类结果
            intent: 意图结果
        """
        self.document = document
        self.document_id = document.document_id
        self.recognition = recognition
        self.classification = classification
        self.intent = intent
        self.update_state(SessionState.PENDING)
    
    def confirm(self) -> None:
        """确认会话"""
        self.update_state(SessionState.CONFIRMED)
    
    def cancel(self) -> None:
        """取消会话"""
        self.update_state(SessionState.CANCELLED)
    
    def is_active(self) -> bool:
        """会话是否活跃
        
        Returns:
            True如果会话还在进行中
        """
        return self.state in [SessionState.UPLOADING, SessionState.PENDING]
    
    def is_completed(self) -> bool:
        """会话是否已完成
        
        Returns:
            True如果会话已确认或取消
        """
        return self.state in [SessionState.CONFIRMED, SessionState.CANCELLED]
    
    def get_summary(self) -> Dict[str, Any]:
        """获取会话摘要
        
        Returns:
            会话摘要字典
        """
        return {
            "session_id": self.session_id,
            "user_id": self.user_id,
            "state": self.state.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "document_id": self.document_id,
            "has_error": bool(self.error),
            "error": self.error
        }


class SessionManager:
    """会话管理器
    
    管理多个会话的生命周期。
    """
    
    def __init__(self):
        """初始化会话管理器"""
        self.sessions: Dict[str, Session] = {}
    
    def create_session(
        self,
        user_id: str,
        image_path: str,
        user_text: Optional[str] = None,
        audio_path: Optional[str] = None
    ) -> Session:
        """创建新会话
        
        Args:
            user_id: 用户ID
            image_path: 图片路径
            user_text: 用户文本
            audio_path: 音频路径
            
        Returns:
            新创建的会话
        """
        session = Session(
            user_id=user_id,
            image_path=image_path,
            user_text=user_text,
            audio_path=audio_path
        )
        self.sessions[session.session_id] = session
        return session
    
    def get_session(self, session_id: str) -> Optional[Session]:
        """获取会话
        
        Args:
            session_id: 会话ID
            
        Returns:
            会话对象，如果不存在返回None
        """
        return self.sessions.get(session_id)
    
    def get_user_sessions(self, user_id: str, active_only: bool = False) -> list[Session]:
        """获取用户的所有会话
        
        Args:
            user_id: 用户ID
            active_only: 是否只返回活跃会话
            
        Returns:
            会话列表
        """
        sessions = [s for s in self.sessions.values() if s.user_id == user_id]
        
        if active_only:
            sessions = [s for s in sessions if s.is_active()]
        
        return sorted(sessions, key=lambda s: s.created_at, reverse=True)
    
    def cleanup_old_sessions(self, max_age_hours: int = 24) -> int:
        """清理旧会话
        
        Args:
            max_age_hours: 最大保留时间（小时）
            
        Returns:
            清理的会话数量
        """
        from datetime import timedelta
        
        cutoff_time = datetime.now() - timedelta(hours=max_age_hours)
        old_sessions = [
            sid for sid, session in self.sessions.items()
            if session.updated_at < cutoff_time and session.is_completed()
        ]
        
        for sid in old_sessions:
            del self.sessions[sid]
        
        return len(old_sessions)
    
    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息
        
        Returns:
            统计信息字典
        """
        total = len(self.sessions)
        by_state = {}
        
        for session in self.sessions.values():
            state = session.state.value
            by_state[state] = by_state.get(state, 0) + 1
        
        return {
            "total_sessions": total,
            "by_state": by_state,
            "active_sessions": sum(1 for s in self.sessions.values() if s.is_active())
        }


__all__ = [
    "Session",
    "SessionState",
    "SessionManager",
]

