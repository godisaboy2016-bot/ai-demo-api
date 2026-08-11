# ai-demo-api

生产级 Python FastAPI 示例项目，使用 Python 3.12、uvicorn 提供服务，支持 Docker 部署。

## 功能特性

- Python 3.12 + FastAPI
- uvicorn 作为 ASGI 服务器
- JWT 用户认证：`/api/auth/register`、`/api/auth/login`、`/api/auth/me`
- `POST /api/chat` DeepSeek 聊天接口（Bearer token 认证，支持用户消息输入，返回 AI 回复）
- `/health` 健康检查接口（供负载均衡器 / 容器编排使用）
- 基于 `pydantic-settings` 的配置管理（环境变量 + `.env`）
- 基于 Alembic 的数据库迁移（`docker compose run --rm migrate`）
- 统一的 API 错误契约（`{error, message, request_id}` + `X-Request-ID`）
- pytest 单元测试 + `docker compose config` 校验脚本
- 多阶段 Docker 构建，以非 root 用户运行，内置 HEALTHCHECK

## 项目结构

```text
.
├── Dockerfile                # 多阶段构建镜像
├── docker-compose.yml        # 一键部署（db / migrate / api）
├── pyproject.toml            # 依赖与构建配置
├── scripts/
│   └── check_compose.sh      # docker compose config 校验脚本
├── src/app/
│   ├── main.py               # FastAPI 应用入口（路由与异常处理器注册）
│   ├── api/
│   │   ├── dependencies.py   # get_current_user 认证依赖
│   │   └── routes/
│   │       ├── auth.py       # 注册 / 登录 / 当前用户
│   │       ├── chat.py       # 聊天路由
│   │       └── health.py     # 健康检查
│   ├── core/
│   │   ├── config.py         # 配置管理（pydantic-settings + JWT 校验）
│   │   ├── security.py       # JWT 签发/校验、bcrypt 密码哈希
│   │   ├── exceptions.py     # 业务异常（AuthError / ConflictError / DeepSeekError）
│   │   └── exception_handlers.py  # 统一错误响应（业务异常 / 422 / 404 / 405 / 500）
│   ├── db/
│   │   ├── alembic.ini       # Alembic 配置
│   │   ├── base.py           # SQLAlchemy Declarative Base
│   │   ├── session.py        # async engine / session
│   │   └── migrations/       # Alembic 迁移脚本（versions/ 下为版本迁移）
│   ├── middleware/
│   │   └── request_logging.py  # 请求日志与 X-Request-ID
│   ├── models/
│   │   └── user.py           # User 模型
│   ├── schemas/
│   │   ├── auth.py           # 注册 / 登录 / 用户响应模型
│   │   └── chat.py           # 聊天请求 / 响应模型
│   └── services/
│       ├── auth_service.py   # 注册 / 认证业务逻辑
│       └── deepseek.py       # DeepSeek API 客户端
└── tests/                    # pytest 测试（认证 / 聊天 / 迁移 / 错误契约 / 日志等）
```

## 快速开始（本地开发）

需要 Python 3.12。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# 创建本地配置（.env 会被 .gitignore 忽略）
cp .env.example .env
# 编辑 .env：设置 JWT_SECRET_KEY（如 openssl rand -hex 32）与 DEEPSEEK_API_KEY

# 启动数据库（PostgreSQL，仅暴露到本机 127.0.0.1:5432）
docker compose up -d db

# 本地连接数据库（与 docker-compose.yml 默认一致）
export DATABASE_URL="postgresql+asyncpg://ai_demo:ai_demo@127.0.0.1:5432/ai_demo"

# 执行数据库迁移（首次运行或模型变更后）
alembic -c src/app/db/alembic.ini upgrade head

# 启动开发服务器（支持热重载）
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000/health` 查看健康状态，`http://127.0.0.1:8000/docs` 查看交互式 API 文档。

注意：注册、登录等接口依赖 `users` 表，启动前必须先执行数据库迁移；本地启动要求 `JWT_SECRET_KEY` 已配置（缺失时应用拒绝启动）。

## Auth API

用户认证基于 JWT Bearer token，密码使用 bcrypt 哈希存储。

### 注册

```bash
curl -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "your-password"}'
```

- 成功：`201`，返回 `UserResponse`（`id`、`email`、`is_active`、`created_at`、`updated_at`）
- 邮箱已存在：`409`，`{"error": "user_already_exists", ...}`
- 密码需 8-72 字符且不超过 72 UTF-8 字节，否则 `422`，`{"error": "validation_error", ...}`

### 登录

```bash
curl -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "your-password"}'
```

