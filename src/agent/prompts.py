"""提示词模板 - Agent使用的所有提示词定义"""

from typing import Any, Dict, List, Optional


# ==================== 票据相关性判断提示词 ====================

DOCUMENT_CHECK_PROMPT = """你是一个专业的票据识别助手。请分析图片中的内容，判断图片是否与票据有关。

**任务**：
判断图片是否为票据相关图片（发票、行程单、小票、收据等）

**票据类型定义**：
- **发票**：增值税普通发票、电子发票、专用发票（包含发票代码、号码、税号等）
- **行程单**：航空、铁路、巴士等交通凭证（包含车次/航班号、出发到达站等）
- **小票**：超市、便利店、餐厅消费小票（包含商家名称、商品明细等）
- **收据**：非税收入、押金、私人交易凭证（包含收付款方、金额等）

**输出格式**：
```json
{{
  "is_document": true/false,
  "reason": "判断理由（如果不是票据，说明原因）"
}}
```

**注意事项**：
- 如果图片模糊、不完整、非票据（如风景照、人物照、截图等），设置 is_document 为 false
- 只判断是否为票据，不需要提取具体内容

请开始分析图片。
"""


# ==================== 票据文本识别提示词 ====================

DOCUMENT_RECOGNITION_PROMPT = """你是一个专业的票据文本识别助手。请识别图片中的票据文本内容。

**任务**：
识别图片中的所有文本内容，并将识别结果包裹在 markdown 代码块中。

**输出格式**：
请直接将识别结果包裹在 markdown 代码块中，格式如下：
```markdown
票据文本内容
```

**注意事项**：
- 识别图片中的所有可见文本
- 保持文本的原始格式和布局
- 必须将识别结果包裹在 ```markdown 代码块中
- 只返回文本内容，不需要进行分类判断
- 直接输出文本，不要使用 JSON 格式

请开始识别文本。
"""


def build_document_check_prompt() -> str:
    """构建票据相关性判断提示词
    
    Returns:
        完整的提示词
    """
    return DOCUMENT_CHECK_PROMPT


def build_document_recognition_prompt(additional_context: Optional[str] = None) -> str:
    """构建票据文本识别提示词
    
    Args:
        additional_context: 额外的上下文信息
        
    Returns:
        完整的提示词
    """
    prompt = DOCUMENT_RECOGNITION_PROMPT
    if additional_context:
        prompt += f"\n\n**额外信息**：\n{additional_context}"
    return prompt


def build_document_classification_prompt(document_content: str) -> str:
    """构建票据分类判断提示词
    
    Args:
        document_content: 票据文本内容
        
    Returns:
        完整的提示词
    """
    return DOCUMENT_CLASSIFICATION_PROMPT.format(document_content=document_content)


# ==================== 分类决策提示词 ====================

CLASSIFICATION_PROMPT_TEMPLATE = """你是一个智能票据分类助手。请根据票据内容、用户画像和历史规则，为已分配用户视角类型的票据分配合适的子标签。

**用户画像**：
{user_profile}

**历史分类规则**：
{classification_rules}

**票据内容**：
{document_content}

**用户意图**：
{user_intent}

**用户视角类型**：
{user_category}

**用户视角标签**：
{user_tags}

**输出格式**：
```json
{{
"reasoning": "请根据用户画像、历史规则、票据内容和用户意图，给出分类理由。"
"tags": ["子标签1", "子标签2", "子标签3"],
}}
```

**注意事项**：
- 可以为tags添加多个子标签。
- 当不存在合适的子标签时，可以使用"其他:xxx"标签,xxx为自定义标签。
- 自定义标签将动态的优化标签系统，并作为下次分类的参考。
- 但在添加自动以标签时需要谨慎，以通用尽可能多的场景为目标，避免过于特殊化，造成标签系统过于复杂。

**强调**
 - 在进行子标签分类时，要进行保守推理，如果用户意图中没有明确体现，仅进行最常见的标签添加。
 - 不要过度推理用户画像内容，其只是做一个参考，不过盲目的去扩展票据背景。
"""

# ==================== 票据分类判断提示词 ====================

