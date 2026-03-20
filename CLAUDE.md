# CLAUDE.md - 项目开发规范

本文档定义项目代码风格、架构约定和开发规范。所有贡献者必须遵循。

---

## 1. 项目概述

**项目**: APP 自动化测试平台
**技术栈**: Vue 3 + FastAPI + MySQL + Redis + MinIO + Celery + Maestro
**Python 版本**: 3.11+
**Node 版本**: 18+

---

## 2. 后端规范 (Python/FastAPI)

### 2.1 代码组织

```
backend/app/
├── api/v1/           # API 路由 (REST endpoints)
├── core/             # 核心业务逻辑
│   ├── intention/    # 意图理解
│   ├── script/       # 脚本管理
│   ├── executor/     # 执行调度
│   ├── vision/       # 视觉校验
│   ├── self_healing/ # 智能纠错
│   └── report/       # 报告生成
├── llm/providers/    # LLM Provider 实现
├── models/           # SQLAlchemy 模型
├── schemas/           # Pydantic schemas
├── services/          # 业务服务层
├── tasks/             # Celery 异步任务
└── db/                # 数据库连接
```

### 2.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 文件 | snake_case | `script_manager.py` |
| 类名 | PascalCase | `ScriptManager` |
| 函数 | snake_case | `async def get_script()` |
| 变量 | snake_case | `script_id`, `total_count` |
| 常量 | UPPER_SNAKE | `MAX_RETRY_COUNT = 3` |
| 私有属性 | `_leading_underscore` | `_internal_cache` |

**Model 字段命名**:
- `user_id`, `script_id`, `task_id` - UUID 字符串
- `id` - 自增主键
- `created_at`, `updated_at` - 时间戳

### 2.3 导入顺序

```python
# 1. 标准库
import os
import json
from typing import Optional

# 2. 第三方库
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

# 3. 本地导入 (按相对路径从近到远)
from app.models.user import User
from app.schemas.user import UserCreate
from app.services.auth import AuthService
from app.utils.logger import get_logger
```

### 2.4 Async/Await 模式

**必须使用**:
```python
from app.db.database import get_db

async def get_script(script_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Script).where(Script.script_id == script_id))
    return result.scalar_one_or_none()
```

**异步上下文管理器**:
```python
async with get_db_context() as db:
    script = await manager.get(script_id)
```

### 2.5 API 设计模式

```python
# api/v1/scripts.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.database import get_db
from app.schemas.script import ScriptCreate, ScriptResponse, ScriptListResponse
from app.services.script import ScriptService
from app.dependencies import get_current_user  # 如果需要认证

router = APIRouter()

@router.post("/", response_model=ScriptResponse, status_code=status.HTTP_201_CREATED)
async def create_script(
    script_data: ScriptCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),  # 如果需要认证
):
    """创建新脚本"""
    service = ScriptService(db)
    script = await service.create_script(script_data, current_user.id)
    return script

@router.get("/", response_model=ScriptListResponse)
async def list_scripts(
    skip: int = 0,
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """列出脚本"""
    service = ScriptService(db)
    scripts, total = await service.list_scripts(skip=skip, limit=limit)
    return {"items": scripts, "total": total}
```

### 2.6 SQLAlchemy Model 模式

```python
from sqlalchemy import String, DateTime, BigInteger, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

class Script(Base):
    __tablename__ = "scripts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    script_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    intent: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=datetime.utcnow)

    # Relationships
    user = relationship("User", back_populates="scripts")

    def __repr__(self) -> str:
        return f"<Script(id={self.id}, script_id={self.script_id})>"
```

### 2.7 Pydantic Schema 模式

```python
from pydantic import BaseModel, Field
from datetime import datetime

class ScriptBase(BaseModel):
    intent: str = Field(..., max_length=255)
    structured_instruction: Optional[dict[str, Any]] = None

class ScriptCreate(ScriptBase):
    pass

class ScriptResponse(ScriptBase):
    script_id: str
    user_id: int
    version: int
    status: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
```

### 2.8 错误处理

