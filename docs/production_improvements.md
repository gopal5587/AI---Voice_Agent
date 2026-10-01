# Production improvements

This build is an assessment prototype: synthetic data, a single process, file-based storage, and offline models by
default. This document lists what would change before handling real customers, ordered by risk.

## 1. Security and privacy

| Area | Prototype | Production |
|---|---|---|
| Secrets | `.env` file, gitignored | Secret manager (AWS Secrets Manager, GCP Secret Manager, Doppler); per-environment keys; rotation; CI secret scanning (gitleaks) as a merge gate |
| API access | Open demo endpoints; Vapi webhooks checked with `X-Vapi-Secret` | OAuth2/OIDC for agents and supervisors; per-tenant API keys; HMAC-signed webhooks with timestamp and replay window; rate limits per key and IP; mTLS between services |
| PII in the KB | Regex and contextual redaction before indexing; `pii_redacted` flag per record | Add an NER model (Presidio or similar) behind the regexes; block publishing when a record still matches PII detectors; a reviewer queue for flagged records |
| PII in calls | Transcripts and CRM events in local JSON files; unanswered questions redacted before logging | Encrypt at rest (KMS) and in transit; redact transcripts before analytics; store raw audio only in a restricted bucket; access audited per record |
| Prompt injection | The KB is curated and synthetic; the LLM is constrained to retrieved records | Treat ingested web content as untrusted: strip instructions at ingestion, keep the system prompt separate from retrieved text, validate tool arguments with schemas, allow-list tools per agent |
| Tool safety | Tools write to a mock CRM | Idempotency keys on every write; human approval for irreversible actions; dry-run mode in staging |

## 2. Consent, recording and retention

- Announce automation and recording in the first turn. All three bots do this already, and Q4 checks it on live human
  calls with the `recording_disclosure` state check. Store the consent outcome with the call.
- Make retention configurable per market: for example 90 days for raw audio, longer for redacted transcripts, and
  deletion on verified customer request. Keep a deletion log.
- Respect contact-hour rules and do-not-call lists in the dialer. The Indonesian bot records `within_contact_hours`, but
  enforcement belongs before the call is placed.
- Honour data residency (India DPDP Act, Philippine Data Privacy Act, Indonesian PDP Law) by deploying per-region
  storage and model endpoints where required.

## 3. Knowledge base operations

- Move from a file build to an ingestion service: source connectors (CMS, SharePoint, S3) with change detection, run
  the existing pipeline per changed document, and publish a new KB version only after automated checks pass. The
  checks would be: retrieval evaluation above threshold, no PII hits, and no unresolved version conflicts.
- Use human approval for policy-bearing categories (rates, fees, eligibility). The ingestion report already lists the
  version conflicts and quality flags a reviewer needs.
- Pin each conversation to the KB version it started on (`kb_version` is already on every record and eligibility
  result), so an answer can be audited against the exact source text.
- Grow the 18-query retrieval evaluation to several hundred labelled queries per market, sampled from real call
  transcripts. Track recall@k, refusal precision and recall, and answer faithfulness on every KB release.

## 4. Model evaluation and monitoring

- **Offline:** the scenario suites (14 conversations, 5 real-time calls) run in CI. Extend them with recorded calls
  that have corrected transcripts, so ASR, NLU and nudge quality are measured on real speech. The WER script already
  takes corrected and ASR transcript pairs.
- **Online:**
  - Dashboards for containment, escalation rate by reason, fallback rate, refusal rate, average handle time, and
    callback completion.
  - Latency at P50, P95 and P99 per stage. The real-time pipeline already stamps audio receipt, ASR final, signal,
    nudge decision, send and display.
  - Nudge acceptance rate, meaning the agent acted on the nudge (`resolved_by_agent`) versus `expired_unactioned`.
- **Quality sampling:** QA reviewers score a random 1 to 2% of calls plus every escalated or complained call. Their
  labels feed the evaluation sets.