DOCUMENT_CLASSIFICATION_PROMPT = """你是一个专业的票据分类助手。请根据票据文本内容，判断票据的专业分类和用户视角分类。

**票据文本内容**：
{document_content}

**专业分类类型**：
- **发票**：增值税普通发票、电子发票、专用发票（包含发票代码、号码、税号等）
- **行程单**：航空、铁路、巴士等交通凭证（包含车次/航班号、出发到达站等）
- **小票**：超市、便利店、餐厅消费小票（包含商家名称、商品明细等）
- **收据**：非税收入、押金、私人交易凭证（包含收付款方、金额等）

**用户视角分类**：
- 餐饮消费：所有食物饮品支出：正餐、小吃、咖啡奶茶、外卖、聚餐等
- 购物消费：日常实物购买：超市、便利店、网购、服饰美妆、数码产品等
- 交通出行：公共交通、打车、加油、停车、机票火车票等
- 居住相关：房租、水电煤、物业费、宽带网络、维修服务
- 医疗健康：门诊药费、体检、保健品、医疗保险自付部分
- 教育文娱：书籍课程、培训学费、电影演出、游戏充值、旅游门票
- 人情往来：礼物送礼、红包随礼、捐款捐赠、朋友分摊
- 收入类：工资、兼职、投资回报、退款、他人转账
- 其他支出：无法明确归类或低频特殊支出（如罚款、手续费）

**输出格式**：
```json
{{
  "reasoning": "请根据票据文本内容，判断票据的专业分类和用户视角分类，并给出分类理由。",
  "professional_category": "发票/行程单/小票/收据",（只能选择一个）
  "user_category": "餐饮消费/购物消费/交通出行/居住相关/医疗健康/教育文娱/人情往来/收入类/其他支出",（只能选择一个）
 
}}
```
**注意事项**：
- 每种分类只能选择一个，不能同时选择。
- 需要注意交通的发票与行程单的区分。

请进行分类判断。
"""

DOCUMENT_STRUCTURE_PROMPT_TEMPLATE = """你是一个票据信息结构化助手。请根据票据内容，结构化票据信息。

**票据内容**：
{document_content}

**结构化规则**
{structure_rules}

**输出格式**：
```json
{{
  "structured_data": {{
    "字段1": "值1",
    "字段2": "值2",
    "字段3": "值3",
  }},
}}
```

**注意事项**：
- 结构化数据需要包含所有关键字段信息，字段名和值需要符合结构化规则。
- 结构化数据需要符合JSON格式。
- 金额字段需要标准化为浮点数，不要单位。
- 时间字段需要标准化为日期格式，格式为YYYY/MM/DD hh:mm:ss,仅保留出现的字段信息，若可以省略具体时分秒。

请进行结构化。
"""

def build_document_structure_prompt(document_content: str, structure_rules: str) -> str:
    """构建票据信息结构化提示词
    
    Args:
        document_content: 票据内容
        
    Returns:
        完整的提示词
    """
    return DOCUMENT_STRUCTURE_PROMPT_TEMPLATE.format(document_content=document_content, structure_rules=structure_rules)

def build_classification_prompt(
    user_profile: str,
    document_content: str,
    user_category: str,
    user_tags: Dict[str, List[str]],
    classification_rules: Optional[str] = None,
    user_intent: Optional[str] = None
) -> str:
    """构建分类提示词
    
    Args:
        user_profile: 用户画像描述
        document_content: 票据内容
        user_tags: 用户视角标签
        classification_rules: 历史分类规则
        user_intent: 用户意图
    Returns:
        完整的提示词    
    """
    # 格式化用户标签
    if user_tags:
        tag_lines = []
        for category, tags in user_tags.items():
            tag_text = ", ".join(tags) if tags else "暂无标签"
            tag_lines.append(f"- {category}: {tag_text}")
        user_tags_text = "\n".join(tag_lines)
    else:
        user_tags_text = "暂无标签"

    return CLASSIFICATION_PROMPT_TEMPLATE.format(
        user_profile=user_profile or "无用户画像信息",
        classification_rules=classification_rules or "暂无历史规则",
        document_content=document_content,
        user_tags=user_tags_text,
        user_category=user_category or "其他支出",
        user_intent=user_intent or "无"
    )


