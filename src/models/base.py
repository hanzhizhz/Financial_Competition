"""基础模型 - 票据系统的基础数据结构和枚举类型"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import uuid4


class DocumentType(str, Enum):
    """专业视角的票据类型分类"""
    INVOICE = "发票"
    ITINERARY = "行程单"
    RECEIPT_SLIP = "小票"
    RECEIPT = "收据"


class UserCategory(str, Enum):
    """用户视角的固定9大类"""
    DINING = "餐饮消费"
    SHOPPING = "购物消费"
    TRANSPORTATION = "交通出行"
    HOUSING = "居住相关"
    MEDICAL = "医疗健康"
    EDUCATION_ENTERTAINMENT = "教育文娱"
    SOCIAL = "人情往来"
    INCOME = "收入类"
    OTHER_EXPENSE = "其他支出"


class DocumentStatus(str, Enum):
    """票据状态"""
    VERIFIED = "已验证"
    PENDING = "待确认"
    VOIDED = "已作废"


@dataclass
class BaseDocument:
    """所有票据的基础数据结构（通用字段）"""
    
    # 基础标识信息
    document_id: str = field(default_factory=lambda: str(uuid4()))
    user_id: str = ""
    upload_time: datetime = field(default_factory=datetime.now)
    
    # 专业视角分类
    document_type: DocumentType = DocumentType.RECEIPT_SLIP
    
    # 文件和内容
    source_image: str = ""  # 原始图片URL或路径
    ocr_text: Optional[str] = None  # 完整OCR文本（可选）
    issued_date: Optional[str] = None  # 统一票据日期，格式：YYYY/MM/DD
    
    # 状态
    status: Optional[DocumentStatus] = None
    amount: Optional[float] = None  # 统一金额字段，去除货币符号后的数值（单位：元）
    
    # 用户视角分类
    user_category: Optional[UserCategory] = None
    tags: List[str] = field(default_factory=list)  # 子标签列表
    document_type_reasoning: Optional[str] = None  # 票据类型分类理由
    tag_classification_reasoning: Optional[str] = None  # 标签分类理由
    
    def add_tag(self, tag: str) -> None:
        """添加标签"""
        if tag and tag not in self.tags:
            self.tags.append(tag)
    
    def remove_tag(self, tag: str) -> None:
        """移除标签"""
        if tag in self.tags:
            self.tags.remove(tag)
    
    def has_tag(self, tag: str) -> bool:
        """检查是否有指定标签"""
        return tag in self.tags


__all__ = [
    "DocumentType",
    "UserCategory",
    "DocumentStatus",
    "BaseDocument",
]

