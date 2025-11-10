# 智能票据/发票管理系统

基于多模态理解的 AI Agent，完成票据的自动分类、入账与用户画像优化。本仓库同时提供后端 API、前端管理页面与 JSON 存储方案，便于在比赛场景中快速迭代。

---

## 功能概览

- 🎯 **自动入账**：图片 + 文本/语音上传 -> 票据识别 -> 分类打标签 -> 待确认入账  
- 🔁 **反馈学习**：用户修改历史分类后自动学习，生成自然语言规则  
- 🧠 **画像优化**：根据票据统计与行为文本持续优化用户画像  
- 📊 **可视化管理**：前端展示分类占比、趋势图与票据列表  
- 🔐 **JSON 账号体系**：无需数据库，使用 `/data/users.json` 存储账号信息，并预置演示账号 `123 / 123`

---

## 项目结构

```
.
├── frontend/                    # React + Vite + Ant Design 前端
├── src/
│   ├── api/                     # FastAPI 路由
│   │   ├── __init__.py
│   │   └── auth.py              # 登录 / 注册 / 当前用户
│   ├── agent/                   # Agent 框架（提示词、工作流等）
│   ├── config.py                # 环境变量加载
│   ├── models/                  # 数据模型（基础类 + 票据 + 用户）
│   ├── multimodal/              # 调用智谱多模态 API 的工具
│   ├── storage/
│   │   ├── auth_storage.py      # JSON 账号存储（含演示账号 123/123）
│   │   └── user_storage.py
│   └── server.py                # FastAPI 入口（uvicorn src.server:app）
└── data/
    └── users.json               # 账号信息（自动生成，明文密码）
```

---

## 后端使用指南

### 1. 环境准备

```bash
pip install fastapi uvicorn aiohttp python-dotenv
```

可根据需要安装 `python-dotenv` 与模型调用所需依赖。若使用智谱 API，请在根目录创建 `.env`：

```bash
ZHIPU_API_KEY=your_api_key_here
GLM_TEXT_MODEL=GLM-4.5-Air
GLM_VISION_MODEL=GLM-4V-Flash
GLM_ASR_MODEL=GLM-ASR
```

### 2. 启动 FastAPI

```bash
uvicorn src.server:app --reload --host 0.0.0.0 --port 8000
```

默认开放以下接口（部分）：

| Method | Path           | 说明               |
|--------|----------------|--------------------|
| POST   | `/api/register`| 注册账号           |
| POST   | `/api/login`   | 登录，返回 token   |
| POST   | `/api/logout`  | 退出登录（可选）    |
| GET    | `/api/me`      | 获取当前用户信息   |
| ...    | `/api/upload`  | 票据上传（Agent）  |
| ...    | `/api/confirm` | 确认票据           |
| ...    | `/api/user_summary` / `/api/documents` | 仪表盘数据 |

> 演示账号在首次启动时自动写入 `/data/users.json`：`用户名 123 / 密码 123`。

---

## 前端使用指南

### 1. 安装依赖

```bash
cd frontend
npm install
```

可在 `frontend/.env` 中设置后端地址（默认为 `/api`）：

```
VITE_API_BASE_URL = http://localhost:8000/api
```

### 2. 启动前端

```bash
npm run dev
```

浏览器访问 `http://localhost:5173` 即可看到页面：

1. **登录页**：支持账号登录/注册；提供「使用演示账号 (123 / 123)」按钮  
2. **自动入账页**：图片上传、语音或文本备注、识别结果预览与确认  
3. **数据概览页**：饼图、折线图、指标卡与票据列表，支持筛选/查看详情  

登录后所有请求自动携带 `Authorization: Bearer <token>`，无需手动配置。

---

## JSON 账号存储说明

- 账号文件：`/data/disk2/zhz/票据管理比赛/data/users.json`  
- 格式示例：

```json
[
  { "username": "123", "password": "123" },
  { "username": "alice", "password": "alice123" }
]
```

- 可直接手工编辑；注册接口也会写入。  
- 默认明文存储，便于比赛快速验证（生产环境请改为哈希）。  

---

## 数据模型与 Agent

- `src/models/base.py`：`BaseDocument` 基础票据字段、`DocumentType`/`UserCategory`枚举  
- `src/models/document/`：发票、行程单、小票、收据等结构化字段定义  
- `src/models/user/`：用户画像、分类模板、学习历史  
- `src/agent/`：提示词模板、核心 `DocumentAgent`、工作流编排、统一 API  

如需扩展票据类型或分类策略，可在对应模块中继承/扩展 dataclass，并更新序列化函数。

---

## 常用命令

```bash
# 后端
uvicorn src.server:app --reload

# 前端
cd frontend
npm run dev

# 构建前端
npm run build
npm run preview
```

---

## 版权

MIT License — 欢迎在比赛场景中直接使用或在此基础上二次开发。若发现问题欢迎提交 Issue / PR。祝比赛顺利！ 🎉

