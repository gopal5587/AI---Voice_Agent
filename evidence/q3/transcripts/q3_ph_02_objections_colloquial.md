# q3_ph_02_objections_colloquial: Sector objections (HMO, mahal, lapse question) in colloquial Tagalog; KB-grounded Taglish answers

- Agent: `ph_life_insurance` | Result: **PASS** | Final stage: `ended`
- Outcome: `{"status": "qualified_lead", "indicative_coverage_php": 1200000.0, "basis": "illustration: PHP 1250/month per PHP 1,000,000 (30-year-old non-smoker)"}`
- Actions: quotation_request, crm_summary | Final language/register: `tl`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hi po, magandang araw! Si Lumi po ito, automated assistant ng Lumina Life, partner ng Bangko Kapwa. Tumatawag po ako kasi nag-request kayo ng info about life insurance sa branch. Naka-record po ang call na ito for quality. Okay lang po ba kung magtanong ako ng ilang quick questions? Mga 2 minutes lang po. | greeting | tl |  |
| 1 | CUSTOMER | Ano ba yan, may HMO na ako eh, bakit kailangan ko pa ng life insurance? |  |  |  |
| 2 | BOT | Ayon po sa aming policy: An HMO pays hospital and medical bills while you are alive. Life insurance gives a cash benefit to your beneficiaries if you pass away. Okay lang po ba kung magtanong ako ng ilang quick questions? Mga 2 minutes lang po. | objection | tl | [kb_ph_i_already_have_an_hmo_3650b9] Lumina Life (DEMO) - Bank Referral Call Guide and FAQ > I already have an HMO (internal playbook, v1.1, ph_faq_objections.md#sec-5) |
| 3 | CUSTOMER | Sige na nga, tanong lang kayo. |  |  |  |
| 4 | BOT | Ilang taon na po kayo? | slot | tl |  |
| 5 | CUSTOMER | 45 po. |  |  |  |
| 6 | BOT | Sino po ang umaasa sa inyo financially, halimbawa asawa, anak, o magulang? Sila po kasi ang magiging beneficiary. | slot | tl |  |
| 7 | CUSTOMER | Mga magulang ko po. |  |  |  |
| 8 | BOT | Magkano po ang comfortable na budget ninyo para sa premium kada buwan? | slot | tl |  |
| 9 | CUSTOMER | Grabe, mahal siguro yan, wala akong budget. |  |  |  |
| 10 | BOT | Ayon po sa aming policy: Naiintindihan ko po, budget is important. Coverage can start at PHP 500,000 and the premium can be paid monthly through auto-debit. Magkano po ang comfortable na budget ninyo para sa premium kada buwan? | objection | tl | [kb_ph_mahal_too_expensive_fd6e6d] Lumina Life (DEMO) - Bank Referral Call Guide and FAQ > Mahal / too expensive (internal playbook, v1.1, ph_faq_objections.md#sec-4) |
| 11 | CUSTOMER | Siguro 1,500 a month. |  |  |  |
| 12 | BOT | Ano po ang pinaka-goal ninyo: proteksyon ng income para sa pamilya, pang-education ng anak, o coverage para sa critical illness? | slot | tl |  |
| 13 | CUSTOMER | Pag na-ospital ako, critical illness. |  |  |  |
| 14 | BOT | May existing life insurance policy na po ba kayo? Hindi po kasama dito ang HMO. | slot | tl |  |
| 15 | CUSTOMER | Paano po kung hindi ako makabayad, ma-lapse ba agad? |  |  |  |
| 16 | BOT | Ayon po sa aming policy: There is a 31-day grace period after the premium due date. If the premium is still unpaid after the grace period, the policy lapses and coverage stops. May existing life insurance policy na po ba kayo? Hindi po kasama dito ang HMO. | question | tl | [kb_ph_grace_period_and_lapse_81cf0d] Lumina Protect Plus - Term Life Insurance > Grace Period and Lapse (website section, v2026.08, lumina-protect-plus.html#h2-6) |
| 17 | CUSTOMER | Wala po. |  |  |  |
| 18 | BOT | Salamat po! Base sa budget na ₱1,500 kada buwan, puwedeng nasa ₱1,200,000 ang coverage ninyo para sa isang 30-year-old na non-smoker. Ihahanda po ng advisor ang exact quotation. Dahil concern n'yo po ang critical illness, puwede rin pong idagdag ang Critical Illness rider. You can name up to 5 beneficiaries. Paalala lang po: hindi po ako licensed financial advisor, at ang premium ay illustration pa lang. Ang final na premium ay depende sa underwriting. Gusto n'yo po bang tawagan kayo ng licensed financial advisor para sa exact quotation? | slot | tl | [kb_ph_beneficiaries_bda5ec] Lumina Protect Plus - Term Life Insurance > Beneficiaries (website section, v2026.08, lumina-protect-plus.html#h2-5) |
| 19 | CUSTOMER | Hindi muna po, pag-iisipan ko pa. |  |  |  |
| 20 | BOT | Sige po. Puwede po kayong pumunta sa kahit anong Bangko Kapwa branch kung may tanong pa kayo. Ayon po sa aming policy: Walang problema po, take your time. A licensed financial advisor can call you back at a time convenient for you. Maraming salamat po sa oras ninyo. Ingat po kayo! | objection | tl | [kb_ph_i_need_to_think_about_it_pag_iis_fcd47c] Lumina Life (DEMO) - Bank Referral Call Guide and FAQ > I need to think about it / Pag-iisipan ko muna (internal playbook, v1.1, ph_faq_objections.md#sec-8) |
