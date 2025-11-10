"""数据模型模块 - 票据管理系统的核心数据结构

目录结构：
- base.py: 基础模型（BaseDocument、枚举类型）
- document/: 票据相关模型（发票、行程单、小票、收据）
- user/: 用户相关模型（用户画像、分类模板、学习历史）
- serialization.py: 序列化工具
"""

# 基础模型
from .base import BaseDocument, DocumentStatus, DocumentType, UserCategory

# 票据模型
from .document import (
    Invoice,
    InvoiceItem,
    Itinerary,
    Receipt,
    ReceiptSlip,
    ReceiptSlipItem,
    TransferInfo,
)

# 用户模型
from .user import (
    ClassificationFeedback,
    LearningHistory,
    User,
    UserCategoryTemplate,
    UserProfile,
    create_default_template,
    create_new_user,
)

__all__ = [
    # 基础模型
    "DocumentType",
    "UserCategory",
    "DocumentStatus",
    "BaseDocument",
    # 票据模型
    "Invoice",
    "InvoiceItem",
    "Itinerary",
    "Receipt",
    "ReceiptSlip",
    "ReceiptSlipItem",
    "TransferInfo",
    # 用户模型
    "User",
    "UserProfile",
    "create_new_user",
    "UserCategoryTemplate",
    "create_default_template",
    "ClassificationFeedback",
    "LearningHistory",
]
