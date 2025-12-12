#!/usr/bin/env python3
"""
Run the Afrimail backend server.
"""
import uvicorn
from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.DEBUG,
        log_level="info" if settings.DEBUG else "warning"
    )
