"""用户设置API路由 - 管理用户画像和分类标签"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional

from ..models.base import UserCategory
from ..api.auth import get_current_user
from ..storage.user_storage import UserStorage
from ..agent.workflow import FeedbackWorkflow

router = APIRouter(prefix="/api/user", tags=["user_settings"])

# User storage instance
user_storage = UserStorage()

# 子标签最大数量限制
MAX_TAGS_PER_CATEGORY = 7


class ProfileResponse(BaseModel):
    """用户画像响应"""
    profile_items: list[str]
    category_tags: dict[str, list[str]]  # category -> tags


class UpdateProfileRequest(BaseModel):
    """更新用户画像请求"""
    items: list[str]


class AddProfileItemRequest(BaseModel):
    """添加画像条目请求"""
    item: str


class CategoryTagsResponse(BaseModel):
    """分类标签响应"""
    category: str
    tags: list[str]


class AddTagRequest(BaseModel):
    """添加标签请求"""
    tag: str


class MessageResponse(BaseModel):
    """通用消息响应"""
    success: bool
    message: str


class LearningResponse(BaseModel):
    """反馈学习响应"""
    success: bool
    triggered: bool
    rules_count: Optional[int] = None
    rules: Optional[list[str]] = None
    summary: Optional[str] = None
    feedback_count: Optional[int] = None
    error: Optional[str] = None


class ClassificationRulesResponse(BaseModel):
    """分类规则响应"""
    rules: list[str]


class AddRuleRequest(BaseModel):
    """添加规则请求"""
    rule: str


class UpdateRuleRequest(BaseModel):
    """更新规则请求"""
    index: int
    rule: str


@router.get("/profile", response_model=ProfileResponse)
def get_user_profile(current_user: dict = Depends(get_current_user)) -> ProfileResponse:
    """获取用户画像和所有分类标签"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 获取所有分类标签
    category_tags = user.category_template.get_all_tags()
    
    return ProfileResponse(
        profile_items=user.profile.profile_text,
        category_tags=category_tags
    )


@router.put("/profile", response_model=MessageResponse)
def update_user_profile(
    request: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """批量更新用户画像"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    user.update_profile(request.items)
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="用户画像更新成功"
    )


@router.post("/profile/items", response_model=MessageResponse)
def add_profile_item(
    request: AddProfileItemRequest,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """添加用户画像条目"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if not request.item or not request.item.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="画像条目不能为空"
        )
    
    user.profile.add_profile_item(request.item.strip())
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="画像条目添加成功"
    )


@router.delete("/profile/items", response_model=MessageResponse)
def remove_profile_item(
    item: str,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """删除用户画像条目"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    success = user.profile.remove_profile_item(item)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="画像条目不存在"
        )
    
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="画像条目删除成功"
    )


@router.get("/categories/{category}/tags", response_model=CategoryTagsResponse)
def get_category_tags(
    category: str,
    current_user: dict = Depends(get_current_user)
) -> CategoryTagsResponse:
    """获取指定分类的子标签"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证分类是否有效
    try:
        user_category = UserCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的分类: {category}"
        )
    
    tags = user.category_template.get_tags(user_category)
    
    return CategoryTagsResponse(
        category=category,
        tags=tags
    )


@router.post("/categories/{category}/tags", response_model=MessageResponse)
def add_category_tag(
    category: str,
    request: AddTagRequest,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """为分类添加子标签（限制最多7个）"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证分类是否有效
    try:
        user_category = UserCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的分类: {category}"
        )
    
    if not request.tag or not request.tag.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标签不能为空"
        )
    
    tag = request.tag.strip()
    
    # 检查当前标签数量
    current_tags = user.category_template.get_tags(user_category)
    if len(current_tags) >= MAX_TAGS_PER_CATEGORY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"该分类的子标签已达到最大数量限制（{MAX_TAGS_PER_CATEGORY}个）"
        )
    
    # 检查标签是否已存在
    if user.category_template.has_tag(user_category, tag):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="标签已存在"
        )
    
    success = user.category_template.add_tag(user_category, tag)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="添加标签失败"
        )
    
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="标签添加成功"
    )


@router.delete("/categories/{category}/tags", response_model=MessageResponse)
def remove_category_tag(
    category: str,
    tag: str,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """删除分类的子标签"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 验证分类是否有效
    try:
        user_category = UserCategory(category)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的分类: {category}"
        )
    
    success = user.category_template.remove_tag(user_category, tag)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="标签不存在"
        )
    
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="标签删除成功"
    )


