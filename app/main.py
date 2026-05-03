from fastapi import FastAPI

from app.api.routes import router

# FastAPI 应用入口。
# 运行命令：.venv\Scripts\python.exe -m uvicorn app.main:app --reload
app = FastAPI(
    title="Let's Go Now Trip Agent",
    description="旅游规划 Agent MVP，使用真实 OpenAI-compatible 模型生成结构化旅游计划。",
    version="0.1.0",
)

app.include_router(router)
