from typing import Optional, Dict, List, Tuple
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


def _clean_tree_line_name(name: str) -> str:
    """Remove explanations/comments that often appear after tree entries."""
    name = (name or "").strip()
    name = re.sub(r"\s+#.*$", "", name).strip()
    name = re.split(r"\s+(?:-|–|—)\s+", name, maxsplit=1)[0].strip()
    name = name.strip("`'\"")
    return name


def _sanitize_archive_path(path: str) -> str:
    """Normalize a generated path and reject unsafe zip paths."""
    raw_parts = re.split(r"[/\\]+", (path or "").strip().strip("/\\"))
    safe_parts: List[str] = []

    for part in raw_parts:
        part = part.strip()
        if not part or part in {".", ".."}:
            continue
        part = re.sub(r"[\x00-\x1f\x7f]", "", part)
        part = re.sub(r"[:*?\"<>|]", "-", part)
        part = part.strip()
        if part:
            safe_parts.append(part)

    return "/".join(safe_parts)


def _extract_project_structure_section(text: str) -> str:
    """Find the Project Structure section; fall back to the first tree-like code block."""
    header = re.search(
        r"(?mi)^\s*(?:#{1,6}\s*)?(?:\*\*)?\d*\.?\s*project\s+structure\s*(?:\*\*)?\s*:?\s*$",
        text or "",
    )
    if header:
        section = text[header.end():]
        next_header = re.search(r"(?m)^\s*#{1,6}\s+.+$", section)
        if next_header:
            section = section[:next_header.start()]
        return section

    for match in re.finditer(r"```(?:[a-zA-Z0-9_-]+)?\n([\s\S]*?)\n```", text or ""):
        candidate = match.group(1)
        if any(symbol in candidate for symbol in ("├──", "└──", "│")) or re.search(r"(?m)^\s*[-*]?\s*[\w.-]+/", candidate):
            return candidate

    return ""


def _extract_project_structure_nodes(text: str) -> List[Tuple[str, bool]]:
    """Parse a Project Structure tree into ordered (path, is_dir) nodes."""
    section = _extract_project_structure_section(text)
    if not section:
        return []

    code_block = re.search(r"```(?:[a-zA-Z0-9_-]+)?\n([\s\S]*?)\n```", section)
    lines = code_block.group(1).splitlines() if code_block else section.splitlines()

    raw_nodes: List[Tuple[str, bool]] = []
    stack: List[str] = []

    for raw_line in lines:
        line = raw_line.rstrip()
        if not line.strip() or re.fullmatch(r"[│|\s]+", line):
            continue

        match = re.match(
            r"^(?P<prefix>(?:[│| ]{4}|\t)*)(?:(?P<branch>[├└+\\|-]+──|[+\\|-]+--|[-*])\s*)?(?P<name>.+?)\s*$",
            line,
        )
        if not match:
            continue

        prefix = (match.group("prefix") or "").replace("\t", "    ")
        branch = match.group("branch")
        original_name = (match.group("name") or "").strip()
        cleaned_name = _clean_tree_line_name(original_name)
        if not cleaned_name or cleaned_name.startswith(("#", "//")):
            continue

        depth = len(prefix) // 4
        if branch and branch not in {"-", "*"}:
            depth += 1

        is_dir = cleaned_name.endswith("/")
        cleaned_name = cleaned_name.rstrip("/")
        cleaned_name = _sanitize_archive_path(cleaned_name)
        if not cleaned_name:
            continue

        if "/" in cleaned_name:
            current_path = cleaned_name
        elif depth == 0:
            stack = [cleaned_name]
            current_path = cleaned_name
        else:
            stack = stack[:depth] + [cleaned_name]
            current_path = "/".join(stack)

        raw_nodes.append((current_path, is_dir))

    if not raw_nodes:
        return []

    parent_paths = set()
    for path, _ in raw_nodes:
        parts = path.split("/")
        for index in range(1, len(parts)):
            parent_paths.add("/".join(parts[:index]))

    nodes: List[Tuple[str, bool]] = []
    seen = set()
    for path, is_dir in raw_nodes:
        safe_path = _sanitize_archive_path(path)
        if not safe_path:
            continue
        final_is_dir = is_dir or safe_path in parent_paths
        key = (safe_path, final_is_dir)
        if key not in seen:
            nodes.append((safe_path, final_is_dir))
            seen.add(key)

    return nodes


def _node_with_parents(path: str, is_dir: bool) -> List[Tuple[str, bool]]:
    parts = [part for part in path.split("/") if part]
    entries: List[Tuple[str, bool]] = []
    for index in range(1, len(parts)):
        entries.append(("/".join(parts[:index]), True))
    entries.append(("/".join(parts), is_dir))
    return entries


def _ensure_single_root(nodes: List[Tuple[str, bool]], root_name: str) -> List[Tuple[str, bool]]:
    if not nodes:
        return [(root_name, True)]

    top_level = {path.split("/", 1)[0] for path, _ in nodes if path}
    if len(top_level) <= 1:
        return nodes

    return [(f"{root_name}/{path}", is_dir) for path, is_dir in nodes]


def _project_root(nodes: List[Tuple[str, bool]], fallback: str) -> str:
    for path, _ in nodes:
        if path:
            return path.split("/", 1)[0]
    return fallback


def _write_zip_entry(zf: zipfile.ZipFile, archive_path: str, is_dir: bool, content: str = ""):
    archive_path = _sanitize_archive_path(archive_path)
    if not archive_path:
        return

    if is_dir:
        zf.writestr(f"{archive_path.rstrip('/')}/", "")
        return

    zf.writestr(archive_path, content)


def _zip_contains(seen_paths: set, archive_path: str) -> bool:
    archive_path = _sanitize_archive_path(archive_path).rstrip("/")
    return archive_path in seen_paths or f"{archive_path}/" in seen_paths


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
        structure_nodes = _extract_project_structure_nodes(payload.content)
        structure_nodes = _ensure_single_root(structure_nodes, safe_name)
        root_dir = _project_root(structure_nodes, safe_name)

        seen_paths = set()
        for path, is_dir in structure_nodes:
            for parent_path, parent_is_dir in _node_with_parents(path, is_dir):
                normalized_path = _sanitize_archive_path(parent_path)
                zip_key = f"{normalized_path}/" if parent_is_dir else normalized_path
                if not normalized_path or zip_key in seen_paths:
                    continue
                seen_paths.add(zip_key)
                _write_zip_entry(zf, normalized_path, parent_is_dir)

        guide_path = f"{root_dir}/VIBE_GUIDER_GUIDE.md"
        readme_path = f"{root_dir}/README.md"
        if not _zip_contains(seen_paths, readme_path):
            guide_path = readme_path

        _write_zip_entry(zf, guide_path, False, payload.content.strip() + "\n")
        seen_paths.add(_sanitize_archive_path(guide_path))

        manifest_path = f"{root_dir}/vibe-guider-manifest.json"
        _write_zip_entry(
            zf,
            manifest_path,
            False,
            json.dumps(
                {
                    "title": payload.title,
                    "archive": archive_name,
                    "root": root_dir,
                    "generated_from": "vibe-guider",
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "structure_nodes": [
                        {"path": path, "type": "directory" if is_dir else "file"}
                        for path, is_dir in structure_nodes
                    ],
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