- **Drift:** alert when fallback or refusal rates, language-switch frequency, or ASR confidence move outside their
  baselines, for example after a product launch or a new region.
- **LLM changes:** evaluate prompt and model versions against the scenario suites before rollout. Roll out with a canary
  and automatic rollback on regression.

## 5. Scaling to 10x

The prototype runs one Python process with in-memory sessions. For 10x the call volume:

| Component | Change |
|---|---|
| Voice agent sessions | Move session state from process memory to Redis with a TTL; make the API stateless behind a load balancer; scale API pods horizontally |
| Retrieval | Move the in-process numpy index to Qdrant (adapter already exists) or pgvector with replicas; cache frequent queries per KB version; measured search is under 1 ms locally, so retrieval is not the bottleneck |
| Real-time ASR | The measured latency bottleneck, but from model behaviour rather than load. Five concurrent calls and a single call give the same end-to-end P50 (about 2.1 s), because the Vosk small model emits a word in its partial hypothesis 1.1 to 2.1 s after the word is spoken. Per-chunk compute is about 25 ms at P50, with occasional spikes above 100 ms. For latency, use a low-latency streaming ASR (Deepgram Nova-3 multichannel, adapter included) and measure it with the same harness. For volume, run ASR workers with one stream per channel, shard calls by call ID, and apply backpressure by dropping to final-only processing under overload |
| Signal engine and nudges | Stateless per call apart from small rolling state; run inside the ASR worker for locality, or as a consumer on a per-call Kafka or Redis Streams partition |
| LLM classifier | Only for ambiguous turns (rules first); batch per call, set a token budget per call, use a smaller model, and degrade to rules-only when LLM latency exceeds the nudge's usefulness window |
| WebSocket fan-out | A dedicated gateway (or managed pub/sub such as Ably or Pusher) between workers and supervisor dashboards |
| Storage | Event logs to object storage and a warehouse for analytics; CRM writes through a queue with retries |

Capacity planning starts from the per-stage numbers in [`evidence/q4/latency_report.md`](../evidence/q4/latency_report.md).
Rules-based signal extraction and nudge control cost under 1 ms per utterance, so the cost and latency at scale are
dominated by ASR, plus the LLM if it's enabled.

## 6. Noisy audio and real telephony

- **Measured so far:** two noisy test calls (4 dB and 6 dB SNR, one held out from tuning) produced zero false-positive
  nudges after the gating changes, and ASR word error rate rises sharply with noise (see
  [`evidence/q4/asr_wer.md`](../evidence/q4/asr_wer.md)). These are synthetic voices with mixed-in noise, not real phone
  lines.
- **Next steps:**
  - Evaluate on 8 kHz narrowband call recordings with real background noise and cross-talk.
  - Add noise suppression before ASR (RNNoise or a telephony provider's built-in suppression).
  - Use per-channel recording (already assumed) so diarization errors don't cause speaker mix-ups.
  - Keep the ASR-confidence and minimum-words gates. Tune thresholds per market on labelled noisy calls.
  - For the voice agents, add Vapi or Deepgram endpointing tuning and an explicit "bad line" path. The callback
    signal already catches "the line is very bad", and the agents offer a callback.

## 7. Compliance review

- Have compliance teams review every customer-facing line, objection answer and nudge message before launch, per
  market. Store approvals with the config version.
- The specific rules encoded here are reasonable defaults, not legal advice:
  - Q1: no approval guarantees; disclose that the decision is subject to credit assessment; no collection of PAN,
    Aadhaar or bank details on the call.
  - Q3 PH: licensed-advisor handoff; illustration disclaimer.
  - Q3 ID: no third-party debt disclosure; no pressure after a hardship disclosure.
  - Q4: risky-claim and fee-evasion nudges.
- They must be checked against the current RBI digital lending guidelines, Insurance Commission circulars, and OJK
  consumer-protection and collection regulations.
- Keep an audit trail per call: the config version, KB version, every retrieved record ID and every tool call. Most of
  this is already in the session JSON and the CRM event log.