# ==================== 意图识别提示词 ====================

INTENT_RECOGNITION_PROMPT_TEMPLATE = """你是一个用户意图识别助手。请分析用户提供的文本，识别是否有明确的分类指定或其他重要信息。

**用户文本**：
{user_text}

**任务**：
1. 判断用户是否明确指定了票据分类或标签
2. 提取票据相关的背景信息、备注说明
3. 识别特殊要求（如报销、紧急等）

**输出格式**：
```json
{{
  "analysis": "分析结果",
  "has_explicit_classification": true/false,
  "information_extraction": "用户文本中的重要信息，以markdown格式返回",
}}
```
**注意事项**：
 - information_extraction表示用户意图提取结果，可以是直接的分类指令，也可以是背景信息，或想添加的备注，以markdown格式返回
请分析用户意图。
"""


def build_intent_recognition_prompt(user_text: str) -> str:
    """构建意图识别提示词
    
    Args:
        user_text: 用户输入的文本
        
    Returns:
        完整的提示词
    """
    return INTENT_RECOGNITION_PROMPT_TEMPLATE.format(user_text=user_text)


# ==================== 单案例反馈分析提示词 ====================

FEEDBACK_ANALYSIS_PROMPT_TEMPLATE = """你是一个票据分类错误分析助手。请分析用户对票据分类的修改，找出原始分类错误的原因。

**票据文本内容（OCR识别结果）**：
{ocr_text}

**原始分类理由**：
- 专业分类理由：{document_type_reasoning}
- 标签分类理由：{tag_classification_reasoning}

**用户修改信息**：
- 原用户分类：{original_user_category}
- 原标签：{original_tags}
- 新用户分类：{new_user_category}
- 新标签：{new_tags}

**任务**：
1. 分析原始分类为什么不符合用户期望
2. 识别导致错误分类的关键因素（文本特征、上下文信息等）

**输出格式**：
```json
{{
  "feedback": "反馈分析文本，说明错误分类的原因"
}}
```

**注意事项**：
- 反馈要具体、可操作，指出错误的关键点
- 关注用户分类倾向，而非单纯描述修改
- 反馈应该有助于后续生成分类规则

请分析并生成反馈。
"""


def build_feedback_analysis_prompt(
    ocr_text: str,
    document_type_reasoning: str,
    tag_classification_reasoning: str,
    original_user_category: Optional[str],
    original_tags: List[str],
    new_user_category: Optional[str],
    new_tags: List[str]
) -> str:
    """构建单案例反馈分析提示词
    
    Args:
        ocr_text: 票据OCR文本
        document_type_reasoning: 专业分类理由
        tag_classification_reasoning: 标签分类理由
        original_user_category: 原用户分类
        original_tags: 原标签列表
        new_user_category: 新用户分类
        new_tags: 新标签列表
        
    Returns:
        完整的提示词
    """
    return FEEDBACK_ANALYSIS_PROMPT_TEMPLATE.format(
        ocr_text=ocr_text or "无OCR文本",
        document_type_reasoning=document_type_reasoning or "无专业分类理由",
        tag_classification_reasoning=tag_classification_reasoning or "无标签分类理由",
        original_user_category=original_user_category or "未分类",
        original_tags=", ".join(original_tags) if original_tags else "无标签",
        new_user_category=new_user_category or "未分类",
        new_tags=", ".join(new_tags) if new_tags else "无标签"
    )


# ==================== 规则生成提示词 ====================



