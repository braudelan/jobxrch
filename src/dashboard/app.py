# src/dashboard/app.py
import os
from fastapi import FastAPI, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from playwright.sync_api import sync_playwright
from pydantic import BaseModel
from src.db.database import (
    init_db, is_job_saved, save_job, get_job_by_link,
    get_job_id, save_evaluation, get_jobs_with_latest_evaluation,
    update_job_status, get_job_with_evaluation, delete_job,
    update_job_metadata,
    get_profile, save_profile, get_profile_updated_at,
    save_message, get_messages,
)
from src.fetcher.fetcher import fetch_job_description, fetch_job_details
from src.llm_utils.evaluate import evaluate_job
from src.llm_utils.chat import chat_reply
from src.llm_utils.profile import distill_profile

SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".session")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

ALL_STATUSES = ["saved", "applied", "in-process", "offer", "rejected"]
STATUS_FLOW = {s: [t for t in ALL_STATUSES if t != s] for s in ALL_STATUSES}

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    jobs = get_jobs_with_latest_evaluation()
    return templates.TemplateResponse("index.html", {
        "request": request,
        "jobs": jobs,
        "status_flow": STATUS_FLOW,
    })


@app.post("/jobs/evaluate")
def evaluate(url: str = Form(...)):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
        )
        if not is_job_saved(url):
            details = fetch_job_details(context, url)
            save_job({
                "job_title": details["job_title"],
                "company": details["company"],
                "location": details["location"],
                "link": url,
                "description": details["description"],
                "source": "manual",
            })
        context.close()

    job = get_job_by_link(url)
    needs_edit = not job["company"] or not job["location"] or job["job_title"] == "Unknown"
    if needs_edit:
        return RedirectResponse(f"/jobs/{job['id']}/edit", status_code=303)

    result, chash = evaluate_job(job)
    save_evaluation(job["id"], chash, result)

    return RedirectResponse(f"/jobs/{job['id']}", status_code=303)


@app.get("/jobs/{job_id}/edit", response_class=HTMLResponse)
def job_edit_page(request: Request, job_id: int):
    job = get_job_with_evaluation(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("job_edit.html", {"request": request, "job": job})


@app.post("/jobs/{job_id}/edit")
def job_edit_save(job_id: int, job_title: str = Form(...), company: str = Form(...), location: str = Form(...)):
    update_job_metadata(job_id, job_title, company, location)
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


@app.post("/jobs/{job_id}/status")
def set_status(job_id: int, status: str = Form(...)):
    update_job_status(job_id, status)
    return RedirectResponse("/", status_code=303)


@app.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: int):
    job = get_job_with_evaluation(job_id)
    if not job:
        raise HTTPException(status_code=404)
    return templates.TemplateResponse("job_detail.html", {
        "request": request,
        "job": job,
        "status_flow": STATUS_FLOW,
    })


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
    return templates.TemplateResponse("chat.html", {
        "request": request,
        "messages": messages,
    })


@app.post("/chat/message")
def chat_message(body: ChatRequest):
    messages = body.messages
    if not messages:
        raise HTTPException(status_code=400, detail="No messages provided")

    # Save user message (last in the list)
    last = messages[-1]
    if last["role"] == "user":
        save_message("user", last["content"])

    # Build DB context snapshot
    jobs = get_jobs_with_latest_evaluation()
    if jobs:
        lines = ["| Title | Company | Score | Status |", "| --- | --- | --- | --- |"]
        for j in jobs:
            score = str(j["score"]) if j.get("score") else "—"
            lines.append(f"| {j['job_title']} | {j['company']} | {score} | {j['status']} |")
        lines.append("\n## Job Details")
        for j in jobs:
            score = str(j["score"]) if j.get("score") else "N/A"
            lines.append(f"\n### {j['job_title']} @ {j['company']} (score: {score}, status: {j['status']})")
            if j.get("description"):
                lines.append(j["description"])
        db_context = "\n".join(lines)
    else:
        db_context = "No jobs saved yet."

    reply = chat_reply(messages, db_context, get_profile())
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
    return templates.TemplateResponse("profile.html", {
        "request": request,
        "content": content,
        "updated_at": updated_at,
    })


@app.post("/profile")
def profile_save(content: str = Form(...)):
    save_profile(content)
    return RedirectResponse("/profile", status_code=303)