```python
from fastapi import HTTPException, status

async def get_script(script_id: str, db: AsyncSession):
    result = await db.execute(select(Script).where(Script.script_id == script_id))
    script = result.scalar_one_or_none()

    if not script:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Script {script_id} not found"
        )
    return script
```

### 2.9 日志记录

```python
from app.utils.logger import get_logger, get_trace_id, LoggerMixin

logger = get_logger(__name__)

class MyService(LoggerMixin):
    async def do_something(self):
        trace_id = get_trace_id()
        self.logger.info(f"[{trace_id}] Starting operation")
        # ...
        self.logger.debug(f"Result: {result}")
```

### 2.10 Service 层模式

```python
class ScriptService:
    """脚本管理服务"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.manager = ScriptManager(db)

    async def create_script(self, script_data: ScriptCreate, user_id: int) -> ScriptResponse:
        """创建脚本"""
        script = await self.manager.create(user_id, script_data)
        return ScriptResponse.model_validate(script)

    async def list_scripts(self, user_id: int, skip: int = 0, limit: int = 20) -> tuple[list[ScriptResponse], int]:
        """列出脚本"""
        scripts, total = await self.manager.list(user_id=user_id, skip=skip, limit=limit)
        return [ScriptResponse.model_validate(s) for s in scripts], total
```

---

## 3. 前端规范 (Vue 3/TypeScript)

### 3.1 代码组织

```
frontend/src/
├── api/              # API 封装 (Axios)
├── components/       # 公共组件
├── composables/      # Composition API hooks
├── pages/            # 页面组件
├── stores/           # Pinia stores
└── router/           # 路由配置
```

### 3.2 命名规范

| 类型 | 规范 | 示例 |
|------|------|------|
| 组件文件 | PascalCase | `UserProfile.vue` |
| 组合式函数 | camelCase + use | `useWebSocket.ts` |
| Store 文件 | camelCase | `taskStore.ts` |
| API 文件 | camelCase | `index.ts` |
| 变量/函数 | camelCase | `taskList`, `fetchTask()` |
| 常量 | UPPER_SNAKE | `API_BASE_URL` |
| Props | camelCase | `taskId`, `isLoading` |
| 事件 | camelCase | `taskUpdated` |

### 3.3 Vue 组件规范

```vue
<template>
  <div class="component-name">
    <!-- 模板内容 -->
  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { useTaskStore } from '@/stores/task'

// 1. Props & Emits
interface Props {
  taskId: string
}
const props = defineProps<Props>()

// 2. Composables / Stores
const router = useRouter()
const taskStore = useTaskStore()

// 3. Reactive state
const loading = ref(false)
const task = computed(() => taskStore.currentTask)

// 4. Methods
const fetchTask = async () => {
  loading.value = true
  try {
    await taskStore.fetchTask(props.taskId)
  } catch (error) {
    ElMessage.error('Failed to fetch task')
  } finally {
    loading.value = false
  }
}

// 5. Lifecycle
onMounted(() => {
  fetchTask()
})
</script>

<style scoped>
.component-name {
  /* 组件样式 */
}
</style>
```

### 3.4 Pinia Store 规范

```typescript
import { defineStore } from 'pinia'

interface Task {
  task_id: string
  status: string
  // ...
}

export const useTaskStore = defineStore('task', {
  state: () => ({
    tasks: [] as Task[],
    currentTask: null as Task | null,
    total: 0,
    loading: false,
  }),

  getters: {
    pendingTasks: (state) => state.tasks.filter(t => t.status === 'pending'),
    runningTasks: (state) => state.tasks.filter(t => t.status === 'running'),
  },

  actions: {
    async fetchTasks(skip = 0, limit = 20) {
      this.loading = true
      try {
        const response = await tasksApi.list(skip, limit)
        this.tasks = response.data.items
        this.total = response.data.total
      } finally {
        this.loading = false
      }
    },

    async createTask(instruction: string, deviceId?: string) {
      const response = await tasksApi.create({ instruction, device_id: deviceId })
      const task = response.data
      this.tasks.unshift(task)
      return task
    },
  },
})
```

### 3.5 API 封装规范

