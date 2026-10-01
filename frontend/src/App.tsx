import { useEffect, useState } from "react";
import { api, PublicConfig } from "./api";
import VoiceAgent from "./features/agent/VoiceAgent";
import KbExplorer from "./features/kb/KbExplorer";
import NudgeDashboard from "./features/nudges/NudgeDashboard";

const TABS = [
  { id: "agent", label: "Voice Agent (Q1 / Q3)" },
  { id: "kb", label: "Knowledge Base (Q2)" },
  { id: "nudges", label: "Live Nudges (Q4)" },
] as const;

type Tab = (typeof TABS)[number]["id"];

export default function App() {
  const [tab, setTab] = useState<Tab>("agent");
  const [config, setConfig] = useState<PublicConfig | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<PublicConfig>("/api/config").then(setConfig).catch((e) => setError(String(e)));
  }, []);

  return (
    <div className="app">
      <header className="topbar">
        <div>
          <h1>Darwix AI Engineer Assessment</h1>
          <p className="muted">Synthetic demo data. Kosha Capital, Lumina Life and Sinar Multifinance are fictional.</p>
        </div>
        {config && (
          <div className="badges">
            <span className="badge">LLM: {config.llm_enabled ? "on" : "off (deterministic)"}</span>
            <span className="badge">Embeddings: {config.embedder}</span>
            <span className="badge">ASR: {config.asr_provider}</span>
            <span className="badge">Vapi: {config.vapi_public_key ? "configured" : "not configured"}</span>
          </div>
        )}
      </header>
      {error && <div className="banner error">Backend unreachable: {error}. Start it with `uvicorn app.main:app` in backend/.</div>}
      <nav className="tabs">
        {TABS.map((t) => (
          <button key={t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>
            {t.label}
          </button>
        ))}
      </nav>
      <main>
        {tab === "agent" && <VoiceAgent config={config} />}
        {tab === "kb" && <KbExplorer />}
        {tab === "nudges" && <NudgeDashboard />}
      </main>
    </div>
  );
}
