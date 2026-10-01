# q3_id_03_regional_hardship_escalation: Javanese-influenced speech (nggih, mboten, sampun), hardship (PHK) routed to restructuring info, then human escalation in Indonesian

- Agent: `id_consumer_finance` | Result: **PASS** | Final stage: `escalated`
- Outcome: `{"escalated": true, "escalation_reason": "customer_requested_human"}`
- Actions: hardship_flag, escalation | Final language/register: `casual` | Regional markers: javanese
- Mode: text-level replay through the production engine (deterministic NLU, local KB retrieval, no LLM).

| # | Speaker | Utterance | Intent | Lang | KB citations |
|---|---|---|---|---|---|
| 0 | BOT | Selamat malam. Saya Sari, asisten otomatis dari Sinar Multifinance. Panggilan ini direkam untuk menjaga kualitas layanan. Apakah saya berbicara dengan Bapak Budi Santoso? | greeting | formal |  |
| 1 | CUSTOMER | Nggih, leres, kula Budi. |  |  |  |
| 2 | BOT | Mau ngingetin aja, Kak, cicilan ke-7 buat Honda Beat sebesar Rp850.000 jatuh temponya Minggu, 4 Oktober 2026. Rencananya mau bayar kapan, Kak? | slot | casual |  |
| 3 | CUSTOMER | Mboten saged mbayar, Mbak, kula sampun di-PHK bulan kemarin. |  |  |  |
| 4 | BOT | Jadi gini, Kak. Kami turut prihatin. Pelanggan dapat mengajukan restrukturisasi melalui kantor cabang atau layanan pelanggan dengan dokumen pendukung. Kondisinya juga saya catat ya, Kak, biar petugas kami bisa hubungi soal pengajuan keringanan. Nggak harus sekarang kok, Kak. Kalau sudah ada perkiraan tanggal bisa bayar, boleh kabari; kalau belum, nanti petugas kami yang hubungi. | objection | casual | [kb_id_lagi_kena_musibah_di_phk_sakit_bb680f] Sinar Multifinance (DEMO) - Panduan Panggilan Pengingat Angsuran > Lagi kena musibah / di-PHK / sakit (internal playbook, v1.0, id_reminder_playbook.md#sec-3) |
| 5 | CUSTOMER | Pripun carane? Sing ngurus sopo? |  |  |  |
| 6 | BOT | Mohon maaf, informasi tersebut tidak tersedia di materi resmi kami, jadi saya tidak bisa memastikannya. Soal itu, petugas kami di 1500-777 bisa bantu jelasin ya, Kak. Nggak harus sekarang kok, Kak. Kalau sudah ada perkiraan tanggal bisa bayar, boleh kabari; kalau belum, nanti petugas kami yang hubungi. | fallback | casual |  |
| 7 | CUSTOMER | Saya mau bicara sama petugas saja, Mbak. |  |  |  |
| 8 | BOT | Siap, Kak. Saya sambungin ke petugas sekarang ya. Ringkasan obrolan ini sudah saya kirim, jadi nggak perlu cerita ulang. | escalation | casual |  |
