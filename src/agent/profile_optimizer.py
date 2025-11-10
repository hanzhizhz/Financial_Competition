"""用户画像优化器 - 基于票据数据和行为优化用户画像"""

from __future__ import annotations

import asyncio
import json
import logging
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from ..config import get_settings
from ..models import BaseDocument
from ..models.base import UserCategory
from ..models.user import User
from ..multimodal.client import create_client
from ..multimodal.text import chat_completion
from ..storage import UserStorage
from .prompts import build_profile_optimization_operations_prompt

logger = logging.getLogger(__name__)


@dataclass
class OptimizationTrigger:
    """优化触发条件"""
    manual: bool = False  # 手动触发
    continuous_modifications: bool = False  # 连续修改
    time_based: bool = False  # 基于时间
    reason: str = ""


class ProfileOptimizer:
    """用户画像优化器
    
    根据用户的历史票据数据和修改行为，优化用户画像。
    """
    
    def __init__(self, user: User, storage: UserStorage):
        """初始化优化器
        
        Args:
            user: 用户对象
            storage: 存储管理器
        """
        self.user = user
        self.storage = storage
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
    
    def should_trigger(
        self,
        manual: bool = False,
        continuous_modification_threshold: int = 3
    ) -> OptimizationTrigger:
        """判断是否应该触发画像优化
        
        Args:
            manual: 是否手动触发
            continuous_modification_threshold: 连续修改阈值
            
        Returns:
            触发条件对象
        """
        if manual:
            return OptimizationTrigger(
                manual=True,
                reason="手动触发"
            )
        
        # 不再支持自动触发，仅保留手动触发
        return OptimizationTrigger(reason="不满足触发条件，仅支持手动触发")
    
    async def optimize_profile(self) -> Dict[str, Any]:
        """优化用户画像（两阶段处理）
        
        第一阶段：统计画像更新时间点后的所有历史票据
        第二阶段：抽取最近100条票据，以10个为一组批处理，生成画像优化操作
        
        Returns:
            优化结果
        """
        try:
            self.logger.info("开始优化用户画像...")
            
            # 第一阶段：收集整体统计信息
            self.logger.info("阶段1：收集整体统计信息...")
            overall_statistics = await self._collect_overall_statistics()
            
            if overall_statistics.get('total_documents', 0) == 0:
                self.logger.info("没有足够的票据数据，跳过画像优化")
                return {
                    "success": False,
                    "error": "没有足够的票据数据"
                }
            
            # 第二阶段：批处理最近100条票据
            self.logger.info("阶段2：批处理最近100条票据...")
            
            # 加载所有票据
            document_ids = self.storage.list_user_documents(self.user.user_id)
            all_documents = []
            for doc_id in document_ids:
                doc = self.storage.load_document(self.user.user_id, doc_id)
                if doc:
                    all_documents.append(doc)
            
            if not all_documents:
                return {
                    "success": False,
                    "error": "没有票据数据"
                }
            
            # 获取画像更新时间点
            profile_updated_at = self.user.profile.updated_at
            
            # 过滤出画像更新后的票据
            recent_documents = [
                doc for doc in all_documents
                if doc.upload_time > profile_updated_at
            ]
            
            # 取最近100条
            recent_documents = sorted(recent_documents, key=lambda x: x.upload_time, reverse=True)[:100]
            
            if not recent_documents:
                self.logger.info("画像更新后没有新的票据，跳过优化")
                return {
                    "success": False,
                    "error": "画像更新后没有新的票据"
                }
            
            self.logger.info(f"将处理 {len(recent_documents)} 条票据")
            
            # 以10个为一组批处理
            batch_size = 10
            all_operations = []
            
            for batch_idx in range(0, len(recent_documents), batch_size):
                batch = recent_documents[batch_idx:batch_idx + batch_size]
                self.logger.info(f"处理第 {batch_idx//batch_size + 1} 批，共 {len(batch)} 个票据")
                
                # 处理当前批次
                operations = await self._process_document_batch(
                    batch=batch,
                    overall_statistics=overall_statistics
                )
                
                if operations:
                    all_operations.extend(operations)
                    self.logger.info(f"第 {batch_idx//batch_size + 1} 批生成了 {len(operations)} 个操作")
            
            # 应用所有操作
            if all_operations:
                self.logger.info(f"共生成 {len(all_operations)} 个操作，开始应用...")
                updated_profile = self._apply_profile_operations(
                    current_profile=self.user.profile.profile_text,
                    operations=all_operations
                )
                
                # 更新用户画像
                self.user.update_profile(updated_profile)
                self.user.settings['last_profile_optimization'] = datetime.now().isoformat()
                
                # 保存用户
                self.storage.save_user(self.user)
                
                self.logger.info(f"画像已更新，共{len(all_operations)}个操作")
                
                return {
                    "success": True,
                    "updated_profile": updated_profile,
                    "operations": all_operations,
                    "operations_count": len(all_operations),
                    "statistics": overall_statistics
                }
            else:
                self.logger.info("未生成任何操作，画像保持不变")
                return {
                    "success": True,
                    "updated_profile": self.user.profile.profile_text,
                    "operations": [],
                    "operations_count": 0,
                    "message": "未发现需要优化的地方",
                    "statistics": overall_statistics
                }
            
        except Exception as e:
            self.logger.error(f"优化画像失败: {e}", exc_info=True)
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _collect_overall_statistics(self) -> Dict[str, Any]:
        """收集整体统计信息（画像更新后的所有票据）
        
        Returns:
            统计信息字典
        """
        try:
            # 加载所有票据
            document_ids = self.storage.list_user_documents(self.user.user_id)
            all_documents = []
            for doc_id in document_ids:
                doc = self.storage.load_document(self.user.user_id, doc_id)
                if doc:
                    all_documents.append(doc)
            
            if not all_documents:
                return {"total_documents": 0}
            
            # 获取画像更新时间点
            profile_updated_at = self.user.profile.updated_at
            
            # 过滤出画像更新后的票据
            documents = [
                doc for doc in all_documents
                if doc.upload_time > profile_updated_at
            ]
            
            if not documents:
                return {"total_documents": 0}
            
            # 统计支出类别分布
            expense_counter = Counter()
            income_counter = Counter()
            tag_counter = Counter()
            
            # 金额统计
            total_expense = 0.0
            total_income = 0.0
            expense_count = 0
            income_count = 0
            
            # 单笔金额分布（按区间统计）
            amount_ranges = {
                "0-50元": 0,
                "50-100元": 0,
                "100-500元": 0,
                "500-1000元": 0,
                "1000元以上": 0
            }
            
            # 时间范围（用于计算月均）
            earliest_date = None
            latest_date = None
            
            for doc in documents:
                # 统计类别
                if doc.user_category:
                    if doc.user_category == UserCategory.INCOME:
                        income_counter[doc.user_category.value] += 1
                    else:
                        expense_counter[doc.user_category.value] += 1
                
                # 统计标签
                for tag in doc.tags:
                    tag_counter[tag] += 1
                
                # 统计金额
                if doc.amount is not None and doc.amount > 0:
                    if doc.user_category == UserCategory.INCOME:
                        total_income += doc.amount
                        income_count += 1
                    else:
                        total_expense += doc.amount
                        expense_count += 1
                    
                    # 统计金额分布
                    if doc.amount < 50:
                        amount_ranges["0-50元"] += 1
                    elif doc.amount < 100:
                        amount_ranges["50-100元"] += 1
                    elif doc.amount < 500:
                        amount_ranges["100-500元"] += 1
                    elif doc.amount < 1000:
                        amount_ranges["500-1000元"] += 1
                    else:
                        amount_ranges["1000元以上"] += 1
                
                # 记录时间范围
                if doc.upload_time:
                    if earliest_date is None or doc.upload_time < earliest_date:
                        earliest_date = doc.upload_time
                    if latest_date is None or doc.upload_time > latest_date:
                        latest_date = doc.upload_time
            
            # 计算月数
            months = 1  # 至少算1个月
            if earliest_date and latest_date:
                days_diff = (latest_date - earliest_date).days
                months = max(1, days_diff / 30.0)  # 按30天算一个月
            
            # 计算支出类别分布（带百分比）
            total_expense_docs = sum(expense_counter.values())
            expense_distribution = {}
            for cat, count in expense_counter.items():
                percentage = (count / total_expense_docs * 100) if total_expense_docs > 0 else 0
                expense_distribution[cat] = {
                    "count": count,
                    "percentage": percentage
                }
            
            # 计算收入类别分布（带百分比）
            total_income_docs = sum(income_counter.values())
            income_distribution = {}
            for cat, count in income_counter.items():
                percentage = (count / total_income_docs * 100) if total_income_docs > 0 else 0
                income_distribution[cat] = {
                    "count": count,
                    "percentage": percentage
                }
            
            # 最常用标签（取前20个）
            frequent_tags = [tag for tag, _ in tag_counter.most_common(20)]
            
            return {
                "total_documents": len(documents),
                "expense_distribution": expense_distribution,
                "income_distribution": income_distribution,
                "monthly_average": {
                    "expense": total_expense / months,
                    "income": total_income / months
                },
                "amount_distribution": amount_ranges,
                "frequent_tags": frequent_tags,
                "time_range": {
                    "earliest": earliest_date.isoformat() if earliest_date else None,
                    "latest": latest_date.isoformat() if latest_date else None,
                    "months": round(months, 1)
                }
            }
            
        except Exception as e:
            self.logger.error(f"收集统计信息失败: {e}")
            return {"total_documents": 0, "error": str(e)}
    
    async def _process_document_batch(
        self,
        batch: List[BaseDocument],
        overall_statistics: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """处理一批票据，生成画像优化操作
        
        Args:
            batch: 票据列表
            overall_statistics: 整体统计信息
            
        Returns:
            操作列表
        """
        try:
            # 提取票据关键信息
            batch_documents = []
            for doc in batch:
                doc_info = {
                    "ocr_text": doc.ocr_text,
                    "document_type": doc.document_type.value if doc.document_type else "未知",
                    "user_category": doc.user_category.value if doc.user_category else "未知",
                    "tags": doc.tags,
                    "amount": doc.amount,
            
                }
                batch_documents.append(doc_info)
            
            # 构建提示词
            prompt = build_profile_optimization_operations_prompt(
                current_profile=self.user.profile.profile_text,
                overall_statistics=overall_statistics,
                batch_documents=batch_documents
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
            
            return operations
            
        except Exception as e:
            self.logger.error(f"处理批次失败: {e}")
            return []
    
    def _apply_profile_operations(
        self,
        current_profile: List[str],
        operations: List[Dict[str, Any]]
    ) -> List[str]:
        """应用画像操作（添加、删除、融合）
        
        Args:
            current_profile: 当前画像列表
            operations: 操作列表
            
        Returns:
            更新后的画像列表
        """
        updated_profile = current_profile.copy()
        
        # 按顺序执行操作（使用索引）
        for op in operations:
            op_type = op.get('type', '').lower()
            
            if op_type == 'add':
                # 添加新画像条目
                profile_item = op.get('profile_item', {})
                text = profile_item.get('text', '')
                if text and text not in updated_profile:
                    updated_profile.append(text)
                    self.logger.info(f"添加画像: {text}")
            
            elif op_type == 'delete':
                # 删除画像条目（通过索引）
                profile_id = op.get('profile_id', '')
                try:
                    # 如果 profile_id 是 profile_N 格式，提取 N
                    if profile_id.startswith('profile_'):
                        idx_str = profile_id.split('_')[-1]
                        idx = int(idx_str)
                        if 0 <= idx < len(updated_profile):
                            deleted_text = updated_profile.pop(idx)
                            self.logger.info(f"删除画像: {deleted_text}")
                except (ValueError, IndexError) as e:
                    self.logger.warning(f"删除操作失败: {e}")
            
            elif op_type == 'merge':
                # 融合多条画像条目
                merge_profile_ids = op.get('merge_profile_ids', [])
                profile_item = op.get('profile_item', {})
                merged_text = profile_item.get('text', '')
                
                if merge_profile_ids and merged_text:
                    # 找到要融合的画像索引（倒序删除，避免索引变化）
                    indices_to_remove = []
                    for pid in merge_profile_ids:
                        try:
                            if pid.startswith('profile_'):
                                idx_str = pid.split('_')[-1]
                                idx = int(idx_str)
                                if 0 <= idx < len(updated_profile):
                                    indices_to_remove.append(idx)
                        except (ValueError, IndexError):
                            continue
                    
                    if indices_to_remove:
                        # 倒序排序，避免删除时索引变化
                        indices_to_remove = sorted(set(indices_to_remove), reverse=True)
                        
                        # 记录被融合的画像
                        merged_items = [updated_profile[idx] for idx in sorted(indices_to_remove)]
                        
                        # 删除旧画像
                        for idx in indices_to_remove:
                            updated_profile.pop(idx)
                        
                        # 添加融合后的画像
                        if merged_text not in updated_profile:
                            updated_profile.append(merged_text)
                            self.logger.info(f"融合画像: {merged_items} -> {merged_text}")
        
        return updated_profile
    
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
            return {
                "operations": []
            }


__all__ = [
    "ProfileOptimizer",
    "OptimizationTrigger",
]
