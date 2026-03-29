# src/llm_utils/chat.py
import importlib
import os

from src.db.database import get_profile, get_all_jobs, get_job
from src.llm_utils.context import format_job_list, format_job
from src.llm_utils.search import get_search_fn


_SEARCH_WEB_TOOL = {
    "name": "search_web",
    "description": (
        "Search the web for up-to-date information about companies, roles, industries, "
        "or anything else that would help give better career advice. "
        "Use this whenever the user asks about a specific company you're unfamiliar with."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query to run.",
            }
        },
        "required": ["query"],
    },
}

_GET_JOB_LIST_TOOL = {
    "name": "get_job_list",
    "description": (
        "Get a summary of all jobs in the user's job list, including ID, title, company, "
        "AI fit score, and current status. Use this when the user asks about their job list, "
        "wants to compare roles, or needs to know which jobs are saved."
    ),
    "input_schema": {
        "type": "object",
        "properties": {},
    },
}

_GET_JOB_DETAILS_TOOL = {
    "name": "get_job_details",
    "description": (
        "Retrieve the full job description and AI assessment for a specific job. "
        "Use this when the user asks about the details of a role — requirements, responsibilities, etc."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "job_id": {
                "type": "integer",
                "description": "The job ID from the job list.",
            }
        },
        "required": ["job_id"],
    },
}


def _load_provider():
    provider_name = os.environ.get("LLM_PROVIDER", "anthropic")
    return importlib.import_module(f"src.llm_utils.providers.{provider_name}")


def _build_system_prompt(
    profile: str,
    static_blocks: list[str] = [],
    tool_hints: list[str] = [],
) -> str:
    """Assemble the system prompt from various pieces of context and instructions."""
    role = "You are a helpful career coach assistant for a job seeker."
    tone = "Be direct, specific, and conversational."
    profile_string = f"Here is what you know about the candidate:\n {profile}" 
    parts = [
        role, 
        tone, 
        profile_string, 
        *static_blocks
    ]
    if tool_hints:
        parts.extend(tool_hints)
    return "\n\n".join(parts)


def chat_reply(messages: list[dict]) -> str:
    """General chat — no static job context. LLM fetches job data on demand via tools."""
    profile = get_profile()
    search_fn = get_search_fn()

    tool_handlers = {
        "get_job_list": lambda _inp: format_job_list(get_all_jobs()),
        "get_job_details": lambda inp: (
            format_job(j) if (j := get_job(inp["job_id"])) else f"No job found with ID {inp['job_id']}."
        ),
    }
    tools = [_GET_JOB_LIST_TOOL, _GET_JOB_DETAILS_TOOL]
    tool_hints = ["Use the get_job_list tool to see the user's saved jobs, and get_job_details to fetch a specific role."]

    if search_fn:
        tool_handlers["search_web"] = lambda inp: search_fn(inp["query"])
        tools.append(_SEARCH_WEB_TOOL)
        tool_hints.append("Use the search_web tool for up-to-date information about companies or roles.")

    system = _build_system_prompt(
        profile,
        static_blocks=["Help them think through their job search, discuss specific roles, and give honest career advice."],
        tool_hints=tool_hints,
    )
    return _load_provider().chat(system, messages, tools, tool_handlers)


def job_chat_reply(job_id: int, messages: list[dict]) -> str:
    """Job-specific chat — pre-loads the target job as static context."""
    profile = get_profile()
    search_fn = get_search_fn()
    job = get_job(job_id)
    job_details = format_job(job) if job else f"No job found with ID {job_id}."

    tool_handlers = {}
    tools = []
    tool_hints = []

    if search_fn:
        tool_handlers["search_web"] = lambda inp: search_fn(inp["query"])
        tools.append(_SEARCH_WEB_TOOL)
        tool_hints.append("Use the search_web tool for up-to-date information about this company or role.")

    system = _build_system_prompt(
        profile,
        static_blocks=[
            f"The user is discussing this specific role:\n\n{job_details}",
            "Help them evaluate this role, prepare for interviews, or think through whether it's a good fit.",
        ],
        tool_hints=tool_hints,
    )
    return _load_provider().chat(system, messages, tools or None, tool_handlers or None)
