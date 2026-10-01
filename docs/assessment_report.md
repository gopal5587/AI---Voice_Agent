# Assessment report: requirement-to-evidence matrix

Every requirement from the assessment brief, where it is implemented, the evidence, and its status.

**Status key:**

- **Done:** implemented and verified by a test, report or generated evidence in this repository.
- **Done (text-level):** the behaviour is verified with scripted conversations through the production engine, but the
  voice recording itself still has to be captured.
- **Owner action:** needs an account, a deployment, or a human recording that can't be produced from this machine.

All data is synthetic. See [`data/raw/README.md`](../data/raw/README.md).

## Summary of measured results

| Area | Result | Source |
|---|---|---|
| Q1 scripted calls | 6 of 6 pass (cooperative, objection, conflicting or incomplete, out-of-scope, human request, excluded purpose) | [`evidence/q1/scenario_results.md`](../evidence/q1/scenario_results.md) |
| Q2 retrieval | 18 queries: 17 correct, 1 partially correct, 0 incorrect; 3 of 3 refusals correct; P95 search 0.6 ms | [`evidence/q2/retrieval_report.md`](../evidence/q2/retrieval_report.md) |
| Q2 KB build | 78 records (73 current, 5 superseded); 7 PII redactions; 4 duplicates removed (3 exact, 1 near); 3 source-quality flags; 1 extraction failure handled | `data/processed/ingestion_report.json` |
| Q3 scripted calls | 8 of 8 pass (3 PH, 5 ID, including Javanese and Sundanese speech) | [`evidence/q3/scenario_results.md`](../evidence/q3/scenario_results.md) |
| Q4 nudges | 15 runs: 18 nudges, 0 false positives, 100% of required kinds; 46 repeat or low-value candidates suppressed | [`evidence/q4/latency_report.md`](../evidence/q4/latency_report.md) |
| Q4 latency | End-to-end from trigger word to display: P50 2.08 s, P95 3.22 s (5 concurrent calls); rules plus control plus delivery under 5 ms; the rest is ASR | same |
| Unit and scenario tests | 45 of 45 pass (`python -m pytest tests -q`) | [`evidence/test_summary.md`](../evidence/test_summary.md) |
| Live API smoke test | 8 of 8 pass, locally and against the Docker image | `backend/scripts/smoke_test.py` |

## Question 1: knowledge-grounded voice agent

| Requirement | Implementation | Evidence | Status |
|---|---|---|---|
| One use case | Business-loan qualification (Kosha Capital) | [`docs/q1_voice_agent.md`](q1_voice_agent.md) | Done |
| Configure the voice platform with script and business rules | `configs/assistants/business_loan.json` (script, lines, slots, Vapi assistant with tools); `backend/scripts/sync_vapi.py` creates and updates it | Dry run prints the payload; the apply path was tested up to Vapi authentication | Done; **owner action:** run with your `VAPI_API_KEY` |
| Connect the Q2 KB; no hardcoded FAQs in the prompt | `kb_search` and `check_eligibility` tools call the Q2 index; eligibility rules are KB records | System prompt has flow and safety rules only; transcripts show per-answer KB citations | Done |
| Flow, qualification, grounded objections, fallback, escalation | `engine.py` and `business_loan.py` | Q1 transcripts | Done |
| Callable number or web calling interface | Web call in the *Voice Agent* tab (browser speech, offline); Vapi web call when configured | UI; `frontend/src/features/agent/VoiceAgent.tsx` | Done locally; **owner action:** deploy for a public URL, optionally attach a Vapi phone number |
| Record at least 3 test calls, with transcripts and results | 6 scripted calls with transcripts and pass/fail checks | [`evidence/q1`](../evidence/q1) | Done (text-level); **owner action:** record 3 or more voice calls from the UI or Vapi with the same scripts |
| Coverage: cooperative, objection, incomplete or conflicting, out-of-scope, human | q1_01 to q1_05 (plus excluded purpose) | Q1 results table | Done |
| States when information is unavailable | `INSUFFICIENT_EVIDENCE` leads to "I don't have verified information... I won't guess" | q1_04; `tests/test_kb.py::test_out_of_scope_queries_are_refused` | Done |
| Optional business action | Preliminary eligibility (rule IDs and KB version), callback scheduling within business hours, mock CRM summary, escalation webhook | CRM panel in the UI; `data/runtime/crm.jsonl` | Done |

