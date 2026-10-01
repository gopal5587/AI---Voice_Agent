"""Synthesize two-speaker call recordings for the Q4 real-time scenarios.

Uses the Windows SAPI voices (agent = Microsoft David, customer = Microsoft Zira) so it runs offline.
Output: data/scenarios/realtime/audio/<id>.wav (16 kHz, 16-bit, stereo: agent=left, customer=right,
like a dual-channel call-center recording) plus <id>.timeline.json with ground-truth segment times.
Noise is added per scenario at the configured SNR."""
import json
import subprocess
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from app.config import settings  # noqa: E402

RATE = 16000
VOICES = {"agent": "Microsoft David Desktop", "customer": "Microsoft Zira Desktop"}
GAP_S = 0.7

PS_TEMPLATE = r"""
Add-Type -AssemblyName System.Speech
$items = Get-Content -Raw -Path '{manifest}' | ConvertFrom-Json
$fmt = New-Object System.Speech.AudioFormat.SpeechAudioFormatInfo({rate}, [System.Speech.AudioFormat.AudioBitsPerSample]::Sixteen, [System.Speech.AudioFormat.AudioChannel]::Mono)
foreach ($it in $items) {{
  $s = New-Object System.Speech.Synthesis.SpeechSynthesizer
  $s.SelectVoice($it.voice)
  $s.Rate = 0
  $s.SetOutputToWaveFile($it.out, $fmt)
  $s.Speak($it.text)
  $s.Dispose()
}}
"""


def synthesize(items: list[dict], workdir: Path) -> None:
    manifest = workdir / "manifest.json"
    manifest.write_text(json.dumps(items), encoding="utf-8")
    script = workdir / "tts.ps1"
    script.write_text(PS_TEMPLATE.format(manifest=manifest, rate=RATE), encoding="utf-8")
    subprocess.run(["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)], check=True)


def read_mono(path: Path) -> np.ndarray:
    with wave.open(str(path)) as w:
        return np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32)


def add_noise(stereo: np.ndarray, snr_db: float, rng: np.random.Generator) -> np.ndarray:
    speech_power = np.mean(stereo[np.abs(stereo) > 200] ** 2) if np.any(np.abs(stereo) > 200) else 1e6
    noise_power = speech_power / (10 ** (snr_db / 10))
    n = len(stereo)
    t = np.arange(n) / RATE
    hum = np.sin(2 * np.pi * 50 * t) * 0.3
    noise = rng.normal(0, 1, (n, 2)) + hum[:, None]
    if snr_db < 10:  # bad line: crackles and short dropouts
        for start in rng.integers(0, n - RATE // 5, size=max(1, n // (RATE * 3))):
            noise[start:start + RATE // 50] += rng.normal(0, 6, (RATE // 50, 2))
    noise *= np.sqrt(noise_power / np.mean(noise ** 2))
    out = stereo + noise
    if snr_db < 10:
        for start in rng.integers(0, n - RATE // 4, size=max(1, n // (RATE * 6))):
            out[start:start + RATE // 8] *= 0.15
    return out


def build(scenario: dict, out_dir: Path) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        tmpdir = Path(tmp)
        items = [{"text": s["text"], "voice": VOICES[s["speaker"]], "out": str(tmpdir / f"seg{i:02d}.wav")}
                 for i, s in enumerate(scenario["segments"])]
        synthesize(items, tmpdir)
        clips = [read_mono(Path(it["out"])) for it in items]

    total = int(sum(len(c) for c in clips) + RATE * GAP_S * (len(clips) + 1))
    stereo = np.zeros((total, 2), dtype=np.float32)
    cursor = int(RATE * 0.5)
    timeline = []
    for seg, clip in zip(scenario["segments"], clips):
        ch = 0 if seg["speaker"] == "agent" else 1
        stereo[cursor:cursor + len(clip), ch] += clip
        timeline.append({"speaker": seg["speaker"], "text": seg["text"], "start_s": round(cursor / RATE, 3),
                         "end_s": round((cursor + len(clip)) / RATE, 3)})
        cursor += len(clip) + int(RATE * GAP_S)
    stereo = stereo[:cursor]
    stereo = add_noise(stereo, scenario.get("noise_snr_db", 30), np.random.default_rng(7))
    pcm = np.clip(stereo, -32768, 32767).astype(np.int16)

    path = out_dir / f"{scenario['id']}.wav"
    with wave.open(str(path), "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(RATE)
        w.writeframes(pcm.tobytes())
    meta = {"id": scenario["id"], "duration_s": round(len(pcm) / RATE, 2), "sample_rate": RATE, "channels": {"0": "agent", "1": "customer"},
            "noise_snr_db": scenario.get("noise_snr_db"), "segments": timeline}
    (out_dir / f"{scenario['id']}.timeline.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main() -> None:
    src = settings.scenarios_dir / "realtime"
    out = src / "audio"
    out.mkdir(parents=True, exist_ok=True)
    for scenario in json.loads((src / "scenarios.json").read_text(encoding="utf-8")):
        meta = build(scenario, out)
        print(f"{meta['id']}: {meta['duration_s']} s, {len(meta['segments'])} segments, SNR {meta['noise_snr_db']} dB")


if __name__ == "__main__":
    main()
