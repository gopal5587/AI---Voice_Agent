"""Word error rate of the streaming ASR on the Q4 test calls (reference = the scripted text in each timeline).

  python scripts/wer.py                       # per scenario and speaker, from evidence/q4/event_logs
  python scripts/wer.py --ref a.txt --hyp b.txt  # any manually corrected transcript pair (e.g. Q3 recordings)

Text is lower-cased and punctuation-stripped; numbers are compared as words, so "twelve" vs "12" counts as an error."""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402


def words(text: str) -> list[str]:
    return re.findall(r"[a-z0-9']+", text.lower())


def edit_distance(ref: list[str], hyp: list[str]) -> int:
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, 1):
        cur = [i] + [0] * len(hyp)
        for j, h in enumerate(hyp, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (r != h))
        prev = cur
    return prev[-1]


def wer(ref: str, hyp: str) -> tuple[float, int]:
    r = words(ref)
    return (edit_distance(r, words(hyp)) / len(r) if r else 0.0), len(r)


def q4_report() -> str:
    audio = settings.scenarios_dir / "realtime" / "audio"
    rows = ["| Scenario | SNR (dB) | Speaker | Reference words | WER |", "|---|---|---|---|---|"]
    out = {}
    for log in sorted((settings.evidence_dir / "q4" / "event_logs").glob("*.jsonl")):
        tl = json.loads((audio / f"{log.stem}.timeline.json").read_text(encoding="utf-8"))
        events = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
        for speaker in ("agent", "customer"):
            ref = " ".join(s["text"] for s in tl["segments"] if s["speaker"] == speaker)
            hyp = " ".join(e["text"] for e in events if e["type"] == "transcript" and e["final"] and e["speaker"] == speaker)
            w, n = wer(ref, hyp)
            out[(log.stem, speaker)] = w
            rows.append(f"| {log.stem} | {tl.get('noise_snr_db')} | {speaker} | {n} | {w:.1%} |")
    return "\n".join(rows)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ref")
    ap.add_argument("--hyp")
    args = ap.parse_args()
    if args.ref and args.hyp:
        w, n = wer(Path(args.ref).read_text(encoding="utf-8"), Path(args.hyp).read_text(encoding="utf-8"))
        print(f"WER {w:.1%} over {n} reference words")
        return
    table = q4_report()
    path = settings.evidence_dir / "q4" / "asr_wer.md"
    path.write_text("# Q4 streaming ASR word error rate\n\nASR: Vosk small en-US 0.15, streamed per channel at 1x. Reference: "
                    "the scripted text used to synthesize each call (Windows SAPI voices plus mixed noise at the stated SNR). "
                    "Synthetic TTS speech is easier than real callers, so treat these as optimistic.\n\n" + table + "\n",
                    encoding="utf-8")
    print(table)


if __name__ == "__main__":
    main()