```typescript
import axios, { AxiosInstance, AxiosError } from 'axios'
import { ElMessage } from 'element-plus'
import router from '@/router'

const BASE_URL = import.meta.env.VITE_API_BASE_URL || '/api/v1'

const api: AxiosInstance = axios.create({
  baseURL: BASE_URL,
  timeout: 30000,
  headers: { 'Content-Type': 'application/json' },
})

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token && config.headers) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error: AxiosError) => Promise.reject(error)
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('token')
      router.push({ name: 'Login' })
      ElMessage.error('Authentication expired')
    }
    return Promise.reject(error)
  }
)

export default api

// API 模块化导出
export const tasksApi = {
  list: (skip = 0, limit = 20) => api.get('/tasks', { params: { skip, limit } }),
  get: (taskId: string) => api.get(`/tasks/${taskId}`),
  create: (data: any) => api.post('/tasks', data),
  update: (taskId: string, data: any) => api.patch(`/tasks/${taskId}`, data),
}
```

---

## 4. 数据库规范

### 4.1 表命名

- 使用复数形式：`users`, `scripts`, `tasks`
- 小写 + 下划线分隔

### 4.2 字段命名

| 字段类型 | 命名 | 类型 |
|---------|------|------|
| 主键 | `id` | BIGINT UNSIGNED AUTO_INCREMENT |
| UUID | `xxx_id` | VARCHAR(64) UNIQUE |
| 时间戳 | `created_at`, `updated_at` | DATETIME |
| 状态 | `status` | VARCHAR(32) |
| 外键 | `xxx_id` | VARCHAR(64) 或 BIGINT |
| 向量 | `xxx_embedding` | BLOB |
| JSON | `xxx_data` | JSON |

### 4.3 索引

- 主键自动有索引
- UUID 字段加 UNIQUE 索引
- 外键字段加普通索引
- status 字段加索引（常用过滤条件）

---

## 5. LLM Provider 规范

### 5.1 Provider 接口

所有 LLM Provider 必须实现：

```python
from abc import ABC, abstractmethod
from app.llm.base import BaseLLMProvider, LLMResponse, EmbeddingResponse

class BaseLLMProvider(ABC):
    @abstractmethod
    async def chat(self, messages: list[dict], **kwargs) -> LLMResponse:
        pass

    @abstractmethod
    async def embed(self, text: str) -> EmbeddingResponse:
        pass

    @abstractmethod
    async def health_check(self) -> bool:
        pass
```

### 5.2 注册新 Provider

1. 创建 `backend/app/llm/providers/<name>.py`
2. 在 `factory.py` 注册：`_providers["name"] = ProviderClass`
3. 在 `llm.yaml` 添加配置

---

## 6. API 版本控制

- 所有 API 使用 `/api/v1` 前缀
- 不兼容的变更使用 `/api/v2`

---

## 7. 环境变量规范

### 7.1 后端 (.env)

```bash
# 分类：数据库、Redis、MinIO、应用配置

# 数据库
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASSWORD=password
DB_NAME=auto_test

# Redis
REDIS_HOST=localhost
REDIS_PORT=6379

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin

# LLM
MINIMAX_API_KEY=xxx
MINIMAX_GROUP_ID=xxx

# 应用
DEBUG=true
JWT_SECRET_KEY=secret
```

### 7.2 前端 (.env)

```bash
VITE_API_BASE_URL=http://localhost:8000/api/v1
```

---

## 8. 提交规范

### 8.1 Commit Message

```
<type>(<scope>): <subject>

types: feat, fix, docs, style, refactor, test, chore
```

示例：
```
feat(script): add vector matching for script reuse
fix(intention): handle empty instruction error
docs(readme): update quick start guide
```

### 8.2 分支命名

```
feature/<task-id>-<description>
bugfix/<task-id>-<description>
hotfix/<task-id>-<description>
```

---

## 9. 测试规范

### 9.1 单元测试

- 放在 `backend/tests/` 目录
- 文件命名：`test_<module>.py`
- 使用 `pytest` + `pytest-asyncio`

```python
import pytest
from app.core.intention.parser import InstructionParser

@pytest.mark.asyncio
async def test_parser_extracts_app_name():
    parser = InstructionParser()
    result = parser.parse("打开微信")
    assert result.app_name == "wechat"
```

