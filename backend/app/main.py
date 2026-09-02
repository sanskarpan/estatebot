from __future__ import annotations

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from pathlib import Path
from typing import Any, AsyncIterator
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import get_settings
from backend.app.bootstrap import seed_if_empty
from backend.app.db.database import Database, row_to_listing
from backend.app.generation.openrouter import OpenRouterGenerator, deterministic_answer, verify_and_extract
from backend.app.models.schema import ChatRequest, ChatResponse
from backend.app.retrieval.service import RetrievalService


settings = get_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("estatebot.api")
db = Database(settings.database_path)
seed_if_empty(db, settings.seed_corpus_path, settings.seed_on_empty)
retrieval = RetrievalService(db, settings.retrieval_mode, settings.max_retrieval_chunks)
generator = OpenRouterGenerator(settings)
started_at = time.monotonic()
rate_buckets: dict[str, deque[float]] = defaultdict(deque)

MODEL_LABELS = {
    "dots-studio/dots-3-note-preview:free": "Dots3 Note Preview",
    "nvidia/nemotron-3-ultra-550b-a55b:free": "Nemotron 3 Ultra",
    "nvidia/nemotron-3-super-120b-a12b:free": "Nemotron 3 Super",
    "google/gemma-4-31b-it:free": "Gemma 4 31B",
    "z-ai/glm-5.2:free": "GLM 5.2",
    "minimax/minimax-m3:free": "MiniMax M3",
}

app = FastAPI(title="EstateBot API", version="1.0.0", description="Grounded DarGlobal and Wasalt property assistant")
app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False, allow_methods=["GET", "POST"], allow_headers=["*"])


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Content-Security-Policy"] = "default-src 'self'; connect-src 'self' http://localhost:5173; img-src 'self' https: data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'"
    return response


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    status = 400 if request.url.path == "/api/chat" else 422
    return JSONResponse(status_code=status, content={"error": "invalid_request", "message": "Please provide a non-empty message no longer than 2,000 characters." if request.url.path == "/api/chat" else "Invalid request."})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    logger.exception("unhandled_request_error", extra={"path": request.url.path})
    return JSONResponse(status_code=500, content={"error": "internal_error", "message": "The service could not complete this request."})


def _rate_limit(request: Request) -> tuple[bool, int]:
    # Public deployments sit behind an edge proxy, so request.client is the
    # proxy hop rather than the caller. Prefer the edge-provided client address
    # and retain local/direct compatibility as a fallback.
    forwarded_for = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    key = request.headers.get("cf-connecting-ip") or forwarded_for or (request.client.host if request.client else "unknown")
    now = time.monotonic()
    bucket = rate_buckets[key]
    while bucket and now - bucket[0] >= settings.chat_rate_limit_window_seconds:
        bucket.popleft()
    if len(bucket) >= settings.chat_rate_limit_requests:
        return False, max(1, int(settings.chat_rate_limit_window_seconds - (now - bucket[0])))
    bucket.append(now)
    return True, 0


def _history_for_prompt(conversation_id: str) -> list[dict[str, str]]:
    return [{"role": row["role"], "content": row["content"]} for row in db.history(conversation_id, settings.chat_history_turns)]


def _answer_payload(answer: str, citations: list[Any], conversation_id: str, message_id: str, model_used: str | None, mode: str, grounded: bool, elapsed: int, degraded: bool = False) -> ChatResponse:
    return ChatResponse(conversation_id=conversation_id, message_id=message_id, answer=answer, citations=citations, model_used=model_used, retrieval_mode=mode, grounded=grounded, response_time_ms=elapsed, degraded=degraded)


async def process_chat(request: Request, body: ChatRequest) -> ChatResponse:
    if body.model and body.model not in settings.selectable_models:
        raise HTTPException(status_code=400, detail={"error": "invalid_model", "message": "Choose one of the available free models."})
    allowed, retry_after = _rate_limit(request)
    if not allowed:
        raise HTTPException(status_code=429, detail={"error": "rate_limited", "retry_after_seconds": retry_after})
    started = time.monotonic()
    conversation_id = db.ensure_conversation(body.conversation_id)
    history_rows = db.history(conversation_id, settings.chat_history_turns)
    history_text = [row["content"] for row in history_rows if row["role"] == "user"]
    db.add_message(conversation_id, "user", body.message)
    result = retrieval.retrieve(body.message, history_text)
    if result.direct_answer:
        answer = result.direct_answer; citations = []; model_used = None; degraded = False; grounded = True; mode = "structured"
    elif result.no_match_reason:
        answer, citations = deterministic_answer(body.message, result.chunks, reason=result.no_match_reason)
        model_used = None; degraded = False; grounded = False; mode = "none"
    else:
        generation = await generator.generate(body.message, result.chunks, [{"role": row["role"], "content": row["content"]} for row in history_rows], preferred_model=body.model)
        if generation.degraded:
            answer, citations = deterministic_answer(body.message, result.chunks)
            model_used = None; degraded = True; grounded = bool(citations); mode = settings.retrieval_mode
        else:
            answer, citations, valid = verify_and_extract(generation.answer, result.chunks)
            if not valid:
                retry = await generator.generate(body.message, result.chunks, [{"role": row["role"], "content": row["content"]} for row in history_rows], strict=True, preferred_model=body.model)
                if retry.degraded:
                    answer, citations = deterministic_answer(body.message, result.chunks)
                    model_used = None; degraded = True; grounded = bool(citations)
                else:
                    answer, citations, valid = verify_and_extract(retry.answer, result.chunks)
                    if not valid:
                        answer, citations = deterministic_answer(body.message, result.chunks)
                        model_used = None; degraded = True; grounded = bool(citations)
                    else:
                        model_used = retry.model_used; degraded = False; grounded = True
            else:
                model_used = generation.model_used; degraded = False; grounded = True
            mode = settings.retrieval_mode
    elapsed = int((time.monotonic() - started) * 1000)
    citation_dicts = [c.model_dump(mode="json") for c in citations]
    message_id = db.add_message(conversation_id, "assistant", answer, citation_dicts, model_used)
    return _answer_payload(answer, citations, conversation_id, message_id, model_used, mode, grounded, elapsed, degraded)


