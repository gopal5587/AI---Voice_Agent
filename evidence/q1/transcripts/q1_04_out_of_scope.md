# q1_04_out_of_scope: Out-of-scope and unsupported questions trigger the safe fallback (no invented answer)

- Agent: `business_loan` | Result: **PASS** | Final stage: `collecting`
- Outcome: `null`
- Actions: none | Final language/register: `en`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hello, this is Asha, an automated assistant from Kosha Capital, calling about your business loan enquiry. This call is recorded for quality. Is now a good time to answer a few quick questions to check your eligibility? | greeting | en |  |
| 1 | CUSTOMER | Yes. |  |  |  |
| 2 | BOT | How many years has your business been operating? | slot | en |  |
| 3 | CUSTOMER | Do you also offer home loans for flats in Pune? |  |  |  |
| 4 | BOT | I don't have verified information about that in our approved material, so I won't guess. A relationship manager can confirm that for you on a callback. How many years has your business been operating? | fallback | en |  |
| 5 | CUSTOMER | Three years. |  |  |  |
| 6 | BOT | What is your approximate annual business turnover? A rough figure in lakhs is fine. | slot | en |  |
| 7 | CUSTOMER | What is today's gold rate? |  |  |  |
| 8 | BOT | I don't have verified information about that in our approved material, so I won't guess. Since I couldn't answer that, would you like me to connect you to a relationship manager? Just say 'talk to a person' at any time. What is your approximate annual business turnover? A rough figure in lakhs is fine. | fallback | en |  |
| 9 | CUSTOMER | Fine. Can I prepay the loan early? |  |  |  |
| 10 | BOT | Yes. You can foreclose the loan after paying 6 EMIs. What is your approximate annual business turnover? A rough figure in lakhs is fine. | question | en | [kb_in_can_i_prepay_or_foreclose_my_loa_9ef140] Frequently Asked Questions - Business Loan > Can I prepay or foreclose my loan (website section, v2026.07, business-loan-faq.html#h2-2) |
