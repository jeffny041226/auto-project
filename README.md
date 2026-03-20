# APP 自动化测试平台

基于自然语言处理的移动应用自动化测试平台。用户通过 Web 端输入测试指令，系统进行意图理解、脚本生成、Maestro 执行、视觉校验、智能纠错，最终生成测试报告。

## 功能特性

- **自然语言指令** - 用户输入自然语言测试指令，如"打开微信并登录"
- **意图理解** - LLM 驱动的指令解析与意图分类
- **脚本生成** - 自动生成 Maestro YAML 测试脚本
- **向量匹配** - 基于 Embedding 的脚本复用（相似度 ≥ 0.85）
- **设备管理** - 支持多设备池化管理
- **执行调度** - 任务调度与实时状态推送
- **视觉校验** - 截图分析与视觉对比
- **智能纠错** - 5 类错误自动修复策略
- **报告生成** - HTML/PDF 测试报告导出

## 技术栈

| 层级 | 技术 |
|------|------|
| 前端 | Vue 3 + TypeScript + Element Plus + Pinia |
| 后端 | FastAPI + Python 3.11 |
| 数据库 | MySQL 8.0 + Redis 7 |
| 对象存储 | MinIO (S3 兼容) |
| 任务队列 | Celery + Redis |
| 测试框架 | Maestro |
| LLM | MiniMax2.7 / OpenAI / Claude (可切换) |

## 目录结构

```
auto-project/
├── backend/                    # Python/FastAPI 后端
│   ├── app/
│   │   ├── api/v1/           # API 路由 (auth, scripts, tasks, devices, reports)
│   │   ├── core/             # 核心业务
│   │   │   ├── intention/     # 意图理解
│   │   │   ├── script/        # 脚本管理
│   │   │   ├── executor/      # 执行调度
│   │   │   ├── vision/        # 视觉校验
│   │   │   ├── self_healing/  # 智能纠错
│   │   │   └── report/        # 报告生成
│   │   ├── llm/               # LLM 抽象层
│   │   │   └── providers/     # Provider 实现 (Mock/MiniMax/OpenAI/Claude)
│   │   ├── models/            # SQLAlchemy 模型
│   │   ├── schemas/           # Pydantic schemas
│   │   ├── services/          # 业务服务层
│   │   └── tasks/             # Celery 异步任务
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                  # Vue 3 前端
│   ├── src/
│   │   ├── api/              # API 封装
│   │   ├── components/        # 公共组件
│   │   ├── pages/             # 页面组件
│   │   │   ├── Login.vue
│   │   │   ├── Dashboard.vue
│   │   │   ├── InstructionInput.vue
│   │   │   ├── ScriptManagement.vue
│   │   │   ├── TaskList.vue
│   │   │   ├── TaskDetail.vue
│   │   │   ├── DeviceManagement.vue
│   │   │   └── ReportView.vue
│   │   ├── stores/            # Pinia 状态管理
│   │   └── router/            # Vue Router 配置
│   ├── package.json
│   └── Dockerfile
│
├── docker/                    # Docker 配置
│   ├── docker-compose.yml     # 容器编排
│   ├── mysql/init.sql         # 数据库初始化
│   └── nginx/nginx.conf       # Nginx 配置
│
└── config/backend/             # 配置文件
    ├── llm.yaml              # LLM 配置
    └── settings.yaml          # 应用配置
```

## 快速开始

### 1. 启动基础设施

```bash
cd /Users/jeffny/sources/4.project/claude_demo1/auto-project
docker-compose -f docker/docker-compose.yml up -d
```

验证服务状态：
```bash
docker-compose -f docker/docker-compose.yml ps
```

### 2. 配置后端

```bash
cd backend

# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入你的 API Key
vim .env
```

`.env` 文件内容：
```bash
# MiniMax API (当前使用)
MINIMAX_API_KEY=你的MiniMax API Key
MINIMAX_GROUP_ID=你的Group ID

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=autotest
DB_PASSWORD=autotest123
DB_NAME=auto_test

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

### 3. 安装后端依赖

```bash
cd backend
pip install -r requirements.txt
```

### 4. 启动后端

```bash
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

