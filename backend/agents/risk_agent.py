"""
risk_agent.py
=============
Identifies specific caveats by reading "gotchas" from the domain knowledge base.
Then asks the LLM to adapt them to the user's exact tech stack choices.
"""

from agents.llm import ask_llm
from agents.knowledge_loader import get_domain_knowledge


def risk_agent(state):

    project_type = state.get("project_type", "general")
    request_mode = state.get("request_mode", "architecture_guide")
    domain_kb    = get_domain_knowledge(project_type)

    choices = state.get("user_choices", {})
    auto    = state.get("auto_decisions", {})

    choices_str = "\n".join(f"  - {k}: {v}" for k, v in choices.items()) or "  None"
    auto_str    = "\n".join(f"  - {k}: {v}" for k, v in auto.items())    or "  None"

    prompt = f"""You are a technical risk analyst for software development projects.
Identify practical, specific risks for the user's exact stack and goal.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
PROJECT CONTEXT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Building: "{state.get('project_summary', state['user_query'])}"
Type: {project_type}
Request mode: {request_mode}
Auto-decided: {auto_str}
User choices: {choices_str}

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
YOUR TASK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Identify 2-3 real, specific technical risks for this exact project and stack.

If request_mode is architecture_guide:
- Focus on architecture-level risks: data flow issues, state management pitfalls,
  performance bottlenecks, testing gaps specific to the user's framework.

If request_mode is recommendation_compare:
- Focus on integration risks: package maturity, compatibility with the user's
  framework version, performance impact, maintenance burden, known issues.

Format as a bullet list. Each bullet must:
- Name the specific risk (be concrete, not generic)
- Explain WHY it matters for THIS user's stack and goal
- Give a practical mitigation or fix

RULES:
- Be specific to the user's actual chosen platform and framework — infer what is relevant from their choices.
- Do NOT give generic advice ("test your code", "use version control").
- Reference real constraints that actually exist in the user's chosen ecosystem and technology stack.
"""

    result = ask_llm(prompt)

    state["risks"]       = [result]
    state["risk_review"] = result
    return state