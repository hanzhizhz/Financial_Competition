"""序列化工具 - JSON编解码和数据验证"""

from __future__ import annotations

import json
from dataclasses import asdict, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Type, TypeVar, Union
import re

from .base import BaseDocument, DocumentStatus, DocumentType, UserCategory
from .document import (
    Invoice,
    InvoiceItem,
    Itinerary,
    Receipt,
    ReceiptSlip,
    ReceiptSlipItem,
    TransferInfo,
)
from .user import (
    ClassificationFeedback,
    LearningHistory,
    User,
    UserCategoryTemplate,
    UserProfile,
)

T = TypeVar("T")


# ==================== JSON编码器 ====================

class DocumentJSONEncoder(json.JSONEncoder):
    """自定义JSON编码器，处理dataclass、datetime、Enum等类型"""
    
    def default(self, obj: Any) -> Any:
        if isinstance(obj, datetime):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif is_dataclass(obj):
            return asdict(obj)
        elif isinstance(obj, set):
            return list(obj)
        return super().default(obj)


# ==================== 序列化函数 ====================

def to_dict(obj: Any) -> Dict[str, Any]:
    """将dataclass对象转换为字典
    
    Args:
        obj: dataclass对象
        
    Returns:
        字典表示
    """
    if not is_dataclass(obj):
        raise TypeError(f"Expected dataclass, got {type(obj)}")
    
    result = {}
    for key, value in asdict(obj).items():
        if isinstance(value, datetime):
            result[key] = value.isoformat()
        elif isinstance(value, Enum):
            result[key] = value.value
        elif isinstance(value, set):
            result[key] = list(value)
        else:
            result[key] = value
    
    # 包含动态属性（如structured_data）
    if hasattr(obj, "structured_data"):
        result["structured_data"] = getattr(obj, "structured_data")
    
    return result
def _normalize_amount_value(value: Any) -> Optional[float]:
    """将金额字符串转换为浮点数"""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.replace("￥", "").replace(",", "").strip()
        if not cleaned:
            return None
        match = re.search(r"[-+]?\d+(?:\.\d+)?", cleaned)
        if match:
            try:
                return float(match.group())
            except ValueError:
                return None
        return None
    return None


def _format_date(value: Any) -> Optional[str]:
    """解析多种日期格式并统一为 YYYY/MM/DD"""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.strftime("%Y/%m/%d")
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        candidates = [
            "%Y-%m-%d",
            "%Y/%m/%d",
            "%Y%m%d",
            "%Y-%m-%d %H:%M:%S",
            "%Y/%m/%d %H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y/%m/%d %H:%M",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y/%m/%dT%H:%M:%S",
            "%Y/%m/%dT%H:%M:%S.%f",
        ]
        for fmt in candidates:
            try:
                parsed = datetime.strptime(cleaned, fmt)
                return parsed.strftime("%Y/%m/%d")
            except ValueError:
                continue
        digits_match = re.search(r"(20\d{2})(?:[-/年]?)(\d{1,2})(?:[-/月]?)(\d{1,2})", cleaned)
        if digits_match:
            year, month, day = digits_match.groups()
            return f"{int(year):04d}/{int(month):02d}/{int(day):02d}"
    return None


def _extract_structured_date(structured: Dict[str, Any], document_type: DocumentType) -> Optional[str]:
    """根据票据类型从结构化数据中提取日期"""
    if not isinstance(structured, dict):
        return None
    keys_by_type = {
        DocumentType.INVOICE: ["issue_date"],
        DocumentType.ITINERARY: ["departure_datetime", "departure_date"],
        DocumentType.RECEIPT_SLIP: ["transaction_datetime", "transaction_date"],
        DocumentType.RECEIPT: ["issue_date"],
    }
    for key in keys_by_type.get(document_type, []):
        value = structured.get(key)
        formatted = _format_date(value)
        if formatted:
            return formatted
    return None



def to_json(obj: Any, indent: int = 2) -> str:
    """将对象序列化为JSON字符串
    
    Args:
        obj: 要序列化的对象
        indent: 缩进空格数
        
    Returns:
        JSON字符串
    """
    return json.dumps(obj, cls=DocumentJSONEncoder, ensure_ascii=False, indent=indent)


