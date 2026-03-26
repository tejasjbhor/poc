"""run.py — start the FastAPI server."""
import os
import uvicorn
from utils.config import get_settings

if __name__ == "__main__":
    cfg = get_settings()
    uvicorn.run(
        "api.main_graph:app",
        host=cfg.app_host,
        port=cfg.app_port,
        reload=True,
        log_level=cfg.log_level.lower(),
        ws_ping_interval=30,
        ws_ping_timeout=60,
    )