@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: Request, body: ChatRequest):
    try:
        result = await asyncio.wait_for(process_chat(request, body), timeout=settings.llm_total_timeout_seconds + 5)
    except HTTPException as exc:
        if exc.status_code == 429:
            detail = exc.detail if isinstance(exc.detail, dict) else {"error": "rate_limited"}
            retry = int(detail.get("retry_after_seconds", 60))
            return JSONResponse(status_code=429, headers={"Retry-After": str(retry)}, content={"error": "rate_limited", "retry_after_seconds": retry})
        raise
    except Exception as exc:
        logger.exception("chat_failed", extra={"error": str(exc)})
        return JSONResponse(status_code=503, content={"error": "service_unavailable", "message": "EstateBot could not complete this request. Please try again."})
    accept = request.headers.get("accept", "application/json")
    if "text/event-stream" not in accept:
        return result

    async def events() -> AsyncIterator[str]:
        # The answer is verified and persisted before the final text is emitted.
        words = result.answer.split(" ")
        for index, word in enumerate(words):
            yield f"event: token\ndata: {json.dumps({'text': word + (' ' if index < len(words) - 1 else '')}, ensure_ascii=False)}\n\n"
            await asyncio.sleep(0)
        yield f"event: done\ndata: {json.dumps(result.model_dump(mode='json'), ensure_ascii=False)}\n\n"
    return StreamingResponse(events(), media_type="text/event-stream", headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/api/health")
def health():
    try:
        stats = db.stats()
    except Exception as exc:
        return JSONResponse(status_code=503, content={"status": "degraded", "reason": "database_unreachable"})
    payload = {"status": "ok" if stats["listings_total"] > 0 else "degraded", "corpus": stats, "model": {"primary": settings.openrouter_model_primary, "fallbacks": [x for x in [settings.openrouter_model_fallback_1, settings.openrouter_model_fallback_2] if x]}, "retrieval_mode": settings.retrieval_mode, "version": "estatebot@local", "uptime_seconds": int(time.monotonic() - started_at)}
    return JSONResponse(status_code=200 if stats["listings_total"] > 0 else 503, content=payload)


@app.get("/api/stats")
def stats():
    return db.stats()


@app.get("/api/models")
def models():
    return {
        "default": settings.openrouter_model_primary,
        "models": [
            {"id": model_id, "label": MODEL_LABELS.get(model_id, model_id), "free": True}
            for model_id in settings.selectable_models
        ],
        "fallback_enabled": True,
        "catalog_checked_at": "2026-09-02",
    }


@app.get("/api/listings/{source_site}/{source_id}")
def listing(source_site: str, source_id: str):
    row = db.get_listing(source_site, source_id, include_inactive=True)
    if row is None:
        raise HTTPException(status_code=404, detail={"error": "not_found"})
    if not row["is_active"]:
        return JSONResponse(status_code=410, content={"error": "gone", "message": "This record was previously scraped but is no longer active on the source.", "record": row_to_listing(row)})
    return row_to_listing(row)


@app.get("/api/listings/search")
def listing_search(city: str | None = None, country: str | None = None, source_site: str | None = None, listing_type: str | None = None, min_price: float | None = None, max_price: float | None = None, bedrooms_min: int | None = None, record_type: str | None = None, q: str | None = None, limit: int = 20, offset: int = 0):
    limit = max(1, min(limit, 100)); offset = max(0, offset)
    clauses = ["is_active=1"]; params: list[Any] = []
    for column, value in (("location_city", city), ("location_country", country), ("source_site", source_site), ("listing_type", listing_type), ("record_type", record_type)):
        if value: clauses.append(f"{column}=?"); params.append(value)
    if min_price is not None: clauses.append("price_amount>=?"); params.append(min_price)
    if max_price is not None: clauses.append("price_amount<=?"); params.append(max_price)
    if bedrooms_min is not None: clauses.append("bedrooms_max>=?"); params.append(bedrooms_min)
    if q: clauses.append("(name LIKE ? OR description LIKE ?)"); params.extend([f"%{q}%", f"%{q}%"])
    with db.connect() as conn:
        where = " AND ".join(clauses)
        total = conn.execute(f"SELECT COUNT(*) FROM listings WHERE {where}", params).fetchone()[0]
        rows = conn.execute(f"SELECT * FROM listings WHERE {where} ORDER BY updated_at DESC LIMIT ? OFFSET ?", [*params, limit, offset]).fetchall()
    return {"results": [row_to_listing(row) for row in rows], "total": total}


@app.get("/", include_in_schema=False)
def root():
    index = static_dir / "index.html"
    if index.exists():
        return FileResponse(index)
    return JSONResponse({"service": "estatebot", "message": "Frontend has not been built yet."})


static_dir = Path(__file__).resolve().parent.parent / "static"
if static_dir.exists():
    app.mount("/assets", StaticFiles(directory=static_dir / "assets"), name="assets")
