"""
ASGI 应用入口；生命周期与资源挂载见 ``config.lifespan``.

使用 **uv** 启动（在 ``backend_job_advisor`` 项目根目录）::

    uv run uvicorn main:app --app-dir src --reload --host 0.0.0.0 --port 8001

或直接运行本文件（无 reload，适合快速起服务）::

    uv run python src/main.py
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.api import router as api_router
from config.api.lifespan import lifespan
from config.log_config import configure_logging


def create_app() -> FastAPI:
    app = FastAPI(title="Job Advisor API", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router, prefix="/api")
    return app


app = create_app()


def main() -> None:
    import uvicorn

    from config.base_conifg import Settings

    port = Settings().api_port
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")


if __name__ == "__main__":
    configure_logging()
    main()
