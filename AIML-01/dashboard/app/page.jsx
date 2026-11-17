export default function Home() {
  return (
    <main className="shell">
      <aside className="sidebar">
        <div className="brand">AIML-01</div>
        <div className="brand-subtitle">Fraud Analyst Platform</div>
        <nav className="nav">
          <span className="nav-active">Overview</span>
          <a href="/scoring">Transaction scoring</a>
          <span>Alerts: demo only</span>
          <a href="/cases">Investigation cases</a>
        </nav>
        <div className="sidebar-footer">
          Nexvia Technologies | Capstone
        </div>
      </aside>

      <section className="workspace">
        <header className="topbar">
          <div>
            <p className="eyebrow">AIML-01 / Analyst workspace</p>
            <h1>Fraud Detection Overview</h1>
            <p className="muted">
              Model-backed financial transaction review
            </p>
          </div>
          <span className="status">Historical demo</span>
        </header>

        <div className="notice">
          <strong>System status:</strong> Authenticated historical fraud scoring is available. Live Kafka streaming and persistent case storage are not enabled.
        </div>

        <div className="cards">
          <article className="panel">
            <p className="eyebrow">Scoring model</p>
            <h2>XGBoost</h2>
            <p className="muted">23-feature inference contract</p>
          </article>
          <article className="panel">
            <p className="eyebrow">Online features</p>
            <h2>Feast</h2>
            <p className="muted">
              Historical feature retrieval tested locally
            </p>
          </article>
          <article className="panel">
            <p className="eyebrow">API mode</p>
            <h2>Hour 377</h2>
            <p className="muted">
              Historical hour-377 scoring with frozen features
            </p>
          </article>
        </div>

        <div className="panel">
          <h2>Analyst workflow</h2>
          <p className="muted">
            Transaction scoring is available through the hosted Next.js API. Persistent investigation cases are not stored in this demo.
          </p>
          <p className="muted">
            No continuous transaction stream or live alert counts are displayed.
          </p>
        </div>
      </section>
    </main>
  );
}
