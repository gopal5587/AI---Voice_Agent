# q3_ph_03_english_switch_escalation: Customer replies in English (bot follows), asks something unsupported, then asks for a human

- Agent: `ph_life_insurance` | Result: **PASS** | Final stage: `escalated`
- Outcome: `{"escalated": true, "escalation_reason": "customer_requested_human"}`
- Actions: escalation | Final language/register: `tl`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hi po, magandang araw! Si Lumi po ito, automated assistant ng Lumina Life, partner ng Bangko Kapwa. Tumatawag po ako kasi nag-request kayo ng info about life insurance sa branch. Naka-record po ang call na ito for quality. Okay lang po ba kung magtanong ako ng ilang quick questions? Mga 2 minutes lang po. | greeting | tl |  |
| 1 | CUSTOMER | Hi, yes, I have a few minutes. Is this really from the bank? |  |  |  |
| 2 | BOT | The policy is issued by Lumina Life and sold only by licensed financial advisors at Bangko Kapwa. You can verify the advisor's license and visit any branch. May I know your age? | question | en | [kb_ph_is_this_a_scam_trust_concern_495d97] Lumina Life (DEMO) - Bank Referral Call Guide and FAQ > Is this a scam? / Trust concern (internal playbook, v1.1, ph_faq_objections.md#sec-6) |
| 3 | CUSTOMER | Okay, go ahead. I'm 28 years old. |  |  |  |
| 4 | BOT | Who depends on you financially, for example a spouse, children, or parents? They would be your beneficiaries. | slot | en |  |
| 5 | CUSTOMER | Do you offer car insurance as well? |  |  |  |
| 6 | BOT | I don't have verified information about that in our approved material, so I won't guess. Our licensed financial advisor can answer that properly. Who depends on you financially, for example a spouse, children, or parents? They would be your beneficiaries. | fallback | en |  |
| 7 | CUSTOMER | Pwede ko bang makausap yung totoong tao, yung advisor? |  |  |  |
| 8 | BOT | Sige po, ikokonekta ko na kayo sa isang licensed financial advisor ng Bangko Kapwa. Naipasa ko na po ang details ninyo para hindi na kayo mag-ulit. Kung busy po sila, tatawagan nila kayo within the day. | escalation | tl |  |
