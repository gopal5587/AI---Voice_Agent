# Q2: Knowledge base design

Code: [`backend/app/ingestion`](../backend/app/ingestion) and [`backend/app/retrieval`](../backend/app/retrieval).
Build it with `python -m app.ingestion.pipeline` (from `backend/`). Outputs go to `data/processed/`:

- `kb_records.jsonl`: one record per line.
- `ingestion_report.json`: per-source status, removed boilerplate, PII counts, duplicates, quality flags and version
  conflicts.
- `kb_changelog.json`: what was added, removed or changed versus the previous build.

The corpus is synthetic. It deliberately contains the defects the assessment lists, so each cleaning step has something
to demonstrate: navigation and cookie banners, a promo block, a 2025 FAQ superseded by a 2026 one, an exact copy and a
near-copy of a paragraph, a 25% typo in the fee table, a missing value, a corrupted PDF, inconsistent terms (*tenor*,
*tenure*, *repayment period*), cryptic form field names, and a CRM export full of fake PII.

## 1. Collection and parsing

Every file is registered in [`data/raw/sources.json`](../data/raw/sources.json) with `source_id`, `source_type`,
`url`, `market`, `product`, default category, `version`, `status` (current or superseded), and its successor if it's
superseded. Unregistered files are reported, not ingested, so nothing enters the KB without provenance.

| Input | Parser | What it does |
|---|---|---|
| Web pages (HTML) | BeautifulSoup | Drops `nav`, `header`, `footer`, `aside`, `script` and `style`, plus any element whose class matches cookie, banner, promo, newsletter, social or breadcrumb. Splits sections on `h2`/`h3`. Reads version and effective-date lines. Each section gets a locator such as `business-loan-faq.html#h2-3` |
| Forms (HTML `<form>`) | Same parser, form branch | Extracts every control (name, type, label, required, options) and maps cryptic names to a canonical schema (`ann_rev` to `annual_turnover_inr`, `cibil` to `credit_score`), marking PII fields (`pan_no`, `dob`, `mob`) |
| PDFs | pypdf | Text per page. Removes running headers and footers ("Confidential", "Page N"). Detects headings with a short-Title-Case-line heuristic and keeps page locators (`credit_policy_v2.pdf#page-1`). Unreadable or text-free PDFs raise `ExtractionError` and are reported as failed sources; the build continues |
| Rule tables (CSV) | csv | One record per rule with machine-readable `structured` fields (`field`, `operator`, `value`). These records feed the eligibility engine directly, so the bot's rules are KB data, not prompt text |
| Fee tables (CSV) | csv + validation | Flags `suspicious_value` (a percentage fee above 10%), `conflicting_duplicate_row` (same fee, different value; the first is kept) and `missing_value` |
| Markdown playbooks | Heading splitter | One section per heading, with a locator such as `ph_faq_objections.md#sec-5` |
| Call-note exports (text) | Note splitter | One section per note. The raw text, including the preamble, is audited for PII before anything is kept |

From the current build: 15 sources parsed, 1 failed (the corrupted brochure PDF, error `PdfStreamError: Stream has
ended unexpectedly`), and 3 quality flags raised on the fee table. All are listed with locators in the ingestion report
and visible in the UI's Knowledge Base tab.

## 2. Cleaning and normalization

- **Boilerplate:** removed at parse time (above). Removed blocks are counted per source in the report.
- **Headings:** whitespace and case normalized, trailing punctuation dropped (`normalize_heading`).
- **Dates:** any of `15 Aug 2026`, `2026-08-15`, `15/08/2026` or `August 15, 2026` become ISO `2026-08-15`
  (`normalize_date`).
- **Terminology:** a glossary maps variants to canonical terms, for example *tenor*, *repayment period* and *loan
  duration* to `tenure`; *prepay* and *close the loan early* to `foreclosure`; *cicilan* to `angsuran`; *hulog* to
  `premium`. Canonical terms are stored on each record (`terms`) and used to expand queries, so a customer saying
  "pay off early" retrieves the foreclosure record.
- **Categories:** keyword rules assign one of `product_feature`, `pricing_fees`, `eligibility_rule`, `policy`,
  `faq`, `objection_handling`, `compliance`, `contact_escalation`, `partnership_benefits`, `form_schema`, falling back
  to the source's default category.
- **Form fields:** canonical names and types, with PII marking (above).

## 3. PII protection

`pii.redact()` runs on every chunk before it is stored:

- Regexes for email, Indian PAN, Aadhaar, card numbers, and phone numbers for India, the Philippines and Indonesia.
- A contextual name rule ("customer Ravi Kumar", "Name: ...").

Matches are replaced with typed placeholders (`[PHONE]`, `[EMAIL]`, `[PAN]`, `[NAME]`), and the record gets
`pii_redacted: true`. Company contact addresses on the brand's own domain are allow-listed. The current build redacted
7 items, all in the CRM export. `tests/test_kb.py` scans every published record with independent PII patterns and fails
the build if any leak.

## 4. Deduplication and versioning

- **Exact duplicates:** a SHA-256 hash of the normalized content. A repeated "Uses of the Loan" section and two
  unchanged answers in the 2025 FAQ are removed, keeping the current-version copy.
- **Near duplicates:** Jaccard similarity of 3-word shingles at 0.80 or above, within the same market and status. The
  partner page's lightly edited copy of the loan-uses paragraph (similarity 0.84) is removed. The threshold was set
  from the measured distribution: genuinely different answers on the same topic, such as the 2025 and 2026 contact
  answers, score at most 0.74.
