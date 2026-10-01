#!/usr/bin/env python3
import os
import sys
import traceback
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

ROOT = Path(__file__).resolve().parent
app = Flask(__name__, static_folder=None)

MAX_MESSAGE_LEN = 8000
MAX_HISTORY_TURNS = 8

SYSTEM_PROMPT = """You are the support assistant embedded on the CodeForge marketing website.
CodeForge is "the end-to-end platform for Python3 teams" — zero-config environments, instant
dependency resolution, CI pipelines (lint/type-check with mypy & ruff, testing), and one-command
deploys for APIs, workers and ETL jobs.

Key facts about CodeForge you can use when answering:
- Native Py3 Runtime: zero-config interpreters/virtualenvs pinned to pyproject.toml.
- Dependency Forge: a dependency resolver that locks hundreds of deps and detects conflicts.
- Pipeline Studio: lint/type-check/test on every push, pipelines written in Python (no YAML).
- Instant Deploy: containerized, autoscaled deploys from laptop to prod in under 60 seconds.
- Package Vault: a private, PyPI-compatible package registry with version history and audit trails.
- Live Profiling: CPU/memory/async bottleneck tracing on running Python processes.
- Pricing: Forge Free ($0/mo, 1 project), Forge Pro ($29/user/mo, unlimited projects, private
  package vault, priority support), Forge Enterprise (custom, SSO/SAML, on-prem/VPC, custom SLAs).

Answer visitor questions about CodeForge's product, pricing and how it works. Be concise (2-4
sentences), friendly and factual. If you don't know something specific (e.g. exact SLAs, legal
terms, account-specific details), say so plainly and suggest they use the "Talk to Sales" /
contact option — do not invent details. Never discuss anything unrelated to CodeForge."""


def get_anthropic_client():
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    import anthropic

    return anthropic.Anthropic(api_key=api_key)


@app.route("/")
@app.route("/<path:path>")
def static_files(path="index.html"):
    full_path = (ROOT / path).resolve()
    if ROOT not in full_path.parents and full_path != ROOT:
        return jsonify({"error": "not found"}), 404
    if full_path.is_dir() or not full_path.exists():
        path = "index.html"
    return send_from_directory(ROOT, path)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(silent=True) or {}
    message = str(data.get("message", "")).strip()
    history = data.get("history", [])

    if not message:
        return jsonify({"error": "message is required"}), 400
    if len(message) > MAX_MESSAGE_LEN:
        return jsonify({"error": f"message too long (max {MAX_MESSAGE_LEN} chars)"}), 400
    if not isinstance(history, list):
        history = []

    client = get_anthropic_client()
    if client is None:
        return (
            jsonify(
                {
                    "error": "chat_not_configured",
                    "reply": (
                        "Our AI assistant isn't connected yet — please use the \"Talk to Sales\" "
                        "link below and our team will get back to you directly."
                    ),
                }
            ),
            503,
        )

    messages = []
    for turn in history[-MAX_HISTORY_TURNS:]:
        role = turn.get("role")
        content = str(turn.get("content", ""))[:MAX_MESSAGE_LEN]
        if role in ("user", "assistant") and content:
            messages.append({"role": role, "content": content})
    messages.append({"role": "user", "content": message})

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=400,
            system=SYSTEM_PROMPT,
            messages=messages,
        )
        reply = "".join(
            block.text for block in response.content if getattr(block, "type", None) == "text"
        ).strip()
        if not reply:
            reply = "Sorry, I didn't catch that — could you rephrase your question?"
        return jsonify({"reply": reply})
    except Exception as exc:
        print(f"{type(exc).__name__}: {exc}", file=sys.stderr)
        traceback.print_exc()
        return (
            jsonify(
                {
                    "error": "chat_failed",
                    "reply": (
                        "Something went wrong on our side answering that — please try again in "
                        "a moment or reach out via \"Talk to Sales\"."
                    ),
                }
            ),
            502,
        )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port)
