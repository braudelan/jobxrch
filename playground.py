"""
playground.py — hands-on experimentation for each jobxrch module.

Usage:
    python playground.py           # run with flags below
    python -i playground.py        # then explore objects interactively in REPL

Toggle sections by flipping the RUN_* flags.
Sections are ordered cheapest → most expensive (no I/O → DB → LLM → browser).
"""

import sys

sys.path.insert(0, ".")

# ── Toggle which sections run ────────────────────────────────────────────────
RUN_PARSER = True  # pure logic, no I/O
RUN_DB = True  # SQLite only
RUN_EVALUATE = False  # LLM call (costs tokens)
RUN_CHAT = False  # LLM call (costs tokens)
RUN_DISTILL = False  # LLM call (costs tokens)
RUN_FETCHER = False  # requires Playwright + LinkedIn browser session
# ────────────────────────────────────────────────────────────────────────────


# ── Sample data (reused across sections) ────────────────────────────────────
SAMPLE_JOB = {
    "job_title": "Staff Engineer",
    "company": "Acme Corp",
    "location": "Remote",
    "link": "https://www.linkedin.com/jobs/view/1234567890",
    "description": (
        "We are looking for a Staff Engineer to lead architecture decisions "
        "across our distributed systems. You will mentor engineers, drive "
        "technical strategy, and work closely with product. Strong Python and "
        "systems design experience required. 8+ years experience preferred."
    ),
    "source": "manual",
}

SAMPLE_PROFILE = (
    "I have 10 years of backend experience, primarily Python and Go. "
    "I care about engineering culture and mentorship. "
    "I want a Staff or Principal role. Remote strongly preferred. "
    "Dealbreakers: on-call for ops issues, no-eng culture."
)


# ── 1. PARSER ────────────────────────────────────────────────────────────────
if RUN_PARSER:
    print("\n" + "=" * 60)
    print("PARSER — clean_job_card_data")
    print("=" * 60)
    from src.scraper.parser import clean_job_card_data

    raw_text = "Staff Engineer\nAcme Corp\nRemote\nPromoted\nActively recruiting"
    raw_link = "https://www.linkedin.com/jobs/view/1234567890?refId=abc&trackingId=xyz"

    result = clean_job_card_data(raw_text, raw_link)
    print("Input text lines:", raw_text.split("\n"))
    print("Output:", result)


# ── 2. DB ────────────────────────────────────────────────────────────────────
if RUN_DB:
    print("\n" + "=" * 60)
    print("DB — init, save_job, query")
    print("=" * 60)
    from src.db.database import (
        init_db,
        save_job,
        is_job_saved,
        get_job_by_link,
        get_all_jobs,
        get_unevaluated_jobs,
        get_profile,
        get_messages,
    )

    init_db()
    print("DB initialized.")

    # Check if our sample job is already saved
    exists = is_job_saved(SAMPLE_JOB["link"])
    print(f"Sample job already in DB: {exists}")

    # List all jobs with their latest evaluation
    jobs = get_all_jobs()
    print(f"Jobs in DB: {len(jobs)}")
    for j in jobs[:5]:  # show first 5
        score = j.get("score") or "—"
        print(f"  [{score}] {j['job_title']} @ {j['company']} ({j['status']})")

    # Profile and chat history
    profile = get_profile()
    print(
        f"\nProfile ({len(profile)} chars): {profile[:100]}{'...' if len(profile) > 100 else ''}"
    )

    messages = get_messages()
    print(f"Chat messages in DB: {len(messages)}")


# ── 3. EVALUATE ──────────────────────────────────────────────────────────────
if RUN_EVALUATE:
    print("\n" + "=" * 60)
    print("EVALUATE — evaluate_job (LLM call)")
    print("=" * 60)
    from src.llm_utils.evaluate import evaluate_job, _build_prompt, profile_hash

    # Inspect the prompt without making an LLM call
    prompt = _build_prompt(SAMPLE_JOB, SAMPLE_PROFILE)
    print("--- Prompt preview (first 500 chars) ---")
    print(prompt[:500])
    print("...")

    # Uncomment to actually call the LLM:
    # result, chash = evaluate_job(SAMPLE_JOB)
    # print(f"\nScore: {result.score}")
    # print(f"Summary: {result.summary}")
    # print(f"Assessment:\n{result.assessment}")
    # print(f"Criteria hash: {chash}")


# ── 4. CHAT ──────────────────────────────────────────────────────────────────
if RUN_CHAT:
    print("\n" + "=" * 60)
    print("CHAT — chat_reply (LLM call)")
    print("=" * 60)
    from src.llm_utils.chat import chat_reply

    messages = [
        {"role": "user", "content": "Which of my saved jobs has the best culture fit?"},
    ]
    db_context = (
        "| Title | Company | Score | Status |\n"
        "| --- | --- | --- | --- |\n"
        "| Staff Engineer | Acme Corp | 8 | saved |\n"
        "| Senior SWE | Initech | 5 | applied |"
    )

    reply = chat_reply(messages, db_context, SAMPLE_PROFILE)
    print("Reply:", reply)


# ── 5. PROFILE DISTILL ───────────────────────────────────────────────────────
if RUN_DISTILL:
    print("\n" + "=" * 60)
    print("PROFILE DISTILL — distill_profile (LLM call)")
    print("=" * 60)
    from src.llm_utils.profile import distill_profile

    conversation = [
        {
            "role": "user",
            "content": "I really don't want to deal with on-call rotations anymore.",
        },
        {
            "role": "assistant",
            "content": "Noted — I'll factor that in when evaluating ops-heavy roles.",
        },
        {
            "role": "user",
            "content": "Also I'd prefer a company with under 500 people if possible.",
        },
    ]

    updated = distill_profile(SAMPLE_PROFILE, conversation)
    print("Updated profile:")
    print(updated)


# ── 6. FETCHER ───────────────────────────────────────────────────────────────
if RUN_FETCHER:
    print("\n" + "=" * 60)
    print("FETCHER — fetch_job_description (Playwright + browser)")
    print("=" * 60)
    import os
    from playwright.sync_api import sync_playwright
    from src.scraper.fetcher import fetch_job_details

    SESSION_DIR = os.path.join(os.path.dirname(__file__), ".session")
    URL = "https://www.linkedin.com/jobs/view/1234567890"  # replace with a real URL

    with sync_playwright() as p:
        context = p.chromium.launch_persistent_context(
            user_data_dir=SESSION_DIR,
            headless=False,
        )
        details = fetch_job_details(context, URL)
        context.close()

    print("Fetched details:")
    for k, v in details.items():
        print(f"  {k}: {str(v)[:120]}")
