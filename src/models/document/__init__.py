"""票据模型模块 - 各类票据的结构化数据定义"""

from .invoice import Invoice, InvoiceItem
from .itinerary import Itinerary
from .receipt import Receipt, TransferInfo
from .receipt_slip import ReceiptSlip, ReceiptSlipItem

__all__ = [
    # 发票相关
    "Invoice",
    "InvoiceItem",
    # 行程单
    "Itinerary",
    # 收据相关
    "Receipt",
    "TransferInfo",
    # 小票相关
    "ReceiptSlip",
    "ReceiptSlipItem",
]

