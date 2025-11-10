"""Agent核心 - 文档处理Agent的主要逻辑"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import logging
from dataclasses import MISSING, asdict, dataclass, field, fields, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Union, get_args, get_origin

import json5

from ..models import (
    BaseDocument,
    DocumentStatus,
    DocumentType,
    Invoice,
    Itinerary,
    Receipt,
    ReceiptSlip,
    UserCategory,
)
from ..models.user import User, create_new_user
from ..multimodal.audio import transcribe_audio
from ..multimodal.text import chat_completion
from ..multimodal.vision import analyze_image
from .prompts import (
    build_classification_prompt,
    build_document_check_prompt,
    build_document_classification_prompt,
    build_document_recognition_prompt,
    build_document_structure_prompt,
    build_intent_recognition_prompt,
)

logger = logging.getLogger(__name__)


def _normalize_amount(value: Any) -> Optional[float]:
    """将金额字段标准化为浮点数（单位：元）"""
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


@dataclass
class RecognitionResult:
    """票据识别结果"""
    is_valid_document: bool
    document_type: Optional[str] = None
    user_category: Optional[str] = None
    markdown_content: str = ""
    reason: str = ""
    structured_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StructuredData:
    """结构化数据结果"""
    structured_data: Dict[str, Any] = field(default_factory=dict)


@dataclass
class IntentResult:
    """用户意图解析结果"""
    analysis: str = ""
    key_information: str = ""
    has_explicit_classification: bool = False


@dataclass
class ProcessResult:
    """上传处理流程结果"""
    success: bool
    error: Optional[str] = None
    document: Optional[BaseDocument] = None
    document_id: Optional[str] = None
    recognition: Optional[RecognitionResult] = None
    classification: Optional[ClassificationResult] = None
    intent: Optional[IntentResult] = None
    is_invalid_image: bool = False  # 是否为无效图片（非票据图片）


DOCUMENT_SCHEMA_MAP = {
    DocumentType.INVOICE.value: Invoice,
    DocumentType.ITINERARY.value: Itinerary,
    DocumentType.RECEIPT_SLIP.value: ReceiptSlip,
    DocumentType.RECEIPT.value: Receipt,
}


def _dataclass_to_json_schema(cls: type) -> Dict[str, Any]:
    """将数据类转换为JSON Schema"""
    definitions: Dict[str, Any] = {}

    def _build_schema(dataclass_type: type) -> Dict[str, Any]:
        if dataclass_type.__name__ in definitions:
            return {"$ref": f"#/$defs/{dataclass_type.__name__}"}

        schema: Dict[str, Any] = {
            "type": "object",
            "title": dataclass_type.__name__,
            "properties": {},
            "additionalProperties": False,
        }
        definitions[dataclass_type.__name__] = schema

        required_fields: List[str] = []
        for field_info in fields(dataclass_type):
            field_schema, is_optional = _annotation_to_schema(field_info.type)
            schema["properties"][field_info.name] = field_schema

            has_default = field_info.default is not MISSING or field_info.default_factory is not MISSING  # type: ignore[arg-type]
            if not is_optional and not has_default:
                required_fields.append(field_info.name)

        if required_fields:
            schema["required"] = required_fields

        return {"$ref": f"#/$defs/{dataclass_type.__name__}"}

    def _annotation_to_schema(annotation: Any) -> tuple[Dict[str, Any], bool]:
        origin = get_origin(annotation)
        args = get_args(annotation)

        if origin is Union:
            nullable = any(arg is type(None) for arg in args)
            non_none_args = [arg for arg in args if arg is not type(None)]
            if len(non_none_args) == 1:
                schema, _ = _annotation_to_schema(non_none_args[0])
                if nullable:
                    schema = {"anyOf": [schema, {"type": "null"}]}
                return schema, True
            schemas = []
            for arg in non_none_args:
                sub_schema, _ = _annotation_to_schema(arg)
                schemas.append(sub_schema)
            if nullable:
                schemas.append({"type": "null"})
            return {"anyOf": schemas}, True

        if origin in {list, List}:
            item_type = args[0] if args else Any
            item_schema, _ = _annotation_to_schema(item_type)
            return {"type": "array", "items": item_schema}, False

        if origin in {dict, Dict}:
            key_schema, _ = _annotation_to_schema(args[0] if args else Any)
            value_schema, _ = _annotation_to_schema(args[1] if len(args) > 1 else Any)
            return {
                "type": "object",
                "additionalProperties": value_schema,
                "propertyNames": key_schema,
            }, False

        if annotation in {str, Any}:
            return {"type": "string"}, False
        if annotation is int:
            return {"type": "integer"}, False
        if annotation is float:
            return {"type": "number"}, False
        if annotation is bool:
            return {"type": "boolean"}, False
        if annotation is datetime:
            return {"type": "string", "format": "date-time"}, False

        if is_dataclass(annotation):
            ref = _build_schema(annotation)  # type: ignore[arg-type]
            return ref, False

        # 默认退化为字符串
        return {"type": "string"}, False

    _build_schema(cls)
    root_schema = definitions[cls.__name__].copy()
    root_schema["$schema"] = "https://json-schema.org/draft/2020-12/schema"
    other_defs = {k: v for k, v in definitions.items() if k != cls.__name__}
    if other_defs:
        root_schema["$defs"] = other_defs
    return root_schema

@dataclass
class ClassificationResult:
    """分类结果"""
    status: bool
    user_category: str = ""
    professional_category: str = ""
    tags: List[str] = field(default_factory=list)
    reasoning: str = ""


class DocumentAgent:
    """文档处理Agent
    
    负责处理票据上传、识别、分类和入账的完整流程。
    """
    
    def __init__(self, user: User):
        """初始化Agent
        
        Args:
            user: 用户对象
        """
        self.user = user
        self.logger = logging.getLogger(f"{__name__}.{user.user_id}")
    
    def _format_classification_rules(self, rules_raw: Any) -> str:
        """格式化分类规则为字符串（兼容旧格式）
        
        Args:
            rules_raw: 规则数据（可能是字符串或列表）
            
        Returns:
            格式化后的规则文本
        """
        if not rules_raw:
            return "暂无历史规则"
        
        # 如果是字符串，尝试解析JSON（兼容旧格式）
        if isinstance(rules_raw, str):
            try:
                parsed = json.loads(rules_raw)
                rules_raw = parsed
            except json.JSONDecodeError:
                # 解析失败，可能是旧格式的纯文本
                return rules_raw
        
        # 现在 rules_raw 应该是列表
        if isinstance(rules_raw, list):
            if not rules_raw:
                return "暂无历史规则"
            
            # 检查是旧格式（Dict列表）还是新格式（字符串列表）
            if isinstance(rules_raw[0], dict):
                # 旧格式：从字典中提取 rule_text
                rules_text = [rule.get('rule_text', '') for rule in rules_raw if rule.get('rule_text')]
            elif isinstance(rules_raw[0], str):
                # 新格式：直接使用字符串列表
                rules_text = [r for r in rules_raw if r]
            else:
                return "暂无历史规则"
            
            if not rules_text:
                return "暂无历史规则"
            
            # 格式化为字符串
            formatted = "历史分类规则：\n"
            for i, rule in enumerate(rules_text, 1):
                formatted += f"{i}. {rule}\n"
            return formatted
        else:
            return "暂无历史规则"
    
    async def process_upload(
        self,
        image_path: Union[str, Path],
        text: Optional[str] = None,
        audio_path: Optional[Union[str, Path]] = None
    ) -> ProcessResult:
        """处理上传流程
        
        Args:
            image_path: 图片路径
            text: 用户文本（可选）
            audio_path: 音频路径（可选）
            
        Returns:
            处理结果
        """
        try:
            self.logger.info(f"开始处理上传: image={image_path}, text={text}, audio={audio_path}")
            
            # 步骤1: 如果有音频，先转文本
            if audio_path and not text:
                self.logger.info("转换音频到文本...")
                text = await self._transcribe_audio(audio_path)
            
            # 步骤2: 判断图片是否为票据
            self.logger.info("判断图片是否为票据...")
            is_document, check_reason = await self._check_if_document(image_path)
            
            if not is_document:
                return ProcessResult(
                    success=False,
                    error=f"上传的图片不是票据: {check_reason}",
                    is_invalid_image=True
                )
            
            # 步骤3: 识别票据文本
            self.logger.info("识别票据文本...")
            recognition = await self._recognize_document(image_path)
            
            # 步骤4: 并行执行分类判断和意图识别
            self.logger.info("并行执行分类判断和意图识别...")
            if text:
                # 如果有文本，并行执行分类和意图识别
                text_classification_task = self._classify_document_with_text(recognition.markdown_content)
                intent_task = self._parse_user_intent(text)
                results = await asyncio.gather(text_classification_task, intent_task, return_exceptions=True)
                
                # 解析并行结果
                text_classification_result = results[0]
                intent_result = results[1]
                
                if isinstance(text_classification_result, Exception):
                    self.logger.error(f"分类判断失败: {text_classification_result}")
                    raise text_classification_result
                
                text_classification: ClassificationResult = text_classification_result  # type: ignore[assignment]
                
                if isinstance(intent_result, Exception):
                    self.logger.warning(f"意图识别失败: {intent_result}")
                    intent = None
                else:
                    intent: Optional[IntentResult] = intent_result  # type: ignore[assignment]
            else:
                # 如果没有文本，只执行分类判断
                text_classification = await self._classify_document_with_text(recognition.markdown_content)
                intent = None
            
            # 更新 recognition 的分类信息
            recognition.document_type = text_classification.professional_category
            recognition.user_category = text_classification.user_category
            
            # 步骤5: 子标签添加和结构化（需要等待分类完成）
            self.logger.info("添加子标签...")
            classification = await self._classify_document(
                recognition=recognition,
                intent=intent
            )

            document_type_reasoning = text_classification.reasoning
            tag_classification_reasoning = classification.reasoning

            # 合并分类的推理说明（专业分类和用户视角分类的推理）
            if text_classification.reasoning:
                if classification.reasoning:
                    # 如果子标签也有推理，合并两者
                    classification.reasoning = f"{text_classification.reasoning}\n\n子标签推理：{classification.reasoning}"
                else:
                    # 如果子标签没有推理，直接使用分类的推理
                    classification.reasoning = text_classification.reasoning

            # 步骤6: 票据信息结构化
            self.logger.info("票据信息结构化...")
            structured_data = await self._structure_document(
                recognition=recognition,
            )
            
            # 步骤7: 创建票据对象并保存为待确认状态
            self.logger.info("创建票据对象...")
            document = await self._create_document(
                recognition=recognition,
                classification=classification,
                intent=intent,
                structured_data=structured_data,
                image_path=str(image_path),
                document_type_reasoning=document_type_reasoning,
                tag_classification_reasoning=tag_classification_reasoning,
            )
            
            return ProcessResult(
                success=True,
                document=document,
                document_id=document.document_id,
                recognition=recognition,
                classification=classification,
                intent=intent
            )
            
        except Exception as e:
            self.logger.error(f"处理上传失败: {e}", exc_info=True)
            return ProcessResult(
                success=False,
                error=str(e)
            )
    
    async def _structure_document(self, recognition: RecognitionResult) -> StructuredData:
        """票据信息结构化
        
        Args:
            recognition: 识别结果
            
        Returns:
            StructuredData: 结构化数据
        """
        try:
            # 构建提示词

            professional_category = recognition.document_type
            schema_cls = DOCUMENT_SCHEMA_MAP.get(professional_category or "")
            if schema_cls:
                schema_definition = _dataclass_to_json_schema(schema_cls)
                structure_rules = (
                    "请严格按照以下 JSON Schema 解析票据内容，并在 structured_data 字段中返回匹配的键值：\n"
                    f"{json.dumps(schema_definition, ensure_ascii=False, indent=2)}"
                )
            else:
                structure_rules = (
                    "未识别到具体票据类型，请尽可能提取票据中的关键信息，"
                    "并以键值对形式填充 structured_data。"
                )
            
            prompt = build_document_structure_prompt(recognition.markdown_content, structure_rules)
            
            # 调用文本API
            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json_object",
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            structured_data = StructuredData(
                structured_data=result_data.get('structured_data', {})
            )
            recognition.structured_data = structured_data.structured_data
            return structured_data
            
        except Exception as e:
            self.logger.error(f"票据信息结构化失败: {e}")
            raise
    
    async def _transcribe_audio(self, audio_path: Union[str, Path]) -> str:
        """转换音频到文本
        
        Args:
            audio_path: 音频文件路径
            
        Returns:
            转录的文本
        """
        try:
            result = await transcribe_audio(audio=audio_path)
            
            # 提取转录文本
            if isinstance(result, dict):
                # 根据实际API返回格式调整
                text = result.get('text', '') or result.get('transcription', '')
            else:
                text = str(result)
            
            self.logger.info(f"音频转录成功: {text[:50]}...")
            return text
            
        except Exception as e:
            self.logger.error(f"音频转录失败: {e}")
            raise
    
    async def _check_if_document(self, image_path: Union[str, Path]) -> tuple[bool, str]:
        """判断图片是否为票据
        
        Args:
            image_path: 图片路径
            
        Returns:
            (是否为票据, 原因说明)
        """
        try:
            # 构建提示词
            prompt = build_document_check_prompt()
            
            # 调用视觉API
            response = await analyze_image(
                image_path=str(image_path),
                prompt=prompt,
                response_format = "json_object",
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            
            is_document = result_data.get('is_document', False)
            reason = result_data.get('reason', '')
            
            return is_document, reason
            
        except Exception as e:
            self.logger.error(f"票据相关性判断失败: {e}")
            return False, f"判断异常: {str(e)}"
    
    async def _recognize_document(self, image_path: Union[str, Path]) -> RecognitionResult:
        """识别票据文本内容
        
        Args:
            image_path: 图片路径
            
        Returns:
            识别结果（包含文本内容）
        """
        try:
            # 构建提示词
            prompt = build_document_recognition_prompt()
            
            # 调用视觉API，使用文本格式输出
            response = await analyze_image(
                image_path=str(image_path),
                prompt=prompt,
                response_format="text"  # 使用文本格式，而不是 JSON
            )
            
            # 提取文本内容
            text_content = self._extract_text_content(response)
            
            # 从 markdown 代码块中提取内容
            markdown_content = self._extract_markdown_content(text_content)
            
            return RecognitionResult(
                is_valid_document=True,  # 已经通过 _check_if_document 检查，这里总是有效的
                document_type=None,  # 分类信息由 _classify_document_with_text 提供
                user_category=None,  # 分类信息由 _classify_document_with_text 提供
                markdown_content=markdown_content,
                reason="",
                structured_data={},
            )
            
        except Exception as e:
            self.logger.error(f"票据文本识别失败: {e}")
            return RecognitionResult(
                is_valid_document=False,
                reason=f"识别异常: {str(e)}",
                structured_data={},
            )
    
    async def _classify_document_with_text(self, document_content: str) -> ClassificationResult:
        """使用文本模块判断票据的专业分类和用户视角分类
        
        Args:
            document_content: 票据文本内容
            
        Returns:
            分类结果（包含专业分类和用户视角分类）
        """
        try:
            # 构建提示词
            prompt = build_document_classification_prompt(document_content)
            
            # 调用文本API
            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json_object",
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            
            return ClassificationResult(
                status=True,
                professional_category=result_data.get('professional_category', DocumentType.RECEIPT_SLIP.value),
                user_category=result_data.get('user_category', UserCategory.OTHER_EXPENSE.value),
                tags=[],  # 子标签由 _classify_document 添加
                reasoning=result_data.get('reasoning', '')
            )
            
        except Exception as e:
            self.logger.error(f"文本分类失败: {e}")
            # 返回默认分类
            return ClassificationResult(
                status=False,
                professional_category=DocumentType.RECEIPT_SLIP.value,
                user_category=UserCategory.OTHER_EXPENSE.value,
                tags=[],
                reasoning=f"分类失败，使用默认值: {str(e)}"
            )
    
    async def _parse_user_intent(self, text: str) -> IntentResult:
        """解析用户意图
        
        Args:
            text: 用户文本
            
        Returns:
            意图结果
        """
        try:
            # 构建提示词
            prompt = build_intent_recognition_prompt(text)
            
            # 调用文本API
            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json_object",
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            
            return IntentResult(
                analysis=result_data.get('analysis', ''),
                has_explicit_classification=result_data.get('has_explicit_classification', False),
                key_information=result_data.get('information_extraction', '')
                
            )
            
        except Exception as e:
            self.logger.error(f"意图识别失败: {e}")
            return IntentResult(
                analysis="",
                key_information="",
                has_explicit_classification=False
            )
    
    async def _classify_document(
        self,
        recognition: RecognitionResult,
        intent: Optional[IntentResult] = None
    ) -> ClassificationResult:
        """为票据添加子标签（专业分类和用户视角分类已由 _classify_document_with_text 确定）
        
        Args:
            recognition: 识别结果（已包含专业分类和用户视角分类）
            intent: 意图结果
            
        Returns:
            分类结果（包含子标签）
        """
        try:
            # 如果用户明确指定了分类，直接使用
            user_intent = ""
            if intent and intent.has_explicit_classification:
                user_intent = intent.key_information
            
            # 准备用户画像
            user_profile = self.user.profile.get_profile_summary()
            
            # 准备历史规则（格式化为字符串）
            classification_rules_raw = self.user.settings.get('classification_rules', [])
            classification_rules = self._format_classification_rules(classification_rules_raw)

            # 用户视角类型（已由 _classify_document_with_text 确定）
            user_category = recognition.user_category or UserCategory.OTHER_EXPENSE.value
            # 准备用户视角标签
            try:
                user_category_enum = UserCategory(user_category)
            except ValueError:
                user_category_enum = UserCategory.OTHER_EXPENSE
                user_category = user_category_enum.value
            user_tags = self.user.category_template.get_tags(user_category_enum)

            # 准备票据内容
            document_content = recognition.markdown_content
            
            # 构建提示词（只用于子标签添加）
            prompt = build_classification_prompt(
                user_profile=user_profile,
                document_content=document_content,
                user_category=user_category,
                user_tags={user_category: user_tags},
                classification_rules=classification_rules,
                user_intent=user_intent,
            )
            
            # 调用文本API
            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                response_format="json_object",
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            
            return ClassificationResult(
                status=True,
                user_category=user_category,
                professional_category=recognition.document_type or DocumentType.RECEIPT_SLIP.value,
                tags=result_data.get('tags', []),
                reasoning=result_data.get('reasoning', '')
            )
            
        except Exception as e:
            self.logger.error(f"子标签添加失败: {e}")
            # 返回默认分类（保留已有的专业分类和用户视角分类）
            return ClassificationResult(
                status=False,
                user_category=recognition.user_category or UserCategory.OTHER_EXPENSE.value,
                professional_category=recognition.document_type or DocumentType.RECEIPT_SLIP.value,
                tags=[],
                reasoning=f"子标签添加失败，使用默认值: {str(e)}"
            )
    
    async def _create_document(
        self,
        recognition: RecognitionResult,
        classification: ClassificationResult,
        intent: Optional[IntentResult],
        structured_data: StructuredData,
        image_path: str,
        document_type_reasoning: Optional[str] = None,
        tag_classification_reasoning: Optional[str] = None,
    ) -> BaseDocument:
        """创建票据对象
        
        Args:
            recognition: 识别结果
            classification: 分类结果
            intent: 意图结果
            structured_data: 结构化数据
            image_path: 图片路径
            
        Returns:
            票据对象
        """
        # 映射专业分类
        doc_type_map = {
            "发票": DocumentType.INVOICE,
            "行程单": DocumentType.ITINERARY,
            "小票": DocumentType.RECEIPT_SLIP,
            "收据": DocumentType.RECEIPT
        }
        document_type = doc_type_map.get(classification.professional_category, DocumentType.RECEIPT_SLIP)
        
        # 映射用户分类
        user_category = None
        for cat in UserCategory:
            if cat.value == classification.user_category:
                user_category = cat
                break
        
        # 创建票据
        structured_values = structured_data.structured_data if structured_data else recognition.structured_data
        amount = None
        if isinstance(structured_values, dict):
            for key in (
                "total_amount",
                "total_amount_including_tax",
                "total_amount_excluding_tax",
                "amount_in_digits",
            ):
                amount = _normalize_amount(structured_values.get(key))
                if amount is not None:
                    break
        issued_date = None
        if isinstance(structured_values, dict):
            keys_by_type = {
                DocumentType.INVOICE: ["issue_date"],
                DocumentType.ITINERARY: ["departure_datetime", "departure_date"],
                DocumentType.RECEIPT_SLIP: ["transaction_datetime", "transaction_date"],
                DocumentType.RECEIPT: ["issue_date"],
            }
            for key in keys_by_type.get(document_type, []):
                issued_date = _format_date(structured_values.get(key))
                if issued_date:
                    break
        document = BaseDocument(  # type: ignore[call-arg]
            user_id=self.user.user_id,
            upload_time=datetime.now(),
            document_type=document_type,
            source_image=image_path,
            ocr_text=recognition.markdown_content,
            status=DocumentStatus.PENDING,  # 待确认状态
            user_category=user_category,
            tags=classification.tags,
            amount=amount,
            issued_date=issued_date,
            document_type_reasoning=document_type_reasoning,
            tag_classification_reasoning=tag_classification_reasoning,
        )

        # 将结构化数据附加到票据（动态属性用于后续处理）
        document.structured_data = structured_values  # type: ignore[attr-defined]
        
        # 如果有备注，添加到OCR文本
        ocr_text = document.ocr_text 
        
        document.ocr_text = ocr_text
        
        return document
    
    def _extract_text_content(self, response: Any) -> str:
        """从API响应中提取文本内容
        
        Args:
            response: API响应
            
        Returns:
            提取的文本内容
        """
        try:
            # 如果已经是字典，提取choices中的内容
            if isinstance(response, dict):
                if 'choices' in response:
                    content = response['choices'][0]['message']['content']
                else:
                    return str(response)
            else:
                content = str(response)
            
            return content
            
        except Exception as e:
            self.logger.error(f"提取文本内容失败: {e}, 原始内容: {response}")
            return ""
    
    def _extract_markdown_content(self, text: str) -> str:
        """从文本中提取 markdown 代码块中的内容
        
        Args:
            text: 包含 markdown 代码块的文本
            
        Returns:
            提取的 markdown 内容
        """
        try:
            # 优先查找 ```markdown 代码块
            if '```markdown' in text:
                start = text.find('```markdown') + 11
                end = text.find('```', start)
                if end != -1:
                    return text[start:end].strip()
            # 其次查找通用的 ``` 代码块
            elif '```' in text:
                start = text.find('```') + 3
                end = text.find('```', start)
                if end != -1:
                    return text[start:end].strip()
            
            # 如果没有找到代码块，返回原文本
            return text.strip()
            
        except Exception as e:
            self.logger.error(f"提取 markdown 内容失败: {e}")
            return text.strip()
    
    def _parse_llm_response(self, response: Any) -> Dict[str, Any]:
        """解析大模型响应（JSON格式）
        
        Args:
            response: API响应
            
        Returns:
            解析后的字典
        """
        try:
            # 如果已经是字典，直接返回
            if isinstance(response, dict):
                # 提取choices中的内容
                if 'choices' in response:
                    content = response['choices'][0]['message']['content']
                else:
                    return response
            else:
                content = str(response)
            
            # 尝试从markdown代码块中提取JSON
            if '```json' in content:
                start = content.find('```json') + 7
                end = content.find('```', start)
                json_str = content[start:end].strip()
            elif '```' in content:
                start = content.find('```') + 3
                end = content.find('```', start)
                json_str = content[start:end].strip()
            else:
                json_str = content
            
            # 解析JSON
            parsed = json5.loads(json_str)
            if isinstance(parsed, dict):
                return parsed
            return {"data": parsed}
            
        except Exception as e:
            self.logger.error(f"解析响应失败: {e}, 原始内容: {response}")
            return {}


async def _run_demo(image_path: Path) -> None:
    """运行票据识别示例"""
    user = create_new_user(
        user_id="demo_user",
        profile_items=["测试用户：用于票据识别示例"]
    )
    agent = DocumentAgent(user)

    result = await agent._recognize_document(image_path=image_path)

    print("=== 票据识别结果 ===")
    print(json.dumps(asdict(result), ensure_ascii=False, indent=2))


async def _test_process_upload(image_path: Path, text: str) -> None:
    """测试process_upload流程"""

        

    user = create_new_user(
        user_id="test_user",
        profile_items=[
            "喜欢与科研院所合作的工程师",
            "经常在西北地区参与技术交流",
        ],
    )

    result = await DocumentAgent(user).process_upload(image_path=image_path, text=text)

    print("=== process_upload 测试结果 ===")
    print(f"处理是否成功：{result.success}")
    if result.error:
        print(f"错误信息：{result.error}")
        return

    summary = {
        "document_id": result.document_id,
        "document_type": (
            result.document.document_type.value if result.document else None
        ),
        "user_category": (
            result.classification.user_category if result.classification else None
        ),
        "tags": result.classification.tags if result.classification else [],
        "structured_data": (
            getattr(result.document, "structured_data", {}) if result.document else {}
        ),
        "intent_analysis": result.intent.analysis if result.intent else "",
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":

    image_path = "/data/disk2/zhz/票据管理比赛/test_data/image.png"
    input_text = "这是我在2025年4月9日从西安北站到绵阳站的高铁票，用于参加“中国工程物理研究院培训中心”组织的为期一周的技术研讨会。"

    image_path = Path(image_path)

    asyncio.run(_test_process_upload(image_path, input_text))


__all__ = [
    "DocumentAgent",
    "RecognitionResult",
    "ClassificationResult",
    "IntentResult",
    "ProcessResult",
]

