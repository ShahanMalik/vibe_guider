from typing import TypedDict, List, Dict, Callable, Optional

class AgentState(TypedDict):
    user_query: str
    requirements: str
    tool_advice: str
    architecture_advice: str
    risk_review: str
    external_resources: str
    final_answer: str
    clarification_needed: bool
    clarification_question: str
    confidence: float
    risks: List[str]

    # Smart advisor fields
    project_type: str           # application | service | data | automation | general
    request_mode: str           # architecture_guide | recommendation_compare
    project_summary: str        # one-line description of what user wants to build
    auto_decisions: Dict[str, str]  # {"architecture_style": "layered modules"} — decided for user
    smart_questions: List[Dict]     # [{"id": "data_layer", "question": "...", "options": [...]}]
    user_choices: Dict[str, str]    # {"data_layer": "Managed cloud datastore"} — user selected
    _stream_writer: Optional[Callable[[str], None]]  # optional callback for incremental answer streaming