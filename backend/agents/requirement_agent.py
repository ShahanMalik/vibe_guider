"""
requirement_agent.py
====================
Step 1 of the pipeline — understands what the user wants to build.

How it works (anti-hallucination design):
- LLM classifies request intent and decides whether clarification is truly needed
- If needed, LLM proposes up to two architecture-changing questions with options
- Python sanitizes and validates question structure before exposing it to frontend
- Auto decisions are still deterministic defaults from the knowledge loader

Platform/framework clarification:
- When a tool/package request is detected without a named platform or framework,
  the LLM is instructed to ask platform first, then framework — generating the
  options dynamically from its own knowledge of the ecosystem.
"""

import json
import re
from agents.llm import ask_llm
from agents.knowledge_loader import (
    normalize_project_type,
    get_auto_decisions,
    load_section,
)

# ── Intent-detection helpers ──────────────────────────────────────────────────

# Signals that indicate the user wants a package / library / tool recommendation
_PKG_SIGNALS = [
    "package", "library", "plugin", "module", "dependency", "sdk",
    "i want to use", "i want use", "i need a", "i need to use",
    "recommend a", "suggest a", "which package", "which library",
    "best package", "best library", "tool for", "package for", "library for",
    "want to integrate", "how to use", "integrate ", "add ", "use ",
]

# Platform/framework names — if any appear in the query, the cascade can be skipped
def _is_package_request(text: str) -> bool:
    t = text.lower()
    return any(sig in t for sig in _PKG_SIGNALS)


def _platform_named_in_query(text: str) -> bool:
    """Return True if the user appears to have named a specific platform/framework."""
    return bool(
        re.search(
            r"\b(?:using|with|in|on)\s+[A-Za-z][A-Za-z0-9+.#-]*(?:\s+[A-Za-z][A-Za-z0-9+.#-]*)?",
            text or "",
        )
    )


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_json_object(text: str) -> dict:
    clean = re.sub(r"```(?:json)?|```", "", text or "").strip()
    match = re.search(r"\{.*\}", clean, re.DOTALL)
    return json.loads(match.group() if match else clean)


def _sanitize_smart_questions(raw_questions) -> list[dict]:
    if not isinstance(raw_questions, list):
        return []
    sanitized = []
    seen_ids = set()
    for idx, item in enumerate(raw_questions[:2]):
        if not isinstance(item, dict):
            continue
        question_text = str(item.get("question", "")).strip()
        options = item.get("options")
        if not question_text or not isinstance(options, list):
            continue
        if not question_text.endswith("?"):
            question_text = f"{question_text}?"
        option_values = []
        seen_options = set()
        for option in options:
            if not isinstance(option, str):
                continue
            value = option.strip()
            if not value:
                continue
            key = value.lower()
            if key in seen_options:
                continue
            seen_options.add(key)
            option_values.append(value)
            if len(option_values) == 6:
                break
        if len(option_values) < 3:
            continue
        raw_id = str(item.get("id", "")).strip().lower()
        if not re.fullmatch(r"[a-z0-9_-]{3,40}", raw_id):
            raw_id = re.sub(r"[^a-z0-9]+", "_", question_text.lower()).strip("_")[:40]
        if not raw_id:
            raw_id = f"question_{idx + 1}"
        if raw_id in seen_ids:
            raw_id = f"{raw_id}_{idx + 1}"
        seen_ids.add(raw_id)
        sanitized.append({"id": raw_id, "question": question_text, "options": option_values})
    return sanitized


def _is_vague_request(user_query: str) -> bool:
    text = (user_query or "").strip().lower()
    if not text:
        return True
    token_count = len(re.findall(r"\w+", text))
    weak_patterns = ["create app", "build app", "make app", "create an app",
                     "start project", "build project", "please start"]
    specific_signals = ["using", "with", "api", "dashboard", "automation",
                        "pipeline", "mobile", "web", "backend", "model"]
    has_weak = any(p in text for p in weak_patterns)
    has_specific = any(s in text for s in specific_signals)
    if has_weak and token_count <= 14 and not has_specific:
        return True
    if token_count <= 6 and ("app" in text or "project" in text):
        return True
    return False