INCREMENTAL_RULE_GENERATION_PROMPT_TEMPLATE = """你是一个行为模式分析助手。请基于一批案例的反馈分析，增量更新分类规则。

**现有分类规则**（共{rule_count}条）：
{existing_rules}

**案例反馈分析**：
{feedback_analyses}

**任务**：
1. 分析这批案例中体现的用户分类倾向
2. 根据现有规则和新的反馈，选择合适的操作来更新规则库


**可执行的操作类型**：
- **add**：添加新规则（当发现新模式且与现有规则不重复时）
- **delete**：删除规则（当规则不再适用或置信度过低时）
- **modify**：修改规则（当需要调整规则的触发条件或目标分类时）
- **merge**：融合规则（当多条规则可以合并为一条更通用的规则时）

**输出格式**：
```json
{{
 "think":"分析思考你将选择的操作，并给出选择理由，生成的规则应该通用而不是为了当前的特例。",
  "operations": [
    {{
      "type": "add",
      "rule": {{
        "rule_text": "规则描述",
      }}
    }},
    {{
      "type": "delete",
      "rule_id": "rule_1"
    }},
    {{
      "type": "modify",
      "rule_id": "rule_2",
      "rule": {{
        "rule_text": "修改后的规则描述",
      }}
    }},
    {{
      "type": "merge",
      "merge_rule_ids": ["rule_3", "rule_4"],
      "rule": {{
        "rule_text": "融合后的规则描述（合并rule_3和rule_4的内容）",
      }}
    }}
  ],
}}
```

**注意事项**：
- 生成的规则应该通用而不是为了当前的特例，你应该谨慎的采取操作。
- 如果没有明显模式，可以返回空操作列表
- 并不需要为每个案例都生成操作，你需要根据案例的相似性来决定是否生成操作。
- {reduction_hint}

请分析并执行规则操作。
"""


def build_rule_generation_prompt(
    feedback_history: Optional[List[Dict]] = None,
    feedback_analyses: Optional[List[str]] = None,
    existing_rules: Optional[Any] = None,
    needs_reduction: bool = False
) -> str:
    """构建规则生成提示词（支持增量生成）
    
    Args:
        feedback_history: 反馈历史列表
        feedback_analyses: 反馈分析文本列表（新版增量方式）
        existing_rules: 现有规则（列表或字符串）
        needs_reduction: 是否需要减少规则数量
        
    Returns:
        完整的提示词
    """
    # 如果使用反馈分析（增量方式）
    if feedback_analyses is not None:
        # 格式化反馈分析
        analyses_text = ""
        if feedback_history and feedback_analyses:
            for i, (case, analysis) in enumerate(zip(feedback_history, feedback_analyses), 1):
                analyses_text += f"\n案例 {i}：\n{case}\n{analysis}\n"
        
        # 格式化现有规则（现在 existing_rules 是字符串列表）
        if isinstance(existing_rules, list):
            rule_count = len(existing_rules)
            if rule_count > 0:
                existing_rules_text = "现有规则列表：\n"
                for i, rule_text in enumerate(existing_rules, 1):
                    if rule_text:  # 只显示非空规则
                        existing_rules_text += f"{i}. [ID: rule_{i-1}] {rule_text}\n"
            else:
                existing_rules_text = "暂无现有规则"
                rule_count = 0
        else:
            existing_rules_text = existing_rules or "暂无现有规则"
            rule_count = 0
        
        # 生成减少规则数量的提示
        if needs_reduction:
            reduction_hint = "⚠️ 重要：当前规则数量已达到或超过20条，请优先使用delete或merge操作来减少规则数量，避免超过限制。"
        else:
            reduction_hint = "规则数量未达上限，可以正常添加新规则。"
        
        return INCREMENTAL_RULE_GENERATION_PROMPT_TEMPLATE.format(
            rule_count=rule_count,
            existing_rules=existing_rules_text,
            feedback_analyses=analyses_text or "暂无反馈分析",
            reduction_hint=reduction_hint
        )
    
    # 如果没有使用反馈分析，返回空字符串（这种情况不应该发生）
    return ""


# ==================== 画像优化提示词 ====================

PROFILE_OPTIMIZATION_PROMPT_TEMPLATE = """你是一个用户画像分析助手。请根据用户的历史票据数据和文本信息，优化用户画像。

**当前用户画像**：
{current_profile}

**票据统计信息**：
{document_statistics}

**用户文本信息**（从历史上传文本中提取）：
{text_insights}

**任务**：
1. 分析用户的消费习惯和偏好
2. 识别用户的职业、生活状态等背景信息
3. 更新或补充用户画像
4. 保持画像简洁、准确

**输出格式**：
```json
{{
  "updated_profile": [
    "职业：软件工程师",
    "收入水平：中高",
    "消费习惯：注重性价比，经常出差",
    "主要支出：交通（35%）、餐饮（25%）、住房（20%）",
    "出差频率：每月2-3次",
    "偏好交通方式：高铁"
  ],
  "changes": [
    "新增：出差频率信息",
    "更新：主要支出比例"
  ],
  "confidence": 0.88
}}
```

**注意事项**：
- 保留有价值的旧画像信息
- 基于数据推断，不要过度猜测
- 画像条目要具体、可操作
- 每条画像不超过30字

请优化用户画像。
"""


