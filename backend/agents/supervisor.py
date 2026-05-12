"""
supervisor.py
=============
Final synthesizer: combines all agent outputs into one polished guide.
Uses the LLM's ecosystem knowledge while staying inside the user's chosen stack.
"""

import re

from agents.llm import ask_llm

_DECISION_DISCUSSION_SIGNALS = {
    "why",
    "why not",
    "why didn't",
    "why did not",
    "instead",
    "rather than",
    "alternative",
    "alternatives",
    "compare",
    "comparison",
    "vs",
    "versus",
    "tradeoff",
    "trade-off",
    "can we use",
    "could we use",
    "should we use",
    "what about",
    "not recommended",
}

_DOWNLOAD_PACKAGE_SIGNALS = {
    "zip",
    "download",
    "downloadable",
    "bundle",
    "archive",
    "package it",
    "code in zip",
    "zip file",
}


def _infer_named_choices(user_query: str) -> dict:
    """Surface important stack choices named directly in the original request."""
    text = (user_query or "").strip()
    match = re.search(
        r"\b(?:using|with|in|on)\s+([A-Za-z][A-Za-z0-9+.#-]*(?:\s+[A-Za-z][A-Za-z0-9+.#-]*)?)",
        text,
    )
    if not match:
        return {}

    named_stack = match.group(1).strip(" .,!?:;")
    if not named_stack:
        return {}
    return {"named_stack": named_stack}


def _has_precise_stack_choice(choices: dict, user_query: str) -> bool:
    """Detect whether the user already selected or named concrete stack pieces."""
    precise_choice_keys = (
        "framework",
        "language",
        "database",
        "backend",
        "auth",
        "hosting",
        "payment",
        "state",
        "stack",
        "named_stack",
    )
    if any(
        key in str(choice_key).lower()
        for choice_key in (choices or {})
        for key in precise_choice_keys
    ):
        return True

    return False


def _wants_decision_discussion(user_query: str) -> bool:
    """Return True when the user is asking for reasoning, alternatives, or pushback."""
    text = (user_query or "").lower()
    return any(signal in text for signal in _DECISION_DISCUSSION_SIGNALS)


def _wants_downloadable_package(user_query: str) -> bool:
    """Return True when the user wants a zip-ready code bundle or downloadable artifact."""
    text = (user_query or "").lower()
    return any(signal in text for signal in _DOWNLOAD_PACKAGE_SIGNALS)


