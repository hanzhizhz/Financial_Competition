"""发票模型 - 增值税普通发票/电子发票"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional


@dataclass
class InvoiceItem:
    """发票明细项"""
    item_name: str = ""  # 项目名称
    specification: str = ""  # 规格型号
    unit: str = ""  # 单位
    quantity: float = 0.0  # 数量
    price_per_unit: float = 0.0  # 单价
    amount_excluding_tax: float = 0.0  # 不含税金额
    tax_rate: float = 0.0  # 税率
    tax_amount: float = 0.0  # 税额


@dataclass
class Invoice:
    """发票（增值税普通发票/电子发票）结构化数据"""
    
    # 发票基本信息
    invoice_code: str = ""  # 发票代码
    invoice_number: str = ""  # 发票号码
    issue_date: Optional[datetime] = None  # 开票日期
    
    # 购买方信息
    buyer_name: str = ""  # 购买方名称
    buyer_tax_id: str = ""  # 购买方纳税人识别号
    buyer_address_phone: str = ""  # 地址电话
    buyer_bank_account: str = ""  # 开户行及账号
    
    # 销售方信息
    seller_name: str = ""  # 销售方名称
    seller_tax_id: str = ""  # 销售方税号
    seller_address_phone: str = ""  # 销售方地址电话
    seller_bank_account: str = ""  # 销售方银行账户
    
    # 金额信息
    total_amount_excluding_tax: float = 0.0  # 不含税总额
    total_tax_amount: float = 0.0  # 税额合计
    total_amount_including_tax: float = 0.0  # 价税合计
    currency: str = "CNY"  # 币种
    
    # 发票类型和状态
    invoice_type: str = ""  # 增值税普通发票|专用发票|电子发票
    invoice_status: str = "正常"  # 正常|红冲|作废
    check_code: str = ""  # 校验码（最后几位数字）
    
    # 明细项
    items: List[InvoiceItem] = field(default_factory=list)
    
    # 支付和备注
    payment_method: str = ""  # 支付宝|微信|银联
    remark: str = ""  # 备注


__all__ = ["Invoice", "InvoiceItem"]

