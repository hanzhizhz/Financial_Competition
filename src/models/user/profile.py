"""用户模型 - 用户画像和个人数据管理"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .categories import UserCategoryTemplate, create_default_template
from .learning import LearningHistory


@dataclass
class UserProfile:
    """用户画像
    
    使用灵活的文本列表结构，通过提示词抽取用户特征。
    可以包含职业、收入水平、家庭状况、消费习惯等任意维度。
    """
    
    user_id: str
    profile_text: List[str] = field(default_factory=list)  # 用户画像文本列表
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)
    
    def add_profile_item(self, item: str) -> None:
        """添加画像条目"""
        if item and item not in self.profile_text:
            self.profile_text.append(item)
            self.updated_at = datetime.now()
    
    def remove_profile_item(self, item: str) -> bool:
        """移除画像条目"""
        if item in self.profile_text:
            self.profile_text.remove(item)
            self.updated_at = datetime.now()
            return True
        return False
    
    def update_profile_items(self, items: List[str]) -> None:
        """批量更新画像条目"""
        self.profile_text = items
        self.updated_at = datetime.now()
    
    def get_profile_summary(self) -> str:
        """获取画像摘要（用于提示词）"""
        if not self.profile_text:
            return "无用户画像信息"
        return "\n".join(f"- {item}" for item in self.profile_text)


@dataclass
class User:
    """用户类 - 完整的用户数据模型
    
    包含用户画像、个性化标签模板、学习历史和票据引用。
    实现"越用越懂你"的核心能力。
    """
    
    user_id: str
    profile: UserProfile # 用户画像
    category_template: UserCategoryTemplate # 用户分类模板
    learning_history: LearningHistory
    document_ids: List[str] = field(default_factory=list)  # 票据ID引用列表
    settings: Dict[str, Any] = field(default_factory=dict)  # 用户设置
    created_at: datetime = field(default_factory=datetime.now)
    
    def add_document(self, doc_id: str) -> None:
        """添加票据引用"""
        if doc_id and doc_id not in self.document_ids:
            self.document_ids.append(doc_id)
    
    def remove_document(self, doc_id: str) -> bool:
        """移除票据引用"""
        if doc_id in self.document_ids:
            self.document_ids.remove(doc_id)
            return True
        return False
    
    def update_profile(self, profile_items: List[str]) -> None:
        """更新用户画像"""
        self.profile.update_profile_items(profile_items)
    
    def record_classification_change(
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
        """记录分类修改并返回反馈ID"""
        return self.learning_history.add_feedback(
            document_id=document_id,
            original_category=original_category,
            original_user_category=original_user_category,
            original_tags=original_tags,
            new_category=new_category,
            new_user_category=new_user_category,
            new_tags=new_tags,
            modification_source=modification_source
        )
    
    def get_recommended_tags(self, category: str, top_n: int = 5) -> List[str]:
        """基于历史使用频率推荐标签
        
        Args:
            category: 用户类别
            top_n: 返回前N个推荐标签
            
        Returns:
            推荐的标签列表
        """
        # 获取该类别的标签使用统计
        stats = self.learning_history.get_tag_usage_stats()
        
        # 筛选出该类别的标签
        category_stats = {
            tag: count 
            for tag, count in stats.items() 
            if tag in self.category_template.get_tags(category)
        }
        
        # 按使用次数排序
        sorted_tags = sorted(
            category_stats.items(), 
            key=lambda x: x[1], 
            reverse=True
        )
        
        # 返回前N个
        return [tag for tag, _ in sorted_tags[:top_n]]
    
    def get_document_count(self) -> int:
        """获取票据总数"""
        return len(self.document_ids)
    
    def get_feedback_count(self) -> int:
        """获取反馈总数"""
        return len(self.learning_history.feedbacks)


def create_new_user(user_id: str, profile_items: Optional[List[str]] = None) -> User:
    """创建新用户
    
    Args:
        user_id: 用户ID
        profile_items: 初始画像条目列表
        
    Returns:
        新创建的用户对象
    """
    profile = UserProfile(
        user_id=user_id,
        profile_text=profile_items or []
    )
    
    category_template = create_default_template(user_id)
    learning_history = LearningHistory(user_id=user_id)
    
    return User(
        user_id=user_id,
        profile=profile,
        category_template=category_template,
        learning_history=learning_history
    )


__all__ = [
    "UserProfile",
    "User",
    "create_new_user",
]

