"""学习历史模型 - 记录用户分类修改行为，实现反馈学习"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import uuid4


@dataclass
class ClassificationFeedback:
    """分类反馈记录
    
    记录用户对票据分类的修改，用于学习用户的分类习惯和偏好。
    """
    
    feedback_id: str = field(default_factory=lambda: str(uuid4()))
    document_id: str = ""  # 票据ID
    timestamp: datetime = field(default_factory=datetime.now)  # 修改时间
    
    # 原始分类信息
    original_category: str = ""  # 原分类（专业视角）
    original_user_category: Optional[str] = None  # 原用户分类
    original_tags: List[str] = field(default_factory=list)  # 原标签列表
    
    # 新分类信息
    new_category: str = ""  # 新分类
    new_user_category: Optional[str] = None  # 新用户分类
    new_tags: List[str] = field(default_factory=list)  # 新标签列表
    
    # 修改来源
    modification_source: str = "用户手动"  # 用户手动 | AI建议
    
    def is_category_changed(self) -> bool:
        """专业分类是否改变"""
        return self.original_category != self.new_category
    
    def is_user_category_changed(self) -> bool:
        """用户分类是否改变"""
        return self.original_user_category != self.new_user_category
    
    def is_tags_changed(self) -> bool:
        """标签是否改变"""
        return set(self.original_tags) != set(self.new_tags)
    
    def get_added_tags(self) -> List[str]:
        """获取新增的标签"""
        return [tag for tag in self.new_tags if tag not in self.original_tags]
    
    def get_removed_tags(self) -> List[str]:
        """获取移除的标签"""
        return [tag for tag in self.original_tags if tag not in self.new_tags]


@dataclass
class LearningHistory:
    """学习历史
    
    管理用户的所有分类修改反馈，提供统计分析功能。
    """
    
    user_id: str
    feedbacks: List[ClassificationFeedback] = field(default_factory=list)
    
    def add_feedback(
        self,
        document_id: str,
        original_category: str,
        original_user_category: Optional[str],
        original_tags: List[str],
        new_category: str,
        new_user_category: Optional[str],
        new_tags: List[str],
        modification_source: str = "用户手动"
    ) -> str:
        """添加新反馈
        
        Returns:
            反馈ID
        """
        feedback = ClassificationFeedback(
            document_id=document_id,
            original_category=original_category,
            original_user_category=original_user_category,
            original_tags=original_tags,
            new_category=new_category,
            new_user_category=new_user_category,
            new_tags=new_tags,
            modification_source=modification_source
        )
        self.feedbacks.append(feedback)
        return feedback.feedback_id
    
    def get_recent_feedbacks(self, days: int = 30) -> List[ClassificationFeedback]:
        """获取最近N天的反馈
        
        Args:
            days: 天数
            
        Returns:
            反馈列表
        """
        cutoff_time = datetime.now() - timedelta(days=days)
        return [
            fb for fb in self.feedbacks 
            if fb.timestamp >= cutoff_time
        ]
    
    def get_tag_usage_stats(self, days: Optional[int] = None) -> Dict[str, int]:
        """统计标签使用频率
        
        Args:
            days: 统计最近N天，None表示全部
            
        Returns:
            标签到使用次数的映射
        """
        feedbacks = self.get_recent_feedbacks(days) if days else self.feedbacks
        
        tag_counter = Counter()
        for fb in feedbacks:
            tag_counter.update(fb.new_tags)
        
        return dict(tag_counter)
    
    def get_category_change_patterns(
        self, 
        days: Optional[int] = None
    ) -> Dict[Tuple[str, str], int]:
        """分析分类修改模式
        
        统计从某个类别改为另一个类别的频率。
        
        Args:
            days: 统计最近N天，None表示全部
            
        Returns:
            (原类别, 新类别) -> 次数的映射
        """
        feedbacks = self.get_recent_feedbacks(days) if days else self.feedbacks
        
        pattern_counter = Counter()
        for fb in feedbacks:
            if fb.is_user_category_changed() and fb.original_user_category and fb.new_user_category:
                pattern = (fb.original_user_category, fb.new_user_category)
                pattern_counter[pattern] += 1
        
        return dict(pattern_counter)
    
    def get_most_used_tags(self, top_n: int = 10, days: Optional[int] = None) -> List[Tuple[str, int]]:
        """获取最常用的标签
        
        Args:
            top_n: 返回前N个
            days: 统计最近N天，None表示全部
            
        Returns:
            (标签, 使用次数) 列表
        """
        stats = self.get_tag_usage_stats(days)
        return sorted(stats.items(), key=lambda x: x[1], reverse=True)[:top_n]
    
    def get_category_tag_preferences(
        self, 
        user_category: str,
        days: Optional[int] = None
    ) -> Dict[str, int]:
        """获取某个类别下的标签使用偏好
        
        Args:
            user_category: 用户类别
            days: 统计最近N天，None表示全部
            
        Returns:
            标签到使用次数的映射
        """
        feedbacks = self.get_recent_feedbacks(days) if days else self.feedbacks
        
        tag_counter = Counter()
        for fb in feedbacks:
            if fb.new_user_category == user_category:
                tag_counter.update(fb.new_tags)
        
        return dict(tag_counter)
    
    def get_modification_source_stats(self, days: Optional[int] = None) -> Dict[str, int]:
        """统计修改来源分布
        
        Args:
            days: 统计最近N天，None表示全部
            
        Returns:
            修改来源到次数的映射
        """
        feedbacks = self.get_recent_feedbacks(days) if days else self.feedbacks
        
        source_counter = Counter(fb.modification_source for fb in feedbacks)
        return dict(source_counter)
    
    def get_feedback_count(self) -> int:
        """获取反馈总数"""
        return len(self.feedbacks)
    
    def get_learning_summary(self, days: int = 30) -> Dict[str, any]:
        """获取学习摘要
        
        Args:
            days: 统计最近N天
            
        Returns:
            包含各种统计信息的字典
        """
        recent_feedbacks = self.get_recent_feedbacks(days)
        
        return {
            "total_feedbacks": len(self.feedbacks),
            "recent_feedbacks": len(recent_feedbacks),
            "days": days,
            "most_used_tags": self.get_most_used_tags(top_n=5, days=days),
            "modification_sources": self.get_modification_source_stats(days=days),
            "category_changes": len([
                fb for fb in recent_feedbacks 
                if fb.is_user_category_changed()
            ]),
            "tag_changes": len([
                fb for fb in recent_feedbacks 
                if fb.is_tags_changed()
            ]),
        }


__all__ = [
    "ClassificationFeedback",
    "LearningHistory",
]

