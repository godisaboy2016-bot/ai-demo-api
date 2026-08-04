# AI Demo API - Codex Development Guide


## 1. Project Overview

This project is a production-style FastAPI backend application.

Main goals:

- Build reliable AI API services
- Integrate Large Language Models
- Provide Docker-based deployment
- Maintain production-quality engineering practices


---

## 2. Technology Stack

### Backend

- Python 3.12
- FastAPI
- Pydantic Settings
- Uvicorn


### Testing

- pytest


### Container

- Docker
- Docker Compose


### AI Provider

- DeepSeek API


---

## 3. Project Structure

ai-demo-api/

├── src/
│ └── app/
│ ├── main.py
│ ├── api/
│ ├── services/
│ ├── schemas/
│ └── config.py
│
├── tests/
│
├── Dockerfile
├── docker-compose.yml
├── pyproject.toml
├── requirements.txt
├── README.md
└── AGENTS.md


---

## 4. Development Principles


Before modifying code:

1. Analyze the existing project structure.
2. Understand current implementation.
3. Avoid unnecessary changes.
4. Preserve existing functionality.


When implementing new features:

1. Create API routes.
2. Create request/response schemas.
3. Put business logic into services.
4. Add automated tests.
5. Update documentation.


---

## 5. Code Standards


Follow these rules:

- Use Python type hints.
- Write clean and readable code.
- Keep functions small.
- Avoid duplicated logic.
- Separate API layer and business logic.
- Use dependency injection when appropriate.


Never:

- Hardcode API keys.
- Commit secrets.
- Modify .env files containing real credentials.
- Remove existing tests without approval.


---

## 6. Configuration Rules


Environment variables must be used for:

- API keys
- Database credentials
- External service configuration


Example:

DEEPSEEK_API_KEY=xxxx



Never put secrets directly into:

- Python files
- Dockerfile
- Git repository


---

## 7. Testing Requirements


After every code modification:


Run:

pytest



All tests must pass before considering the task complete.


For new features:

- Add unit tests.
- Test API endpoints.
- Test error handling.


---

## 8. Docker Requirements


The application must run with:


Build:

docker compose build


Start:

docker compose up



After backend changes:

Verify:

docker compose build

docker compose up




The container must start successfully.


---

## 9. API Development Rules


New APIs should follow:

Request
|
Schema
|
API Router
|
Service Layer
|
External Provider



Example:

api/chat.py

    |
    v

DeepSeek API



---

## 10. Git Workflow


Before committing:

Check:

git status



Commit messages should describe changes clearly.


Examples:

add deepseek chat api

fix docker configuration

add api tests



---

## 11. Current Project Objective


The next major feature:


Implement DeepSeek Chat API.


Requirements:


- Add POST /api/chat
- Support user message input
- Call DeepSeek API
- Return AI response
- Add tests
- Update README
- Keep Docker deployment working


---

## 12. Codex Behavior Rules


When working on this project:


1. Explain the plan before large changes.
2. Avoid changing unrelated files.
3. Show modified files.
4. Run tests after modifications.
5. Report any problems clearly.

