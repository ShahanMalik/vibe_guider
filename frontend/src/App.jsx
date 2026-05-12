import { useState, useRef, useEffect, useCallback } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import "./App.css";

const API_URL = import.meta.env.VITE_API_URL || "http://localhost:8000";

// Status messages that cycle while loading
const THINKING_STAGES = [
  "Contemplating, stand by…",
  "Analyzing your request…",
  "Searching knowledge base…",
  "Synthesizing recommendations…",
];

// Markdown renderer components
const mdComponents = {
  h1: (p) => <h1 className="md-h1" {...p} />,
  h2: (p) => <h2 className="md-h2" {...p} />,
  h3: (p) => <h3 className="md-h3" {...p} />,
  p:  (p) => <p  className="md-p"  {...p} />,
  ul: (p) => <ul className="md-ul" {...p} />,
  ol: (p) => <ol className="md-ol" {...p} />,
  li: (p) => <li className="md-li" {...p} />,
  a: ({ href = "", ...p }) => {
    const isExternal = /^https?:\/\//i.test(href);
    return (
      <a
        className={isExternal ? "md-link md-link-external" : "md-link"}
        href={href}
        target={isExternal ? "_blank" : undefined}
        rel={isExternal ? "noreferrer" : undefined}
        {...p}
      />
    );
  },
  strong:     (p) => <strong className="md-strong" {...p} />,
  blockquote: (p) => <blockquote className="md-quote" {...p} />,
  hr:  (p) => <hr  className="md-hr"  {...p} />,
  pre: (p) => <pre className="md-pre" {...p} />,
  code: ({ inline, className, ...p }) =>
    inline
      ? <code className="md-inline-code" {...p} />
      : <code className={["md-code", className].filter(Boolean).join(" ")} {...p} />,
  table: ({ children, ...p }) => (
    <div className="md-table-wrap">
      <table className="md-table" {...p}>{children}</table>
    </div>
  ),
  th: (p) => <th className="md-th" {...p} />,
  td: (p) => <td className="md-td" {...p} />,
};

// Sunburst / asterisk SVG icon (matches Claude style)
function SpinIcon({ spinning = false }) {
  return (
    <svg
      className={`tp-spin-icon${spinning ? " is-spinning" : ""}`}
      viewBox="0 0 24 24"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      aria-hidden="true"
    >
      {[0, 30, 60, 90, 120, 150, 180, 210, 240, 270, 300, 330].map((deg) => (
        <line
          key={deg}
          x1="12" y1="3" x2="12" y2="7"
          stroke="currentColor"
          strokeWidth="2.2"
          strokeLinecap="round"
          transform={`rotate(${deg} 12 12)`}
        />
      ))}
    </svg>
  );
}

let _id = 0;
const uid = () => ++_id;

