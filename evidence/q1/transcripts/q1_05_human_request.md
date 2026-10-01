# q1_05_human_request: Customer asks for a human mid-flow; escalation with handoff summary

- Agent: `business_loan` | Result: **PASS** | Final stage: `escalated`
- Outcome: `{"escalated": true, "escalation_reason": "customer_requested_human"}`
- Actions: escalation | Final language/register: `en`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Hello, this is Asha, an automated assistant from Kosha Capital, calling about your business loan enquiry. This call is recorded for quality. Is now a good time to answer a few quick questions to check your eligibility? | greeting | en |  |
| 1 | CUSTOMER | Yes. |  |  |  |
| 2 | BOT | How many years has your business been operating? | slot | en |  |
| 3 | CUSTOMER | Six years. |  |  |  |
| 4 | BOT | What is your approximate annual business turnover? A rough figure in lakhs is fine. | slot | en |  |
| 5 | CUSTOMER | Look, can I just speak to a real person please? |  |  |  |
| 6 | BOT | Sure. I'm connecting you to a relationship manager now, and I've shared your details so you won't need to repeat them. If no one is available, they will call you back within 1 business day. | escalation | en |  |
