"""小票模型 - 超市/便利店/餐厅等消费小票"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class ReceiptSlipItem:
    """小票明细项"""
    item_name: str = ""  # 商品名称
    quantity: float = 1.0  # 数量
    unit_price: float = 0.0  # 单价
    category_hint: str = ""  # 类别提示（可选）


@dataclass
class ReceiptSlip:
    """小票（超市/便利店/餐厅等消费小票）结构化数据"""
    
    # 商家信息
    merchant_name: str = ""  # 商家名称
    store_location: str = ""  # 门店位置
    terminal_id: str = ""  # POS机编号
    cashier_id: str = ""  # 收银员编号
    
    # 交易信息
    transaction_datetime: Optional[datetime] = None  # 交易时间
    transaction_id: str = ""  # 流水号
    
    # 支付信息
    payment_method: str = ""  # 微信支付|现金|信用卡
    total_amount: float = 0.0  # 总金额
    
    # 明细项
    items: List[ReceiptSlipItem] = field(default_factory=list)


__all__ = ["ReceiptSlip", "ReceiptSlipItem"]