- **Versions:** a record from a superseded source is kept, marked `status: superseded`, and linked to its replacement
  with `superseded_by`. Retrieval excludes superseded records unless `include_superseded=true`. The 5 conflicts are
  listed side by side in the report, for example foreclosure after 12 EMIs at 5% (2025) versus after 6 EMIs at 4%
  (2026).
- **KB version:** a hash of all content hashes, stamped on every record and on every eligibility result. The changelog
  records added, removed and changed records per build.

Current build: 78 records (73 current, 5 superseded), 4 duplicates removed.

## 5. Schema and sample record

| Field | Meaning |
|---|---|
| `record_id` | `kb_{market}_{title-slug}_{hash6}`: stable for the same content, readable in citations |
| `title`, `doc_title` | Section heading, and the document it came from |
| `content` | Cleaned, PII-redacted chunk text |
| `category`, `product`, `market`, `lang` | Taxonomy and filters |
| `source_id`, `source_type`, `source_uri`, `source_locator` | Provenance down to the section, row, page or note |
| `version`, `effective_from`, `status`, `superseded_by` | Versioning |
| `content_hash`, `kb_version` | Deduplication and build identity |
| `pii`, `pii_redacted` | Whether PII was detected, and whether it was redacted |
| `terms` | Canonical glossary terms found in the record |
| `structured` | Machine-readable payload for rules, fees and form fields |

The example from the assessment brief, as produced by the pipeline:

```json
{
  "record_id": "kb_in_branch_partnership_benefits_6a3035",
  "title": "Branch Partnership Benefits",
  "doc_title": "Branch Partnership Program",
  "content": "Operational, marketing, and technology support is provided to branch partners. Partners receive co-branded marketing material, access to the Kosha partner portal for lead tracking, and training for their staff.",
  "category": "partnership_benefits",
  "product": "branch_partnership",
  "market": "IN",
  "lang": "en",
  "source_id": "web_branch_partnership",
  "source_type": "website section",
  "source_uri": "https://kosha-demo.example/partners",
  "source_locator": "branch-partnership.html#h2-1",
  "version": "2026.07",
  "status": "current",
  "superseded_by": null,
  "pii": false,
  "pii_redacted": false,
  "kb_version": "1b1460816e"
}
```

A rule record carries `structured`, for example
`{"rule_id": "BL-ELIG-01", "field": "business_vintage_years", "operator": ">=", "value": "2"}`. The agent's
eligibility check reads these rules from the index. Changing the CSV changes the bot's behaviour after a rebuild, with
no prompt edits.

## 6. Chunking

Sections are already semantically scoped (one FAQ answer, one policy clause, one rule row, one note), so a chunk is one
section. Sections over 220 words (about 300 tokens) are split on sentence boundaries. Each chunk keeps its heading as
`title`, which is indexed with the content. Short chunks keep retrieval precise and answers quotable in a voice reply.

## 7. Indexing and retrieval

`KBIndex` (`backend/app/retrieval/index.py`) is built in-process at startup from `kb_records.jsonl`:

1. **Filters:** market, product, categories and status are applied first. Superseded records are excluded by default.
2. **Lexical:** BM25 over the title and content, with the query expanded by the glossary.
3. **Dense:** cosine similarity on embeddings.
   - Default: a local hashed word and character n-gram embedding (4,096 dimensions). It is deterministic, needs no
     API key, and tolerates spelling variants and ASR errors, but it is not semantic across languages.
   - With `EMBEDDING_PROVIDER=openai`: `text-embedding-3-small`.
   - With `QDRANT_URL`: vectors are pushed to Qdrant.
4. **Fusion:** reciprocal-rank fusion (k = 60) of the BM25 and dense rankings.
5. **Confidence:** `0.35 x dense + 0.25 x normalized BM25 + 0.40 x IDF-weighted query-term coverage`. Query terms
   that never occur in the corpus get twice the maximum IDF, so a query about *home loans* or *car insurance* has low
   coverage even when generic words match.
6. **Ranking:** `0.5 x fused + 0.5 x confidence`, with a 1.1x boost for objection-handling records when the caller is
   objecting.
7. **Refusal:** if the top confidence is below `RETRIEVAL_MIN_SCORE` (0.40), the result is `INSUFFICIENT_EVIDENCE`. The
   answer layer then returns a market-language "I don't have verified information" message instead of guessing.

## 8. Answers and citations

`answer()` returns the answer text, `record_ids`, and human-readable citations. The citation format is
`[record_id] doc_title > title (source_type, v<version>, <locator>)`.

- Without an LLM, the answer is extractive: the best-matching sentences from the top records.
- With `OPENAI_API_KEY`, GPT-4o-mini rewrites only from the retrieved records, and must return
  `INSUFFICIENT_EVIDENCE` if they don't contain the answer.

Voice-agent replies carry the same citations into transcripts (see the Q1 and Q3 evidence), the web UI shows them per
turn, and Vapi tool responses include them.

## 9. Retrieval evaluation

There are 18 labelled queries in [`data/eval/retrieval_queries.json`](../data/eval/retrieval_queries.json), spanning
product, policy, qualification, FAQ, objection, the PH and ID markets, and 3 out-of-scope probes. Results are in
[`evidence/q2/retrieval_report.md`](../evidence/q2/retrieval_report.md): 17 correct, 1 partially correct, 0 incorrect,
3 of 3 refusals correct, and search latency P50 0.4 ms / P95 0.6 ms.

The partial result is kept in the report deliberately. "What documents are required for the application?" ranks the
"I don't want to share my documents" objection first, and the actual documents list second. Both are relevant, but the
best record should be first. A cross-encoder re-ranker or OpenAI embeddings would likely fix this. The threshold and
fusion weights were tuned on these same queries, so the numbers are optimistic. A held-out query set built from real
call transcripts is the next step (see [`production_improvements.md`](production_improvements.md)).
