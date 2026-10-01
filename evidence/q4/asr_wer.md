# Q4 streaming ASR word error rate

ASR: Vosk small en-US 0.15, streamed per channel at 1x. Reference: the scripted text used to synthesize each call (Windows SAPI voices plus mixed noise at the stated SNR). Synthetic TTS speech is easier than real callers, so treat these as optimistic.

| Scenario | SNR (dB) | Speaker | Reference words | WER |
|---|---|---|---|---|
| rt_compliance | 28 | agent | 68 | 11.8% |
| rt_compliance | 28 | customer | 28 | 10.7% |
| rt_cross_sell | 28 | agent | 75 | 13.3% |
| rt_cross_sell | 28 | customer | 47 | 8.5% |
| rt_frustration | 28 | agent | 56 | 17.9% |
| rt_frustration | 28 | customer | 56 | 3.6% |
| rt_holdout_noisy | 6 | agent | 39 | 20.5% |
| rt_holdout_noisy | 6 | customer | 31 | 29.0% |
| rt_noisy | 4 | agent | 26 | 26.9% |
| rt_noisy | 4 | customer | 32 | 46.9% |
