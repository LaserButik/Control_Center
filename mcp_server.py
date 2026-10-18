# -*- coding: utf-8 -*-
"""
AI Mentors Agency — Secure MCP Server (SSE Transport)
"""

import os
import json
import uvicorn
from pathlib import Path

from fastmcp import FastMCP
from starlette.responses import JSONResponse

from atlas_services import prospect_finder as pf
from atlas_services import social_engine

# ------------------------------------------------------------------
# 1. Configuration & Security
# ------------------------------------------------------------------
# تثبيت المفتاح هنا للتأكد من تطابقه مع العميل
MCP_API_KEY = "default_super_secret_key_123"

mcp = FastMCP("AI_Mentors_Agency")

# ------------------------------------------------------------------
# 2. MCP Tools
# ------------------------------------------------------------------
@mcp.tool()
def find_new_prospects(sector: str, country: str = "AE", max_results: int = 20) -> dict:
    try:
        result = pf.find_all_sectors([sector], country, max_results, "serper")
        return {"status": "success", "companies_found": result.get("companies_found", 0)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@mcp.tool()
def get_funnel_stats() -> dict:
    reports_dir = Path(__file__).resolve().parent / "data" / "reports"
    if not reports_dir.exists(): return {"error": "No reports found."}
    files = sorted(reports_dir.glob("daily_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files: return {"error": "No reports found."}
    try:
        latest = json.loads(files[0].read_text(encoding="utf-8"))
        metrics = latest.get("metrics", {})
        return {"date": latest.get("date"), "emails_sent": metrics.get("serper_found", 0) + metrics.get("pw_found", 0)}
    except Exception as e:
        return {"error": str(e)}

@mcp.tool()
def run_social_post() -> dict:
    try:
        result = social_engine.run_daily_social(dry_run=False, image_mode="auto")
        return {"status": "success", "linkedin": result.get("linkedin", {}).get("ok", False)}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ------------------------------------------------------------------
# 3. Pure ASGI Security Middleware
# ------------------------------------------------------------------
class BearerAuthMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Read headers from ASGI scope
        headers = dict(scope["headers"])
        auth_header = headers.get(b"authorization", b"").decode("utf-8")

        if not auth_header.startswith("Bearer "):
            response = JSONResponse({"error": "Unauthorized: Missing Bearer token"}, status_code=401)
            return await response(scope, receive, send)

        token = auth_header.split(" ", 1)[1].strip()
        if token != MCP_API_KEY:
            response = JSONResponse({"error": "Forbidden: Invalid API key"}, status_code=403)
            return await response(scope, receive, send)

        return await self.app(scope, receive, send)

# ------------------------------------------------------------------
# 4. Server Runner
# ------------------------------------------------------------------
if __name__ == "__main__":
    print(f"🔒 Starting Secure MCP Server (SSE) on http://localhost:8000/sse")
    
    # Get the SSE app
    app = mcp.http_app(transport="sse")
    
    # Wrap it with our custom ASGI middleware
    app = BearerAuthMiddleware(app)
    
    uvicorn.run(app, host="0.0.0.0", port=8000)