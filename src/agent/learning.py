"""反馈学习模块 - 分析用户修改行为，生成分类规则"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..models.user import ClassificationFeedback, User
from ..multimodal.client import create_client
from ..multimodal.text import chat_completion
from ..storage import UserStorage
from .prompts import build_rule_generation_prompt, build_feedback_analysis_prompt

logger = logging.getLogger(__name__)


@dataclass
class Rule:
    """分类规则"""
    rule_text: str  # 规则描述
    trigger_conditions: Dict[str, Any]  # 触发条件
    confidence: float  # 置信度
    sample_count: int  # 样本数量


@dataclass
class LearningResult:
    """学习结果"""
    rules: List[Rule]
    summary: str
    feedback_count: int


class FeedbackLearner:
    """反馈学习器
    
    分析用户的分类修改历史，生成自然语言描述的规则。
    """
    
    def __init__(self, user: User, user_storage: Optional[UserStorage] = None):
        """初始化学习器
        
        Args:
            user: 用户对象
            user_storage: 用户存储实例，用于加载文档
        """
        self.user = user
        self.user_storage = user_storage or UserStorage()
        self.logger = logging.getLogger(f"{__name__}.{user.user_id}")
        self._deepseek_client = None  # 延迟初始化 deepseek 客户端
    
    def _get_deepseek_client(self):
        """获取或创建 deepseek 客户端（延迟初始化）
        
        Returns:
            deepseek 客户端实例
        """
        if self._deepseek_client is None:
            settings = get_settings()
            if not settings.has_deepseek_credentials:
                raise ValueError(
                    "Deepseek 配置未提供，请在环境变量或 .env 文件中配置 "
                    "DEEKSEEP_API_KEY、DEEKSEEP_TEXT_MODEL 和 DEEKSEEP_BASE_URL"
                )
            # 创建 deepseek 客户端（使用不同的 base_url 和 api_key）
            from ..config import Settings
            
            # 创建临时的 Settings 对象用于 deepseek
            deepseek_settings = Settings(
                api_key=settings.deepseek_api_key,
                base_url=settings.deepseek_base_url,
                text_model=settings.deepseek_text_model,
                vision_model="",  # deepseek 不需要
                asr_model="",  # deepseek 不需要
                http_timeout=settings.http_timeout,
                deepseek_api_key="",
                deepseek_text_model="",
                deepseek_base_url=""
            )
            self._deepseek_client = create_client(settings=deepseek_settings)
        return self._deepseek_client
    
    async def analyze_feedback(
        self,
        feedback: ClassificationFeedback
    ) -> Optional[str]:
        """分析单次反馈
        
        Args:
            feedback: 分类反馈
            
        Returns:
            简单的分析结果描述
        """
        try:
            analysis = []
            
            if feedback.is_category_changed():
                analysis.append(
                    f"用户将类别从'{feedback.original_user_category}'改为'{feedback.new_user_category}'"
                )
            
            if feedback.is_tags_changed():
                added = feedback.get_added_tags()
                removed = feedback.get_removed_tags()
                
                if added:
                    analysis.append(f"添加标签: {', '.join(added)}")
                if removed:
                    analysis.append(f"移除标签: {', '.join(removed)}")
            
            return "; ".join(analysis) if analysis else None
            
        except Exception as e:
            self.logger.error(f"分析反馈失败: {e}")
            return None
    
    async def generate_rules(
        self,
        max_feedbacks: int = 50,
        batch_size: int = 10
    ) -> LearningResult:
        """生成分类规则（增量方式）
        
        Args:
            max_feedbacks: 最多分析的反馈数量，默认50
            batch_size: 每批处理的反馈数量，默认10
            
        Returns:
            学习结果
        """
        try:
            # 获取所有反馈，按时间倒序排序，取最新的max_feedbacks条
            all_feedbacks = self.user.learning_history.feedbacks.copy()
            all_feedbacks.sort(key=lambda x: x.timestamp, reverse=True)
            feedbacks = all_feedbacks[:max_feedbacks]
            
         
            
            # 获取现有规则（直接使用列表）
            existing_rules = self.user.settings.get('classification_rules', [])
            # 兼容旧格式：如果是字符串，尝试解析
            if isinstance(existing_rules, str):
                existing_rules = self._load_rules_list(existing_rules)
            # 确保是列表格式
            if not isinstance(existing_rules, list):
                existing_rules = []
            
            # 为每个反馈加载文档信息
            enriched_feedbacks = []
            for fb in feedbacks:
                try:
                    # 加载文档
                    document = self.user_storage.load_document(self.user.user_id, fb.document_id)
                    if document:
                        document_type_reasoning = getattr(document, 'document_type_reasoning', None) or ''
                        tag_classification_reasoning = getattr(document, 'tag_classification_reasoning', None) or ''
                        # 如果这两项有一项为空，则跳过这一条数据
                        if not document_type_reasoning or not tag_classification_reasoning:
                            continue
                        enriched_feedbacks.append({
                            "feedback": fb,
                            "ocr_text": getattr(document, 'ocr_text', ''),
                            "document_type_reasoning": document_type_reasoning,
                            "tag_classification_reasoning": tag_classification_reasoning
                        })
                    else:
                        self.logger.warning(f"无法加载文档 {fb.document_id}，跳过该反馈")
                except Exception as e:
                    self.logger.warning(f"加载文档 {fb.document_id} 失败: {e}，跳过该反馈")
            
            # if len(enriched_feedbacks) < min_feedbacks:
            #     self.logger.info(f"有效反馈数量不足({len(enriched_feedbacks)} < {min_feedbacks})，跳过规则生成")
            #     return LearningResult(
            #         rules=[],
            #         summary="有效反馈数量不足，暂无规则生成",
            #         feedback_count=len(enriched_feedbacks)
            #     )
            
            # 按批次处理：10个为一组
            all_rules = []
            all_summaries = []
            
            for batch_idx in range(0, len(enriched_feedbacks), batch_size):
                batch = enriched_feedbacks[batch_idx:batch_idx + batch_size]
                self.logger.info(f"处理第 {batch_idx//batch_size + 1} 批，共 {len(batch)} 个案例")
                
                # 并行为每个案例生成反馈
                batch_feedbacks = []
                tasks = [self._generate_case_feedback(case) for case in batch]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for result in results:
                    if isinstance(result, Exception):
                        self.logger.error(f"生成案例反馈失败: {result}")
                    elif result:
                        batch_feedbacks.append(result)
                
                # 如果有反馈，直接生成并应用规则操作
                if batch_feedbacks:
                    result = await self._generate_and_apply_rule_operations(
                        batch=batch,
                        batch_feedbacks=batch_feedbacks,
                        existing_rules=existing_rules
                    )
                    
                    if result:
                        existing_rules = result['updated_rules']
                        if result.get('summary'):
                            all_summaries.append(result['summary'])
                        # 收集新增的规则用于返回结果
                        all_rules.extend(result.get('new_rules', []))
            
            # 构建最终结果
            summary = "\n\n".join(all_summaries) if all_summaries else "已生成分类规则"
            
            # 更新用户设置中的规则（直接保存为列表）
            self.user.settings['classification_rules'] = existing_rules
            self.user.settings['rules_updated_at'] = datetime.now().isoformat()
            self.logger.info(f"已更新用户规则，共{len(existing_rules)}条")
            
            # 清空反馈历史数据
            feedback_count_before_clear = len(self.user.learning_history.feedbacks)
            self.user.learning_history.feedbacks.clear()
            self.logger.info(f"已清空反馈历史，共清空 {feedback_count_before_clear} 条反馈记录")
            
            return LearningResult(
                rules=all_rules,
                summary=summary,
                feedback_count=len(enriched_feedbacks)
            )
            
        except Exception as e:
            self.logger.error(f"生成规则失败: {e}", exc_info=True)
            return LearningResult(
                rules=[],
                summary=f"规则生成失败: {str(e)}",
                feedback_count=0
            )
    
    async def _generate_case_feedback(self, case: Dict) -> Optional[str]:
        """为单个案例生成反馈分析
        
        Args:
            case: 包含反馈和文档信息的字典
            
        Returns:
            反馈分析文本
        """
        try:
            fb = case['feedback']
            
            # 构建单案例反馈分析提示词
            prompt = build_feedback_analysis_prompt(
                ocr_text=case['ocr_text'],
                document_type_reasoning=case['document_type_reasoning'],
                tag_classification_reasoning=case['tag_classification_reasoning'],
                original_user_category=fb.original_user_category,
                original_tags=fb.original_tags,
                new_user_category=fb.new_user_category,
                new_tags=fb.new_tags
            )
            
            # 调用大模型（使用 deepseek）
            settings = get_settings()
            deepseek_client = self._get_deepseek_client()
            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                client=deepseek_client,
                model=settings.deepseek_text_model,
                response_format="json_object"
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            return result_data.get('feedback', '')
            
        except Exception as e:
            self.logger.error(f"生成案例反馈失败: {e}")
            return None
    
    async def _generate_and_apply_rule_operations(
        self,
        batch: List[Dict],
        batch_feedbacks: List[str],
        existing_rules: List[str]
    ) -> Optional[Dict[str, Any]]:
        """基于一批反馈生成规则操作并直接应用
        
        Args:
            batch: 一批案例的文档信息列表
            batch_feedbacks: 一批案例的反馈文本列表
            existing_rules: 现有规则列表
            
        Returns:
            包含更新后的规则列表、摘要和新增规则的字典，失败时返回None
        """
        try:
            # 检查规则数量限制
            rule_count = len(existing_rules)
            needs_reduction = rule_count >= 20
            
            # 构建增量规则生成提示词
            prompt = build_rule_generation_prompt(
                feedback_history=batch,
                feedback_analyses=batch_feedbacks,
                existing_rules=existing_rules,
                needs_reduction=needs_reduction
            )
            
            # 调用大模型（使用 deepseek）
            settings = get_settings()
            deepseek_client = self._get_deepseek_client()
            response = await chat_completion(
                messages=[{"role": "user", "content": prompt}],
                client=deepseek_client,
                model=settings.deepseek_text_model,
                response_format="json_object"
            )
            
            # 解析响应
            result_data = self._parse_llm_response(response)
            operations = result_data.get('operations', [])
            
            if not operations:
                return None
            
            # 从操作中提取新增的规则（用于返回结果）
            new_rules = self._extract_rules_from_operations(operations)
            
            # 应用规则操作
            operations_dict = {
                'operations': operations,
                'summary': result_data.get('summary', '')
            }
            updated_rules = self._apply_rule_operations(existing_rules, operations_dict)
            
            return {
                'updated_rules': updated_rules,
                'summary': result_data.get('summary', ''),
                'new_rules': new_rules
            }
            
        except Exception as e:
            self.logger.error(f"生成并应用规则操作失败: {e}")
            return None
    
    def _extract_rules_from_operations(self, operations: List[Dict[str, Any]]) -> List[Rule]:
        """从操作中提取新增的规则对象（用于返回结果）
        
        Args:
            operations: 规则操作列表
            
        Returns:
            规则对象列表
        """
        rules = []
        for op in operations:
            op_type = op.get('type', '').lower()
            # 提取添加、修改和融合操作中的规则
            if op_type in ['add', 'modify', 'merge']:
                rule_data = op.get('rule', {})
                if rule_data:
                    rules.append(Rule(
                        rule_text=rule_data.get('rule_text', ''),
                        trigger_conditions=rule_data.get('trigger_conditions', {}),
                        confidence=rule_data.get('confidence', 0.0),
                        sample_count=rule_data.get('sample_count', 0)
                    ))
        return rules
    
    def _load_rules_list(self, rules_raw: Any) -> List[str]:
        """加载规则列表（仅返回规则文本列表，兼容旧格式）
        
        Args:
            rules_raw: 规则数据（可能是字符串或列表）
            
        Returns:
            规则文本列表
        """
        if not rules_raw:
            return []
        
        # 如果是字符串，尝试解析JSON
        if isinstance(rules_raw, str):
            try:
                parsed = json.loads(rules_raw)
                if isinstance(parsed, list):
                    # 检查是旧格式（Dict列表）还是新格式（字符串列表）
                    if parsed and isinstance(parsed[0], dict):
                        # 旧格式：从字典中提取 rule_text
                        return [rule.get('rule_text', '') for rule in parsed if rule.get('rule_text')]
                    elif parsed and isinstance(parsed[0], str):
                        # 新格式：直接返回字符串列表
                        return parsed
                    else:
                        return []
                else:
                    return []
            except json.JSONDecodeError:
                # 不是JSON格式，可能是旧格式的纯文本，返回空列表
                return []
        
        # 如果已经是列表
        if isinstance(rules_raw, list):
            if rules_raw and isinstance(rules_raw[0], dict):
                # 旧格式：从字典中提取 rule_text
                return [rule.get('rule_text', '') for rule in rules_raw if rule.get('rule_text')]
            elif rules_raw and isinstance(rules_raw[0], str):
                # 新格式：直接返回
                return rules_raw
            else:
                return []
        
        return []
    
    def _apply_rule_operations(
        self,
        existing_rules: List[str],
        batch_rules: Dict[str, Any]
    ) -> List[str]:
        """应用规则操作（添加、删除、融合、修改）
        
        Args:
            existing_rules: 现有规则文本列表
            batch_rules: 包含操作和规则的字典
            
        Returns:
            更新后的规则文本列表
        """
        operations = batch_rules.get('operations', [])
        if not operations:
            return existing_rules
        
        updated_rules = existing_rules.copy()
        
        # 按顺序执行操作（使用索引而不是ID）
        for op in operations:
            op_type = op.get('type', '').lower()
            
            if op_type == 'add':
                # 添加新规则
                rule_data = op.get('rule', {})
                if rule_data:
                    rule_text = rule_data.get('rule_text', '')
                    if rule_text:
                        updated_rules.append(rule_text)
            
            elif op_type == 'delete':
                # 删除规则（通过索引）
                rule_id = op.get('rule_id', '')
                # 尝试从 rule_id 中提取索引（格式：rule_0, rule_1 等）
                try:
                    # 如果 rule_id 是 rule_N 格式，提取 N
                    if rule_id.startswith('rule_'):
                        idx_str = rule_id.split('_')[-1]
                        idx = int(idx_str)
                        if 0 <= idx < len(updated_rules):
                            updated_rules.pop(idx)
                except (ValueError, IndexError):
                    # 如果无法解析索引，尝试通过规则文本匹配删除
                    rule_data = op.get('rule', {})
                    rule_text = rule_data.get('rule_text', '')
                    if rule_text and rule_text in updated_rules:
                        updated_rules.remove(rule_text)
            
            elif op_type == 'modify':
                # 修改规则（通过索引）
                rule_id = op.get('rule_id', '')
                rule_data = op.get('rule', {})
                new_rule_text = rule_data.get('rule_text', '')
                
                if new_rule_text:
                    try:
                        # 尝试从 rule_id 中提取索引
                        if rule_id.startswith('rule_'):
                            idx_str = rule_id.split('_')[-1]
                            idx = int(idx_str)
                            if 0 <= idx < len(updated_rules):
                                updated_rules[idx] = new_rule_text
                    except (ValueError, IndexError):
                        # 如果无法解析索引，跳过修改
                        pass
            
            elif op_type == 'merge':
                # 融合多条规则
                merge_rule_ids = op.get('merge_rule_ids', [])
                rule_data = op.get('rule', {})
                merged_rule_text = rule_data.get('rule_text', '')
                
                if merge_rule_ids and merged_rule_text:
                    # 找到要融合的规则索引（倒序删除，避免索引变化）
                    indices_to_remove = []
                    for rid in merge_rule_ids:
                        try:
                            if rid.startswith('rule_'):
                                idx_str = rid.split('_')[-1]
                                idx = int(idx_str)
                                if 0 <= idx < len(updated_rules):
                                    indices_to_remove.append(idx)
                        except (ValueError, IndexError):
                            continue
                    
                    if indices_to_remove:
                        # 倒序排序，避免删除时索引变化
                        indices_to_remove = sorted(set(indices_to_remove), reverse=True)
                        
                        # 删除旧规则
                        for idx in indices_to_remove:
                            updated_rules.pop(idx)
                        
                        # 添加融合后的规则
                        updated_rules.append(merged_rule_text)
        
        # 限制最多20条规则
        if len(updated_rules) > 20:
            updated_rules = updated_rules[:20]
            self.logger.warning(f"规则数量超过20条，已自动保留前20条")
        
        return updated_rules
    
    def _update_user_rules(self, rules: List[Rule], summary: str) -> None:
        """更新用户设置中的规则
        
        Args:
            rules: 规则列表
            summary: 规则摘要
        """
        try:
            # 格式化规则文本
            rules_text = summary + "\n\n具体规则：\n"
            for i, rule in enumerate(rules, 1):
                rules_text += f"{i}. {rule.rule_text} (置信度: {rule.confidence:.2f})\n"
            
            # 保存到用户设置
            self.user.settings['classification_rules'] = rules_text
            self.user.settings['rules_updated_at'] = datetime.now().isoformat()
            
            self.logger.info(f"已更新用户规则，共{len(rules)}条")
            
        except Exception as e:
            self.logger.error(f"更新用户规则失败: {e}")
    
    def _parse_llm_response(self, response: Any) -> Dict[str, Any]:
        """解析大模型响应
        
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
            return json.loads(json_str)
            
        except Exception as e:
            self.logger.error(f"解析响应失败: {e}, 原始内容: {response}")
            return {"rules": [], "summary": "解析失败"}


__all__ = [
    "FeedbackLearner",
    "Rule",
    "LearningResult",
]