def supervisor(state):
    project_type = state.get("project_type", "general")
    request_mode = state.get("request_mode", "architecture_guide")
    user_query = state.get("user_query", "")

    auto = state.get("auto_decisions", {})
    choices = state.get("user_choices", {})
    visible_choices = {**_infer_named_choices(user_query), **choices}

    external_resources = (state.get("external_resources") or "").strip()
    if not external_resources:
        external_resources = "_No relevant public links found from web search._"

    auto_str = "\n".join(
        f"- **{k.replace('_', ' ').title()}**: {v}"
        for k, v in auto.items()
    ) if auto else "_None_"

    choices_str = "\n".join(
        f"- **{k.replace('_', ' ').title()}**: {v}"
        for k, v in visible_choices.items()
    ) if visible_choices else "_None specified_"

    precise_stack = _has_precise_stack_choice(visible_choices, user_query)
    wants_decision_discussion = _wants_decision_discussion(user_query)
    wants_downloadable_package = _wants_downloadable_package(user_query)

    if wants_decision_discussion:
        output_structure = """Synthesize the above into ONE polished markdown response for a user who is asking about reasoning, alternatives, or a different opinion.

Use headings that match the user's exact question. Do not always use fixed headings like "Why This Direction", "Why Avoided", or "Alternative Approaches".

Required content:
- Directly answer the user's challenge or alternative.
- Re-evaluate the earlier recommendation instead of defending it automatically.
- If the user's simpler option is enough for the project scope, say that clearly and recommend the simpler option.
- Compare only the relevant options the user mentioned or the agent previously recommended.
- Give a practical recommendation and short tradeoff explanation.
- If useful, include a small comparison table.
- Keep the answer concise; do not repeat the full architecture guide unless the user asks for it.
"""
    elif request_mode == "recommendation_compare":
        output_structure = """Synthesize the above into ONE polished markdown response, structured like this:

## Recommendation Overview
Brief context summary in 1-2 sentences.

## Candidate Approaches
Short bullet list of viable options considered.

## Comparison Matrix
A clear table with practical comparison criteria.
Suggested columns:
Option | Performance | Complexity | Maintenance | Compatibility | Best For

## Recommended Option
Pick one option and justify the decision for this user's goal.
Add 1-2 bullets explaining when to choose an alternative.

## Implementation Starter Steps
Provide 3-5 concrete steps to start with the recommended option.

## Watch Out For
Include the most relevant caveats from the risk agent.
"""
    elif wants_downloadable_package:
        output_structure = """Synthesize the above into ONE polished markdown response for a zip-ready code delivery request.

Do NOT include decision-framing sections such as "Why This Direction", "Why Avoided", "Alternative Approaches", or "Comparison Matrix" unless the user explicitly asks for them.

Use this structure:

## [Specific Project Name] - Downloadable Bundle
Brief intro: what is included and why this bundle is narrow enough to download directly.

## Decided For You
List the auto-decisions from `auto_str` with a short reason for each.

## Your Choices
List visible choices from `choices_str`.

## Key Packages
Use one compact markdown table with columns: Package | Role | Why it matters | Notes.
Only include packages that apply given the user's choices.
If stack/framework/language is not explicitly selected, do NOT name concrete packages.

## Project Structure
Show the exact folder tree for the bundle, but include only the essential files and folders.
Keep the structure framework-neutral unless the user explicitly names a framework or platform.
Omit boilerplate or generated folders unless the user explicitly asks for them.

## How It Works
Explain the data flow and how the included files work together.

## First 5 Coding Steps
Numbered file-level actions only.
Do not include shell commands or package installation commands.

## Downloadable Bundle
State the suggested zip name and list the exact files and folders to include in the archive.
Make it obvious that the bundle is ready to be zipped and downloaded.

## Watch Out For
The most relevant gotchas from the risk agent, formatted as bullets.
"""
    else:
        output_structure = """Synthesize the above into ONE polished markdown response for a basic architecture/build request.

Do NOT include decision-framing sections such as "Why This Direction", "Why Avoided", "Alternative Approaches", "Comparison Matrix", "When NOT to Use This", or "When to Use This".

Use this structure:

## [Specific Project Name] - Architecture Guide
Brief intro: what we're building and the key technical approach.

## Decided For You
List the auto-decisions from `auto_str` with a short reason for each.

## Your Choices
List visible choices from `choices_str`. Do not output "None specified" when the user named a framework, platform, or integration in the request.

## Key Packages
Use one compact markdown table with columns: Package | Role | Why it matters | Notes.
Only include packages that apply given the user's choices.
Do not list two packages for the same job unless both are truly required.
For Notes, use "current stable" or a short setup caveat; do not guess stale exact versions.
If stack/framework/language is not explicitly selected, do NOT name concrete packages.
In that case, keep the heading as "Key Packages" but use a compact table with columns:
Dependency Role | Why it matters | Selection Criteria | Notes.

## Project Structure
The exact folder tree from the architecture agent output, formatted cleanly.

## How It Works
Data flow explanation specific to this project.
If stack is explicit, tie it to the selected database/auth/framework/runtime.
If stack is not explicit, keep it stack-agnostic and describe responsibilities only.
2-3 focused paragraphs.

## First 5 Coding Steps
Numbered file-level actions only.
Do not include shell commands or package installation commands.

## Watch Out For
The most relevant gotchas from the risk agent, formatted as bullets.
"""

    prompt = f"""You are the final synthesizer for a professional project advisor AI.
Your job is to combine the agent outputs below into one polished, accurate guide.
Use the agent outputs as your primary source. Fill gaps using your own knowledge
of the user's ecosystem, but stay within the user's chosen platform and stack.

PROJECT
Building: "{state.get('project_summary', state.get('user_query', ''))}"
Type: {project_type}
Request mode: {request_mode}
Precise stack already named: {precise_stack}
User is asking for decision reasoning/alternatives: {wants_decision_discussion}

Decided automatically:
{auto_str}

Visible user choices (explicit answers plus stack named in the request):
{choices_str}

AGENT OUTPUTS
[Architecture Agent]:
{state.get('architecture_advice', '')}

[Package Agent]:
{state.get('tool_advice', '')}

[Risk Agent]:
{state.get('risk_review', '')}

YOUR TASK - Write the final response
{output_structure}

RULES:
- Stay within the user's chosen platform and framework; do not switch ecosystems.
- Treat user-named stack items in the original request as selected choices, even if user_choices is empty.
- Do not claim a framework, backend, or state-management library was chosen unless it appears in the user request, visible choices, or agent outputs.
- Do not mix competing packages for the same responsibility.
- Key Packages must be a compact markdown table using Package | Role | Why it matters | Notes.
- If precise stack is not named, keep the answer framework-agnostic and package-agnostic (no concrete framework/package/library names).
- When stack is not named, Key Packages should be a compact decision table using Dependency Role | Why it matters | Selection Criteria | Notes.
- First coding steps must be file-level implementation actions, not shell commands or package installation commands.
- For basic architecture/build requests, do not include reasoning/comparison headings.
- For reasoning/alternative follow-ups, choose headings that match the user's scenario instead of reusing fixed headings every time.
- Keep external links curated-looking: each link should have a clear title and one short reason.
- Use clean markdown throughout.
- If the user asks for a downloadable code package, zip output, or archive-ready bundle,
  prefer the downloadable bundle structure and keep the project tree narrow enough to archive
  directly.
"""

    stream_writer = state.get("_stream_writer")
    base_answer = ask_llm(prompt, stream_writer=stream_writer).rstrip()
    links_section = f"\n\n## Helpful External Links\n{external_resources}"
    if stream_writer is not None:
        stream_writer(links_section)
    state["final_answer"] = f"{base_answer}{links_section}"
    return state