def _normalize_request_mode(raw_mode: str, user_query: str) -> str:
    value = (raw_mode or "").strip().lower()
    if value in {"recommendation_compare", "recommendation", "compare",
                 "package_recommendation", "tool_recommendation"}:
        return "recommendation_compare"
    if value in {"architecture_guide", "architecture", "build_plan", "implementation_plan"}:
        return "architecture_guide"
    text = (user_query or "").strip().lower()
    rec_signals = ["recommend", "suggest", "which package", "which library", "best package",
                   "best library", "compare", "difference", "vs", "versus", "tool for",
                   "package for", "library for", "integrate", "add ", "use "]
    arc_signals = ["architecture", "folder structure", "project structure",
                   "data flow", "coding steps", "implementation plan", "build"]
    rec_hits = sum(1 for s in rec_signals if s in text)
    arc_hits = sum(1 for s in arc_signals if s in text)
    return "recommendation_compare" if rec_hits >= arc_hits else "architecture_guide"


# ─────────────────────────────────────────────────────────────────────────────
# Platform cascade — fully LLM-driven (no hardcoded options)
# ─────────────────────────────────────────────────────────────────────────────

def _ask_llm_platform_question(user_query: str) -> dict | None:
    """
    Ask the LLM to generate ONE question: 'What platform are you targeting?'
    with ecosystem-appropriate options derived from its own knowledge.
    Returns a sanitized question dict, or None on failure.
    """
    prompt = f"""The user wants: "{user_query}"

They are asking about a package, library, or tool but have not specified a target platform.

Generate exactly ONE clarification question asking what platform they are targeting.
The options must be the most common, real-world platform categories relevant to software development.
Use your own knowledge to decide what the best platform options are.

Return ONLY this JSON (no markdown, no explanation):
{{
    "id": "platform",
    "question": "<ask which platform they are targeting>",
    "options": ["<platform 1>", "<platform 2>", "<platform 3>", "<platform 4>", "<platform 5>"]
}}

Rules:
- Options must be short platform/category names.
- Between 4 and 6 options
- No framework names in this question — only target environment categories
- Real, commonly used options only
"""
    try:
        raw = ask_llm(prompt)
        clean = re.sub(r"```(?:json)?|```", "", raw or "").strip()
        data = json.loads(clean)
        questions = _sanitize_smart_questions([data])
        return questions[0] if questions else None
    except Exception:
        return None


def _ask_llm_framework_question(user_query: str, platform: str) -> dict | None:
    """
    Ask the LLM to generate ONE question: 'Which framework/language are you using?'
    with options tailored to the chosen platform.
    Returns a sanitized question dict, or None on failure.
    """
    prompt = f"""The user wants: "{user_query}"
They have chosen the platform: "{platform}"

Generate exactly ONE clarification question asking which specific framework or programming language
they are using on that platform. Use your own knowledge of the {platform} ecosystem to list
the most popular, real-world frameworks or languages used there.

Return ONLY this JSON (no markdown, no explanation):
{{
    "id": "framework_or_language",
    "question": "<ask which framework or language on {platform}>",
    "options": ["<framework 1>", "<framework 2>", "<framework 3>", "<framework 4>", "<framework 5>"]
}}

Rules:
- Options must be real framework or language names commonly used on {platform}
- Between 4 and 6 options
- Only list frameworks/languages, not packages or libraries
- Use their official/common names exactly as developers write them
"""
    try:
        raw = ask_llm(prompt)
        clean = re.sub(r"```(?:json)?|```", "", raw or "").strip()
        data = json.loads(clean)
        questions = _sanitize_smart_questions([data])
        return questions[0] if questions else None
    except Exception:
        return None


