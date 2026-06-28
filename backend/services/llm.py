"""Generate a newsletter from topics + articles using OpenRouter.

OpenRouter exposes an OpenAI-compatible chat-completions endpoint, so this is a
plain HTTPS POST — no provider SDK needed.

Free models get rate-limited and saturated constantly, so instead of relying on
one model we try a list of them in order and fall through to the next whenever a
request fails (429, model unavailable, empty response, etc.).

The model returns a small header block (subject lines + preview text) followed by
a `---` separator and the Markdown body, which we parse apart below. This is more
robust with weak free models than asking for strict JSON.
"""

import os
from dataclasses import dataclass, field

import httpx

from models.schemas import Article

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# Tried in order — the first one that succeeds is used. Add/reorder ":free"
# models from https://openrouter.ai/models?max_price=0
MODELS = [
    "google/gemma-4-26b-a4b-it:free",
    "google/gemma-4-31b-it:free",
    "qwen/qwen3-next-80b-a3b-instruct:free",
    "nvidia/nemotron-3-super-120b-a12b:free",
    "nvidia/nemotron-3-ultra-550b-a55b:free",
]

SYSTEM_PROMPT = """You are an expert newsletter writer. You are given a set of \
topics the reader cares about and recent news articles about those topics. \
Write a single cohesive newsletter.

Format your entire response EXACTLY like this — a header block, then a line \
containing only three dashes, then the Markdown body:

SUBJECT: <a punchy email subject line, under 70 characters>
SUBJECT: <a second subject line option>
SUBJECT: <a third subject line option>
PREVIEW: <one-sentence inbox preview/teaser, under 120 characters>
---
## TL;DR
- <3 to 5 bullet points summarizing the whole issue>

## <Topic name>
<2-3 short paragraphs synthesizing the news for this topic>

(repeat a section per topic)

Body rules:
- Start the body with the `## TL;DR` section, then one `## ` section per topic.
- Summarize newsworthy items in your own words; synthesize across articles. Don't \
just list headlines.
- Link to sources inline using the article URLs, e.g. [source](https://...).
- If an article provides an Image URL, embed it once near the top of that topic's \
section as `![](IMAGE_URL)` — use ONLY the provided image URLs, never invent one.
- Only use the provided articles as source material. Do not invent facts, quotes, \
or links. If a topic has thin coverage, say so briefly rather than padding.
- Do NOT use a `---` horizontal rule anywhere in the body; the only `---` is the \
separator after the header block.
- No preamble and no code fences."""


@dataclass
class GeneratedNewsletter:
    """Structured result parsed out of the model's response."""

    markdown: str
    subject_options: list[str] = field(default_factory=list)
    preview_text: str | None = None


class LLMError(RuntimeError):
    """Raised when every model fails or OpenRouter rejects the request."""


def _format_articles(articles: list[Article]) -> str:
    """Render the fetched articles into a compact block for the prompt."""
    lines: list[str] = []
    for art in articles:
        lines.append(f"- Topic: {art.topic}")
        lines.append(f"  Title: {art.title}")
        if art.description:
            lines.append(f"  Summary: {art.description}")
        lines.append(f"  Source: {art.source or 'unknown'}")
        lines.append(f"  URL: {art.url}")
        if art.image_url:
            lines.append(f"  Image: {art.image_url}")
        lines.append("")
    return "\n".join(lines)


def _parse_newsletter(text: str) -> GeneratedNewsletter:
    """Split the model output into subject options, preview text, and body.

    Falls back to treating the whole thing as the body if the expected header
    block isn't present (weak models occasionally skip it)."""
    lines = text.splitlines()

    # Find the separator: the first line that is exactly `---`, near the top.
    sep_idx = next(
        (i for i, line in enumerate(lines[:15]) if line.strip() == "---"), None
    )
    if sep_idx is None:
        return GeneratedNewsletter(markdown=text.strip())

    header = lines[:sep_idx]
    if not any(
        line.strip().upper().startswith(("SUBJECT:", "PREVIEW:")) for line in header
    ):
        return GeneratedNewsletter(markdown=text.strip())

    subjects: list[str] = []
    preview: str | None = None
    for line in header:
        stripped = line.strip()
        upper = stripped.upper()
        if upper.startswith("SUBJECT:"):
            value = stripped.split(":", 1)[1].strip()
            if value:
                subjects.append(value)
        elif upper.startswith("PREVIEW:"):
            preview = stripped.split(":", 1)[1].strip() or None

    body = "\n".join(lines[sep_idx + 1 :]).strip()
    return GeneratedNewsletter(markdown=body, subject_options=subjects, preview_text=preview)


async def _try_model(
    client: httpx.AsyncClient, api_key: str, model: str, messages: list[dict]
) -> str:
    """Call one model. Returns its text, or raises LLMError so the caller can
    fall through to the next model."""
    resp = await client.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            # Optional OpenRouter attribution headers.
            "HTTP-Referer": "http://localhost:5173",
            "X-Title": "Newsletter Generator",
        },
        json={"model": model, "messages": messages, "max_tokens": 4000},
    )

    try:
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        detail = ""
        if isinstance(exc, httpx.HTTPStatusError):
            try:
                body = exc.response.json()
                detail = body.get("error", {}).get("message", "") or str(body)
            except ValueError:
                detail = exc.response.text[:200]
        raise LLMError(f"{exc} {detail}".strip()) from exc

    data = resp.json()
    try:
        content = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError) as exc:
        raise LLMError(f"unexpected response shape: {data}") from exc

    if not content or not content.strip():
        raise LLMError("empty response")
    return content


async def generate_newsletter(
    topics: list[str], articles: list[Article], tone: str
) -> GeneratedNewsletter:
    """Send the topics + articles to OpenRouter, trying each model in MODELS
    until one succeeds. Returns the parsed newsletter."""
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        raise LLMError("OPENROUTER_API_KEY is not set. Add it to backend/.env.")

    user_message = (
        f"Topics: {', '.join(topics)}\n"
        f"Desired tone: {tone}\n\n"
        f"Here are the recent articles to work from:\n\n{_format_articles(articles)}"
    )
    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    errors: list[str] = []
    # Free models can be slow, so allow a generous timeout per attempt.
    async with httpx.AsyncClient(timeout=120.0) as client:
        for model in MODELS:
            try:
                content = await _try_model(client, api_key, model, messages)
                print(f"[llm] generated with {model}")
                return _parse_newsletter(content)
            except (LLMError, httpx.HTTPError) as exc:
                print(f"[llm] {model} failed, trying next: {exc}")
                errors.append(f"{model}: {exc}")

    raise LLMError(
        "All models failed — free models are likely rate-limited right now. "
        "Try again shortly, or edit MODELS in backend/services/llm.py.\n"
        + "\n".join(errors)
    )