def save_to_file(obj: Any, file_path: Union[str, Path]) -> None:
    """将对象保存到JSON文件
    
    Args:
        obj: 要保存的对象
        file_path: 文件路径
    """
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    
    with path.open("w", encoding="utf-8") as f:
        json.dump(obj, f, cls=DocumentJSONEncoder, ensure_ascii=False, indent=2)


# ==================== 反序列化函数 ====================

def _parse_datetime(value: Any) -> datetime:
    """解析datetime对象"""
    if isinstance(value, datetime):
        return value
    elif isinstance(value, str):
        return datetime.fromisoformat(value)
    else:
        raise ValueError(f"Cannot parse datetime from {type(value)}")


def _parse_enum(enum_class: Type[Enum], value: Any) -> Enum:
    """解析枚举值"""
    if isinstance(value, enum_class):
        return value
    elif isinstance(value, str):
        # 尝试按值匹配
        for member in enum_class:
            if member.value == value:
                return member
        # 尝试按名称匹配
        return enum_class[value]
    else:
        raise ValueError(f"Cannot parse {enum_class.__name__} from {value}")


def from_dict_invoice_item(data: Dict[str, Any]) -> InvoiceItem:
    """从字典创建InvoiceItem对象"""
    return InvoiceItem(
        item_name=data.get("item_name", ""),
        specification=data.get("specification", ""),
        unit=data.get("unit", ""),
        quantity=float(data.get("quantity", 0.0)),
        price_per_unit=float(data.get("price_per_unit", 0.0)),
        amount_excluding_tax=float(data.get("amount_excluding_tax", 0.0)),
        tax_rate=float(data.get("tax_rate", 0.0)),
        tax_amount=float(data.get("tax_amount", 0.0)),
    )


def from_dict_invoice(data: Dict[str, Any]) -> Invoice:
    """从字典创建Invoice对象"""
    items = [from_dict_invoice_item(item) for item in data.get("items", [])]
    
    issue_date = None
    if data.get("issue_date"):
        issue_date = _parse_datetime(data["issue_date"])
    
    return Invoice(
        invoice_code=data.get("invoice_code", ""),
        invoice_number=data.get("invoice_number", ""),
        issue_date=issue_date,
        buyer_name=data.get("buyer_name", ""),
        buyer_tax_id=data.get("buyer_tax_id", ""),
        buyer_address_phone=data.get("buyer_address_phone", ""),
        buyer_bank_account=data.get("buyer_bank_account", ""),
        seller_name=data.get("seller_name", ""),
        seller_tax_id=data.get("seller_tax_id", ""),
        seller_address_phone=data.get("seller_address_phone", ""),
        seller_bank_account=data.get("seller_bank_account", ""),
        total_amount_excluding_tax=float(data.get("total_amount_excluding_tax", 0.0)),
        total_tax_amount=float(data.get("total_tax_amount", 0.0)),
        total_amount_including_tax=float(data.get("total_amount_including_tax", 0.0)),
        currency=data.get("currency", "CNY"),
        invoice_type=data.get("invoice_type", ""),
        invoice_status=data.get("invoice_status", "正常"),
        check_code=data.get("check_code", ""),
        items=items,
        payment_method=data.get("payment_method", ""),
        remark=data.get("remark", ""),
    )


def from_dict_itinerary(data: Dict[str, Any]) -> Itinerary:
    """从字典创建Itinerary对象"""
    departure_datetime = None
    if data.get("departure_datetime"):
        departure_datetime = _parse_datetime(data["departure_datetime"])
    
    arrival_datetime = None
    if data.get("arrival_datetime"):
        arrival_datetime = _parse_datetime(data["arrival_datetime"])
    
    return Itinerary(
        transport_type=data.get("transport_type", ""),
        ticket_number=data.get("ticket_number", ""),
        passenger_name=data.get("passenger_name", ""),
        id_card_number=data.get("id_card_number", ""),
        departure_station=data.get("departure_station", ""),
        arrival_station=data.get("arrival_station", ""),
        departure_datetime=departure_datetime,
        arrival_datetime=arrival_datetime,
        flight_train_number=data.get("flight_train_number", ""),
        seat_class=data.get("seat_class", ""),
        seat_number=data.get("seat_number", ""),
        base_fare=float(data.get("base_fare", 0.0)),
        fuel_surcharge=float(data.get("fuel_surcharge", 0.0)),
        airport_railway_fee=float(data.get("airport_railway_fee", 0.0)),
        insurance_fee=float(data.get("insurance_fee", 0.0)),
        total_amount=float(data.get("total_amount", 0.0)),
        payment_method=data.get("payment_method", ""),
    )


