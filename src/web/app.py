# src/web/app.py
import os
import time
import uuid
import threading
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response as StarletteResponse
from src.db.database import (
    init_db,
    save_evaluation,
    save_job_manual,
    get_all_jobs,
    update_job_status,
    log_job_event,
    get_job,
    delete_job,
    update_job_metadata,
    get_profile,
    save_profile,
    get_profile_updated_at,
    save_message,
    get_messages,
    get_cv_version,
    get_job_cv_versions,
)
from src.scraper.fetcher import ingest_job_from_url
from src.llm_utils.evaluate import evaluate_job
from src.llm_utils.chat import chat_reply
from src.llm_utils.profile import distill_profile
from src.cv_tailor import generate_cv_tailor

SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".session")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

ALL_STATUSES = ["saved", "applied", "in-process", "offer", "rejected"]
STATUS_FLOW = {s: [t for t in ALL_STATUSES if t != s] for s in ALL_STATUSES}

_STARTUP_T = str(time.time())
_DEV_SCRIPT = (
    b"<script>"
    b"(function(){"
    b"var t;"
    b"setInterval(function(){"
    b"fetch('/__dev__/ping').then(function(r){return r.json();}).then(function(d){"
    b"if(t&&t!==d.t)location.reload();"
    b"t=d.t;"
    b"}).catch(function(){});"
    b"},800);"
    b"})();"
    b"</script>"
)


class _DevReloadMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if "text/html" not in response.headers.get("content-type", ""):
            return response
        body = b"".join([chunk async for chunk in response.body_iterator])
        body = body.replace(b"</body>", _DEV_SCRIPT + b"</body>")
        headers = dict(response.headers)
        headers["content-length"] = str(len(body))
        return StarletteResponse(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


app = FastAPI()
app.add_middleware(_DevReloadMiddleware)
templates = Jinja2Templates(directory=TEMPLATES_DIR)

ingest_tasks: dict[str, dict] = {}
tailor_tasks: dict[str, dict] = {}


@app.on_event("startup")
def startup():
    init_db()


@app.get("/__dev__/ping")
def dev_ping():
    return JSONResponse({"t": _STARTUP_T})


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    jobs = get_all_jobs()
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "jobs": jobs,
            "status_flow": STATUS_FLOW,
        },
    )


@app.get("/ingest", response_class=HTMLResponse)
def ingest_page(request: Request) -> HTMLResponse:
    """Page to submit a new job posting URL for ingestion."""
    return templates.TemplateResponse("ingest.html", {"request": request})


def _run_ingest(task_id: str, url: str) -> None:
    """Background thread target: delegates to fetcher, updates task state."""
    try:
        job_id = ingest_job_from_url(SESSION_DIR, url)
        ingest_tasks[task_id] = {"status": "done", "job_id": job_id}
    except BaseException as e:
        ingest_tasks[task_id] = {
            "status": "error",
            "message": f"{type(e).__name__}: {e}",
        }


@app.post("/ingest")
def ingest_submit(url: str = Form(...)) -> JSONResponse:
    """Start background thread to ingest job posting from the provided URL."""
    task_id = str(uuid.uuid4())
    ingest_tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_ingest, args=(task_id, url), daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.get("/ingest/status/{task_id}")
def ingest_status(task_id: str):
    task = ingest_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse(task)


@app.get("/jobs/new", response_class=HTMLResponse)
def job_new_page(request: Request):
    return templates.TemplateResponse("job_add.html", {"request": request})


@app.post("/jobs/new")
def job_new_save(
    job_title: str = Form(...),
    company: str = Form(...),
    location: str = Form(...),
    link: str = Form(""),
    description: str = Form(""),
):
    job_id = save_job_manual(
        job_title, 
        company, 
        location, 
        link.strip() or None, 
        description
    )
    return RedirectResponse(f"/jobs/{job_id}?new=1", status_code=303)


