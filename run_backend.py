from __future__ import annotations

import uvicorn

from backend.app.main import create_app

app = create_app()

if __name__ == "__main__":
    from backend.app.core.config import settings

    uvicorn.run(
        "run_backend:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.is_development,
    )
