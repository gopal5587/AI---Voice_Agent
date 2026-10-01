import { useEffect, useRef, useState } from "react";
import { api, API_BASE, WS_BASE } from "../../api";
import { createRecognizer } from "../../lib/speech";
import { startMic } from "./micCapture";

interface Scenario { id: string; title: string; duration_s: number | null; audio_available: boolean; noise_snr_db: number; expected: { required: string[] } }
interface NudgeCard {
  id: string; kind: string; topic: string; priority: number; title: string; message: string; confidence: number;
  evidence: string[]; t_stream: number; expires_in_s: number; source: string; status: string; receivedAt: number;
  latency: Record<string, number | null>;
}
interface Line { speaker: string; text: string; final: boolean; t_stream: number; asr_conf: number; asr_lag_ms: number | null }
type Mode = "replay" | "mic" | "browser_asr";

export default function NudgeDashboard() {
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [scenario, setScenario] = useState("rt_cross_sell");
  const [mode, setMode] = useState<Mode>("replay");
  const [lines, setLines] = useState<Line[]>([]);
  const [partials, setPartials] = useState<Record<string, string>>({});
  const [nudges, setNudges] = useState<NudgeCard[]>([]);
  const [suppressed, setSuppressed] = useState<Record<string, unknown>[]>([]);
  const [topics, setTopics] = useState<{ to: string; t_stream: number }[]>([]);
  const [summary, setSummary] = useState<Record<string, unknown> | null>(null);
  const [status, setStatus] = useState("idle");
  const [now, setNow] = useState(Date.now());
  const wsRef = useRef<WebSocket | null>(null);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const cleanupRef = useRef<(() => void) | null>(null);

  useEffect(() => { api<Scenario[]>("/api/realtime/scenarios").then(setScenarios).catch(() => undefined); }, []);
  useEffect(() => { const t = setInterval(() => setNow(Date.now()), 500); return () => clearInterval(t); }, []);

  function reset() {
    setLines([]); setPartials({}); setNudges([]); setSuppressed([]); setTopics([]); setSummary(null);
  }

  function start() {
    stop();
    reset();
    const ws = new WebSocket(`${WS_BASE}/ws/realtime`);
    ws.binaryType = "arraybuffer";
    wsRef.current = ws;
    ws.onopen = async () => {
      ws.send(JSON.stringify({ type: "start", mode, scenario, speed: 1 }));
      if (mode === "mic") cleanupRef.current = await startMic((pcm) => ws.readyState === 1 && ws.send(pcm));
      if (mode === "browser_asr") startBrowserAsr(ws);
    };
    ws.onmessage = (m) => onEvent(JSON.parse(m.data as string), ws);
    ws.onclose = () => setStatus((s) => (s.startsWith("done") ? s : "disconnected"));
  }

  function startBrowserAsr(ws: WebSocket) {
    const loop = () => {
      const rec = createRecognizer("en-IN");
      if (!rec) return setStatus("Web Speech API unavailable");
      rec.continuous = true;
      rec.onresult = (e) => {
        const r = e.results[e.resultIndex];
        ws.send(JSON.stringify({ type: "text", speaker: "mixed", text: r[0].transcript, final: r.isFinal }));
      };
      rec.onend = () => { if (wsRef.current === ws && ws.readyState === 1) loop(); };
      rec.start();
      cleanupRef.current = () => rec.abort();
    };
    loop();
  }

  function onEvent(ev: Record<string, any>, ws: WebSocket) {
    switch (ev.type) {
      case "started": setStatus(`streaming (${ev.mode}, ASR ${ev.asr})`); break;
      case "replay_started":
        if (audioRef.current) { audioRef.current.src = `${API_BASE}/api/realtime/audio/${scenario}`; void audioRef.current.play(); }
        break;
      case "transcript":
        if (ev.final) {
          setLines((l) => [...l, ev as Line]);
          setPartials((p) => ({ ...p, [ev.speaker]: "" }));
        } else setPartials((p) => ({ ...p, [ev.speaker]: ev.text }));
        break;
      case "nudge":
        setNudges((n) => [{ ...(ev as NudgeCard), status: "active", receivedAt: Date.now() }, ...n]);
        requestAnimationFrame(() => ws.send(JSON.stringify({ type: "ack", id: ev.id, displayed_at_ms: Date.now() })));
        break;
      case "nudge_updated":
        setNudges((n) => n.map((x) => (x.id === ev.id ? { ...x, message: ev.message, evidence: ev.evidence } : x)));
        break;
      case "nudge_closed":
        setNudges((n) => n.map((x) => (x.id === ev.id ? { ...x, status: ev.status } : x)));
        break;
      case "suppressed": setSuppressed((s) => [ev, ...s].slice(0, 40)); break;
      case "topic": setTopics((t) => [...t, ev as { to: string; t_stream: number }]); break;
      case "end": setSummary(ev.summary); setStatus("done - summary below"); break;
      case "error": setStatus(`error: ${ev.message}`); break;
    }
  }

  function stop() {
    cleanupRef.current?.();
    cleanupRef.current = null;
    if (wsRef.current?.readyState === 1) wsRef.current.send(JSON.stringify({ type: "stop" }));
    audioRef.current?.pause();
  }

  const current = scenarios.find((s) => s.id === scenario);
  const latency = (summary?.latency_ms ?? {}) as Record<string, { n: number; p50: number | null; p95: number | null }>;

  return (
    <div className="grid nudge-layout">
      <section className="card">
        <h2>Live call</h2>
        <div className="row wrap">
          <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
            <option value="replay">Replay recorded call at 1x (dual-channel, server ASR)</option>
            <option value="mic">Live microphone (server ASR)</option>
            <option value="browser_asr">Live microphone (browser ASR)</option>
          </select>
          {mode === "replay" && (
            <select value={scenario} onChange={(e) => setScenario(e.target.value)}>
              {scenarios.map((s) => <option key={s.id} value={s.id}>{s.id} ({s.duration_s}s, SNR {s.noise_snr_db} dB)</option>)}
            </select>
          )}
          <button className="primary" onClick={start}>Start</button>
          <button onClick={stop}>Stop</button>
        </div>
        {mode === "replay" && current && <p className="muted small">{current.title}</p>}
        <p className="status">{status}</p>
        <audio ref={audioRef} controls className="grow" />
        <div className="topics">{topics.map((t, i) => <span key={i} className="tag">{t.t_stream}s: {t.to}</span>)}</div>
        <div className="transcript live">
          {lines.map((l, i) => (
            <div key={i} className={`turn ${l.speaker === "agent" ? "bot" : "customer"}`}>
              <div className="who">{l.speaker} @ {l.t_stream}s <span className="tag">asr conf {l.asr_conf}</span>
                {l.asr_lag_ms != null && <span className="tag">asr {l.asr_lag_ms} ms</span>}</div>
              {l.text}
            </div>
          ))}
          {Object.entries(partials).filter(([, t]) => t).map(([s, t]) => <div key={s} className="turn interim">{s}: {t}...</div>)}
        </div>
      </section>
      <section className="card">
        <h2>Nudges</h2>
        {nudges.length === 0 && <p className="muted">No nudges yet. Low-value or low-confidence signals are suppressed (see log).</p>}
        {nudges.map((n) => {
          const left = Math.max(0, Math.round(n.expires_in_s - (now - n.receivedAt) / 1000));
          return (
            <div key={n.id} className={`nudge p${n.priority} ${n.status !== "active" ? "closed" : ""}`}>
              <div className="row between"><b>{n.title}</b><span className="tag">{n.status === "active" ? `${left}s` : n.status}</span></div>
              <div>{n.message}</div>
              <div className="muted small">{n.kind}/{n.topic} | conf {n.confidence} | at {n.t_stream}s | {n.source} | evidence: "{n.evidence.join('", "')}"</div>
            </div>
          );
        })}
        <h3>Suppressed candidates</h3>
        <div className="small suppressed">
          {suppressed.map((s, i) => <div key={i}><span className="tag">{String(s.reason)}</span> {String(s.kind)}/{String(s.topic)} conf {String(s.confidence)} "{String(s.evidence)}"</div>)}
        </div>
        {summary && (
          <>
            <h3>Session latency (ms)</h3>
            <table>
              <thead><tr><th>Stage</th><th>n</th><th>P50</th><th>P95</th></tr></thead>
              <tbody>{Object.entries(latency).map(([k, v]) => <tr key={k}><td>{k}</td><td>{v.n}</td><td>{v.p50 ?? "-"}</td><td>{v.p95 ?? "-"}</td></tr>)}</tbody>
            </table>
          </>
        )}
      </section>
    </div>
  );
}