def build_profile_optimization_prompt(
    current_profile: List[str],
    document_statistics: Dict,
    text_insights: Optional[str] = None
) -> str:
    """构建画像优化提示词
    
    Args:
        current_profile: 当前用户画像列表
        document_statistics: 票据统计信息
        text_insights: 从文本中提取的洞察
        
    Returns:
        完整的提示词
    """
    # 格式化当前画像
    profile_text = "\n".join(f"- {item}" for item in current_profile) if current_profile else "无"
    
    # 格式化统计信息
    stats_text = ""
    if document_statistics:
        total = document_statistics.get('total_documents', 0)
        stats_text += f"总票据数：{total}\n"
        
        if 'category_distribution' in document_statistics:
            stats_text += "\n类别分布：\n"
            for cat, count in document_statistics['category_distribution'].items():
                percentage = (count / total * 100) if total > 0 else 0
                stats_text += f"  - {cat}: {count}张 ({percentage:.1f}%)\n"
        
        if 'average_amount' in document_statistics:
            stats_text += f"\n平均金额：¥{document_statistics['average_amount']:.2f}"
        
        if 'frequent_tags' in document_statistics:
            stats_text += f"\n常用标签：{', '.join(document_statistics['frequent_tags'])}"
    
    return PROFILE_OPTIMIZATION_PROMPT_TEMPLATE.format(
        current_profile=profile_text,
        document_statistics=stats_text or "暂无统计数据",
        text_insights=text_insights or "暂无文本洞察"
    )


# ==================== 画像优化操作提示词 ====================

PROFILE_OPTIMIZATION_OPERATIONS_PROMPT_TEMPLATE = """你是一个用户画像优化助手。请基于整体统计信息和一批票据的详细信息，生成用户画像优化操作。

**当前用户画像**（共{profile_count}条）：
{current_profile}

**整体统计信息**（画像更新后的所有票据）：
{overall_statistics}

**本批票据信息**（共{batch_count}条）：
{batch_documents}

**任务**：
1. 分析这批票据体现的用户特征和消费习惯
2. 结合整体统计信息，判断是否需要更新用户画像
3. 选择合适的操作来优化画像

**可执行的操作类型**：
- **add**：添加新画像条目（当发现新的用户特征且与现有画像不重复时）
- **delete**：删除画像条目（当画像不再适用或置信度过低时）
- **merge**：融合画像条目（当多条画像可以合并为一条更通用的描述时）

**输出格式**：
```json
{{
  "think": "分析思考你将选择的操作，并给出选择理由。生成的画像应该简洁、通用而不是为了当前的特例。",
  "operations": [
    {{
      "type": "add",
      "profile_item": {{
        "text": "新画像描述（不超过30字）"
      }}
    }},
    {{
      "type": "delete",
      "profile_id": "profile_0"
    }},
    {{
      "type": "merge",
      "merge_profile_ids": ["profile_1", "profile_2"],
      "profile_item": {{
        "text": "融合后的画像描述（不超过30字）"
      }}
    }}
  ]
}}
```

**注意事项**：
- 生成的画像应该**简洁、通用、可操作**，每条不超过30字
- 基于数据推断，不要过度猜测或过于特殊化
- 操作要谨慎，不是每批票据都需要生成操作
- 如果没有明显需要更新的地方，可以返回空操作列表
- 画像条目使用索引标识（profile_0, profile_1, ...）
- 优先考虑merge操作来精简画像，避免画像条目过多

请分析并生成画像优化操作。
"""


