import { useCallback, useEffect, useRef, useState } from "react";
import Vapi from "@vapi-ai/web";
import { AgentInfo, AgentReply, api, post, PublicConfig } from "../../api";
import { createRecognizer, Recognizer, speak } from "../../lib/speech";

interface Turn {
  role: "bot" | "customer";
  text: string;
  intent?: string;
  citations?: string[];
  lang?: string;
  latency?: number | null;
}

type Mode = "browser" | "text" | "vapi";

export default function VoiceAgent({ config }: { config: PublicConfig | null }) {
  const [agents, setAgents] = useState<AgentInfo[]>([]);
  const [key, setKey] = useState("business_loan");
  const [lang, setLang] = useState<string>("");
  const [mode, setMode] = useState<Mode>("browser");
  const [turns, setTurns] = useState<Turn[]>([]);
  const [reply, setReply] = useState<AgentReply | null>(null);
  const [status, setStatus] = useState("idle");
  const [interim, setInterim] = useState("");
  const [typed, setTyped] = useState("");
  const [voiceNote, setVoiceNote] = useState("");
  const [crm, setCrm] = useState<unknown[]>([]);
  const sessionRef = useRef<string | null>(null);
  const recRef = useRef<Recognizer | null>(null);
  const endedRef = useRef(false);
  const vapiRef = useRef<Vapi | null>(null);
  const sendRef = useRef<((text: string) => Promise<void>) | null>(null);

  const agent = agents.find((a) => a.key === key);
  const vapiAssistant = config?.vapi_assistants?.[key];

  useEffect(() => {
    api<AgentInfo[]>("/api/agent/list").then(setAgents).catch(() => undefined);
    window.speechSynthesis?.getVoices();
  }, []);

  useEffect(() => {
    setLang(agent?.languages[0] ?? "");
  }, [agent]);

  const listen = useCallback((voiceLang: string) => {
    if (endedRef.current) return;
    const rec = createRecognizer(voiceLang);
    if (!rec) {
      setStatus("speech recognition unavailable in this browser (use Chrome/Edge), switch to text mode");
      return;
    }
    recRef.current = rec;
    let gotFinal = false;
    rec.onresult = (e) => {
      const res = e.results[e.resultIndex];
      setInterim(res[0].transcript);
      if (res.isFinal) {
        gotFinal = true;
        setInterim("");
        rec.stop();
        void sendRef.current?.(res[0].transcript);
      }
    };
    rec.onerror = (e) => setStatus(`mic: ${e.error}`);
    rec.onend = () => {
      if (!gotFinal && !endedRef.current) setTimeout(() => listen(voiceLang), 250);
    };
    setStatus("listening...");
    rec.start();
  }, []);

  const handleReply = useCallback(
    async (r: AgentReply, currentMode: Mode) => {
      setReply(r);
      setTurns((t) => [...t, { role: "bot", text: r.text, intent: r.intent, citations: r.citations, lang: r.lang, latency: r.latency_ms }]);
      if (r.end_call) {
        endedRef.current = true;
        setStatus(`call ended (${r.state.stage})`);
        api<unknown[]>("/api/agent/crm?limit=20").then((all) =>
          setCrm(all.filter((a) => (a as { session_id?: string }).session_id === r.session_id)),
        );
      }
      if (currentMode === "browser") {
        setStatus("speaking...");
        const v = await speak(r.text, r.voice_lang);
        setVoiceNote(v.native ? `TTS voice: ${v.voiceName}` : `No native ${r.voice_lang} voice installed; fell back to ${v.voiceName}`);
        if (!r.end_call) listen(r.voice_lang);
      } else if (!r.end_call) setStatus("waiting for your reply");
    },
    [listen],
  );

  const send = useCallback(
    async (text: string) => {
      if (!sessionRef.current || !text.trim()) return;
      setTurns((t) => [...t, { role: "customer", text }]);
      setStatus("thinking...");
      const r = await post<AgentReply>(`/api/agent/session/${sessionRef.current}/message`, { text });
      await handleReply(r, mode);
    },
    [handleReply, mode],
  );
  sendRef.current = send;

  async function start() {
    stop();
    endedRef.current = false;
    setTurns([]);
    setCrm([]);
    if (mode === "vapi") return startVapi();
    const r = await post<AgentReply>(`/api/agent/${key}/start`, { lang });
    sessionRef.current = r.session_id;
    await handleReply(r, mode);
  }

  function startVapi() {
    if (!config?.vapi_public_key || !vapiAssistant) return;
    const vapi = new Vapi(config.vapi_public_key);
    vapiRef.current = vapi;
    vapi.on("message", (m: { type: string; role?: string; transcript?: string; transcriptType?: string }) => {
      if (m.type === "transcript" && m.transcriptType === "final" && m.transcript) {
        setTurns((t) => [...t, { role: m.role === "assistant" ? "bot" : "customer", text: m.transcript! }]);
      }
    });
    vapi.on("call-end", () => setStatus("Vapi call ended - recording and transcript are saved by the end-of-call webhook"));
    setStatus("connecting to Vapi...");
    void vapi.start(vapiAssistant).then(() => setStatus("Vapi call live"));
  }

  function stop() {
    endedRef.current = true;
    recRef.current?.abort();
    window.speechSynthesis?.cancel();
    vapiRef.current?.stop();
    vapiRef.current = null;
    setStatus("idle");
  }

  function exportTranscript() {
    const md = [
      `# Call transcript - ${agent?.name ?? key}`,
      `Session: ${sessionRef.current} | Mode: ${mode} | Outcome: ${JSON.stringify(reply?.state.outcome)}`,
      "",
      ...turns.map((t) => `**${t.role === "bot" ? "BOT" : "CUSTOMER"}** ${t.intent ? `[${t.intent}]` : ""}: ${t.text}` +
        (t.citations?.length ? `\n  - sources: ${t.citations.join("; ")}` : "")),
    ].join("\n");
    const a = document.createElement("a");
    a.href = URL.createObjectURL(new Blob([md], { type: "text/markdown" }));
    a.download = `transcript_${key}_${sessionRef.current ?? "vapi"}.md`;
    a.click();
  }

  return (
    <div className="grid two">
      <section className="card">
        <h2>Web call</h2>
        <div className="row">
          <label>
            Agent
            <select value={key} onChange={(e) => setKey(e.target.value)}>
              {agents.map((a) => (
                <option key={a.key} value={a.key}>{a.name}</option>
              ))}
            </select>
          </label>
          <label>
            Opening language / register
            <select value={lang} onChange={(e) => setLang(e.target.value)}>
              {agent?.languages.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
          </label>
          <label>
            Mode
            <select value={mode} onChange={(e) => setMode(e.target.value as Mode)}>
              <option value="browser">Browser voice (Web Speech ASR + TTS)</option>
              <option value="text">Text (type customer turns)</option>
              <option value="vapi" disabled={!vapiAssistant}>Vapi web call {vapiAssistant ? "" : "(not configured)"}</option>
            </select>
          </label>
        </div>
        <p className="muted small">{agent?.description}</p>
        <div className="row">
          <button className="primary" onClick={start}>Start call</button>
          <button onClick={stop}>Hang up</button>
          <button onClick={exportTranscript} disabled={!turns.length}>Export transcript</button>
          <span className="status">{status}</span>
        </div>
        {voiceNote && <p className="muted small">{voiceNote}</p>}
        <div className="transcript">
          {turns.map((t, i) => (
            <div key={i} className={`turn ${t.role}`}>
              <div className="who">{t.role === "bot" ? "Bot" : "Customer"} {t.intent && <span className="tag">{t.intent}</span>}
                {t.lang && <span className="tag">{t.lang}</span>} {t.latency != null && <span className="tag">{t.latency} ms</span>}</div>
              <div>{t.text}</div>
              {t.citations && t.citations.length > 0 && (
                <details><summary>{t.citations.length} KB source(s)</summary>{t.citations.map((c) => <div key={c} className="cite">{c}</div>)}</details>
              )}
            </div>
          ))}
          {interim && <div className="turn customer interim">{interim}...</div>}
        </div>
        {mode !== "vapi" && (
          <form className="row" onSubmit={(e) => { e.preventDefault(); void send(typed); setTyped(""); }}>
            <input className="grow" value={typed} onChange={(e) => setTyped(e.target.value)} placeholder="Type a customer reply (works in any mode)" />
            <button type="submit">Send</button>
          </form>
        )}
      </section>
      <section className="card">
        <h2>Call state</h2>
        {reply ? (
          <>
            <p><b>Stage:</b> {reply.state.stage} | <b>Pending:</b> {reply.state.pending ?? "-"} | <b>Language:</b> {reply.state.lang}
              {reply.state.dialects.length > 0 && <> | <b>Regional markers:</b> {reply.state.dialects.join(", ")}</>}</p>
            <h3>Collected slots</h3>
            <pre>{JSON.stringify(reply.state.slots, null, 2)}</pre>
            <h3>Outcome</h3>
            <pre>{JSON.stringify(reply.state.outcome, null, 2)}</pre>
          </>
        ) : <p className="muted">Start a call to see qualification state, outcome, and business actions.</p>}
        {crm.length > 0 && (<><h3>Business actions (mock CRM)</h3><pre>{JSON.stringify(crm, null, 2)}</pre></>)}
      </section>
    </div>
  );
}
