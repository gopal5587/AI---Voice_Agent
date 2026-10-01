# q1_02_objection: Objections (rate too high, hidden charges, documents) answered from the KB with citations

- Agent: `business_loan` | Result: **PASS** | Final stage: `ended`
- Outcome: `{"status": "pre_qualified", "failed_rules": [], "unverified_rules": [], "passed_rules": ["BL-ELIG-01", "BL-ELIG-02", "BL-ELIG-03", "BL-ELIG-05", "BL-ELIG-06", "BL-ELIG-07"], "excluded_purpose": null, "rules_version": "1b1460816e", "disclaimer": "Preliminary check only, not an approval; final decision subject to credit assessment."}`
- Actions: eligibility_check, crm_summary | Final language/register: `en`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hello, this is Asha, an automated assistant from Kosha Capital, calling about your business loan enquiry. This call is recorded for quality. Is now a good time to answer a few quick questions to check your eligibility? | greeting | en |  |
| 1 | CUSTOMER | Okay, but honestly your interest rate is too high. |  |  |  |
| 2 | BOT | I understand the rate matters. Our rates are risk-based and start at 14% per annum on a reducing balance, and no collateral is required. How many years has your business been operating? | objection | en | [kb_in_the_interest_rate_is_too_high_d08543] Kosha Capital - Business Loan Objection Handling Playbook (internal) > The interest rate is too high (internal playbook, v2.0, objection_handling.md#sec-1) |
| 3 | CUSTOMER | About four years. |  |  |  |
| 4 | BOT | What is your approximate annual business turnover? A rough figure in lakhs is fine. | slot | en |  |
| 5 | CUSTOMER | Roughly 60 lakh annual turnover. |  |  |  |
| 6 | BOT | How much would you like to borrow? | slot | en |  |
| 7 | CUSTOMER | I am worried there will be hidden charges. |  |  |  |
| 8 | BOT | There are no hidden charges. Every charge is listed in the Key Fact Statement before you sign. How much would you like to borrow? | objection | en | [kb_in_i_am_worried_about_hidden_charge_804c57] Kosha Capital - Business Loan Objection Handling Playbook (internal) > I am worried about hidden charges (internal playbook, v2.0, objection_handling.md#sec-4) |
| 9 | CUSTOMER | 25 lakh. |  |  |  |
| 10 | BOT | What will you mainly use the loan for? | slot | en |  |
| 11 | CUSTOMER | Working capital for salaries. |  |  |  |
| 12 | BOT | Do you know your approximate CIBIL credit score? It's fine if you don't. | slot | en |  |
| 13 | CUSTOMER | I don't want to share my documents with you people. |  |  |  |
| 14 | BOT | That is a fair concern. Your documents are used only for KYC and credit assessment, stored in encrypted form, and shared only with credit bureaus and regulators as required by law. Do you know your approximate CIBIL credit score? It's fine if you don't. | objection | en | [kb_in_i_don_t_want_to_share_my_documen_b06029] Kosha Capital - Business Loan Objection Handling Playbook (internal) > I don't want to share my documents (internal playbook, v2.0, objection_handling.md#sec-2) |
| 15 | CUSTOMER | It is 712. |  |  |  |
| 16 | BOT | In the last 12 months, have you missed any loan payment by more than 90 days? | slot | en |  |
| 17 | CUSTOMER | No. |  |  |  |
| 18 | BOT | Is your business registered, for example with GST, Udyam, or a shop and establishment licence? | slot | en |  |
| 19 | CUSTOMER | Yes, Udyam registered. |  |  |  |
| 20 | BOT | Thank you. Based on what you've shared, you appear to meet our preliminary criteria. Please note this is a preliminary check only, not an approval. The final decision is subject to credit assessment. Would you like a relationship manager to call you back to take this forward? | slot | en |  |
| 21 | CUSTOMER | No, I'll think about it. |  |  |  |
| 22 | BOT | Okay, no callback then. You can reach us any time at support@kosha-demo.example. Of course, take your time. I can schedule a callback with a relationship manager at a time that suits you, with no obligation. Thank you for your time. Goodbye. | objection | en | [kb_in_i_need_time_to_think_b1948c] Kosha Capital - Business Loan Objection Handling Playbook (internal) > I need time to think (internal playbook, v2.0, objection_handling.md#sec-3) |
