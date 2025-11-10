# 数据模型目录结构说明

## 📁 目录结构

```
src/models/
├── __init__.py              # 主入口，导出所有公共接口
├── base.py                  # 基础模型（BaseDocument、枚举类型）
├── document/                # 📄 票据相关模型
│   ├── __init__.py
│   ├── invoice.py          # 发票（增值税普通发票/电子发票）
│   ├── itinerary.py        # 行程单（航空/铁路/巴士等交通凭证）
│   ├── receipt.py          # 收据（非税收入、押金、私人交易）
│   └── receipt_slip.py     # 小票（超市/便利店/餐厅消费小票）
├── user/                    # 👤 用户相关模型
│   ├── __init__.py
│   ├── profile.py          # 用户画像和用户类
│   ├── categories.py       # 用户分类模板（9大类+动态子标签）
│   └── learning.py         # 学习历史（分类反馈、行为分析）
└── serialization.py         # 🔄 序列化工具（JSON编解码）
```

## 📖 模块说明

### 1. base.py - 基础模型

**包含内容：**
- `DocumentType`: 专业视角分类枚举（发票、行程单、小票、收据）
- `UserCategory`: 用户视角9大类枚举
- `DocumentStatus`: 票据状态枚举
- `BaseDocument`: 所有票据的基础数据类

**使用示例：**
```python
from src.models import BaseDocument, DocumentType, UserCategory

doc = BaseDocument(
    document_id="doc_001",
    user_id="user_001",
    document_type=DocumentType.INVOICE,
    user_category=UserCategory.SHOPPING,
    tags=["日常生活用品"]
)
```

### 2. document/ - 票据模型

#### invoice.py - 发票
- `Invoice`: 发票主体数据
- `InvoiceItem`: 发票明细项

**字段包含：** 发票代码、号码、买卖方信息、金额明细、税额等

#### itinerary.py - 行程单
- `Itinerary`: 交通凭证数据

**字段包含：** 交通类型、乘客信息、行程信息、座位、费用明细等

#### receipt_slip.py - 小票
- `ReceiptSlip`: 小票主体数据
- `ReceiptSlipItem`: 商品明细项

**字段包含：** 商家信息、交易信息、商品明细等

#### receipt.py - 收据
- `Receipt`: 收据主体数据
- `TransferInfo`: 转账信息

**字段包含：** 收付款方、金额、事由、转账信息等

**使用示例：**
```python
from src.models import Invoice, Itinerary

# 创建发票
invoice = Invoice(
    invoice_number="00001234",
    total_amount_including_tax=200.0
)

# 创建行程单
itinerary = Itinerary(
    transport_type="高铁",
    departure_station="北京南",
    arrival_station="上海虹桥"
)
```

### 3. user/ - 用户模型

#### profile.py - 用户画像
- `UserProfile`: 用户画像（灵活的文本列表）
- `User`: 完整的用户数据模型
- `create_new_user()`: 创建新用户的工厂函数

**特点：**
- 用户画像采用文本列表，不限制维度
- 集成分类模板和学习历史
- 支持智能标签推荐

#### categories.py - 分类模板
- `UserCategoryTemplate`: 用户自定义分类模板
- `DEFAULT_CATEGORY_TAGS`: 默认标签映射
- `create_default_template()`: 创建默认模板

**9大类标签：**
1. 餐饮消费：日常用餐、社交聚餐、商务招待、节日庆典
2. 购物消费：日常生活、服饰鞋帽、数码家电、家居个护
3. 交通出行：日常通勤、差旅商务、长途旅行、车辆维护
4. 居住相关：住房固定、生活能源、网络通讯、房屋维修
5. 医疗健康：诊疗医药、健康保健、医疗保险、紧急医疗
6. 教育文娱：学习教育、文化娱乐、运动休闲、兴趣爱好
7. 人情往来：礼金礼物、请客孝敬、社交关系、公益捐赠
8. 收入类：固定工作、额外劳务、投资理财、资金返还
9. 其他支出：通讯服务、金融服务、个人生活、特殊意外

#### learning.py - 学习历史
- `ClassificationFeedback`: 单次分类修改记录
- `LearningHistory`: 学习历史管理

**功能：**
- 记录用户分类修改行为
- 统计标签使用频率
- 分析分类修改模式
- 生成学习摘要

**使用示例：**
```python
from src.models import create_new_user, UserCategory

# 创建用户
user = create_new_user(
    user_id="user_001",
    profile_items=["职业：工程师", "消费习惯：理性"]
)

# 记录分类修改
user.record_classification_change(
    document_id="doc_001",
    original_category="行程单",
    original_user_category="交通出行",
    original_tags=["日常通勤出行"],
    new_category="行程单",
    new_user_category="交通出行",
    new_tags=["差旅商务出行"]
)

# 获取推荐标签
recommended = user.get_recommended_tags(UserCategory.TRANSPORTATION)
```

### 4. serialization.py - 序列化工具

**功能：**
- JSON编码/解码
- 文件保存/加载
- 数据验证

**主要函数：**
- `to_dict()`: dataclass → 字典
- `to_json()`: 对象 → JSON字符串
- `save_to_file()`: 保存到文件
- `from_dict()`: 字典 → dataclass
- `from_json()`: JSON字符串 → 对象
- `load_from_file()`: 从文件加载

**使用示例：**
```python
from src.models import Invoice
from src.models.serialization import save_to_file, load_from_file

# 保存
invoice = Invoice(invoice_number="001")
save_to_file(invoice, "data/invoice_001.json")

# 加载
loaded = load_from_file("data/invoice_001.json", Invoice)
```

## 🎯 设计优势

1. **职责清晰**
   - 票据模型独立：每种票据类型单独文件
   - 用户模块独立：用户相关功能集中管理
   - 基础类分离：通用枚举和基类独立

2. **易于维护**
   - 文件小而专注：每个文件只负责一种数据类型
   - 模块化设计：修改某个模块不影响其他模块
   - 清晰的依赖关系：base → document/user → serialization

3. **便于扩展**
   - 新增票据类型：在 `document/` 下添加新文件
   - 新增用户功能：在 `user/` 下扩展
   - 统一入口：所有导出通过 `__init__.py` 管理

4. **开发友好**
   - 目录结构直观：一眼看出模块组织
   - 文件命名清晰：文件名即功能
   - 易于导航：IDE 中快速定位代码

## 📦 导入方式

所有公共接口都可以从 `src.models` 直接导入：

```python
# 基础模型
from src.models import BaseDocument, DocumentType, UserCategory

# 票据模型
from src.models import Invoice, Itinerary, ReceiptSlip, Receipt

# 用户模型
from src.models import User, UserProfile, create_new_user

# 分类和学习
from src.models import UserCategoryTemplate, LearningHistory

# 序列化
from src.models.serialization import save_to_file, load_from_file
```

## 🔗 相关文档

- 完整使用示例：`examples/user_workflow.py`
- 存储管理：`src/storage/user_storage.py`
- 项目文档：`README.md`