export default function App() {
  const [messages,      setMessages]      = useState([]);
  const [input,         setInput]         = useState("");
  const [loading,       setLoading]       = useState(false);
  const [downloadLoading, setDownloadLoading] = useState(false);
  const [thinkingText,  setThinkingText]  = useState("");
  const [accChoices,    setAccChoices]    = useState({});
  const [originalQuery, setOriginalQuery] = useState("");
  const [projectSummary,setProjectSummary]= useState("");
  const [projectType,   setProjectType]   = useState("");
  const [requestMode,   setRequestMode]   = useState("");
  const [autoDecisions, setAutoDecisions] = useState({});
  const [pendingQuestions, setPendingQuestions] = useState([]);
  const [error,         setError]         = useState("");

  const threadRef      = useRef(null);
  const inputRef       = useRef(null);
  const timerRefs      = useRef([]);
  const streamAnswerIdRef = useRef(null);

  const hasMessages = messages.length > 0;

  const latestAnswer = [...messages].reverse().find(
    (msg) => msg.role === "assistant" && msg.type === "answer" && String(msg.content || "").trim()
  )?.content || "";

  const hasDownloadableAnswer = Boolean(latestAnswer.trim());

  // ── Auto-scroll ────────────────────────────────────────────────────────────
  useEffect(() => {
    if (threadRef.current) {
      threadRef.current.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
    }
  }, [messages, thinkingText]);

  // ── Auto-resize textarea ───────────────────────────────────────────────────
  useEffect(() => {
    if (inputRef.current) {
      inputRef.current.style.height = "auto";
      inputRef.current.style.height = Math.min(inputRef.current.scrollHeight, 200) + "px";
    }
  }, [input]);

  const addMsg = (msg) => setMessages((prev) => [...prev, { id: uid(), ...msg }]);

  const renderAnswerProgressively = useCallback(async (text) => {
    const fullText = text || "";
    const answerId = uid();
    streamAnswerIdRef.current = answerId;

    setMessages((prev) => [
      ...prev,
      { id: answerId, role: "assistant", type: "answer", content: "" },
    ]);

    const chunkSize = 16;
    for (let i = 0; i < fullText.length; i += chunkSize) {
      const piece = fullText.slice(i, i + chunkSize);
      setMessages((prev) =>
        prev.map((msg) =>
          msg.id === answerId
            ? { ...msg, content: `${msg.content || ""}${piece}` }
            : msg
        )
      );
      await new Promise((resolve) => setTimeout(resolve, 14));
    }
  }, []);

  const handleDownloadZip = async () => {
    if (!hasDownloadableAnswer || downloadLoading) return;

    setDownloadLoading(true);
    try {
      const bundleTitle = originalQuery || projectSummary || "vibe-guider-bundle";
      const res = await fetch(`${API_URL}/download/zip`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          title: bundleTitle,
          content: latestAnswer,
        }),
      });

      if (!res.ok) {
        throw new Error("Download failed.");
      }

      const blob = await res.blob();
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${bundleTitle
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-+|-+$/g, "") || "vibe-guider-bundle"}.zip`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      setError("Could not create the ZIP download.");
    } finally {
      setDownloadLoading(false);
    }
  };

  // ── Thinking cycle ─────────────────────────────────────────────────────────
  const startThinking = () => {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
    setThinkingText(THINKING_STAGES[0]);
    THINKING_STAGES.slice(1).forEach((stage, i) => {
      const t = setTimeout(() => setThinkingText(stage), (i + 1) * 2000);
      timerRefs.current.push(t);
    });
  };

  const stopThinking = () => {
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
    setThinkingText("");
  };

  // ── API call ───────────────────────────────────────────────────────────────
  const callApi = useCallback(async (query, choices, summary, auto, questions, type, mode) => {
    startThinking();
    setLoading(true);
    setError("");
    streamAnswerIdRef.current = null;
    try {
      const res = await fetch(`${API_URL}/ask/stream`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
        question:     query,
        user_choices: choices,
        project_summary: summary,
        auto_decisions: auto,
        smart_questions: questions,
        project_type: type,
        request_mode: mode,
        }),
      });

      if (!res.ok || !res.body) {
        throw new Error("Streaming response is unavailable.");
      }

      const reader = res.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let hasReceivedChunk = false;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n");
        buffer = lines.pop() || "";

        for (const line of lines) {
          const trimmed = line.trim();
          if (!trimmed) continue;

          let event;
          try {
            event = JSON.parse(trimmed);
          } catch {
            continue;
          }

          if (event.type === "chunk") {
            if (!hasReceivedChunk) {
              hasReceivedChunk = true;
              stopThinking();
            }

            if (streamAnswerIdRef.current == null) {
              const answerId = uid();
              streamAnswerIdRef.current = answerId;
              setMessages((prev) => [
                ...prev,
                { id: answerId, role: "assistant", type: "answer", content: "" },
              ]);
            }

            const answerId = streamAnswerIdRef.current;
            const chunkText = event.content || "";
            if (chunkText) {
              setMessages((prev) =>
                prev.map((msg) =>
                  msg.id === answerId
                    ? { ...msg, content: `${msg.content || ""}${chunkText}` }
                    : msg
                )
              );
            }
            continue;
          }

          if (event.type === "stage") {
            const label = event.label || event.stage || "Processing";
            setThinkingText(`${label}...`);
            continue;
          }

          if (event.type === "choices" && event.needs_choices && event.smart_questions?.length > 0) {
            stopThinking();
            streamAnswerIdRef.current = null;

            const newSummary = event.project_summary || summary || query;
            const newAuto    = event.auto_decisions  || auto   || {};
            const newQuestions = event.smart_questions || [];
            const newType    = event.project_type || type || "";
            const newMode    = event.request_mode || mode || "architecture_guide";
            setProjectSummary(newSummary);
            setProjectType(newType);
            setRequestMode(newMode);
            setAutoDecisions(newAuto);
            setPendingQuestions(newQuestions);

            setMessages((prev) => {
              const visibleQuestionIds = new Set(
                prev
                  .filter((msg) => msg.role === "assistant" && msg.type === "question")
                  .map((msg) => msg.questionId)
              );
              const visibleQuestionText = new Set(
                prev
                  .filter((msg) => msg.role === "assistant" && msg.type === "question")
                  .map((msg) => String(msg.question || "").trim().toLowerCase())
              );
              const additions = newQuestions
                .filter((q) => {
                  const questionText = String(q.question || "").trim().toLowerCase();
                  return !visibleQuestionIds.has(q.id) && !visibleQuestionText.has(questionText);
                })
                .map((q) => ({
                  id:         uid(),
                  role:       "assistant",
                  type:       "question",
                  question:   q.question,
                  options:    q.options,
                  questionId: q.id,
                }));

              return additions.length > 0 ? [...prev, ...additions] : prev;
            });
            continue;
          }

          if (event.type === "done") {
            stopThinking();
            setPendingQuestions([]);

            // Fallback: if no token chunks were streamed, still render progressively.
            if (streamAnswerIdRef.current == null) {
              await renderAnswerProgressively(event.answer || "");
            }
            continue;
          }

          if (event.type === "error") {
            throw new Error(event.message || "Streaming failed.");
          }
        }
      }
    } catch {
      stopThinking();
      setError("Could not reach the backend. Make sure the API is running on localhost:8000.");
    } finally {
      streamAnswerIdRef.current = null;
      setLoading(false);
    }
  }, [renderAnswerProgressively]);

  // ── Send initial query ─────────────────────────────────────────────────────
  const handleSend = async () => {
    if (!input.trim() || loading) return;
    const query = input.trim();
    setInput("");
    setOriginalQuery(query);
    setAccChoices({});
    setProjectSummary("");
    setProjectType("");
    setRequestMode("");
    setAutoDecisions({});
    setPendingQuestions([]);
    addMsg({ role: "user", type: "text", content: query });
    await callApi(query, {}, "", {}, [], "", "");
  };

  // ── User selects an option in a question card ──────────────────────────────
  const handleOptionSelect = async (questionId, option) => {
    if (loading) return;
    const newChoices = { ...accChoices, [questionId]: option };
    setAccChoices(newChoices);
    // User bubble with their selection
    addMsg({ role: "user", type: "selection", content: option });
    await callApi(originalQuery, newChoices, projectSummary, autoDecisions, pendingQuestions, projectType, requestMode);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const handleReset = () => {
    setMessages([]);
    setInput("");
    setLoading(false);
    setThinkingText("");
    setAccChoices({});
    setOriginalQuery("");
    setProjectSummary("");
    setProjectType("");
    setRequestMode("");
    setAutoDecisions({});
    setPendingQuestions([]);
    setError("");
    streamAnswerIdRef.current = null;
    timerRefs.current.forEach(clearTimeout);
    timerRefs.current = [];
    setTimeout(() => inputRef.current?.focus(), 100);
  };

  // ─────────────────────────────────────────────────────────────────────────
  return (
    <div className="chat-root">
      {/* ── Header ── */}
      <header className="chat-header">
        <div className="chat-header-inner">
          <div className="chat-brand-row">
            <SpinIcon />
            <span className="chat-brand-name">Vibe Guider</span>
          </div>
          {hasMessages && (
            <div className="chat-header-actions">
              <button
                className="chat-download-btn"
                onClick={handleDownloadZip}
                disabled={!hasDownloadableAnswer || loading || downloadLoading}
                aria-label="Download ZIP"
              >
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <path d="M7.5 1.5v7m0 0 2.5-2.5M7.5 8.5 5 6" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                  <path d="M2.5 10.5v2h10v-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
                {downloadLoading ? "Preparing ZIP…" : "Download ZIP"}
              </button>
              <button className="chat-new-btn" onClick={handleReset} aria-label="New chat">
                <svg width="15" height="15" viewBox="0 0 15 15" fill="none">
                  <path d="M7.5 1v13M1 7.5h13" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round"/>
                </svg>
                New chat
              </button>
            </div>
          )}
        </div>
      </header>

      {/* ── Thread ── */}
      <main className="chat-thread" ref={threadRef}>
        {!hasMessages ? (
          /* Welcome screen */
          <div className="chat-welcome">
            <div className="chat-welcome-glow" />
            <div className="chat-welcome-icon-wrap">
              <SpinIcon />
            </div>
            <h1 className="chat-welcome-title">Vibe Guider</h1>
            <p className="chat-welcome-sub">
              Describe what you want to build, or which package you need.<br />
              I'll guide you to the right tool for your exact stack.
            </p>
            <div className="chat-welcome-chips">
              {[
                "I want to use a video compressor package",
                "Build a REST API with authentication",
                "Which state manager should I use?",
                "Create a real-time chat app",
              ].map((ex) => (
                <button
                  key={ex}
                  className="chat-example-chip"
                  onClick={() => { setInput(ex); inputRef.current?.focus(); }}
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        ) : (
          /* Message thread */
          <div className="chat-messages">
            {messages.map((msg) => {
              /* User bubble */
              if (msg.role === "user") {
                return (
                  <div key={msg.id} className="chat-row chat-row-user">
                    <div className="chat-bubble-user">
                      {msg.content}
                    </div>
                  </div>
                );
              }

              /* Assistant: question card */
              if (msg.role === "assistant" && msg.type === "question") {
                const answered = accChoices[msg.questionId] != null;
                return (
                  <div key={msg.id} className="chat-row chat-row-assistant">
                    <div className="chat-assistant-icon">
                      <SpinIcon />
                    </div>
                    <div className="chat-bubble-assistant">
                      <p className="chat-question-label">{msg.question}</p>
                      <div className="chat-options-grid">
                        {msg.options.map((opt) => {
                          const isSelected = accChoices[msg.questionId] === opt;
                          return (
                            <button
                              key={opt}
                              className={`chat-option-btn${isSelected ? " is-selected" : ""}${answered && !isSelected ? " is-faded" : ""}`}
                              onClick={() => handleOptionSelect(msg.questionId, opt)}
                              disabled={loading || answered}
                            >
                              {opt}
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                );
              }

              /* Assistant: final answer */
              if (msg.role === "assistant" && msg.type === "answer") {
                return (
                  <div key={msg.id} className="chat-row chat-row-assistant">
                    <div className="chat-assistant-icon">
                      <SpinIcon />
                    </div>
                    <div className="chat-bubble-assistant chat-answer-card">
                      <ReactMarkdown remarkPlugins={[remarkGfm]} components={mdComponents}>
                        {msg.content}
                      </ReactMarkdown>
                    </div>
                  </div>
                );
              }

              return null;
            })}

            {/* Thinking status row */}
            {thinkingText && (
              <div className="chat-row chat-row-assistant chat-thinking-row">
                <div className="chat-assistant-icon is-thinking">
                  <SpinIcon spinning />
                </div>
                <span className="chat-thinking-text">{thinkingText}</span>
              </div>
            )}

            {/* Error */}
            {error && <div className="chat-error">{error}</div>}
          </div>
        )}
      </main>

      {/* ── Composer ── */}
      <footer className="chat-footer">
        <div className="chat-composer">
          <textarea
            ref={inputRef}
            className="chat-input"
            placeholder="Message Vibe Guider…"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            rows={1}
            disabled={loading}
          />
          <button
            className="chat-send-btn"
            onClick={handleSend}
            disabled={loading || !input.trim()}
            aria-label="Send message"
          >
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <path
                d="M2 8h12M10 4l4 4-4 4"
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
                strokeLinejoin="round"
              />
            </svg>
          </button>
        </div>
        <p className="chat-footer-note">
          Vibe Guider can make mistakes. Verify important technical decisions independently.
        </p>
      </footer>
    </div>
  );
}
