import os
from datetime import datetime, timezone

from fastapi import FastAPI, Header, HTTPException

from app.main import run_once


app = FastAPI(title="Agentic Trader API")


@app.get("/")
def root():
    return {
        "message": "Agentic Trader API is running",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/cron")
def cron_run(authorization: str | None = Header(default=None)):
    cron_secret = os.getenv("CRON_SECRET")
    if cron_secret:
        expected_header = f"Bearer {cron_secret}"
        if authorization != expected_header:
            raise HTTPException(status_code=401, detail="Unauthorized")

    auto_trade_enabled = os.getenv("AUTO_TRADE", "false").lower() == "true"
    if os.getenv("VERCEL", ""):
        # Vercel runs on Linux; MT5 execution is not available there.
        auto_trade_enabled = False

    cycle_result = run_once(auto_trade_enabled_for_cycle=auto_trade_enabled)

    return {
        "ok": True,
        "mode": "cron",
        "auto_trade_enabled_for_cycle": auto_trade_enabled,
        "cycle_result": cycle_result,
        "time": datetime.now(timezone.utc).isoformat(),
    }
