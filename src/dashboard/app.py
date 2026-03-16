# src/dashboard/app.py
import os
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from playwright.sync_api import sync_playwright
from src.db.database import (
    init_db, is_job_saved, save_job, get_job_by_link,
    get_job_id, save_evaluation, get_jobs_with_latest_evaluation
)
from src.fetcher.fetcher import fetch_job_description
from src.evaluator.evaluator import evaluate_job

SESSION_DIR = os.path.join(os.path.dirname(__file__), "..", "..", ".session")
TEMPLATES_DIR = os.path.join(os.path.dirname(__file__), "templates")

app = FastAPI()
templates = Jinja2Templates(directory=TEMPLATES_DIR)


@app.on_event("startup")
def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    jobs = get_jobs_with_latest_evaluation()
    return templates.TemplateResponse("index.html", {"request": request, "jobs": jobs})


@app.post("/jobs/evaluate")
def evaluate(url: str = Form(...)):
    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
        )
        if not is_job_saved(url):
            description = fetch_job_description(context, url)
            save_job({
                "job_title": "Unknown",
                "company": "Unknown",
                "location": "Unknown",
                "link": url,
                "description": description,
                "source": "manual",
            })
        context.close()

    job = get_job_by_link(url)
    result, chash = evaluate_job(job)
    save_evaluation(get_job_id(url), chash, result)

    return RedirectResponse("/", status_code=303)