@app.post("/jobs/{job_id}/evaluate")
def reevaluate(job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    result, chash = evaluate_job(job)
    save_evaluation(job_id, chash, result)
    return JSONResponse({"score": result.score, "summary": result.summary})


@app.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
def job_edit_page(request: Request, job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("job_edit.html", {"request": request, "job": job})


@app.post("/jobs/{job_id}/edit")
def job_edit_save(
    job_id: int,
    job_title: str = Form(...),
    company: str = Form(...),
    location: str = Form(...),
):
    update_job_metadata(job_id, job_title, company, location)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/status")
def set_status(job_id: int, status: str = Form(...), note: str = Form("")):
    update_job_status(job_id, status, note.strip() or None)
    return RedirectResponse("/", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int, new: bool = False):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "status_flow": STATUS_FLOW,
            "new": new,
            "cv_versions": get_job_cv_versions(job_id),
        },
    )


@app.post("/jobs/{job_id}/note")
def add_note(job_id: int, note: str = Form(...)):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    note = note.strip()
    if not note:
        raise HTTPException(status_code=400, detail="Note cannot be empty")
    log_job_event(job_id, "note", note)
    return JSONResponse({"ok": True})


@app.post("/jobs/{job_id}/delete")
def delete(job_id: int):
    delete_job(job_id)
    return RedirectResponse("/", status_code=303)


# --- CV Tailor ---


def _run_tailor(task_id: str, job_id: int) -> None:
    try:
        job = get_job(job_id)
        if not job:
            tailor_tasks[task_id] = {"status": "error", "message": f"Job {job_id} not found."}
            return
        _, cv_id = generate_cv_tailor(job["description"], job_id=job_id)
        tailor_tasks[task_id] = {"status": "done", "cv_id": cv_id}
    except BaseException as e:
        tailor_tasks[task_id] = {"status": "error", "message": f"{type(e).__name__}: {e}"}


@app.post("/jobs/{job_id}/tailor")
def tailor_cv(job_id: int):
    task_id = str(uuid.uuid4())
    tailor_tasks[task_id] = {"status": "pending"}
    threading.Thread(target=_run_tailor, args=(task_id, job_id), daemon=True).start()
    return JSONResponse({"task_id": task_id})


@app.get("/jobs/{job_id}/tailor/status/{task_id}")
def tailor_status(job_id: int, task_id: str):
    task = tailor_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return JSONResponse(task)


@app.get("/cv/{cv_id}", response_class=HTMLResponse)
def cv_view(request: Request, cv_id: int):
    cv = get_cv_version(cv_id)
    if not cv:
        raise HTTPException(status_code=404)
    job = get_job(cv["job_id"]) if cv.get("job_id") else None
    return templates.TemplateResponse(
        "cv_view.html",
        {"request": request, "cv": cv, "job": job},
    )


# --- Chat ---


class ChatRequest(BaseModel):
    messages: list[dict]


@app.get("/chat", response_class=HTMLResponse)
def chat_page(request: Request):
    messages = get_messages()
    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "messages": messages,
        },
    )


@app.post("/chat/message")
def chat_message(body: ChatRequest):
    messages = body.messages
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Save user message (last in the list)
    last = messages[-1]
    if last["role"] == "user":
        save_message("user", last["content"])

    reply = chat_reply(messages)
    save_message("assistant", reply)
    return JSONResponse({"reply": reply})


@app.post("/chat/distill")
def chat_distill():
    messages = get_messages()
    existing = get_profile()
    msg_dicts = [{"role": m["role"], "content": m["content"]} for m in messages]
    updated = distill_profile(existing, msg_dicts)
    save_profile(updated)
    return JSONResponse({"profile": updated})


# --- Profile ---


@app.get("/profile", response_class=HTMLResponse)
def profile_page(request: Request):
    content = get_profile()
    updated_at = get_profile_updated_at()
    return templates.TemplateResponse(
        "profile.html",
        {
            "request": request,
            "content": content,
            "updated_at": updated_at,
        },
    )


@app.post("/profile")
def profile_save(content: str = Form(...)):
    save_profile(content)
    return RedirectResponse("/profile", status_code=303)
