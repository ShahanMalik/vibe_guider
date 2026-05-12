from typing import Optional, Dict, List
from io import BytesIO
import json
import re
import threading
import zipfile
from datetime import datetime, timezone
from queue import Queue

from fastapi import FastAPI
from pydantic import BaseModel
from graph.workflow import execute_workflow
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class UserQuery(BaseModel):
    question: str
    user_choices: Optional[Dict[str, str]] = None
    smart_questions: Optional[List[Dict]] = None
    project_summary: Optional[str] = ""
    auto_decisions: Optional[Dict[str, str]] = None
    project_type: Optional[str] = ""
    request_mode: Optional[str] = ""


class ZipBundleRequest(BaseModel):
    title: str = "vibe-guider-bundle"
    content: str


def _build_state(q: UserQuery, stream_writer=None):
    return {
        "user_query":           q.question,
        "requirements":         "",
        "tool_advice":          "",
        "architecture_advice":  "",
        "risk_review":          "",
        "external_resources":   "",
        "final_answer":         "",
        "clarification_needed": False,
        "clarification_question": "",
        "confidence":           1.0,
        "risks":                [],
        # Smart advisor fields
        "project_type":         q.project_type or "",
        "request_mode":         q.request_mode or "architecture_guide",
        "project_summary":      q.project_summary or "",
        "auto_decisions":       q.auto_decisions or {},
        "smart_questions":      q.smart_questions or [],
        "user_choices":         q.user_choices or {},
        # Optional streaming hook used by supervisor/LLM
        "_stream_writer":       stream_writer,
    }


def _safe_filename(value: str) -> str:
    text = (value or "vibe-guider-bundle").strip().lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    text = text.strip("-")
    return text or "vibe-guider-bundle"


@app.get("/")
def health():
    return {"status": "running"}


@app.post("/ask")
def ask(q: UserQuery):
    state = _build_state(q)

    result = execute_workflow(state)

    # ── Phase 1: smart questions to ask the user ──
    if result.get("smart_questions") and len(result["smart_questions"]) > 0:
        return {
            "needs_choices":   True,
            "project_type":    result.get("project_type", ""),
            "request_mode":    result.get("request_mode", "architecture_guide"),
            "project_summary": result.get("project_summary", q.question),
            "auto_decisions":  result.get("auto_decisions", {}),
            "smart_questions": result["smart_questions"],
        }

    # ── Phase 2: final answer ──
    return {
        "needs_choices": False,
        "answer":        result["final_answer"],
    }


@app.post("/ask/stream")
def ask_stream(q: UserQuery):
    stage_labels = {
        "requirements": "Understanding your request",
        "smart_clarify": "Preparing clarification",
        "tool_agent": "Evaluating tools and packages",
        "architect_agent": "Designing architecture",
        "risk_agent": "Analyzing risks",
        "resource_agent": "Gathering references",
        "supervisor": "Composing final answer",
    }

    def stream_ndjson():
        out_queue: Queue = Queue()
        result_holder: Dict = {}

        def stream_writer(chunk: str):
            out_queue.put({"type": "chunk", "content": chunk})

        def stage_writer(stage_name: str, payload_state: Dict):
            out_queue.put({
                "type": "stage",
                "stage": stage_name,
                "label": stage_labels.get(stage_name, stage_name),
                "request_mode": payload_state.get("request_mode", "architecture_guide"),
            })

        def worker():
            try:
                state = _build_state(q, stream_writer=stream_writer)
                result_holder["result"] = execute_workflow(state, on_stage=stage_writer)
            except Exception as exc:
                result_holder["error"] = str(exc)
            finally:
                out_queue.put({"type": "_done"})

        threading.Thread(target=worker, daemon=True).start()

        while True:
            item = out_queue.get()
            if item.get("type") == "_done":
                break
            yield json.dumps(item) + "\n"

        if "error" in result_holder:
            yield json.dumps({"type": "error", "message": result_holder["error"]}) + "\n"
            return

        result = result_holder.get("result", {})
        if result.get("smart_questions") and len(result["smart_questions"]) > 0:
            yield json.dumps({
                "type": "choices",
                "needs_choices": True,
                "project_type": result.get("project_type", ""),
                "request_mode": result.get("request_mode", "architecture_guide"),
                "project_summary": result.get("project_summary", q.question),
                "auto_decisions": result.get("auto_decisions", {}),
                "smart_questions": result["smart_questions"],
            }) + "\n"
            return

        yield json.dumps({
            "type": "done",
            "needs_choices": False,
            "answer": result.get("final_answer", ""),
        }) + "\n"

    return StreamingResponse(stream_ndjson(), media_type="application/x-ndjson")


@app.post("/download/zip")
def download_zip(payload: ZipBundleRequest):
    safe_name = _safe_filename(payload.title)
    archive_name = f"{safe_name}.zip"

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            "README.md",
            payload.content.strip() + "\n",
        )
        zf.writestr(
            "manifest.json",
            json.dumps(
                {
                    "title": payload.title,
                    "archive": archive_name,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            )
            + "\n",
        )

    buffer.seek(0)
    headers = {
        "Content-Disposition": f'attachment; filename="{archive_name}"',
    }
    return Response(content=buffer.getvalue(), media_type="application/zip", headers=headers)