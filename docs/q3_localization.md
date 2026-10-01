# Q3: Localized voice bots for the Philippines and Indonesia

Both bots run on the same conversation engine as Q1 (`backend/app/agents/engine.py`). They are separate agents with
their own goal, flow, slots, compliance rules, business actions and knowledge base, not translations of the Q1 bot. All
brands, products and figures are synthetic demo data.

| | Philippines: Lumina Life (`ph_life_insurance`) | Indonesia: Sinar Multifinance (`id_consumer_finance`) |
|---|---|---|
| Use case | Bank-referral life-insurance lead qualification (bancassurance) | Motor-loan installment reminder and promise to pay |
| Languages and registers | Taglish (Tagalog-English code-switching) and English | Formal Indonesian (*Bapak/Ibu*, *saya*) and colloquial Jakarta register (*Kak*, *gue*, *nggak*) |
| Collected data | Age, dependants or beneficiaries, monthly budget, goal, existing cover; then advisor callback | Identity, payment date, payment channel |
| Market-specific logic | PHP formatting (₱2,500), coverage illustration from budget, rider hint for critical illness, Tagalog day and time phrasing (*Sabado, alas-3:00 ng hapon*) | IDR formatting (Rp850.000), Indonesian dates (*Minggu, 4 Oktober 2026*), late-fee estimate (0.2% per day from the KB), WIB time-of-day greeting, contact-hour check (08:00 to 20:00 WIB) recorded in the outcome; enforcement belongs in the dialer |
| Compliance behaviour | Bot says it is not a licensed advisor; the premium is an illustration subject to underwriting; HMO is distinguished from life cover | No debt disclosure to third parties; no pressure after a hardship disclosure; an "already paid" claim is recorded for verification, not disputed |
| Business actions | `quotation_request`, `callback_scheduled`, `crm_summary`, `escalation` | `promise_to_pay`, `payment_claim`, `hardship_flag`, `crm_summary`, `escalation` |
| Knowledge base | `data/raw/ph/` (product page and customer-facing objection FAQ) | `data/raw/id/` (FAQ and reminder playbook) |

## How localization is implemented

- **Language and register detection.** Each turn is scored against per-language marker lexicons
  (`script.language_detection` in each config). The bot switches only when the new language scores strictly higher than
  the current one, so one English loanword in a Tagalog sentence doesn't flip the reply language. Every line in the
  script exists in each supported language or register, and the switch is logged in the session state.