后端启动后：
- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health

### 5. 安装前端依赖并启动

```bash
cd frontend
npm install
npm run dev
```

前端启动后访问：http://localhost:3000

### 6. (可选) 安装 Maestro

如需真机测试，安装 Maestro：

```bash
curl -Ls "https://get.maestro.mobile.dev" | bash
```

验证安装：
```bash
maestro --version
```

## 使用流程

### 1. 注册/登录

访问 http://localhost:3000/login

默认可以注册新用户。

### 2. 输入测试指令

进入 **Instruction Input** 页面，输入自然语言指令：

```
打开微信并使用 test@example.com 登录
```

系统会自动：
1. 解析指令意图
2. 匹配或生成测试脚本
3. 分配设备执行
4. 实时显示执行进度

### 3. 查看任务状态

进入 **Tasks** 页面，查看所有任务：
- 待处理 (pending)
- 执行中 (running)
- 已完成 (completed)
- 失败 (failed)

### 4. 查看报告

任务完成后，进入 **Reports** 页面查看/下载测试报告。

## API 文档

### 认证接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/v1/auth/register | 注册用户 |
| POST | /api/v1/auth/login | 登录获取 Token |
| POST | /api/v1/auth/refresh | 刷新 Token |

### 脚本接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/scripts | 列表脚本 |
| POST | /api/v1/scripts | 创建脚本 |
| GET | /api/v1/scripts/{script_id} | 获取脚本详情 |
| PUT | /api/v1/scripts/{script_id} | 更新脚本 |
| DELETE | /api/v1/scripts/{script_id} | 删除脚本 |

### 任务接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/tasks | 列表任务 |
| POST | /api/v1/tasks | 创建任务 |
| GET | /api/v1/tasks/{task_id} | 获取任务详情 |
| PATCH | /api/v1/tasks/{task_id} | 更新任务状态 |

### 设备接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/devices | 列表设备 |
| POST | /api/v1/devices | 注册设备 |
| GET | /api/v1/devices/{device_id} | 获取设备详情 |
| PATCH | /api/v1/devices/{device_id} | 更新设备 |

### 报告接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/v1/reports/{report_id} | 获取报告 |
| GET | /api/v1/reports/{report_id}/download | 下载 PDF |

## LLM 配置

### 切换 LLM Provider

编辑 `config/backend/llm.yaml`：

```yaml
default_provider: minimax  # 可选: mock, minimax, openai, anthropic
```

### Provider 配置

#### MiniMax (当前默认)
```yaml
minimax:
  enabled: true
  type: minimax
  api_key: ${MINIMAX_API_KEY}
  group_id: ${MINIMAX_GROUP_ID}
  api_base: https://api.minimax.chat/v
  models:
    primary: MiniMax2.7
    embedding: emb通用
```

#### OpenAI
```yaml
openai:
  enabled: false
  type: openai
  api_key: ${OPENAI_API_KEY}
  models:
    primary: gpt-4o
    embedding: text-embedding-3-small
```

#### Claude
```yaml
anthropic:
  enabled: false
  type: anthropic
  api_key: ${ANTHROPIC_API_KEY}
  models:
    primary: claude-3-5-sonnet-20241022
```

#### Mock (开发用)
```yaml
mock:
  enabled: true
  type: mock
  models:
    primary: mock-gpt-4
    embedding: mock-embedding
```

## 核心模块说明

### 意图理解 (Intention)

`InstructionParser` 负责：
- 指令清洗与标准化
- 敏感信息脱敏
- 应用名称提取

`IntentClassifier` 负责：
- LLM 驱动的意图分类
- 实体提取
- 支持的意图类型：
  - `app_open` - 打开应用
  - `login` - 登录
  - `logout` - 登出
  - `tap` - 点击
  - `input` - 输入
  - `swipe` - 滑动
  - `assert` - 断言
  - `scroll` - 滚动
  - `capture` - 截图

### 脚本管理 (Script)

