function Emblem() {
  return (
    <svg className="emblem" width="30" height="30" viewBox="0 0 32 32" fill="none">
      <rect width="32" height="32" rx="7" fill="var(--ink)" />
      <path d="M9 8h14v16H9z" stroke="var(--brass)" strokeWidth="1.6" />
      <path d="M12 13h8M12 17h8M12 21h5" stroke="var(--brass)" strokeWidth="1.6" strokeLinecap="round" />
    </svg>
  );
}

export default function Header({ status, view, onChangeView }) {
  const badgeText = !status
    ? "No document on file"
    : status.error
      ? "Server unreachable"
      : status.ready
        ? `${status.filename} · ${status.chunks} chunks`
        : "No document on file";

  const badgeState = !status || status.error ? (status?.error ? "error" : "idle") : status.ready ? "ok" : "idle";

  return (
    <div className="header">
      <div className="brand">
        <Emblem />
        <div className="brand-text">
          <span className="brand-name">Handbook Registry</span>
          <span className="brand-tagline">
            {view === "race" ? "Agent vs. workflow comparison" : "Document Q&A"}
          </span>
        </div>
      </div>

      <nav className="header-tabs" aria-label="View">
        <button
          type="button"
          className={`header-tab${view === "qa" ? " active" : ""}`}
          onClick={() => onChangeView("qa")}
        >
          <span className="header-tab-index">01</span>
          Document Q&amp;A
        </button>
        <button
          type="button"
          className={`header-tab${view === "race" ? " active" : ""}`}
          onClick={() => onChangeView("race")}
        >
          <span className="header-tab-index">02</span>
          Agent vs Workflow
        </button>
      </nav>

      {view === "qa" && (
        <span className={`doc-badge doc-badge-${badgeState}`}>
          <span className="doc-badge-dot" />
          {badgeText}
        </span>
      )}
    </div>
  );
}
