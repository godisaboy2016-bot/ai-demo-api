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

# 启动开发服务器（支持热重载）
uvicorn app.main:app --reload
```

访问 `http://127.0.0.1:8000/health` 查看健康状态，`http://127.0.0.1:8000/docs` 查看交互式 API 文档。

## DeepSeek Chat API

向 DeepSeek 发送用户消息并返回 AI 回复：

```bash
curl -X POST http://127.0.0.1:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好"}'
```

响应示例：

```json
{
  "reply": "AI回复内容"
}
```

请求体可选的 `model` 字段用于覆盖默认模型。使用前需配置 `DEEPSEEK_API_KEY`；未配置时接口返回 `503`，DeepSeek 上游错误返回 `502`，请求超时返回 `504`，参数校验失败返回 `422`。

## 运行测试

```bash
pytest
```

## Docker 部署

构建并启动：

```bash
docker compose up -d --build
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

可参考 `.env.example` 创建本地 `.env` 文件。