- `ScriptManager` - CRUD 操作
- `ScriptMatcher` - Embedding 向量匹配（余弦相似度 ≥ 0.85）
- `ScriptGenerator` - LLM 生成伪代码
- `MaestroTemplate` - Jinja2 模板生成 Maestro YAML
- `ScriptValidator` - 脚本预校验

### 执行调度 (Executor)

- `DevicePool` - 设备分配与回收
- `MaestroDriver` - Maestro 驱动封装
- `TaskScheduler` - 任务调度器

### 视觉校验 (Vision)

- `VisionAnalyzer` - 截图分析与元素识别
- `ScreenshotComparator` - 页面状态对比
- `AccessibilityTreeFallback` - Accessibility Tree 降级方案
- `ScreenshotRedactor` - 敏感信息脱敏

### 智能纠错 (Self-Healing)

`SelfHealingDetector` 支持 5 类错误修复：

| 错误类型 | 修复策略 |
|---------|---------|
| `element_not_found` | 尝试替代选择器 |
| `page_jump` | 添加导航返回 |
| `popup` | 添加弹窗关闭 |
| `timeout` | 延长等待时间 |
| `input_fail` | 先清空再输入 |

### 报告生成 (Report)

- `ReportGenerator` - 生成报告数据结构
- `ReportExporter` - 导出 HTML/PDF

## 数据库表

| 表名 | 说明 |
|------|------|
| `users` | 用户表 |
| `scripts` | 脚本表 (含 instruction_embedding 向量) |
| `tasks` | 任务表 |
| `task_steps` | 任务步骤表 |
| `devices` | 设备表 |

## WebSocket 实时通知

连接：`ws://localhost:8000/ws?token=<jwt_token>`

消息类型：
```json
{ "type": "task_update", "task_id": "...", "data": {...} }
{ "type": "task_completed", "task_id": "...", "result": {...} }
```

## 开发指南

### 添加新的 LLM Provider

1. 创建 `backend/app/llm/providers/<provider>.py`：
```python
from app.llm.base import BaseLLMProvider, LLMResponse

class MyProvider(BaseLLMProvider):
    async def chat(self, messages, **kwargs) -> LLMResponse:
        # 实现 chat 接口
        pass

    async def embed(self, text) -> EmbeddingResponse:
        # 实现 embed 接口
        pass

    async def health_check(self) -> bool:
        # 健康检查
        pass
```

2. 在 `factory.py` 注册：
```python
_providers["myprovider"] = MyProvider
```

3. 在 `llm.yaml` 添加配置

### 添加新的 Self-Healing 策略

1. 创建 `backend/app/core/self_healing/strategies/<strategy>.py`：
```python
class MyStrategy:
    async def fix(self, step, error, screenshot):
        # 返回修复后的 step 或 None
        pass
```

2. 在启动时注册：
```python
detector.register_strategy(ErrorType.MY_TYPE, MyStrategy())
```

## 常见问题

### Q: 启动报 "No module named 'xxx'"
```bash
pip install -r requirements.txt
```

### Q: MySQL 连接失败
```bash
# 检查 MySQL 是否运行
docker-compose -f docker/docker-compose.yml ps mysql

# 检查端口
netstat -an | grep 3306
```

### Q: MiniMax API 调用失败
```bash
# 检查 .env 配置
cat backend/.env

# 确认 API Key 有效
curl -H "Authorization: Bearer $MINIMAX_API_KEY" https://api.minimax.chat/v
```

### Q: 前端无法访问后端 API
```bash
# 检查 CORS 配置 (main.py)
# 检查 Nginx 反向代理 (docker/nginx/nginx.conf)
```

## 环境变量参考

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `DEBUG` | true | 调试模式 |
| `DB_HOST` | localhost | MySQL 主机 |
| `DB_PORT` | 3306 | MySQL 端口 |
| `DB_NAME` | auto_test | 数据库名 |
| `REDIS_HOST` | localhost | Redis 主机 |
| `REDIS_PORT` | 6379 | Redis 端口 |
| `MINIO_ENDPOINT` | localhost:9000 | MinIO 端点 |
| `MINIMAX_API_KEY` | - | MiniMax API Key |
| `JWT_SECRET_KEY` | - | JWT 密钥 |

## License

MIT
