"""用户分类模板 - 管理用户视角的分类和子标签"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set

from ..base import UserCategory


# 默认的类别到子标签映射（初始模板）
# 设计原则：极简、通用、高频场景优先
DEFAULT_CATEGORY_TAGS: Dict[UserCategory, List[str]] = {
    UserCategory.DINING: [
        "日常用餐消费",      # 工作日三餐、常规饮食
        "社交聚餐支出",      # 朋友/同事聚会、请客
        "商务招待费用",      # 客户会议、工作洽谈相关餐饮
        "节日庆典餐饮"       # 生日宴、节日聚餐等特殊场合
    ],
    UserCategory.SHOPPING: [
        "日常生活用品",      # 食品杂货、清洁用品等必需品
        "服饰鞋帽消费",      # 衣物、鞋类、配饰等个人穿着
        "数码家电采购",      # 手机、电脑、小家电等电子产品
        "家居个护支出"       # 家具、日用品、化妆品等
    ],
    UserCategory.TRANSPORTATION: [
        "日常通勤出行",      # 上下班/学的固定交通方式
        "差旅商务出行",      # 因公出差产生的交通费用
        "长途旅行交通",      # 旅游、探亲等长途交通
        "车辆维护费用"       # 加油、停车、保养、维修
    ],
    UserCategory.HOUSING: [
        "住房固定支出",      # 房租、物业费、管理费
        "生活能源费用",      # 水电燃气、取暖费
        "网络通讯费用",      # 宽带、有线电视、固定电话
        "房屋维修维护"       # 家具维修、装修、清洁服务
    ],
    UserCategory.MEDICAL: [
        "诊疗医药支出",      # 门诊、住院、药品费用
        "健康保健消费",      # 体检、保健品、理疗
        "医疗保险费用",      # 医疗类保险支出
        "紧急医疗支出"       # 突发疾病、急诊相关费用
    ],
    UserCategory.EDUCATION_ENTERTAINMENT: [
        "学习教育投入",      # 培训、课程、书籍、文具
        "文化娱乐消费",      # 电影、演出、游戏、订阅
        "运动休闲活动",      # 健身、旅游、户外活动
        "兴趣爱好支出"       # 个人兴趣相关的持续投入
    ],
    UserCategory.SOCIAL: [
        "礼金礼物支出",      # 红包、礼品、节日礼物
        "请客孝敬费用",      # 请客吃饭、孝敬长辈
        "社交关系维护",      # 人情往来、关系维护支出
        "公益捐赠支出"       # 慈善捐款、公益支持
    ],
    UserCategory.INCOME: [
        "固定工作收入",      # 工资、基本薪资、稳定收入
        "额外劳务收入",      # 奖金、提成、兼职、临时工作
        "投资理财收益",      # 利息、股息、租金、理财收益
        "资金返还收入"       # 退款、押金退还、报销回款
    ],
    UserCategory.OTHER_EXPENSE: [
        "通讯服务费用",      # 手机话费、流量套餐
        "金融服务支出",      # 手续费、利息、金融产品费用
        "个人生活服务",      # 美容美发、宠物、个人护理
        "特殊意外支出"       # 罚款、临时应急、意外花费
    ],
}


@dataclass
class UserCategoryTemplate:
    """用户自定义的分类模板
    
    每个用户可以有自己的分类标签体系，初始化时使用默认模板，
    之后可以动态添加、删除、修改子标签。
    """
    
    user_id: str = ""
    category_tags: Dict[UserCategory, Set[str]] = field(default_factory=dict)
    
    def __post_init__(self) -> None:
        """初始化时，如果没有提供分类标签，则使用默认模板"""
        if not self.category_tags:
            self.category_tags = {
                category: set(tags) 
                for category, tags in DEFAULT_CATEGORY_TAGS.items()
            }
    
    def add_tag(self, category: UserCategory, tag: str) -> bool:
        """为指定类别添加子标签
        
        Args:
            category: 用户类别
            tag: 要添加的标签
            
        Returns:
            True 如果成功添加（标签不存在），False 如果标签已存在
        """
        if category not in self.category_tags:
            self.category_tags[category] = set()
        
        if tag in self.category_tags[category]:
            return False
        
        self.category_tags[category].add(tag)
        return True
    
    def remove_tag(self, category: UserCategory, tag: str) -> bool:
        """从指定类别移除子标签
        
        Args:
            category: 用户类别
            tag: 要移除的标签
            
        Returns:
            True 如果成功移除，False 如果标签不存在
        """
        if category not in self.category_tags:
            return False
        
        if tag not in self.category_tags[category]:
            return False
        
        self.category_tags[category].remove(tag)
        return True
    
    def get_tags(self, category: UserCategory) -> List[str]:
        """获取指定类别的所有子标签（排序后）
        
        Args:
            category: 用户类别
            
        Returns:
            该类别下的所有标签列表（按字母排序）
        """
        if category not in self.category_tags:
            return []
        return sorted(self.category_tags[category])
    
    def has_tag(self, category: UserCategory, tag: str) -> bool:
        """检查指定类别是否包含某个标签
        
        Args:
            category: 用户类别
            tag: 要检查的标签
            
        Returns:
            True 如果标签存在，否则 False
        """
        if category not in self.category_tags:
            return False
        return tag in self.category_tags[category]
    
    def get_all_tags(self) -> Dict[str, List[str]]:
        """获取所有类别的标签映射（用于序列化）
        
        Returns:
            类别名称到标签列表的映射
        """
        return {
            category.value: self.get_tags(category)
            for category in UserCategory
        }
    
    def rename_tag(self, category: UserCategory, old_tag: str, new_tag: str) -> bool:
        """重命名某个标签
        
        Args:
            category: 用户类别
            old_tag: 旧标签名
            new_tag: 新标签名
            
        Returns:
            True 如果成功重命名，False 如果旧标签不存在或新标签已存在
        """
        if category not in self.category_tags:
            return False
        
        if old_tag not in self.category_tags[category]:
            return False
        
        if new_tag in self.category_tags[category]:
            return False
        
        self.category_tags[category].remove(old_tag)
        self.category_tags[category].add(new_tag)
        return True
    
    def reset_to_default(self, category: Optional[UserCategory] = None) -> None:
        """重置为默认模板
        
        Args:
            category: 如果指定，只重置该类别；否则重置所有类别
        """
        if category is not None:
            if category in DEFAULT_CATEGORY_TAGS:
                self.category_tags[category] = set(DEFAULT_CATEGORY_TAGS[category])
        else:
            self.category_tags = {
                cat: set(tags) 
                for cat, tags in DEFAULT_CATEGORY_TAGS.items()
            }


def create_default_template(user_id: str) -> UserCategoryTemplate:
    """为新用户创建默认分类模板
    
    Args:
        user_id: 用户ID
        
    Returns:
        初始化好的用户分类模板
    """
    return UserCategoryTemplate(user_id=user_id)


__all__ = [
    "DEFAULT_CATEGORY_TAGS",
    "UserCategoryTemplate",
    "create_default_template",
]