def _handle_platform_cascade(state: dict, user_query: str, user_choices: dict) -> dict:
    """
    Sequential LLM-driven platform → framework clarification for tool/package requests.
    The LLM generates all options dynamically — no hardcoded values.
    """
    platform  = user_choices.get("platform")
    framework = user_choices.get("framework_or_language")

    # ── Step 1: Ask platform ──────────────────────────────────────────────────
    if not platform:
        question = _ask_llm_platform_question(user_query)
        if not question:
            # Fallback: skip cascade and let normal LLM flow handle it
            return None
        state.update({
            "project_type":         "general",
            "request_mode":         "recommendation_compare",
            "project_summary":      f"Finding the best tool/package for: {user_query}",
            "auto_decisions":       {},
            "smart_questions":      [question],
            "clarification_needed": True,
            "requirements":         "",
            "confidence":           0.9,
        })
        return state

    # ── Step 2: Ask framework based on chosen platform ────────────────────────
    if not framework:
        question = _ask_llm_framework_question(user_query, platform)
        if not question:
            return None
        state.update({
            "project_type":         "application",
            "request_mode":         "recommendation_compare",
            "project_summary":      f"Finding the best tool/package for {platform}: {user_query}",
            "auto_decisions":       {"Platform": platform},
            "smart_questions":      [question],
            "clarification_needed": True,
            "requirements":         "",
            "confidence":           0.9,
        })
        return state

    # ── Step 3: Both answered — build requirements and proceed to pipeline ────
    state.update({
        "project_type":         "application",
        "request_mode":         "recommendation_compare",
        "project_summary":      f"Best tool/package for '{user_query}' in {framework} ({platform})",
        "auto_decisions":       {"Platform": platform, "Framework / Language": framework},
        "smart_questions":      [],
        "clarification_needed": False,
        "requirements": (
            f"Project: finding the best tool/package/library for: {user_query}\n"
            f"Type: application\n"
            f"Mode: recommendation_compare\n"
            f"Platform: {platform}\n"
            f"Framework/Language: {framework}\n"
        ),
        "confidence": 0.95,
    })
    return state


def _run_dynamic_clarification(state: dict, user_query: str, user_choices: dict) -> dict | None:
    """
    Run dynamic clarification pipelines based on intent and missing high-impact choices.
    This keeps clarification extensible without hardcoding one-off request scenarios.
    """
    if _is_package_request(user_query) and not _platform_named_in_query(user_query):
        return _handle_platform_cascade(state, user_query, user_choices)
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Main agent entry point
# ─────────────────────────────────────────────────────────────────────────────