def from_dict_receipt_slip_item(data: Dict[str, Any]) -> ReceiptSlipItem:
    """从字典创建ReceiptSlipItem对象"""
    return ReceiptSlipItem(
        item_name=data.get("item_name", ""),
        quantity=float(data.get("quantity", 1.0)),
        unit_price=float(data.get("unit_price", 0.0)),
        category_hint=data.get("category_hint", ""),
    )


def from_dict_receipt_slip(data: Dict[str, Any]) -> ReceiptSlip:
    """从字典创建ReceiptSlip对象"""
    items = [from_dict_receipt_slip_item(item) for item in data.get("items", [])]
    
    transaction_datetime = None
    if data.get("transaction_datetime"):
        transaction_datetime = _parse_datetime(data["transaction_datetime"])
    
    return ReceiptSlip(
        merchant_name=data.get("merchant_name", ""),
        store_location=data.get("store_location", ""),
        terminal_id=data.get("terminal_id", ""),
        cashier_id=data.get("cashier_id", ""),
        transaction_datetime=transaction_datetime,
        transaction_id=data.get("transaction_id", ""),
        payment_method=data.get("payment_method", ""),
        total_amount=float(data.get("total_amount", 0.0)),
        items=items,
    )


def from_dict_transfer_info(data: Dict[str, Any]) -> TransferInfo:
    """从字典创建TransferInfo对象"""
    return TransferInfo(
        bank_name=data.get("bank_name", ""),
        account_from=data.get("account_from", ""),
        account_to=data.get("account_to", ""),
        transaction_id=data.get("transaction_id", ""),
    )


def from_dict_receipt(data: Dict[str, Any]) -> Receipt:
    """从字典创建Receipt对象"""
    issue_date = None
    if data.get("issue_date"):
        issue_date = _parse_datetime(data["issue_date"])
    
    transfer_info = None
    if data.get("transfer_info"):
        transfer_info = from_dict_transfer_info(data["transfer_info"])
    
    return Receipt(
        title=data.get("title", "收据"),
        receipt_number=data.get("receipt_number", ""),
        issue_date=issue_date,
        payer_name=data.get("payer_name", ""),
        payee_name=data.get("payee_name", ""),
        amount_in_words=data.get("amount_in_words", ""),
        amount_in_digits=float(data.get("amount_in_digits", 0.0)),
        currency=data.get("currency", "CNY"),
        reason=data.get("reason", ""),
        payment_method=data.get("payment_method", ""),
        transfer_info=transfer_info,
        witness_name=data.get("witness_name", ""),
        is_official=bool(data.get("is_official", False)),
        notes=data.get("notes", ""),
    )