def build_profile_optimization_operations_prompt(
    current_profile: List[str],
    overall_statistics: Dict[str, Any],
    batch_documents: List[Dict[str, Any]]
) -> str:
    """构建画像优化操作提示词
    
    Args:
        current_profile: 当前用户画像列表
        overall_statistics: 整体统计信息
        batch_documents: 本批票据列表
        
    Returns:
        完整的提示词
    """
    # 格式化当前画像（带索引）
    if current_profile:
        profile_text = "当前画像列表：\n"
        for i, item in enumerate(current_profile):
            profile_text += f"{i}. [ID: profile_{i}] {item}\n"
    else:
        profile_text = "暂无用户画像"
    
    # 格式化整体统计信息
    stats_text = ""
    if overall_statistics:
        total = overall_statistics.get('total_documents', 0)
        stats_text += f"总票据数：{total}\n"
        
        # 支出类别分布
        if 'expense_distribution' in overall_statistics:
            stats_text += "\n支出类别分布：\n"
            for cat, data in overall_statistics['expense_distribution'].items():
                percentage = data.get('percentage', 0)
                count = data.get('count', 0)
                stats_text += f"  - {cat}: {count}张 ({percentage:.1f}%)\n"
        
        # 收入类别
        if 'income_distribution' in overall_statistics:
            stats_text += "\n收入类别分布：\n"
            for cat, data in overall_statistics['income_distribution'].items():
                percentage = data.get('percentage', 0)
                count = data.get('count', 0)
                stats_text += f"  - {cat}: {count}张 ({percentage:.1f}%)\n"
        
        # 月均支出和收入
        if 'monthly_average' in overall_statistics:
            avg_data = overall_statistics['monthly_average']
            stats_text += f"\n月均总支出：¥{avg_data.get('expense', 0):.2f}\n"
            stats_text += f"月均总收入：¥{avg_data.get('income', 0):.2f}\n"
        
        # 单笔金额分布
        if 'amount_distribution' in overall_statistics:
            stats_text += "\n单笔金额分布：\n"
            for range_key, count in overall_statistics['amount_distribution'].items():
                stats_text += f"  - {range_key}: {count}张\n"
        
        # 高频标签
        if 'frequent_tags' in overall_statistics:
            tags = overall_statistics['frequent_tags'][:10]  # 取前10个
            stats_text += f"\n高频标签（前10）：{', '.join(tags)}\n"
    
    # 格式化本批票据
    batch_text = ""
    if batch_documents:
        for i, doc in enumerate(batch_documents, 1):
            batch_text += f"\n票据 {i}：\n"
            batch_text += f"  - OCR文本内容：{doc.get('ocr_text', '未知')}\n"
            batch_text += f"  - 类型：{doc.get('document_type', '未知')}\n"
            batch_text += f"  - 分类：{doc.get('user_category', '未知')}\n"
            batch_text += f"  - 标签：{', '.join(doc.get('tags', [])) if doc.get('tags') else '无'}\n"

    
    return PROFILE_OPTIMIZATION_OPERATIONS_PROMPT_TEMPLATE.format(
        profile_count=len(current_profile),
        current_profile=profile_text,
        overall_statistics=stats_text or "暂无统计数据",
        batch_count=len(batch_documents),
        batch_documents=batch_text or "暂无票据信息"
    )


__all__ = [
    "DOCUMENT_CHECK_PROMPT",
    "DOCUMENT_RECOGNITION_PROMPT",
    "DOCUMENT_CLASSIFICATION_PROMPT",
    "CLASSIFICATION_PROMPT_TEMPLATE",
    "INTENT_RECOGNITION_PROMPT_TEMPLATE",
    "FEEDBACK_ANALYSIS_PROMPT_TEMPLATE",
    "INCREMENTAL_RULE_GENERATION_PROMPT_TEMPLATE",
    "PROFILE_OPTIMIZATION_PROMPT_TEMPLATE",
    "PROFILE_OPTIMIZATION_OPERATIONS_PROMPT_TEMPLATE",
    "build_document_check_prompt",
    "build_document_recognition_prompt",
    "build_document_classification_prompt",
    "build_classification_prompt",
    "build_intent_recognition_prompt",
    "build_feedback_analysis_prompt",
    "build_rule_generation_prompt",
    "build_profile_optimization_prompt",
    "build_profile_optimization_operations_prompt",
]

