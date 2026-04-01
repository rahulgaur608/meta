"""
FastAPI application exposing the SQLQueryEnv via OpenEnv HTTP API.
Endpoints: GET /tasks, POST /reset, POST /step, GET /state, GET /health
"""
from __future__ import annotations

import uuid
from contextlib import asynccontextmanager
from typing import Any, Dict, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel  # FastAPI still needs pydantic for its own request models

from meta.env.environment import SQLQueryEnv
from meta.env.models import SQLAction, TaskInfo


# ---------------------------------------------------------------------------
# Session store (in-process; fine for single-worker evaluation)
# ---------------------------------------------------------------------------

_sessions: Dict[str, SQLQueryEnv] = {}


def _get_or_create_session(session_id: Optional[str]) -> tuple[str, SQLQueryEnv]:
    if session_id and session_id in _sessions:
        return session_id, _sessions[session_id]
    sid = session_id or str(uuid.uuid4())
    env = SQLQueryEnv()
    _sessions[sid] = env
    return sid, env


# ---------------------------------------------------------------------------
# Request/response schemas
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    task_id: str
    session_id: Optional[str] = None
    seed: Optional[int] = None


class StepRequest(BaseModel):
    sql: str
    explanation: Optional[str] = None
    session_id: Optional[str] = None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    # Teardown all sessions on shutdown
    for env in _sessions.values():
        env.teardown()
    _sessions.clear()


app = FastAPI(
    title="SQL Query Optimization Environment",
    description=(
        "OpenEnv-compliant environment for training and evaluating agents "
        "that write efficient, correct SQL queries."
    ),
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/")
async def root():
    return {
        "message": "Welcome to the SQL Query Optimization Environment API",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {"status": "ok", "env": "sql-query-optimization", "version": "1.0.0"}


@app.get("/tasks")
async def list_tasks():
    env = SQLQueryEnv()
    tasks = env.list_tasks()
    env.teardown()
    return {"tasks": [t.model_dump() for t in tasks]}


@app.post("/reset")
async def reset(req: ResetRequest):
    sid, env = _get_or_create_session(req.session_id)
    try:
        state = env.reset(req.task_id, seed=req.seed)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"session_id": sid, "observation": state.model_dump()}


@app.post("/step")
async def step(req: StepRequest):
    if not req.session_id or req.session_id not in _sessions:
        raise HTTPException(
            status_code=400,
            detail="Invalid or missing session_id. Call /reset first.",
        )
    env = _sessions[req.session_id]
    try:
        action = SQLAction(sql=req.sql, explanation=req.explanation)
        result = env.step(action)
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return result.model_dump()


@app.get("/state")
async def state(session_id: str):
    if session_id not in _sessions:
        raise HTTPException(status_code=404, detail="Session not found.")
    env = _sessions[session_id]
    s = env.state()
    if s is None:
        raise HTTPException(status_code=400, detail="No active episode. Call /reset first.")
    return s.model_dump()


@app.delete("/session/{session_id}")
async def delete_session(session_id: str):
    if session_id in _sessions:
        _sessions[session_id].teardown()
        del _sessions[session_id]
    return {"status": "deleted", "session_id": session_id}


def main():
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=True)


if __name__ == "__main__":
    main()
