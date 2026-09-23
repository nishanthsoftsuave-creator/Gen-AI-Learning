export default function Header({ status, view, onChangeView }) {
  const badgeText = !status
    ? "No document loaded"
    : status.error
      ? "⚠️ Server unreachable"
      : status.ready
        ? `✅ ${status.filename} (${status.chunks} chunks)`
        : "No document loaded";

  return (
    <div className="header">
      <h1>{view === "race" ? "⚖️ Agent vs Workflow" : "📄 Document Q&A"}</h1>

      <div className="header-tabs">
        <button
          type="button"
          className={`header-tab${view === "qa" ? " active" : ""}`}
          onClick={() => onChangeView("qa")}
        >
          Document Q&amp;A
        </button>
        <button
          type="button"
          className={`header-tab${view === "race" ? " active" : ""}`}
          onClick={() => onChangeView("race")}
        >
          Agent vs Workflow
        </button>
      </div>

      {view === "qa" && (
        <span className={`doc-badge${status?.ready ? " loaded" : ""}`}>{badgeText}</span>
      )}
    </div>
  );
}