## Question 2: production-ready knowledge base

| Requirement | Implementation | Evidence | Status |
|---|---|---|---|
| Mixed inputs: web, product, policy, forms, tables, PDFs, duplicates, inconsistent terms, PII | 16 synthetic sources in `data/raw/` with a registry | [`data/raw/README.md`](../data/raw/README.md) | Done |
| Explain website extraction and document parsing | Per-format parsers | [`docs/q2_knowledge_base.md`](q2_knowledge_base.md) section 1 | Done |
| Remove navigation, headers, footers, repeated and irrelevant content | Tag and class boilerplate removal; PDF running-header and footer removal | Ingestion report: `boilerplate_blocks_removed` per source | Done |
| Handle extraction failures; flag source errors | `ExtractionError` keeps the build going; fee-table validation | Corrupted brochure reported; 25% fee typo, conflicting row and missing value flagged | Done |
| Remove duplicates and near-duplicates | SHA-256 exact; 3-word-shingle Jaccard of 0.80 or more for near-duplicates | 3 exact and 1 near removed; `test_near_duplicate_threshold_separates_copies_from_versions` | Done |
| Standardize headings, dates, terminology, categories, form fields | `normalize.py` | Doc section 2; `terms` and `category` on records; form schema record | Done |
| Identify and protect PII | `pii.py` redaction before storage | 7 redactions; `test_no_pii_in_published_records` | Done |
| Schema and sample records; chunking; metadata; taxonomy; source tracking | Record schema with full provenance | Doc sections 5 and 6 (includes the brief's example record) | Done |
| Versioning, embedding and indexing, ranking, citations | Superseded linking, KB version hash, changelog; BM25 plus dense with RRF and a coverage-based confidence; citation strings | Doc sections 4, 7 and 8; `test_default_search_excludes_superseded_policy` | Done |
| At least 5 retrieval queries, each with question, chunk, source, explanation, verdict | 18 labelled queries | [`evidence/q2/retrieval_report.md`](../evidence/q2/retrieval_report.md) | Done |
| Connect to the voice bot or a retrieval interface | Both: agents call the index; the *Knowledge Base* tab is a retrieval interface | UI; transcripts with citations | Done |
| Product, policy, qualification, FAQ and objection answers | Covered by the evaluation categories | Retrieval report | Done |

## Question 3: native-language voice bots

| Requirement | Implementation | Evidence | Status |
|---|---|---|---|
| Philippines: life insurance or bancassurance, with English, Tagalog and Taglish | Lumina Life bank-referral lead qualifier | [`docs/q3_localization.md`](q3_localization.md); q3_ph transcripts | Done (text-level) |
| PH terminology: premium, policy, beneficiary, rider, lapse, coverage, bank referral | Used in lines, KB and ASR keyterms | Transcripts q3_ph_01 and 02 | Done |
| Indonesia: multifinance, formal and colloquial, loanwords, a regional accent outside Jakarta | Sinar Multifinance installment reminder; Javanese, Sundanese and Betawi normalization | q3_id transcripts | Done (text-level); regional coverage is **lexical only** |
| ID terminology: cicilan, tenor, denda, DP, jatuh tempo, angsuran, pembiayaan | Lines, KB, keyterms | Transcripts q3_id_01 and 02 | Done |
| Language-specific ASR, configured and tested per market; report provider, model, quality, errors, accent | Deepgram Nova-3 `tl` and `id` with keyterms (Vapi); Web Speech `fil-PH` and `id-ID` (browser) | Q3 doc, ASR section and observed gaps; WER tool provided | Configured; **owner action:** record calls and correct transcripts to measure WER and accent performance |
| Localized design: scripts, FAQs, objections, rules, politeness, dates, amounts, payments | Per-market configs, KBs and agent classes | Q3 doc comparison table | Done |
| At least 3 localization examples per market | 3 PH and 3 ID, quoted from transcripts | Q3 doc | Done |
| Native TTS, with compromises documented | Azure `fil-PH-BlessicaNeural` and `id-ID-GadisNeural`; browser fallback warning | Q3 doc | Configured; compromises documented |
| Fallback and escalation stay in the customer's language and register | Same-language fallback and escalation lines; strict-greater language switching | q3_ph_03 (returns to Tagalog for escalation), q3_id_03 | Done |
| Coverage: cooperative, objection, mixed English and finance terms, colloquial, escalation, ID regional accent | 8 scenarios | Q3 results table | Done (text-level) |
| Two recorded calls per market | Scripts ready; web UI and Vapi recording paths | | **Owner action** |
| Known native-speaker and compliance gaps | Listed | Q3 doc, observed gaps | Done |

## Question 4: live insights and nudges

| Requirement | Implementation | Evidence | Status |
|---|---|---|---|
| Streaming input: live audio or replay at real-time speed in chunks | 100 ms PCM chunks paced at 1x over the WebSocket; live mic mode | [`docs/q4_realtime_nudges.md`](q4_realtime_nudges.md) section 1 | Done |
| Continuous ASR with agent and customer separation; transcription latency per chunk | Per-channel streaming Vosk (Deepgram multichannel adapter) | Latency report: per-chunk compute and finalization lag | Done |
| Signals: topic shifts, compliance and risk, frustration, buying signals, missed opportunities, callback needs | `signals.py` and `rules.json` | Q4 doc section 2 | Done |
| Short actionable nudges via dashboard and WebSocket | *Live Nudges* tab; `/ws/realtime` | Event logs `evidence/q4/event_logs/` | Done |
| End-to-end and component latency, P50 and P95 (ASR, signals, LLM, delivery) | Stamped per stage; client display acknowledgement | Latency report (LLM reported as n/a because no key was used) | Done |
| Nudge control: thresholds, duplicates, cooldowns, topic grouping, priorities, expiry | `nudges.py` | Q4 doc section 3; `tests/test_nudges.py` | Done |
| Approximate false-positive analysis | Labelled scenarios, a held-out negative control, a missed-callback case discussed | Q4 doc section 6 | Done |
| Coverage: cross-sell, disclosure or risky statement, frustration, noisy call | 5 scenarios, including 2 noisy (one held out) | Latency report | Done |
| At least one compliance example and one missed-opportunity example | risky_claim, fee_evasion and recording_disclosure; cross_sell closed as `missed_opportunity` | Latency report, round-1 detail | Done |
| Limitations at 10x scale and with noisy audio | | [`production_improvements.md`](production_improvements.md) sections 5 and 6 | Done |
| Recorded live demo | Dashboard replays with synced audio | | **Owner action:** screen-record the dashboard |

## Submission package

| Item | Status |
|---|---|
| Repository with README and environment-variable template | Done (`README.md`, `.env.example`); **owner action:** push to GitHub |
| Architecture diagram, setup, sample inputs, test results | Done (README mermaid diagram; `data/`; `evidence/`) |
| Recorded voice calls, transcripts, audio samples | Transcripts and Q4 audio done; **owner action:** voice recordings for Q1 and Q3 |
| Video walkthrough | **Owner action** (outline in the README) |
| Known limitations and production-improvement plan | Done (`docs/production_improvements.md`; limitations in each question doc) |
| No credentials, secrets or customer information committed | Secret scan clean; `.env` gitignored; only synthetic, redacted data |

## Decisions worth defending

1. **Deterministic engine, with the LLM optional.** The offline engine makes every test reproducible and every answer
   traceable to a KB record. The Vapi path uses the same KB and rules through tools for natural conversation. This
   trades some conversational flexibility for verifiable grounding.
2. **Coverage-weighted confidence for refusals.** Pure similarity scores can't tell "foreclosure charge" from "home
   loan": both match generic words. Weighting by IDF-weighted coverage of the query's terms, with a heavy penalty for
   terms the corpus has never seen, is what makes the 3 refusals and the 15 answers separable at one threshold.
3. **Rules first for nudges.** Compliance nudges must be explainable and cheap. Rules cost under 1 ms. An LLM
   classifier is reserved for ambiguous customer turns and has to pass the same gates.
4. **Honest latency.** End-to-end latency is measured from the trigger word's audio, not from utterance end. This
   raised the reported number from about 0.8 s to about 2.1 s, and showed the bottleneck is ASR decoding, not the
   pipeline.
