"""
tool_agent.py
=============
Recommends tools/packages/libraries for the user's exact stack.

The agent uses the LLM's own knowledge of the ecosystem, guided by the
agent instructions (which define quality standards and output format).
The knowledge base provides behavioral instructions only — not a list of
allowed packages. This allows the agent to correctly recommend packages
for the tech stack the user specifies.
"""

from agents.llm import ask_llm
from agents.knowledge_loader import get_domain_knowledge, load_section


def tool_agent(state):

    project_type = state.get("project_type", "general")
    request_mode = state.get("request_mode", "architecture_guide")

    # Behavioral instructions (NOT a technology whitelist)
    tool_instructions = load_section("Tool Agent Instructions")
    domain_profile    = get_domain_knowledge(project_type)

    auto    = state.get("auto_decisions", {})
    choices = state.get("user_choices",   {})

    auto_str    = "\n".join(f"  - {k}: {v}" for k, v in auto.items())    or "  None"
    choices_str = "\n".join(f"  - {k}: {v}" for k, v in choices.items()) or "  None"

    if request_mode == "recommendation_compare":
        mode_task = """You are in package/tool comparison mode.

## 🧩 Candidate Packages
Identify 3–5 real, widely-used packages/libraries that solve this specific problem
in the user's exact framework/language. Use your knowledge of the ecosystem.

## ⚖️ Comparison Matrix
Create a table with these columns:
Package | Popularity / Stars | Maintenance | Performance | Ease of Integration | Best For

## ✅ Recommended Choice
- Pick ONE package as the primary recommendation.
- Explain why it best fits the user's exact stack and goal.
- Add 1–2 bullets: "When to choose an alternative".

## 🚀 Quick Start
- Show the appropriate installation or dependency setup step for the user's chosen technology and package manager.
- Give 3–5 concrete implementation steps specific to the user's chosen technology stack.
- Include a minimal code snippet if helpful.
"""
    else:
        mode_task = """Select the most relevant packages/dependencies for this specific project.

For each package:
- Exact package name as it appears in the official package registry
- Role within the project
- Why it matters within THIS specific project (not generic)
- Any important setup note for this stack

Group by category (Core / AI / Data / Networking / UI / Testing — use what fits).
Only list packages that are directly needed. Skip packages the user's framework already bundles.
Prefer a compact table shape that the final answer can render as:
Package | Role | Why it matters | Notes
Avoid overlapping alternatives in the final package list:
- Choose one primary state-management approach.
- Choose one primary HTTP/API client unless the project clearly needs both.
- Do not add UI helper packages for simple widgets the framework can build directly.
Complexity-fit rule:
- For a simple, low-scope project with no shared state across components or modules,
  prefer the built-in mechanisms of the user's chosen technology.
- Do not recommend an external state-management library unless shared state, asynchronous
  workflows, coordination across multiple components, real-time streams, or the user's
  explicit request makes it worthwhile.

If the platform/framework/language is not clearly specified in the user's request and choices:
- Do NOT output concrete package names.
- Output a technology-neutral dependency planning outline instead, as a compact table:
    Dependency Role | Why it matters | Selection Criteria | Notes
- Keep recommendations generic and decision-oriented until the stack is confirmed.
"""

    prompt = f"""You are an expert package and dependency advisor for software development.
Your job is to recommend real, accurate packages for the user's exact technology stack.

Use your knowledge of the ecosystem to recommend the best packages.
The instructions below define the quality standard and output format.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{tool_instructions}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User's goal: "{state.get('project_summary', state.get('user_query', ''))}"
Project type: {project_type}
Request mode: {request_mode}

Auto-decided context:
{auto_str}

User-selected stack/integrations:
{choices_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{mode_task}

RULES:
- Recommend packages that are REAL and exist in the ecosystem for the user's chosen framework/language.
- Stay within the user's chosen platform and framework — do NOT switch ecosystems.
- Be specific: use the actual package name, not a vague wrapper description.
- If the user has not chosen a framework/language yet, keep the output stack-agnostic and avoid concrete package names.
- Do NOT mention installation of runtimes, SDKs, or IDEs.
- Do NOT fabricate package names. If unsure, say so and suggest checking the official package registry for the user's ecosystem.
- Avoid redundant or conflicting packages. Pick one package per responsibility unless both are explicitly needed and explain why.
- If exact latest versions are uncertain, use "current stable" instead of guessing stale version numbers.
"""

    state["tool_advice"] = ask_llm(prompt)
    return state
