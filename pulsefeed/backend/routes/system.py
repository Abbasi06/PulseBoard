"""
GET /system/status          — current model load state (polled by frontend)
GET /system/model-progress  — download progress as Server-Sent Events stream
"""
from __future__ import annotations

import asyncio
import json
import platform

from fastapi import APIRouter
from fastapi.responses import StreamingResponse

import llm.model_manager as mm
from llm.engine import LLMEngine

router = APIRouter(prefix="/system", tags=["system"])


@router.get("/status")
def get_status() -> dict:
    engine = LLMEngine.get()
    return {
        "status": mm.state["status"] if not engine.is_ready() else "ready",
        "model_name": mm.state["model_name"],
        "model_tier": mm.state["model_tier"],
        "gpu_type": mm.state["gpu_type"],
        "ram_gb": mm.state["ram_gb"],
        "progress": mm.state["progress"],
        "error": mm.state.get("error") or engine.get_error(),
        "platform": platform.system(),
        "ready": engine.is_ready(),
    }


@router.get("/model-progress")
async def model_progress_stream() -> StreamingResponse:
    """
    SSE stream that the frontend SetupProgress screen subscribes to.
    Emits a JSON event every second until the model is ready or errored.
    """
    async def _generate():
        engine = LLMEngine.get()
        while not engine.is_ready() and mm.state["status"] not in ("error", "disabled"):
            data = {
                "status": mm.state["status"],
                "progress": round(mm.state["progress"], 3),
                "downloaded_mb": mm.state["downloaded_bytes"] // (1024 * 1024),
                "total_mb": mm.state["total_bytes"] // (1024 * 1024),
                "model_name": mm.state["model_name"],
            }
            yield f"data: {json.dumps(data)}\n\n"
            await asyncio.sleep(1)
        # Final event
        final = {
            "status": "ready" if engine.is_ready() else "error",
            "progress": 1.0 if engine.is_ready() else mm.state["progress"],
            "error": mm.state.get("error") or engine.get_error(),
            "model_name": mm.state["model_name"],
        }
        yield f"data: {json.dumps(final)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
