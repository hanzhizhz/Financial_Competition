"""用户模型模块 - 用户画像、分类模板和学习历史"""

from .categories import DEFAULT_CATEGORY_TAGS, UserCategoryTemplate, create_default_template
from .learning import ClassificationFeedback, LearningHistory
from .profile import User, UserProfile, create_new_user

__all__ = [
    # 用户画像和用户类
    "User",
    "UserProfile",
    "create_new_user",
    # 分类模板
    "UserCategoryTemplate",
    "create_default_template",
    "DEFAULT_CATEGORY_TAGS",
    # 学习历史
    "ClassificationFeedback",
    "LearningHistory",
]

