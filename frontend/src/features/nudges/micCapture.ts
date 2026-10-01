/** Capture the microphone, downsample to 16 kHz mono PCM16 and emit ~100 ms frames. */
export async function startMic(onFrame: (pcm: ArrayBuffer) => void): Promise<() => void> {
  const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
  const ctx = new AudioContext();
  const source = ctx.createMediaStreamSource(stream);
  const processor = ctx.createScriptProcessor(4096, 1, 1);
  const ratio = ctx.sampleRate / 16000;
  let pending: number[] = [];
  processor.onaudioprocess = (e) => {
    const input = e.inputBuffer.getChannelData(0);
    for (let i = 0; i < input.length / ratio; i++) {
      const s = Math.max(-1, Math.min(1, input[Math.floor(i * ratio)]));
      pending.push(s < 0 ? s * 0x8000 : s * 0x7fff);
    }
    while (pending.length >= 1600) {
      onFrame(Int16Array.from(pending.slice(0, 1600)).buffer);
      pending = pending.slice(1600);
    }
  };
  source.connect(processor);
  processor.connect(ctx.destination);
  return () => {
    processor.disconnect();
    source.disconnect();
    stream.getTracks().forEach((t) => t.stop());
    void ctx.close();
  };
}
