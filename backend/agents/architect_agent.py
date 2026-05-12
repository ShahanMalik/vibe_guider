"""
architect_agent.py
==================
Generates project architecture, folder structure, and data flow.

Uses the LLM's own knowledge of the user's chosen stack, guided by
the agent instructions which define format and quality standards.
"""

from agents.llm import ask_llm
from agents.knowledge_loader import load_section


def architect_agent(state):

    architect_instructions = load_section("Architect Agent Instructions")

    auto    = state.get("auto_decisions", {})
    choices = state.get("user_choices",   {})

    auto_str    = "\n".join(f"  ✓ {k.replace('_', ' ').title()}: {v}" for k, v in auto.items())    or "  None"
    choices_str = "\n".join(f"  → {k.replace('_', ' ').title()}: {v}" for k, v in choices.items()) or "  None specified"

    request_mode = state.get("request_mode", "architecture_guide")

    # In comparison/recommendation mode, architecture details are secondary
    if request_mode == "recommendation_compare":
        prompt = f"""You are an expert software architect.
The user is asking for a package/tool recommendation, not a full architecture plan.

User's goal: "{state.get('project_summary', state['user_query'])}"

Platform: {choices.get('platform', 'not specified')}
Framework: {choices.get('framework_or_language', 'not specified')}

Provide a BRIEF integration architecture note:
- How the recommended package typically fits into the app structure
- Where in the project it is initialized / called
- Any architectural pattern to follow, described generically

Keep it under 10 lines. This is supplementary context, not a full architecture plan.
"""
    else:
        prompt = f"""You are an expert software architect. Design a complete project architecture
for the user's specific stack and goals. Use your knowledge of best practices for their
chosen framework and platform.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
AGENT INSTRUCTIONS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
{architect_instructions}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
User wants to build: "{state.get('project_summary', state['user_query'])}"
Project type: {state.get('project_type', 'general')}

Technical decisions (already made):
{auto_str}

User-selected integrations:
{choices_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
## Project Structure
Show the exact folder tree for THIS project using the user's chosen framework and platform.
Use real folder conventions for that framework without naming unrelated frameworks as examples.
Briefly explain each key folder.

If the user has not named a specific platform/framework/language, do not invent one.
In that case, provide a stack-agnostic modular folder tree and clearly mark framework-specific
details as pending a stack choice.

## Architecture Pattern
Explain the chosen pattern and why it fits. 2-3 focused paragraphs, specific to the user's stack.

## Data Flow
Describe how data moves through this architecture. Use the user's actual chosen tools.

## 5 Concrete First Coding Steps
Real file-level actions. Reference specific files. Do not include runtime, SDK, IDE, shell, or package-installation steps.
Write steps as implementation actions rather than command-line instructions.

RULES:
- Use the user's actual platform and framework — do NOT switch ecosystems.
- Be specific and realistic. Use real file names and folder conventions.
- Do NOT give SDK/IDE installation instructions.
- Do NOT claim the user chose a library or pattern unless it is in the request, choices, or prior context.
- For simple, low-scope projects, keep the architecture minimal and use the built-in state mechanisms of the chosen technology instead of heavy external state-management patterns.
- If the stack is not explicitly selected, keep the plan technology-neutral and avoid naming specific frameworks, packages, or state-management libraries.
"""

    state["architecture_advice"] = ask_llm(prompt)
    return state
