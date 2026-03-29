# src/web/app.py
import os
import uuid
import threading
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from src.db.database import (
    init_db,
    save_evaluation,
    get_all_jobs,
    update_job_status,
    get_job,
    delete_job,
    update_job_metadata,
    get_profile,
    save_profile,
    get_profile_updated_at,
    save_message,
    get_messages,
)
from src.scraper.fetcher import ingest_job_from_url
from src.llm_utils.evaluate import evaluate_job
from src.llm_utils.chat import chat_reply
from src.llm_utils.profile import distill_profile

SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".session")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

ALL_STATUSES = ["saved", "applied", "in-process", "offer", "rejected"]
STATUS_FLOW = {s: [t for t in ALL_STATUSES if t != s] for s in ALL_STATUSES}

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)

ingest_tasks: dict[str, dict] = {}


@app.on_event("startup")
def startup():
    init_db()


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
def set_status(job_id: int, status: str = Form(...)):
    update_job_status(job_id, status)
    return RedirectResponse("/", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse(
        "job_detail.html",
        {
            "request": request,
            "job": job,
            "status_flow": STATUS_FLOW,
        },
    )


@app.post("/jobs/{job_id}/delete")
def delete(job_id: int):
    delete_job(job_id)
    return RedirectResponse("/", status_code=303)


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