def from_dict_base_document(data: Dict[str, Any]) -> BaseDocument:
    """从字典创建BaseDocument对象"""
    upload_time = datetime.now()
    if data.get("upload_time"):
        upload_time = _parse_datetime(data["upload_time"])
    
    document_type = DocumentType.RECEIPT_SLIP
    if data.get("document_type"):
        document_type = _parse_enum(DocumentType, data["document_type"])
    
    status = None
    if data.get("status"):
        status = _parse_enum(DocumentStatus, data["status"])
    
    user_category = None
    if data.get("user_category"):
        user_category = _parse_enum(UserCategory, data["user_category"])
    
    amount = None
    if "amount" in data and data["amount"] not in (None, ""):
        amount = _normalize_amount_value(data["amount"])
    if amount is None and "structured_data" in data and isinstance(data["structured_data"], dict):
        for key in (
            "total_amount",
            "total_amount_including_tax",
            "total_amount_excluding_tax",
            "amount_in_digits",
        ):
            amount = _normalize_amount_value(data["structured_data"].get(key))
            if amount is not None:
                break
    
    issued_date = None
    if data.get("issued_date"):
        issued_date = _format_date(data["issued_date"])

    doc = BaseDocument(
        document_id=data.get("document_id", ""),
        user_id=data.get("user_id", ""),
        upload_time=upload_time,
        document_type=document_type,
        source_image=data.get("source_image", ""),
        ocr_text=data.get("ocr_text"),
        status=status,
        user_category=user_category,
        tags=data.get("tags", []),
        amount=amount,
        issued_date=issued_date,
        document_type_reasoning=data.get("document_type_reasoning"),
        tag_classification_reasoning=data.get("tag_classification_reasoning"),
    )
    
    # 恢复结构化数据（动态属性）
    if "structured_data" in data:
        doc.structured_data = data["structured_data"]  # type: ignore[attr-defined]
        if doc.issued_date is None and isinstance(doc.structured_data, dict):
            doc.issued_date = _extract_structured_date(doc.structured_data, document_type)

    return doc


def from_dict_category_template(data: Dict[str, Any]) -> UserCategoryTemplate:
    """从字典创建UserCategoryTemplate对象"""
    user_id = data.get("user_id", "")
    category_tags = {}
    
    if data.get("category_tags"):
        for cat_name, tags in data["category_tags"].items():
            try:
                category = _parse_enum(UserCategory, cat_name)
                category_tags[category] = set(tags) if isinstance(tags, list) else tags
            except (KeyError, ValueError):
                continue
    
    return UserCategoryTemplate(
        user_id=user_id,
        category_tags=category_tags,
    )


def from_json(json_str: str, target_type: Type[T]) -> T:
    """从JSON字符串反序列化对象
    
    Args:
        json_str: JSON字符串
        target_type: 目标类型
        
    Returns:
        反序列化后的对象
    """
    data = json.loads(json_str)
    return from_dict(data, target_type)


def from_dict_classification_feedback(data: Dict[str, Any]) -> ClassificationFeedback:
    """从字典创建ClassificationFeedback对象"""
    timestamp = datetime.now()
    if data.get("timestamp"):
        timestamp = _parse_datetime(data["timestamp"])
    
    return ClassificationFeedback(
        feedback_id=data.get("feedback_id", ""),
        document_id=data.get("document_id", ""),
        timestamp=timestamp,
        original_category=data.get("original_category", ""),
        original_user_category=data.get("original_user_category"),
        original_tags=data.get("original_tags", []),
        new_category=data.get("new_category", ""),
        new_user_category=data.get("new_user_category"),
        new_tags=data.get("new_tags", []),
        modification_source=data.get("modification_source", "用户手动"),
    )


def from_dict_learning_history(data: Dict[str, Any]) -> LearningHistory:
    """从字典创建LearningHistory对象"""
    feedbacks = []
    if data.get("feedbacks"):
        feedbacks = [
            from_dict_classification_feedback(fb_data) 
            for fb_data in data["feedbacks"]
        ]
    
    return LearningHistory(
        user_id=data.get("user_id", ""),
        feedbacks=feedbacks,
    )


def from_dict_user_profile(data: Dict[str, Any]) -> UserProfile:
    """从字典创建UserProfile对象"""
    created_at = datetime.now()
    if data.get("created_at"):
        created_at = _parse_datetime(data["created_at"])
    
    updated_at = datetime.now()
    if data.get("updated_at"):
        updated_at = _parse_datetime(data["updated_at"])
    
    return UserProfile(
        user_id=data.get("user_id", ""),
        profile_text=data.get("profile_text", []),
        created_at=created_at,
        updated_at=updated_at,
    )


