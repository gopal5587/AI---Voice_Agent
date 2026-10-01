# q3_id_04_wrong_person: Third party answers; bot ends without disclosing the debt (collection-ethics rule)

- Agent: `id_consumer_finance` | Result: **PASS** | Final stage: `ended`
- Outcome: `{"ended_reason": "identity_confirmed_declined"}`
- Actions: crm_summary | Final language/register: `formal`
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Selamat malam. Saya Sari, asisten otomatis dari Sinar Multifinance. Panggilan ini direkam untuk menjaga kualitas layanan. Apakah saya berbicara dengan Bapak Budi Santoso? | greeting | formal |  |
| 1 | CUSTOMER | Bukan, ini istrinya. Bapaknya lagi kerja. |  |  |  |
| 2 | BOT | Mohon maaf atas gangguannya. Terima kasih, selamat malam. | slot_end | formal |  |
