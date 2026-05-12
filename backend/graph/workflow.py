from langgraph.graph import StateGraph, END

from graph.state import AgentState

from agents.requirement_agent import requirement_agent
from agents.tool_agent import tool_agent
from agents.architect_agent import architect_agent
from agents.risk_agent import risk_agent
from agents.resource_agent import resource_agent
from agents.supervisor import supervisor


# ── Routing: if smart questions generated → stop and return them to frontend ──
def route(state):
    if state.get("smart_questions") and len(state["smart_questions"]) > 0:
        return "smart_clarify"
    return "tool_agent"


def route_after_tool(state):
    if state.get("request_mode") == "recommendation_compare":
        return "risk_agent"
    return "architect_agent"


# Pass-through node: just returns state, workflow ends here
def smart_clarify_node(state):
    return state


# ── Build graph ──
builder = StateGraph(AgentState)

builder.add_node("requirements",   requirement_agent)
builder.add_node("smart_clarify",  smart_clarify_node)
builder.add_node("tool_agent",     tool_agent)
builder.add_node("architect_agent",architect_agent)
builder.add_node("risk_agent",     risk_agent)
builder.add_node("resource_agent", resource_agent)
builder.add_node("supervisor",     supervisor)

builder.set_entry_point("requirements")

builder.add_conditional_edges(
    "requirements",
    route,
    {
        "smart_clarify": "smart_clarify",
        "tool_agent":    "tool_agent",
    }
)

builder.add_conditional_edges(
    "tool_agent",
    route_after_tool,
    {
        "architect_agent": "architect_agent",
        "risk_agent":      "risk_agent",
    }
)

builder.add_edge("smart_clarify",   END)
builder.add_edge("architect_agent", "risk_agent")
builder.add_edge("risk_agent",      "resource_agent")
builder.add_edge("resource_agent",  "supervisor")
builder.add_edge("supervisor",      END)

graph = builder.compile()


def execute_workflow(state, on_stage=None):
    """
    Execute the same workflow logic step-by-step and optionally emit stage updates.
    Used by streaming APIs to surface progress before final text chunks arrive.
    """
    def emit(stage_name, payload_state):
        if on_stage is not None:
            on_stage(stage_name, payload_state)

    state = requirement_agent(state)
    emit("requirements", state)

    if route(state) == "smart_clarify":
        state = smart_clarify_node(state)
        emit("smart_clarify", state)
        return state

    state = tool_agent(state)
    emit("tool_agent", state)

    next_stage = route_after_tool(state)
    if next_stage == "architect_agent":
        state = architect_agent(state)
        emit("architect_agent", state)

    state = risk_agent(state)
    emit("risk_agent", state)

    state = resource_agent(state)
    emit("resource_agent", state)

    state = supervisor(state)
    emit("supervisor", state)
    return state