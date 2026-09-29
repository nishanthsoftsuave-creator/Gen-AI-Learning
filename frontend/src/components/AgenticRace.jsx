import { useState } from "react";
import { renderMarkdown } from "../lib/markdown.js";

let nextRaceId = 1;

const EXAMPLE_QUESTIONS = [
  "Who is the CEO of Soft Suave, and who is the Managing Director?",
  "How many times has the Employee Handbook been revised, and when was the most recent one?",
  "What email address should I use to reach the HR team, and who is the HRM?",
];

function formatCost(cost) {
  return `$${cost.toFixed(6)}`;
}

function formatLatency(seconds) {
  return seconds >= 10 ? `${seconds.toFixed(1)}s` : `${Math.round(seconds * 1000)}ms`;
}

function SystemPanel({ label, system, run, isWinner }) {
  const clean = run.termination_reason === "COMPLETED";

  return (
    <div className={`race-panel race-panel-${system}${isWinner ? " winner" : ""}`}>
      <div className="race-panel-head">
        <span className="race-panel-label">{label}</span>
        {isWinner && <span className="race-panel-crown">More efficient</span>}
        <span className={`race-status-badge${clean ? " ok" : " warn"}`}>
          {clean ? "completed" : run.termination_reason.replace(/_/g, " ").toLowerCase()}
        </span>
      </div>

      <div
        className="race-answer"
        dangerouslySetInnerHTML={{ __html: renderMarkdown(run.answer || "*No answer.*") }}
      />

      <div className="race-metrics">
        <div className="race-metric">
          <span className="race-metric-value">{run.iterations}</span>
          <span className="race-metric-label">iteration{run.iterations === 1 ? "" : "s"}</span>
        </div>
        <div className="race-metric">
          <span className="race-metric-value">{formatLatency(run.elapsed_seconds)}</span>
          <span className="race-metric-label">latency</span>
        </div>
        <div className="race-metric">
          <span className="race-metric-value">{run.total_tokens.toLocaleString()}</span>
          <span className="race-metric-label">tokens</span>
        </div>
        <div className="race-metric">
          <span className="race-metric-value">{formatCost(run.cost)}</span>
          <span className="race-metric-label">cost</span>
        </div>
      </div>

      {run.tool_calls.length > 0 && (
        <details className="race-tool-calls">
          <summary>{run.tool_calls.length} tool call{run.tool_calls.length === 1 ? "" : "s"}</summary>
          {run.tool_calls.map((call, idx) => (
            <div className="race-tool-call" key={idx}>
              <code>{call.tool}</code>
              <span className="race-tool-args">{JSON.stringify(call.arguments)}</span>
            </div>
          ))}
        </details>
      )}
    </div>
  );
}

function RaceResult({ entry }) {
  const winnerLabel = entry.verdict.winner === "agent" ? "Dynamic Agent" : "Fixed Workflow";

  return (
    <div className="race-result">
      <div className="race-question">{entry.question}</div>

      <div className={`race-verdict ${entry.verdict.winner}`}>
        <strong>{winnerLabel}</strong> was more efficient here — {entry.verdict.reason}.
        <span className="race-verdict-caveat">
          {" "}
          (efficiency only — read both answers below to judge accuracy yourself)
        </span>
      </div>

      <div className="race-columns">
        <SystemPanel
          label="Dynamic Agent"
          system="agent"
          run={entry.agent}
          isWinner={entry.verdict.winner === "agent"}
        />
        <SystemPanel
          label="Fixed Workflow"
          system="workflow"
          run={entry.workflow}
          isWinner={entry.verdict.winner === "workflow"}
        />
      </div>
    </div>
  );
}

export default function AgenticRace() {
  const [value, setValue] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [results, setResults] = useState([]);

  async function runCompare(question) {
    setRunning(true);
    setError(null);

    try {
      const res = await fetch("/agentic/compare", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ question }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.detail || "Comparison failed.");

      setResults((prev) => [{ id: nextRaceId++, ...data }, ...prev]);
    } catch (err) {
      setError(err.message);
    } finally {
      setRunning(false);
    }
  }

  function handleSubmit(e) {
    e.preventDefault();
    const question = value.trim();
    if (!question || running) return;
    setValue("");
    runCompare(question);
  }

  return (
    <div className="race-view">
      <div className="race-intro">
        <p>
          Ask a question about the <strong>Soft Suave Employee Handbook</strong> (policies,
          contacts, revision history). It runs on <strong>both</strong> a dynamic tool-calling
          agent and a fixed, hard-coded pipeline, so you can compare what each one costs and
          produces.
        </p>
        <p className="race-hint">
          Both systems share a Groq rate limit. A comparison usually takes 20–60 seconds, but can
          take much longer if that shared limit is currently exhausted.
        </p>
        <div className="race-examples">
          {EXAMPLE_QUESTIONS.map((q) => (
            <button
              key={q}
              type="button"
              className="race-example-chip"
              disabled={running}
              onClick={() => runCompare(q)}
            >
              {q}
            </button>
          ))}
        </div>
      </div>

      <form className="race-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="e.g. What happens if I raise a grievance, and how is it resolved?"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          disabled={running}
        />
        <button type="submit" disabled={running || !value.trim()}>
          {running ? "Running both…" : "Compare"}
        </button>
      </form>

      {error && <div className="race-error">{error}</div>}

      {running && (
        <div className="race-loading">
          <div className="typing">
            <span></span>
            <span></span>
            <span></span>
          </div>
          Running the agent and the workflow…
        </div>
      )}

      {results.length === 0 && !running && (
        <div className="race-empty">
          <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
            <path d="M5 4v16M19 4v16" strokeLinecap="round" />
            <path d="M5 4h5m4 0h5" strokeLinecap="round" />
            <circle cx="5" cy="11" r="2.4" />
            <circle cx="19" cy="11" r="2.4" />
          </svg>
          <p>No comparisons yet — ask a question above or try an example.</p>
        </div>
      )}

      <div className="race-results">
        {results.map((entry) => (
          <RaceResult key={entry.id} entry={entry} />
        ))}
      </div>
    </div>
  );
}
