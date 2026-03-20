# API 文档

## 基础信息

- **Base URL**: `http://localhost:8000/api/v1`
- **认证方式**: JWT Bearer Token
- **Headers**: `Authorization: Bearer <token>`

---

## 认证接口

### 注册用户

```
POST /api/v1/auth/register
```

**Request Body:**
```json
{
  "username": "testuser",
  "password": "password123",
  "email": "test@example.com"
}
```

**Response (201):**
```json
{
  "user_id": "uuid-string",
  "username": "testuser",
  "email": "test@example.com",
  "role": "user",
  "status": "active",
  "created_at": "2026-03-20T10:00:00Z"
}
```

---

### 登录

```
POST /api/v1/auth/login
```

**Request Body:**
```json
{
  "username": "testuser",
  "password": "password123"
}
```

**Response (200):**
```json
{
  "access_token": "eyJ...",
  "refresh_token": "eyJ...",
  "token_type": "bearer"
}
```

---

### 刷新 Token

```
POST /api/v1/auth/refresh
```

**Request Body:**
```json
{
  "refresh_token": "eyJ..."
}
```

---

## 脚本接口

### 创建脚本

```
POST /api/v1/scripts
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "intent": "login",
  "structured_instruction": {
    "app_name": "WeChat",
    "username": "test@example.com"
  }
}
```

**Response (201):**
```json
{
  "script_id": "uuid-string",
  "user_id": 1,
  "intent": "login",
  "structured_instruction": {...},
  "pseudo_code": "...",
  "maestro_yaml": "appId: com.tencent.mm\n---\n...",
  "version": 1,
  "hit_count": 0,
  "status": "active",
  "created_at": "2026-03-20T10:00:00Z"
}
```

---

### 列表脚本

```
GET /api/v1/scripts?skip=0&limit=20
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "items": [...],
  "total": 100
}
```

---

### 获取脚本

```
GET /api/v1/scripts/{script_id}
Authorization: Bearer <token>
```

---

### 更新脚本

```
PUT /api/v1/scripts/{script_id}
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "intent": "login",
  "pseudo_code": "...",
  "maestro_yaml": "..."
}
```

---

### 删除脚本

```
DELETE /api/v1/scripts/{script_id}
Authorization: Bearer <token>
```

**Response:** 204 No Content

---

## 任务接口

### 创建任务

```
POST /api/v1/tasks
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "instruction": "打开微信并登录",
  "device_id": "device-uuid-optional"
}
```

**Response (201):**
```json
{
  "task_id": "uuid-string",
  "user_id": 1,
  "instruction": "打开微信并登录",
  "script_id": "script-uuid",
  "device_id": "device-uuid",
  "status": "pending",
  "total_steps": 0,
  "completed_steps": 0,
  "created_at": "2026-03-20T10:00:00Z"
}
```

---

### 列表任务

```
GET /api/v1/tasks?skip=0&limit=20
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "items": [
    {
      "task_id": "uuid-string",
      "instruction": "打开微信并登录",
      "status": "running",
      "total_steps": 10,
      "completed_steps": 5,
      "device_id": "device-uuid",
      "created_at": "2026-03-20T10:00:00Z"
    }
  ],
  "total": 50
}
```

---

### 获取任务详情

```
GET /api/v1/tasks/{task_id}
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "task_id": "uuid-string",
  "instruction": "打开微信并登录",
  "status": "completed",
  "total_steps": 10,
  "completed_steps": 10,
  "error_type": null,
  "error_message": null,
  "duration_ms": 45000,
  "steps": [
    {
      "step_id": "uuid",
      "step_index": 0,
      "action": "launchApp",
      "target": "com.tencent.mm",
      "value": null,
      "status": "completed",
      "screenshot_before": null,
      "screenshot_after": "https://...",
      "retry_count": 0,
      "duration_ms": 2000
    }
  ]
}
```

---

### 更新任务状态

```
PATCH /api/v1/tasks/{task_id}
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "status": "running",
  "completed_steps": 5
}
```

---

## 设备接口

### 注册设备

```
POST /api/v1/devices
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "device_id": "android-emulator-01",
  "device_name": "Android Emulator",
  "os_version": "Android 14",
  "model": "Pixel 7"
}
```

---

### 列表设备

```
GET /api/v1/devices
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "items": [
    {
      "device_id": "android-emulator-01",
      "device_name": "Android Emulator",
      "os_version": "Android 14",
      "model": "Pixel 7",
      "status": "online",
      "current_task_id": null,
      "last_heartbeat": "2026-03-20T10:00:00Z"
    }
  ],
  "total": 5
}
```

---

### 更新设备

```
PATCH /api/v1/devices/{device_id}
Authorization: Bearer <token>
```

**Request Body:**
```json
{
  "status": "offline"
}
```

---

## 报告接口

### 获取报告

```
GET /api/v1/reports/{report_id}
Authorization: Bearer <token>
```

**Response (200):**
```json
{
  "report_id": "report_task-uuid",
  "task_id": "task-uuid",
  "summary": {
    "status": "completed",
    "total_steps": 10,
    "passed_steps": 9,
    "failed_steps": 1,
    "pass_rate": 90.0,
    "total_duration_ms": 45000
  },
  "instruction": "打开微信并登录",
  "steps": [...],
  "failures": [...],
  "generated_at": "2026-03-20T10:05:00Z"
}
```

---

### 下载报告 PDF

```
GET /api/v1/reports/{report_id}/download
Authorization: Bearer <token>
```

**Response:** PDF 文件流

---

## WebSocket 接口

### 连接

```
ws://localhost:8000/ws?token=<jwt_token>
```

### 发送消息

**订阅任务更新：**
```json
{
  "type": "subscribe",
  "task_id": "task-uuid"
}
```

**取消订阅：**
```json
{
  "type": "unsubscribe",
  "task_id": "task-uuid"
}
```

**心跳检测：**
```json
{
  "type": "ping"
}
```

### 接收消息

**任务更新：**
```json
{
  "type": "task_update",
  "task_id": "task-uuid",
  "data": {
    "status": "running",
    "completed_steps": 5,
    "current_step": {...}
  }
}
```

**任务完成：**
```json
{
  "type": "task_completed",
  "task_id": "task-uuid",
  "result": {
    "status": "completed",
    "duration_ms": 45000
  }
}
```

---

## 错误响应

**格式：**
```json
{
  "detail": "Error message"
}
```

**常见错误码：**
- `401 Unauthorized` - Token 无效或过期
- `403 Forbidden` - 无权限访问
- `404 Not Found` - 资源不存在
- `422 Validation Error` - 请求参数验证失败
- `500 Internal Server Error` - 服务器内部错误