- **Code-switching is expected, not a failure.** The Tagalog lines are written in natural Taglish ("Magkano po ang
  comfortable na budget ninyo para sa premium kada buwan?"), because Filipino customers say *premium*, *coverage* and
  *beneficiary* in English. The NLU parses *libo* and *k* amounts, Tagalog numbers, and *kada buwan* / *a month* as
  monthly.
- **Regional Indonesian speech.** Before parsing, Javanese, Sundanese and Betawi function words are normalized to
  standard Indonesian (*mboten* to *tidak*, *nggih* and *muhun* to *iya*, *sampun* and *parantos* to *sudah*, *durung*
  to *belum*, *sesok* to *besok*, *kagak* to *tidak*) in `nlu.REGIONAL_NORMALIZE`. Dialect markers are recorded on the
  session (`dialects`) for QA and analytics. Money parsing handles *juta*, *ribu*, *sejuta*, *Rp* and the `850.000`
  thousands separator.
- **Grounding.** Objections and questions retrieve from the market's own KB with canonical queries (`kb_query_map`).
  Unknown questions get a same-language refusal plus the human route, and facts quoted inside flow lines (retail admin
  fee, beneficiary limit) come from the KB at runtime through `kb_fact()`.

## Three concrete localization examples per market

All quotes come from the generated transcripts in [`evidence/q3/transcripts`](../evidence/q3/transcripts).

### Philippines

1. **Sector objection in colloquial Tagalog** ([q3_ph_02](../evidence/q3/transcripts/q3_ph_02_objections_colloquial.md)).
   The customer says "Ano ba yan, may HMO na ako eh, bakit kailangan ko pa ng life insurance?" The bot answers from the
   KB objection record: an HMO pays medical bills while you're alive, while life insurance pays your beneficiaries. It
   then returns to the consent question instead of losing the flow. HMO confusion is a Philippine-specific objection,
   since many employees have company HMO cover.
2. **Budget objection and local money phrasing** (q3_ph_02). "Grabe, mahal siguro yan, wala akong budget" triggers the
   *mahal* objection answer (coverage can start at PHP 500,000, with auto-debit). The later answer "Siguro 1,500 a month"
   is parsed as ₱1,500 monthly and produces "Base sa budget na ₱1,500 kada buwan, puwedeng nasa ₱1,200,000 ang coverage
   ninyo", followed by the mandatory "hindi po ako licensed financial advisor" disclaimer.
3. **Language following and Tagalog scheduling** ([q3_ph_03](../evidence/q3/transcripts/q3_ph_03_english_switch_escalation.md),
   [q3_ph_01](../evidence/q3/transcripts/q3_ph_01_cooperative_taglish.md)). When the customer answers in English, the bot
   continues in English. When they switch back with "Pwede ko bang makausap yung totoong tao?", the escalation is
   delivered in Tagalog. Callback times are spoken the local way: "sa Sabado, October 3, alas-3:00 ng hapon".

### Indonesia

1. **Register switching** ([q3_id_01](../evidence/q3/transcripts/q3_id_01_cooperative_formal.md) vs
   [q3_id_02](../evidence/q3/transcripts/q3_id_02_colloquial_objection.md)). The same reminder is formal for a formal
   customer ("Kapan Bapak berencana melakukan pembayaran?") and colloquial once the customer uses *gue* ("Rencananya mau
   bayar kapan, Kak?").
2. **"Belum gajian" and the late fee** (q3_id_02). "Waduh, gue belum gajian nih" is the most common Indonesian reason for
   paying late. It gets a KB-grounded answer that the 0.2% daily penalty grows with time. "Abis gajian tanggal 10 deh" is
   parsed to 10 October, and the bot states the estimated penalty: "Karena lewat 6 hari dari jatuh tempo, nanti ada denda
   sekitar Rp10.200".
3. **Regional speech and hardship** ([q3_id_03](../evidence/q3/transcripts/q3_id_03_regional_hardship_escalation.md),
   [q3_id_05](../evidence/q3/transcripts/q3_id_05_already_paid_sundanese.md)). The Javanese "Mboten saged mbayar, Mbak,
   kula sampun di-PHK" is understood as a layoff hardship. The bot gives the KB restructuring answer, records a
   `hardship_flag`, and stops pressing for a date ("Nggak harus sekarang kok, Kak"). The Sundanese "Atuh Teh, saya teh
   sudah bayar kemarin" is recorded as a payment claim with the KB posting times (1x24 hours for virtual accounts), and
   the bot asks which channel was used so the payment can be verified.

## ASR and TTS configuration

| | Philippines | Indonesia |
|---|---|---|
| Hosted ASR (Vapi) | Deepgram Nova-3, `language: tl`, keyterms: premium, beneficiary, rider, lapse, coverage, HMO, Bangko Kapwa, Lumina | Deepgram Nova-3, `language: id`, keyterms: cicilan, angsuran, tenor, denda, jatuh tempo, DP, pembiayaan, Sinar, Indomaret, Alfamart |
| Hosted TTS (Vapi) | Azure `fil-PH-BlessicaNeural` | Azure `id-ID-GadisNeural` |
| Browser demo | Web Speech ASR `fil-PH` for Tagalog turns and `en-PH` for English; TTS uses an installed `fil`/`tl` voice if present | Web Speech ASR and TTS `id-ID` |

Choices and compromises:

- Deepgram Nova-3 supports Tagalog (`tl`) and Indonesian (`id`) monolingually. The `multi` code-switching mode doesn't
  include Tagalog, so Taglish is transcribed by the `tl` model. English words inside Tagalog speech are common in its
  training domain, but this hasn't been measured here. The keyterms bias recognition toward the English insurance
  vocabulary that Filipino customers use.
- Azure neural voices are used for PH and ID because they're native-locale voices. A multilingual ElevenLabs voice
  sounds more natural in English but tends to carry an English accent in Tagalog. The trade-off is less expressive
  prosody. The browser demo falls back to the default English voice when no Filipino voice is installed (common on
  Windows), and the UI shows a warning when that happens.
- KB answers in the PH bot are quoted from English-language source records inside Tagalog framing ("Ayon po sa aming
  policy: ..."). That is acceptable Taglish for this segment, but an LLM rephrasing step (enabled with `OPENAI_API_KEY`)
  or Tagalog KB content would be better for less English-fluent customers.

## Test results and what they do and don't show

[`evidence/q3/scenario_results.md`](../evidence/q3/scenario_results.md) records 8 of 8 scripted conversations passing:
3 Philippine and 5 Indonesian. They cover cooperative and code-switching, sector objection with colloquial terms,
escalation, third-party pickup, already-paid, and two regional-speech cases.

These are text-level tests through the production engine. They verify NLU, flow, grounding, language following and
actions. They don't measure speech recognition. Specifically:

- **WER has not been measured for Tagalog or Indonesian.** That needs recorded calls with manually corrected
  transcripts. `python backend/scripts/wer.py --ref corrected.txt --hyp asr.txt` computes it once recordings from the
  web UI or Vapi exist. For reference, the same script on the English Q4 test calls (synthetic voices) is in
  [`evidence/q4/asr_wer.md`](../evidence/q4/asr_wer.md).
- **Regional-accent coverage is lexical only.** The Javanese and Sundanese cases test regional words and particles, not
  regional pronunciation. No native speakers were available. Synthetic TTS can't establish accent robustness, so these
  results don't claim acoustic accent accuracy.

## Observed gaps

- **Javanese questions outside the lexicon fail.** "Pripun carane? Sing ngurus sopo?" ("How do I do it? Who handles
  it?") falls through to the same-language fallback with the hotline (q3_id_03). The normalizer only covers frequent
  function words. Production would need a larger Javanese and Sundanese lexicon or an LLM normalization step, evaluated
  on real calls.
- **Detection is lexicon-based.** Very short replies ("Okay", "Sige") carry little signal, so the bot stays in the
  current language. That is intended, but can lag a real switch by one turn.
- **Single mock account.** The Indonesian bot reads a mock account. A production version would fetch from the
  loan-management system and verify identity with more than a name confirmation before quoting amounts.
- **Compliance review.** The PH flow follows common bancassurance practice (licensed-advisor handoff, illustration
  disclaimer), and the ID flow follows common collection ethics (contact hours, no third-party disclosure). Neither has
  been reviewed against the current Insurance Commission or OJK rules. That review is required before use.