- 成功：`200`，返回 `{"access_token": "<jwt>", "token_type": "bearer"}`（默认有效期 30 分钟）
- 邮箱或密码错误：`401`，`{"error": "invalid_credentials", ...}`

### 当前用户

```bash
curl http://127.0.0.1:8000/api/auth/me \
  -H "Authorization: Bearer $TOKEN"
```

- 成功：`200`，返回 `UserResponse`
- 缺失 / 无效 / 过期 token、token 类型非 access、用户不存在或已停用：`401`，`{"error": "invalid_token", ...}`

## DeepSeek Chat API

向 DeepSeek 发送用户消息并返回 AI 回复。该接口需要 Bearer token 认证，token 通过 `POST /api/auth/login` 获取：

```bash
TOKEN=$(curl -s -X POST http://127.0.0.1:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "your@email.com", "password": "your-password"}' \
  | python3 -c "import sys, json; print(json.load(sys.stdin)['access_token'])")

curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "你好"}'

# 继续上一轮会话（携带 conversation_id）
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message": "请继续解释", "conversation_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301"}'
```

响应示例：

```json
{
  "reply": "AI回复内容",
  "conversation_id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
}
```

请求体可选的 `model` 字段用于覆盖默认模型，未指定时使用 `DEEPSEEK_MODEL` 默认模型。
请求体可选的 `conversation_id` 用于继续已有会话：携带时会加载该会话最近的历史消息
作为多轮上下文（受 `DEEPSEEK_HISTORY_MAX_MESSAGES` 条数与 `DEEPSEEK_HISTORY_MAX_CHARS`
字符数上限约束，超出部分按完整 user/assistant 对从最旧优先丢弃，保证发给 DeepSeek 的
messages 首条为 user 且角色严格交替）；不携带时自动创建新会话。
响应中的 `conversation_id` 标识本轮用户消息与 AI 回复所属的会话。
`conversation_id` 不存在或不属于当前用户时返回 `404 not_found`。
使用前需配置 `DEEPSEEK_API_KEY`。

状态码说明：

| 状态码 | 场景 | `error` |
| --- | --- | --- |
| `200` | 成功返回 AI 回复 | - |
| `401` | 未认证 / token 无效 | `invalid_token` |
| `422` | 请求体校验失败（如 `message` 缺失） | `validation_error` |
| `404` | `conversation_id` 不存在或不属于当前用户 | `not_found` |
| `502` | DeepSeek 上游错误 | `deepseek_error` |
| `503` | 未配置 `DEEPSEEK_API_KEY` | `deepseek_error` |
| `504` | 请求超时 | `deepseek_error` |

所有错误响应统一为：

```json
{
  "error": "错误码",
  "message": "错误信息",
  "request_id": "请求 ID（与 X-Request-ID header 一致）"
}
```

## Chat History API

返回当前登录用户的历史聊天消息，按时间倒序（最新在前），支持游标分页。需要 Bearer token 认证，token 获取方式与 `POST /api/chat` 相同。

### 获取历史

```bash
curl "http://127.0.0.1:8000/api/chat/history?limit=20" \
  -H "Authorization: Bearer $TOKEN"
```

参数说明：

| 参数 | 类型 | 默认值 | 说明 |
| --- | --- | --- | --- |
| `limit` | int | `20` | 每页返回的消息数，取值范围 1-100 |
| `cursor` | string | 无 | 上一页响应中的 `next_cursor`，用于获取下一页 |
| `conversation_id` | UUID | 无 | 可选，只返回指定会话的消息 |

响应示例：

```json
{
  "items": [
    {
      "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3301",
      "conversation_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "role": "user",
      "content": "你好",
      "model": null,
      "created_at": "2026-08-11T12:00:00+00:00"
    },
    {
      "id": "3f2504e0-4f89-11d3-9a0c-0305e82c3302",
      "conversation_id": "6ba7b810-9dad-11d1-80b4-00c04fd430c8",
      "role": "assistant",
      "content": "你好！有什么可以帮你的吗？",
      "model": "deepseek-chat",
      "created_at": "2026-08-11T12:00:01+00:00"
    }
  ],
  "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wOC0xMVQxMjowMDowMSswMDowMCIsImlkIjoiM2YyNTA0ZTAtNGY4OS0xMWQzLTlhMGMtMDMwNWU4MmMzMzAyIn0="
}
```

`items` 中每条消息包含 `id`、`conversation_id`、`role`（`user` 或 `assistant`）、`content`、`model`（assistant 消息为实际调用模型，user 消息为 `null`）与 `created_at`。

分页：将上一页响应中的 `next_cursor` 作为下一次请求的 `cursor` 参数传入，直到 `next_cursor` 为 `null` 表示没有更多消息：