---

## 10. 异常处理规范

### 10.1 HTTP 异常

```python
from fastapi import HTTPException, status

raise HTTPException(
    status_code=status.HTTP_404_NOT_FOUND,
    detail="Resource not found"
)
```

### 10.2 业务异常

在 service 层抛出，API 层统一处理：

```python
# services/script.py
class ScriptNotFoundError(Exception):
    pass

# api/v1/scripts.py
@router.get("/{script_id}")
async def get_script(script_id: str, db: AsyncSession = Depends(get_db)):
    try:
        return await script_service.get_script(script_id)
    except ScriptNotFoundError:
        raise HTTPException(status_code=404, detail="Script not found")
```

---

## 11. 配置管理

### 11.1 YAML 配置

```yaml
# config/backend/llm.yaml
default_provider: minimax

providers:
  minimax:
    enabled: true
    type: minimax
    models:
      primary: MiniMax2.7
      embedding: emb通用
```

### 11.2 配置加载

```python
# app/config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DB_HOST: str = "localhost"

    class Config:
        env_file = ".env"
```

---

## 12. 依赖管理

### 12.1 Python

```
backend/requirements.txt
```

```
# 按分类排序
# 核心框架
fastapi==0.109.2
uvicorn[standard]==0.27.1

# 数据库
sqlalchemy[asyncio]==2.0.25
aiomysql==0.2.0

# Redis
redis==5.0.1

# ... 等等
```

### 12.2 Node

```json
{
  "dependencies": {
    "vue": "^3.4.21",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.7",
    "element-plus": "^2.6.1"
  }
}
```

---

## 13. Docker 规范

### 13.1 镜像命名

```
auto-test-backend:latest
auto-test-frontend:latest
```

### 13.2 Docker Compose 服务

```yaml
services:
  backend:
    build: ../backend
    environment:
      DB_HOST: mysql
    depends_on:
      mysql:
        condition: service_healthy
```

---

## 14. 安全规范

### 14.1 敏感信息

- 密码/密钥不硬编码
- 使用环境变量或 `.env` 文件
- `.env` 文件加入 `.gitignore`

### 14.2 认证

- JWT Token 有效期：30 分钟
- Refresh Token 有效期：7 天
- 敏感操作需要重新认证

### 14.3 输入校验

- 所有 API 输入使用 Pydantic Schema 校验
- SQL 参数化查询防注入
- XSS 防护（前端转义）

---

## 15. 性能规范

### 15.1 数据库

- 使用索引优化查询
- 批量操作使用 `bulk_insert`
- 大数据分页查询

### 15.2 缓存

- Redis 缓存热点数据
- 合理设置过期时间

### 15.3 异步

- I/O 操作使用 async/await
- 长时间任务使用 Celery

---

## 16. 文档规范

### 16.1 代码注释

```python
def complex_function(x: int, y: int) -> int:
    """
    复杂函数的详细说明。

    Args:
        x: 第一个参数说明
        y: 第二个参数说明

    Returns:
        返回值说明

    Raises:
        ValueError: 当参数无效时抛出
    """
    pass
```

### 16.2 README

每个模块应有简要说明：

```python
"""脚本管理服务。

提供脚本的 CRUD 操作、向量化匹配和生成功能。
"""
```

---

## 17. Git 工作流

```
main (生产)
  └── develop (开发)
        ├── feature/xxx
        ├── bugfix/xxx
        └── hotfix/xxx
```

### 17.1 PR 合并规则

- 至少 1 个 Review
- CI 通过
- 无冲突

---

## 18. IDE 配置

### 18.1 VS Code (推荐)

```json
{
  "editor.formatOnSave": true,
  "editor.defaultFormatter": "esbenp.prettier-vscode",
  "[python]": {
    "editor.defaultFormatter": "ms-python.black-formatter"
  }
}
```

### 18.2 Python Linter

```toml
# pyproject.toml
[tool.black]
line-length = 100
target-version = ['py311']
```

---

**最后更新**: 2026-03-20
