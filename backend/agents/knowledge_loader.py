"""
knowledge_loader.py
====================
Loads the agent instruction file from the knowledge base.
This is the ONLY knowledge file — it contains general reasoning instructions,
NOT framework-specific content. The LLM decides what technologies are appropriate
based on the user's actual request.
"""

import os
from typing import Dict

_KNOWLEDGE_DIR = os.path.join(os.path.dirname(__file__), "..", "knowledge")

_PROJECT_TYPE_ALIASES = {
    "application": "application",
    "app": "application",
    "product": "application",
    "client": "application",
    "service": "service",
    "backend": "service",
    "api": "service",
    "data": "data",
    "analytics": "data",
    "model": "data",
    "pipeline": "data",
    "automation": "automation",
    "workflow": "automation",
    "script": "automation",
    "general": "general",
}

_DOMAIN_FOCUS = {
    "application": "Project profile: Interactive user-facing application. Prioritize modular UI, clear state boundaries, and reliable data sync.",
    "service": "Project profile: Backend/API service. Prioritize clear contracts, validation, observability, and fault isolation.",
    "data": "Project profile: Data and intelligence workload. Prioritize data quality checks, reproducible stages, and measurable outputs.",
    "automation": "Project profile: Automation workflow. Prioritize idempotent tasks, scheduling/retry strategy, and operational visibility.",
    "general": "Project profile: General software guidance. Prioritize pragmatic defaults, maintainability, and incremental delivery.",
}

_AUTO_DECISIONS_BY_TYPE = {
    "application": {
        "architecture_style": "feature-based modules with shared core utilities",
        "quality_baseline": "linting, formatting, and unit test coverage for core flows",
        "error_strategy": "input validation with clear user-facing error states",
    },
    "service": {
        "architecture_style": "layered endpoints, domain logic, and data access",
        "quality_baseline": "contract validation plus unit and integration tests",
        "observability": "structured logs, request tracing, and health checks",
    },
    "data": {
        "architecture_style": "ingest, transform, and output stages with explicit interfaces",
        "quality_baseline": "schema validation, data checks, and deterministic runs",
        "risk_control": "versioned inputs/outputs and rollback-safe releases",
    },
    "automation": {
        "architecture_style": "task-oriented modules with retry-aware orchestration",
        "quality_baseline": "smoke tests for critical paths and failure notifications",
        "reliability": "idempotent operations and timeout safeguards",
    },
    "general": {
        "architecture_style": "modular structure with clear responsibility boundaries",
        "quality_baseline": "basic linting, formatting, and targeted tests",
        "delivery": "start with a thin vertical slice before broad expansion",
    },
}

def load_instructions() -> str:
    """Load the universal agent instructions file."""
    path = os.path.join(_KNOWLEDGE_DIR, "agent_instructions.md")
    path = os.path.abspath(path)
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    return ""


def load_section(section_name: str) -> str:
    """
    Extract a specific ## section from agent_instructions.md.
    e.g., load_section("Requirement Agent Instructions")
    """
    full = load_instructions()
    if not full:
        return ""

    lines = full.split("\n")
    section_lines = []
    in_section = False

    for line in lines:
        if line.strip() == f"## {section_name}":
            in_section = True
            continue
        if in_section:
            if line.startswith("## "):
                break
            section_lines.append(line)

    return "\n".join(section_lines).strip()


def normalize_project_type(raw_type: str) -> str:
    """Normalize classifier output to a stable internal project type."""
    value = (raw_type or "").strip().lower()
    if value in _PROJECT_TYPE_ALIASES:
        return _PROJECT_TYPE_ALIASES[value]
    return "general"


def get_domain_knowledge(project_type: str) -> str:
    """
    Return the universal knowledge file with a small project-profile focus hint.
    """
    normalized = normalize_project_type(project_type)
    profile = _DOMAIN_FOCUS.get(normalized, _DOMAIN_FOCUS["general"])
    base = load_instructions().strip()

    if not base:
        return profile

    return f"{base}\n\n---\n\n## Project Profile\n{profile}"


def get_auto_decisions(project_type: str) -> Dict[str, str]:
    """Return conservative default decisions by project type."""
    normalized = normalize_project_type(project_type)
    defaults = _AUTO_DECISIONS_BY_TYPE.get(normalized, _AUTO_DECISIONS_BY_TYPE["general"])
    return dict(defaults)