```bash
curl "http://127.0.0.1:8000/api/chat/history?limit=20&cursor=$NEXT_CURSOR" \
  -H "Authorization: Bearer $TOKEN"
```

按会话过滤：传入 `conversation_id` 只返回该会话的消息；会话不存在时返回空列表（HTTP 200），不会返回 404。

错误说明：

| 状态码 | 场景 | `error` |
| --- | --- | --- |
| `401` | 未认证 / token 无效 | `invalid_token` |
| `422` | `limit` 超出 1-100、`cursor` 非法、`conversation_id` 格式错误 | `validation_error` |

## 运行测试

```bash
pytest
./scripts/check_compose.sh
```

## 数据库迁移

数据库结构变更通过 Alembic 管理，迁移脚本位于 `src/app/db/migrations/`。迁移会等待 `db` 服务健康后再执行：

```bash
docker compose run --rm migrate
```

`migrate` 复用 `ai-demo-api` 镜像，等价于在容器内执行 `alembic upgrade head`，环境变量与 `api` 服务保持一致（至少需要 `DATABASE_URL`；`JWT_SECRET_KEY` 若已配置则继承使用，未配置时 migrate 会自动生成一次性临时值仅用于通过配置校验，迁移本身不使用 JWT）。本地开发也可以直接执行：

```bash
alembic -c src/app/db/alembic.ini upgrade head
```

创建数据库并迁移后的验证方法：

```bash
# 查看已应用的迁移版本
docker compose exec db psql -U ai_demo -d ai_demo -c "SELECT * FROM alembic_version;"

# 查看业务表
docker compose exec db psql -U ai_demo -d ai_demo -c "\dt"
```

或调用注册接口验证 `users` 表可用（期望返回 `201`）：

```bash
curl -s -X POST http://127.0.0.1:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email": "demo@example.com", "password": "password123"}'
```

## Docker 部署

构建并启动：

```bash
# 先设置 JWT_SECRET_KEY（api 必填，与 migrate 使用同一来源；缺失时 compose 会直接报错）
export JWT_SECRET_KEY="$(openssl rand -hex 32)"

docker compose up -d --build
```

`docker compose up` 会先启动 `db` 与 `migrate` 服务（迁移幂等，已应用过的不会重复执行），
`api` 会在 `migrate` 成功完成后才启动，因此 `docker compose up -d` 是唯一可靠的启动方式。
如需手动重跑迁移（例如重置后初始化），仍可使用 `docker compose run --rm migrate`。

或仅构建镜像：

```bash
docker build -t ai-demo-api .
docker run -p 8000:8000 ai-demo-api
```

容器内置 `HEALTHCHECK`，会每 30 秒请求一次 `/health` 检查服务状态。

`JWT_SECRET_KEY` 可通过 `.env` 文件或环境变量提供；`migrate` 在未配置时会自动生成一次性临时值用于通过配置校验（迁移不使用 JWT），`api` 则必须显式配置。

## 配置

所有配置项通过环境变量注入（详见 `src/app/core/config.py`）。通用前缀为 `APP_`；部分变量支持无前缀别名（如 `DATABASE_URL` / `APP_DATABASE_URL`、`JWT_SECRET_KEY` / `APP_JWT_SECRET_KEY`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_APP_NAME` | `ai-demo-api` | 服务名称 |
| `APP_APP_VERSION` | `0.1.0` | 服务版本 |
| `APP_ENVIRONMENT` | `development` | 运行环境（生产环境强制 `JWT_SECRET_KEY` 至少 32 字符） |
| `APP_LOG_LEVEL` | `INFO` | 日志级别 |
| `DATABASE_URL` | `postgresql+asyncpg://ai_demo:ai_demo@db:5432/ai_demo` | 数据库连接串 |
| `DEEPSEEK_API_KEY` | 无 | DeepSeek API Key（缺失时聊天接口返回 503） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 基础地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 默认模型名 |
| `DEEPSEEK_TIMEOUT_SECONDS` | `60.0` | DeepSeek 请求超时（秒） |
| `DEEPSEEK_HISTORY_MAX_MESSAGES` | `20` | 多轮上下文最多加载的历史消息条数 |
| `DEEPSEEK_HISTORY_MAX_CHARS` | `8000` | 多轮上下文历史消息总字符数上限 |
| `JWT_SECRET_KEY` | 无 | JWT 签名密钥（必填；生产环境至少 32 字符，缺失或过短时服务拒绝启动）。生成示例：`openssl rand -hex 32` |
| `JWT_ALGORITHM` | `HS256` | JWT 签名算法 |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `30` | access token 有效期（分钟） |

可参考 `.env.example` 创建本地 `.env` 文件。
