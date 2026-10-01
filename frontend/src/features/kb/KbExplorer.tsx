import { useEffect, useState } from "react";
import { api, KbSearchResult, post } from "../../api";

const EXAMPLES: Record<string, string[]> = {
  IN: ["What is the foreclosure charge?", "How many years should my business be running?", "Your interest rate is too high",
    "Is a GST certificate mandatory?", "Do you offer home loans?"],
  PH: ["What happens if I miss my premium payment?", "I already have an HMO", "Can I add a rider later?"],
  ID: ["berapa denda keterlambatan angsuran", "saya sudah bayar kok masih ditagih", "berapa harga emas hari ini"],
};

interface Report {
  summary?: Record<string, unknown>;
  duplicates?: { removed: string; duplicate_of: string; type: string; locator: string }[];
  quality_flags?: { source_id: string; locator: string; issue: string; detail: string }[];
  sources?: { source_id: string; status: string; error?: string; pii_redactions?: Record<string, number> }[];
  version_conflicts?: { topic: string; old: { version: string; content: string }; new: { version: string; content: string } }[];
}

export default function KbExplorer() {
  const [q, setQ] = useState(EXAMPLES.IN[0]);
  const [market, setMarket] = useState("IN");
  const [superseded, setSuperseded] = useState(false);
  const [res, setRes] = useState<KbSearchResult | null>(null);
  const [ans, setAns] = useState<{ answer: string; status: string; citations: string[]; generator: string } | null>(null);
  const [report, setReport] = useState<Report>({});

  useEffect(() => { api<Report>("/api/kb/report").then(setReport).catch(() => undefined); }, []);

  async function search(query = q) {
    setQ(query);
    const params = new URLSearchParams({ q: query, market, include_superseded: String(superseded), top_k: "5" });
    setRes(await api<KbSearchResult>(`/api/kb/search?${params}`));
    setAns(await post("/api/kb/answer", { query, market, lang: market === "ID" ? "id" : "en" }));
  }

  return (
    <div className="grid two">
      <section className="card">
        <h2>Retrieval interface</h2>
        <form className="row" onSubmit={(e) => { e.preventDefault(); void search(); }}>
          <input className="grow" value={q} onChange={(e) => setQ(e.target.value)} />
          <select value={market} onChange={(e) => setMarket(e.target.value)}>
            <option value="IN">IN business loan</option><option value="PH">PH life insurance</option><option value="ID">ID motor finance</option>
          </select>
          <label className="inline"><input type="checkbox" checked={superseded} onChange={(e) => setSuperseded(e.target.checked)} /> include superseded</label>
          <button className="primary" type="submit">Search</button>
        </form>
        <div className="row wrap">{EXAMPLES[market].map((e) => <button key={e} className="chip" onClick={() => void search(e)}>{e}</button>)}</div>
        {ans && (
          <div className={`banner ${ans.status === "OK" ? "ok" : "warn"}`}>
            <b>{ans.status === "OK" ? "Grounded answer" : "Refusal (insufficient evidence)"}</b> <span className="tag">{ans.generator}</span>
            <div>{ans.answer}</div>
            {ans.citations.map((c) => <div key={c} className="cite">{c}</div>)}
          </div>
        )}
        {res && (
          <>
            <p className="muted small">status {res.status} | {res.latency_ms} ms | ranking = 0.5 x RRF(BM25, dense) + 0.5 x confidence</p>
            {res.hits.map((h, i) => (
              <div key={h.record_id} className="hit">
                <div className="row between">
                  <b>#{i + 1} {h.title}</b>
                  <span className="tag">conf {h.confidence.toFixed(2)}</span>
                </div>
                <div className="muted small">{h.record_id} | {h.category} | v{h.version} | {h.status} | {h.source_locator}</div>
                <div>{h.content}</div>
                <div className="muted small">BM25 {h.bm25} | dense {h.dense} | term coverage {h.term_coverage} | <a href={h.source_uri} target="_blank">{h.source_uri}</a></div>
              </div>
            ))}
          </>
        )}
      </section>
      <section className="card">
        <h2>Ingestion report</h2>
        <pre>{JSON.stringify(report.summary, null, 2)}</pre>
        <h3>Extraction failures</h3>
        {report.sources?.filter((s) => s.status !== "ok").map((s) => <div key={s.source_id} className="banner warn">{s.source_id}: {s.error}</div>)}
        <h3>PII redactions</h3>
        {report.sources?.filter((s) => s.pii_redactions && Object.keys(s.pii_redactions).length).map((s) =>
          <div key={s.source_id}>{s.source_id}: {JSON.stringify(s.pii_redactions)}</div>)}
        <h3>Source quality flags</h3>
        {report.quality_flags?.map((f) => <div key={f.locator + f.issue} className="small">{f.locator} <span className="tag">{f.issue}</span> {f.detail}</div>)}
        <h3>Duplicates removed</h3>
        {report.duplicates?.map((d) => <div key={d.removed} className="small">{d.locator} <span className="tag">{d.type}</span> duplicate of {d.duplicate_of}</div>)}
        <h3>Version conflicts (old superseded by new)</h3>
        {report.version_conflicts?.map((v) => (
          <div key={v.topic} className="small hit"><b>{v.topic}</b><div>v{v.old.version}: {v.old.content}</div><div>v{v.new.version}: {v.new.content}</div></div>
        ))}
      </section>
    </div>
  );
}