def from_dict_user(data: Dict[str, Any]) -> User:
    """从字典创建User对象"""
    profile = from_dict_user_profile(data.get("profile", {}))
    category_template = from_dict_category_template(data.get("category_template", {}))
    learning_history = from_dict_learning_history(data.get("learning_history", {}))
    
    created_at = datetime.now()
    if data.get("created_at"):
        created_at = _parse_datetime(data["created_at"])
    
    return User(
        user_id=data.get("user_id", ""),
        profile=profile,
        category_template=category_template,
        learning_history=learning_history,
        document_ids=data.get("document_ids", []),
        settings=data.get("settings", {}),
        created_at=created_at,
    )


def from_dict(data: Dict[str, Any], target_type: Type[T]) -> T:
    """从字典创建指定类型的对象
    
    Args:
        data: 字典数据
        target_type: 目标类型
        
    Returns:
        创建的对象
    """
    if target_type == Invoice:
        return from_dict_invoice(data)  # type: ignore
    elif target_type == Itinerary:
        return from_dict_itinerary(data)  # type: ignore
    elif target_type == ReceiptSlip:
        return from_dict_receipt_slip(data)  # type: ignore
    elif target_type == Receipt:
        return from_dict_receipt(data)  # type: ignore
    elif target_type == BaseDocument:
        return from_dict_base_document(data)  # type: ignore
    elif target_type == UserCategoryTemplate:
        return from_dict_category_template(data)  # type: ignore
    elif target_type == ClassificationFeedback:
        return from_dict_classification_feedback(data)  # type: ignore
    elif target_type == LearningHistory:
        return from_dict_learning_history(data)  # type: ignore
    elif target_type == UserProfile:
        return from_dict_user_profile(data)  # type: ignore
    elif target_type == User:
        return from_dict_user(data)  # type: ignore
    else:
        raise ValueError(f"Unsupported target type: {target_type}")


def load_from_file(file_path: Union[str, Path], target_type: Type[T]) -> T:
    """从JSON文件加载对象
    
    Args:
        file_path: 文件路径
        target_type: 目标类型
        
    Returns:
        加载的对象
    """
    path = Path(file_path)
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return from_dict(data, target_type)


# ==================== 验证函数 ====================

def validate_amount(amount: float, field_name: str = "amount") -> None:
    """验证金额字段
    
    Args:
        amount: 金额值
        field_name: 字段名称（用于错误消息）
        
    Raises:
        ValueError: 如果金额为负数
    """
    if amount < 0:
        raise ValueError(f"{field_name} cannot be negative: {amount}")


def validate_required_string(value: str, field_name: str) -> None:
    """验证必填字符串字段
    
    Args:
        value: 字符串值
        field_name: 字段名称
        
    Raises:
        ValueError: 如果字符串为空
    """
    if not value or not value.strip():
        raise ValueError(f"{field_name} is required and cannot be empty")


def validate_invoice(invoice: Invoice) -> List[str]:
    """验证发票数据的基本完整性
    
    Args:
        invoice: 发票对象
        
    Returns:
        验证错误消息列表（空列表表示验证通过）
    """
    errors = []
    
    try:
        validate_required_string(invoice.invoice_number, "invoice_number")
    except ValueError as e:
        errors.append(str(e))
    
    try:
        validate_amount(invoice.total_amount_including_tax, "total_amount_including_tax")
    except ValueError as e:
        errors.append(str(e))
    
    try:
        validate_amount(invoice.total_tax_amount, "total_tax_amount")
    except ValueError as e:
        errors.append(str(e))
    
    return errors


def validate_base_document(doc: BaseDocument) -> List[str]:
    """验证基础票据数据
    
    Args:
        doc: 基础票据对象
        
    Returns:
        验证错误消息列表
    """
    errors = []
    
    try:
        validate_required_string(doc.document_id, "document_id")
    except ValueError as e:
        errors.append(str(e))
    
    try:
        validate_required_string(doc.user_id, "user_id")
    except ValueError as e:
        errors.append(str(e))
    
    return errors


__all__ = [
    "DocumentJSONEncoder",
    "to_dict",
    "to_json",
    "save_to_file",
    "from_dict",
    "from_json",
    "load_from_file",
    "validate_amount",
    "validate_required_string",
    "validate_invoice",
    "validate_base_document",
]

