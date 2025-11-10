"""收据模型 - 非税收入、押金、私人交易等"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class TransferInfo:
    """转账信息"""
    bank_name: str = ""  # 银行名称
    account_from: str = ""  # 付款账户
    account_to: str = ""  # 收款账户
    transaction_id: str = ""  # 交易流水号


@dataclass
class Receipt:
    """收据（非税收入、押金、私人交易等）结构化数据"""
    
    # 收据基本信息
    title: str = "收据"  # 收据|收款证明|押金条
    receipt_number: str = ""  # 收据编号
    issue_date: Optional[datetime] = None  # 开具日期
    
    # 收付款方信息
    payer_name: str = ""  # 付款人姓名
    payee_name: str = ""  # 收款人姓名
    
    # 金额信息
    amount_in_words: str = ""  # 大写金额（如：人民币捌佰元整）
    amount_in_digits: float = 0.0  # 数字金额
    currency: str = "CNY"  # 币种
    
    # 事由和支付方式
    reason: str = ""  # 事由（如：房租押金|水电预缴|借款归还）
    payment_method: str = ""  # 现金|银行转账
    
    # 转账信息（如果是银行转账）
    transfer_info: Optional[TransferInfo] = None
    
    # 其他信息
    witness_name: str = ""  # 见证人（可选）
    is_official: bool = False  # 是否为正式收据
    notes: str = ""  # 备注


__all__ = ["Receipt", "TransferInfo"]

