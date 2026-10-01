# q1_06_excluded_purpose: Policy-excluded purpose (stock trading) is declined using KB rules

- Agent: `business_loan` | Result: **PASS** | Final stage: `ended`
- Outcome: `{"status": "not_eligible", "failed_rules": [], "unverified_rules": [], "passed_rules": ["BL-ELIG-01", "BL-ELIG-02", "BL-ELIG-03", "BL-ELIG-05", "BL-ELIG-06", "BL-ELIG-07"], "excluded_purpose": "stock market trading", "rules_version": "1b1460816e", "disclaimer": "Preliminary check only, not an approval; final decision subject to credit assessment."}`
- Actions: eligibility_check, crm_summary | Final language/register: `en`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hello, this is Asha, an automated assistant from Kosha Capital, calling about your business loan enquiry. This call is recorded for quality. Is now a good time to answer a few quick questions to check your eligibility? | greeting | en |  |
| 1 | CUSTOMER | Yes. |  |  |  |
| 2 | BOT | How many years has your business been operating? | slot | en |  |
| 3 | CUSTOMER | Ten years. |  |  |  |
| 4 | BOT | What is your approximate annual business turnover? A rough figure in lakhs is fine. | slot | en |  |
| 5 | CUSTOMER | 2 crore turnover. |  |  |  |
| 6 | BOT | How much would you like to borrow? | slot | en |  |
| 7 | CUSTOMER | 50 lakh. |  |  |  |
| 8 | BOT | What will you mainly use the loan for? | slot | en |  |
| 9 | CUSTOMER | Mostly for stock market trading. |  |  |  |
| 10 | BOT | Do you know your approximate CIBIL credit score? It's fine if you don't. | slot | en |  |
| 11 | CUSTOMER | 800. |  |  |  |
| 12 | BOT | In the last 12 months, have you missed any loan payment by more than 90 days? | slot | en |  |
| 13 | CUSTOMER | No. |  |  |  |
| 14 | BOT | Is your business registered, for example with GST, Udyam, or a shop and establishment licence? | slot | en |  |
| 15 | CUSTOMER | Yes. |  |  |  |
| 16 | BOT | Our business loan cannot be used for stock market trading. Thank you for sharing these details. Based on our current policy, we may not be able to proceed right now because: the loan purpose is not supported. Please note this is a preliminary check only, not an approval. The final decision is subject to credit assessment. Would you like a relationship manager to call you back to take this forward? | slot | en |  |
| 17 | CUSTOMER | No. |  |  |  |
| 18 | BOT | Okay, no callback then. You can reach us any time at support@kosha-demo.example. Thank you for your time. Goodbye. | slot | en |  |