def requirement_agent(state):

    user_query   = state.get("user_query", "")
    user_choices = state.get("user_choices", {})
    current_questions = state.get("smart_questions", []) or []

    # ── If clarification questions are already pending, wait for all answers ──
    if user_choices and current_questions:
        remaining_questions = [
            question for question in current_questions
            if str(question.get("id", "")).strip() not in user_choices
        ]
        if remaining_questions:
            state["smart_questions"] = remaining_questions
            state["clarification_needed"] = True
            state["confidence"] = 0.95
            return state

        # All current questions are answered. Continue dynamic clarification flows
        # (for example: platform -> framework) before finalizing requirements.
        dynamic_state = _run_dynamic_clarification(state, user_query, user_choices)
        if dynamic_state is not None:
            return dynamic_state

        request_mode = _normalize_request_mode(state.get("request_mode", ""), user_query)
        choices_str = "\n".join(
            f"  - {k.replace('_', ' ').title()}: {v}" for k, v in user_choices.items()
        )
        auto_str = "\n".join(
            f"  - {k.replace('_', ' ').title()}: {v}"
            for k, v in state.get("auto_decisions", {}).items()
        )
        state["requirements"] = (
            f"Project: {state.get('project_summary', user_query)}\n"
            f"Type: {state.get('project_type', 'general')}\n"
            f"Mode: {request_mode}\n"
            f"Auto-decided:\n{auto_str or '  None'}\n"
            f"User selected:\n{choices_str or '  None'}"
        )
        state["request_mode"] = request_mode
        state["smart_questions"] = []
        state["clarification_needed"] = False
        state["confidence"] = 0.95
        return state

    # ── Platform cascade: intercepts tool/package requests without a platform ─
    # Only triggers when no platform/framework is already named in the query.
    result = _run_dynamic_clarification(state, user_query, user_choices)
    if result is not None:
        return result
    # If dynamic clarification returned None (for example LLM failed), fall through to normal flow

    # ── Path A: First request — LLM detection and normalization ───────────────
    requirement_policy = load_section("Requirement Agent Instructions")
    is_vague = _is_vague_request(user_query)

    detection_prompt = f"""You are a senior requirements analyst.
Follow the requirement policy below and return ONLY a JSON object.

Requirement policy:
{requirement_policy or 'Use clear, high-impact, architecture-changing clarification only.'}

User request: "{user_query}"
is_vague_request: {str(is_vague).lower()}

Return ONLY this JSON (no markdown, no explanation):
{{
    "normalized_query": "<rewrite the user request in clear, correct language while preserving intent>",
    "project_type": "<one of: application | service | data | automation | general>",
    "request_mode": "<one of: architecture_guide | recommendation_compare>",
    "project_summary": "<one clear sentence describing exactly what the user wants to build>",
    "clarification_needed": <true or false>,
    "clarification_reason": "<empty string if not needed; concrete reason if needed>",
    "smart_questions": [
        {{
            "id": "<snake_case_id>",
            "question": "<architecture-changing question>",
            "options": ["<option 1>", "<option 2>", "<option 3>"]
        }}
    ]
}}

Classification guide:
- application: interactive software product with a user-facing interface
- service: backend service, API, or microservice
- data: analytical, data-processing, or model-driven workload
- automation: task automation, job orchestration, or workflow tooling
- general: general question, not a build request

Request mode guide:
- architecture_guide: user asks for architecture, project design, implementation flow, or coding steps
- recommendation_compare: user asks to suggest/compare packages, tools, libraries, approaches, or alternatives
  NOTE: "integrate X", "use X package", "add X library", "which tool for X" → always recommendation_compare

Question policy:
- Ask 0-2 questions maximum.
- Ask a question ONLY if its answer would significantly change architecture, dependency choices,
  data flow, or deployment strategy.
- Default: clarification_needed = false unless a missing decision is architecture-critical.
- Never ask about editor/OS/tool preference or other low-impact details.
- Keep each question concise with 3-6 concrete, real-world options.

If is_vague_request is true:
- clarification_needed must be true.
- Ask exactly 2 questions.
- Question 1 must clarify product kind.
- Question 2 must clarify primary purpose.

Output quality rules:
- Questions must be plain and unambiguous.
- Each question must contain one decision only.
- Options must be distinct and easy to compare.
- Use the most common real-world option names developers actually use.
- Correct obvious typos, shorthand, and broken phrasing when the intent is still clear.
- If the request is unclear, prefer asking the minimum number of high-value questions over guessing.
"""

    result = ask_llm(detection_prompt)

    try:
        data = _extract_json_object(result)
    except (json.JSONDecodeError, AttributeError):
        data = {
            "project_type": "general",
            "project_summary": user_query,
            "clarification_needed": False,
            "clarification_reason": "",
            "smart_questions": [],
        }

    raw_type        = data.get("project_type", "general")
    project_type    = normalize_project_type(raw_type)
    request_mode    = _normalize_request_mode(data.get("request_mode", ""), user_query)
    normalized_query = str(data.get("normalized_query", user_query)).strip() or user_query
    project_summary = str(data.get("project_summary", normalized_query)).strip() or normalized_query
    auto_decisions  = get_auto_decisions(project_type)

    smart_questions      = _sanitize_smart_questions(data.get("smart_questions", []))
    clarification_reason = str(data.get("clarification_reason", "")).strip()
    clarification_needed = (
        bool(data.get("clarification_needed", False))
        and len(smart_questions) > 0
        and len(clarification_reason) >= 12
    )
    if is_vague and len(smart_questions) > 0:
        clarification_needed = True

    state["project_type"]         = project_type
    state["request_mode"]         = request_mode
    state["project_summary"]      = project_summary
    state["auto_decisions"]       = auto_decisions
    state["smart_questions"]      = smart_questions
    state["requirements"]         = (
        f"Project type: {project_type}\n"
        f"Request mode: {request_mode}\n"
        f"Summary: {project_summary}\n"
        f"Auto-decided: {auto_decisions}"
    )
    state["clarification_needed"] = clarification_needed
    state["confidence"]           = 0.95
    return state
