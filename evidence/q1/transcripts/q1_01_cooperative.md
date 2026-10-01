# q1_01_cooperative: Cooperative customer, multi-detail answer, pre-qualified, callback scheduled

- Agent: `business_loan` | Result: **PASS** | Final stage: `ended`
- Outcome: `{"status": "pre_qualified", "failed_rules": [], "unverified_rules": [], "passed_rules": ["BL-ELIG-01", "BL-ELIG-02", "BL-ELIG-03", "BL-ELIG-05", "BL-ELIG-06", "BL-ELIG-07"], "excluded_purpose": null, "rules_version": "1b1460816e", "disclaimer": "Preliminary check only, not an approval; final decision subject to credit assessment."}`
- Actions: eligibility_check, callback_scheduled, crm_summary | Final language/register: `en`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hello, this is Asha, an automated assistant from Kosha Capital, calling about your business loan enquiry. This call is recorded for quality. Is now a good time to answer a few quick questions to check your eligibility? | greeting | en |  |
| 1 | CUSTOMER | Yes, go ahead. |  |  |  |
| 2 | BOT | How many years has your business been operating? | slot | en |  |
| 3 | CUSTOMER | We've been running the shop since 2019. |  |  |  |
| 4 | BOT | What is your approximate annual business turnover? A rough figure in lakhs is fine. | slot | en |  |
| 5 | CUSTOMER | Our turnover is about 3 lakh a month and I need around 15 lakh. |  |  |  |
| 6 | BOT | Noted, that's about 36 lakh rupees a year. What will you mainly use the loan for? | slot | en |  |
| 7 | CUSTOMER | To buy a new packaging machine. |  |  |  |
| 8 | BOT | Do you know your approximate CIBIL credit score? It's fine if you don't. | slot | en |  |
| 9 | CUSTOMER | It's around 745. |  |  |  |
| 10 | BOT | In the last 12 months, have you missed any loan payment by more than 90 days? | slot | en |  |
| 11 | CUSTOMER | No, never. |  |  |  |
| 12 | BOT | Is your business registered, for example with GST, Udyam, or a shop and establishment licence? | slot | en |  |
| 13 | CUSTOMER | Yes, we have GST registration. |  |  |  |
| 14 | BOT | Thank you. Based on what you've shared, you appear to meet our preliminary criteria. Please note this is a preliminary check only, not an approval. The final decision is subject to credit assessment. Would you like a relationship manager to call you back to take this forward? | slot | en |  |
| 15 | CUSTOMER | Yes please. |  |  |  |
| 16 | BOT | What day and time works best for the callback? | slot | en |  |
| 17 | CUSTOMER | Tomorrow at 11 am. |  |  |  |
| 18 | BOT | Done. I've scheduled a callback with a relationship manager for Friday 2 October at 11:00 AM India time. Thank you for your time. Goodbye. | slot | en |  |
