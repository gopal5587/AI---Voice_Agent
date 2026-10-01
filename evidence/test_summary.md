# Test summary

Environment: Windows 11, Python 3.13, 12-thread laptop CPU, no API keys (offline providers: local embeddings, Vosk
ASR, deterministic agents). All data is synthetic.

| Suite | Command (from `backend/` unless noted) | Result |
|---|---|---|
| Unit and scenario tests | `python -m pytest tests -q` (repository root) | **45 of 45 passed** |
| Q1 and Q3 conversation scenarios | `python scripts/run_agent_scenarios.py` | **14 of 14 passed** (6 Q1, 3 PH, 5 ID) |
| Q2 retrieval evaluation | `python scripts/eval_retrieval.py` | **17 correct, 1 partially correct, 0 incorrect** of 18; 3 of 3 refusals |
| Q4 real-time evaluation | `python scripts/run_realtime_eval.py --rounds 3` | 15 concurrent runs plus 5 single-call runs; **0 false positives, 100% of required kinds**; end-to-end P50 2.08 s / P95 3.22 s |
| Q4 ASR word error rate | `python scripts/wer.py` | 4 to 18% on clean calls, 21 to 47% on noisy calls ([`q4/asr_wer.md`](q4/asr_wer.md)) |
| Live API smoke test | `python scripts/smoke_test.py` (backend running) | **8 of 8 passed** locally and against the Docker image |
| Frontend type check and build | `npm run build` (in `frontend/`) | Passed (TypeScript strict, Vite production build) |
| Docker image | `docker build -f backend/Dockerfile .` (repository root) | Built; container passes the smoke test |
| Secret scan | ripgrep for key, token and private-key patterns; `.env` files | Clean: only `.env.example` with empty placeholders |

## What the pytest suite covers

- **KB (`tests/test_kb.py`):**
  - No exact duplicate content; exact and near duplicates detected.
  - The near-duplicate threshold separates copies from versions.
  - No email, PAN, Indian mobile or Aadhaar number in any published record; the redactor masks the common
    identifiers.
  - Every record is traceable to a registered source.
  - Superseded records link to a current replacement.
  - Default search excludes superseded policy, and the old version is reachable on request.
  - Out-of-scope queries are refused in English and Indonesian.
  - Grounded answers carry well-formed citations.
- **Agents (`tests/test_agents.py`):**
  - All 14 conversation scenarios, each with per-turn expectations: intent, citations, slot values, reply language,
    required and forbidden phrases, final stage, outcome and actions.
  - The required Q1 behaviours are all covered.
  - Money parsing for lakh, crore, juta, sejuta and k; years parsing.
  - The eligibility outcomes `pre_qualified`, `not_eligible`, `needs_review` and excluded purpose, computed from KB
    rules.
- **Nudges (`tests/test_nudges.py`):**
  - Low-confidence, low-ASR-confidence and too-short candidates are suppressed.
  - Duplicates are grouped; cooldown folds a new topic into the visible card, and the same topic isn't repeated.
  - Max-active priority eviction; expiry.
  - Frustration needs accumulated evidence; risky agent claims trigger a compliance nudge.

## Not covered by automated tests

- Real voice calls (browser or Vapi), Tagalog and Indonesian ASR accuracy, and acoustic accent robustness. These need
  recordings; see the README section "Recording the evidence and the walkthrough".
- The React UI in a real browser. It type-checks and builds, and the API and WebSocket it uses pass the smoke test, but
  no automated browser test was run.
- LLM-enabled paths (OpenAI answer generation, Vapi LLM conversation, LLM nudge classifier). They are implemented with
  deterministic fallbacks but were not exercised without keys.
