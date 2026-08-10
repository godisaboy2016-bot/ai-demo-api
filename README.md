# ai-demo-api

生产级 Python FastAPI 示例项目，使用 Python 3.12、uvicorn 提供服务，支持 Docker 部署。

## 功能特性

- Python 3.12 + FastAPI
- uvicorn 作为 ASGI 服务器
- `/health` 健康检查接口（供负载均衡器 / 容器编排使用）
- `POST /api/chat` DeepSeek 聊天接口（支持用户消息输入，返回 AI 回复）
- 基于 `pydantic-settings` 的配置管理（环境变量 + `.env`）
- pytest 单元测试
- 多阶段 Docker 构建，以非 root 用户运行，内置 HEALTHCHECK

## 项目结构

```text
.
├── Dockerfile              # 多阶段构建镜像
├── docker-compose.yml      # 一键部署
├── pyproject.toml          # 依赖与构建配置
├── src/app/
│   ├── main.py             # FastAPI 应用入口
│   ├── core/config.py      # 配置管理
│   ├── schemas/chat.py     # 聊天请求/响应模型
│   ├── services/deepseek.py# DeepSeek API 服务
│   └── api/routes/
│       ├── health.py       # 健康检查路由
│       └── chat.py         # 聊天路由
└── tests/                  # pytest 测试
```

## 快速开始（本地开发）

需要 Python 3.12。

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

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

注意：注册、登录等接口依赖 `users` 表，启动前必须先执行数据库迁移；`JWT_SECRET_KEY` 需在 `.env` 中配置（见下文“配置”）。

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
```

响应示例：

```json
{
  "reply": "AI回复内容"
}
```

请求体可选的 `model` 字段用于覆盖默认模型。使用前需配置 `DEEPSEEK_API_KEY`；未认证请求返回 `401`，未配置 API Key 时返回 `503`，DeepSeek 上游错误返回 `502`，请求超时返回 `504`，参数校验失败返回 `422`。

## 运行测试

```bash
pytest
```

## 数据库迁移

数据库结构变更通过 Alembic 管理，迁移脚本位于 `src/app/db/migrations/`。迁移会等待 `db` 服务健康后再执行：

```bash
docker compose run --rm migrate
```

`migrate` 复用 `ai-demo-api` 镜像，等价于在容器内执行 `alembic upgrade head`，需要与 `api` 服务相同的环境变量（至少 `DATABASE_URL` 与 `JWT_SECRET_KEY`）。本地开发也可以直接执行：

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
docker compose up -d --build
docker compose run --rm migrate
```

或仅构建镜像：

```bash
docker build -t ai-demo-api .
docker run -p 8000:8000 ai-demo-api
```

容器内置 `HEALTHCHECK`，会每 30 秒请求一次 `/health` 检查服务状态。

## 配置

所有配置项通过 `APP_` 前缀的环境变量注入（详见 `src/app/core/config.py`）：

| 变量 | 默认值 | 说明 |
| --- | --- | --- |
| `APP_APP_NAME` | `ai-demo-api` | 服务名称 |
| `APP_APP_VERSION` | `0.1.0` | 服务版本 |
| `APP_ENVIRONMENT` | `development` | 运行环境 |
| `APP_LOG_LEVEL` | `INFO` | 日志级别 |
| `DEEPSEEK_API_KEY` | 无 | DeepSeek API Key（必填，缺失时聊天接口返回 503） |
| `DEEPSEEK_BASE_URL` | `https://api.deepseek.com` | DeepSeek API 基础地址 |
| `DEEPSEEK_MODEL` | `deepseek-chat` | 默认模型名 |
| `DEEPSEEK_TIMEOUT_SECONDS` | `60.0` | DeepSeek 请求超时（秒） |
| `JWT_SECRET_KEY` | 无 | JWT 签名密钥（必填；生产环境至少 32 字符，缺失或过短时服务拒绝启动）。生成示例：`openssl rand -hex 32` |

可参考 `.env.example` 创建本地 `.env` 文件。