@router.post("/trigger_learning", response_model=LearningResponse)
async def trigger_feedback_learning(
    current_user: dict = Depends(get_current_user)
) -> LearningResponse:
    """手动触发反馈学习
    
    基于用户修改历史，生成分类规则。
    """
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    try:
        workflow = FeedbackWorkflow(user, user_storage)
        result = await workflow.execute(max_feedbacks=50, batch_size=10)
        
        return LearningResponse(
            success=result.get('triggered', False),
            triggered=result.get('triggered', False),
            rules_count=result.get('rules_count', 0),
            rules=result.get('rules', []),
            summary=result.get('summary', ''),
            feedback_count=result.get('feedback_count', 0),
            error=result.get('error')
        )
    except Exception as e:
        return LearningResponse(
            success=False,
            triggered=False,
            error=str(e)
    )


@router.get("/classification_rules", response_model=ClassificationRulesResponse)
def get_classification_rules(
    current_user: dict = Depends(get_current_user)
) -> ClassificationRulesResponse:
    """获取分类规则列表"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 获取分类规则（兼容旧格式）
    rules_raw = user.settings.get('classification_rules', [])
    if isinstance(rules_raw, str):
        import json
        try:
            rules_raw = json.loads(rules_raw)
        except json.JSONDecodeError:
            rules_raw = []
    
    # 确保是列表格式
    if not isinstance(rules_raw, list):
        rules_raw = []
    
    # 如果是旧格式（Dict列表），提取 rule_text
    if rules_raw and isinstance(rules_raw[0], dict):
        rules = [rule.get('rule_text', '') for rule in rules_raw if rule.get('rule_text')]
    else:
        rules = [r for r in rules_raw if isinstance(r, str) and r]
    
    return ClassificationRulesResponse(rules=rules)


@router.post("/classification_rules", response_model=MessageResponse)
def add_classification_rule(
    request: AddRuleRequest,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """添加分类规则"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if not request.rule or not request.rule.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="规则不能为空"
        )
    
    # 获取现有规则
    rules_raw = user.settings.get('classification_rules', [])
    if isinstance(rules_raw, str):
        import json
        try:
            rules_raw = json.loads(rules_raw)
        except json.JSONDecodeError:
            rules_raw = []
    
    if not isinstance(rules_raw, list):
        rules_raw = []
    
    # 如果是旧格式，转换为新格式
    if rules_raw and isinstance(rules_raw[0], dict):
        rules = [rule.get('rule_text', '') for rule in rules_raw if rule.get('rule_text')]
    else:
        rules = [r for r in rules_raw if isinstance(r, str) and r]
    
    # 检查规则数量限制（最多20条）
    if len(rules) >= 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="分类规则已达到最大数量限制（20条）"
        )
    
    # 添加新规则
    new_rule = request.rule.strip()
    if new_rule in rules:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="规则已存在"
        )
    
    rules.append(new_rule)
    user.settings['classification_rules'] = rules
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="规则添加成功"
    )


@router.put("/classification_rules", response_model=MessageResponse)
def update_classification_rule(
    request: UpdateRuleRequest,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """修改分类规则"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    if not request.rule or not request.rule.strip():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="规则不能为空"
        )
    
    # 获取现有规则
    rules_raw = user.settings.get('classification_rules', [])
    if isinstance(rules_raw, str):
        import json
        try:
            rules_raw = json.loads(rules_raw)
        except json.JSONDecodeError:
            rules_raw = []
    
    if not isinstance(rules_raw, list):
        rules_raw = []
    
    # 如果是旧格式，转换为新格式
    if rules_raw and isinstance(rules_raw[0], dict):
        rules = [rule.get('rule_text', '') for rule in rules_raw if rule.get('rule_text')]
    else:
        rules = [r for r in rules_raw if isinstance(r, str) and r]
    
    # 检查索引是否有效
    if request.index < 0 or request.index >= len(rules):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="规则索引无效"
        )
    
    # 更新规则
    rules[request.index] = request.rule.strip()
    user.settings['classification_rules'] = rules
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="规则修改成功"
    )


@router.delete("/classification_rules", response_model=MessageResponse)
def remove_classification_rule(
    index: int,
    current_user: dict = Depends(get_current_user)
) -> MessageResponse:
    """删除分类规则"""
    user_id = current_user["user_id"]
    user = user_storage.load_user(user_id)
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="用户不存在"
        )
    
    # 获取现有规则
    rules_raw = user.settings.get('classification_rules', [])
    if isinstance(rules_raw, str):
        import json
        try:
            rules_raw = json.loads(rules_raw)
        except json.JSONDecodeError:
            rules_raw = []
    
    if not isinstance(rules_raw, list):
        rules_raw = []
    
    # 如果是旧格式，转换为新格式
    if rules_raw and isinstance(rules_raw[0], dict):
        rules = [rule.get('rule_text', '') for rule in rules_raw if rule.get('rule_text')]
    else:
        rules = [r for r in rules_raw if isinstance(r, str) and r]
    
    # 检查索引是否有效
    if index < 0 or index >= len(rules):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="规则索引无效"
        )
    
    # 删除规则
    rules.pop(index)
    user.settings['classification_rules'] = rules
    user_storage.save_user(user)
    
    return MessageResponse(
        success=True,
        message="规则删除成功"
    )

