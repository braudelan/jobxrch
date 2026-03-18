# src/llm_utils/profile.py
import anthropic
import os


def distill_profile(existing_profile: str, messages: list[dict]) -> str:
    """Distill preference signals from conversation into an updated profile."""
    conversation_text = "\n".join(
        f"{m['role'].upper()}: {m['content']}" for m in messages
    )

    prompt = f"""You are updating a candidate's career profile based on a recent conversation.

Current profile:
{existing_profile if existing_profile.strip() else "(empty)"}

Recent conversation:
{conversation_text}

Extract any new preferences, constraints, goals, or signals from the conversation and merge them into the profile.
- Preserve all existing content
- Add or refine based on what you learned from the conversation
- Be specific and concrete — avoid vague language
- Write in first person from the candidate's perspective
- Keep it concise (aim for 3-6 sentences or bullet points)

Return only the updated profile text, nothing else."""

    client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    response = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text.strip()
