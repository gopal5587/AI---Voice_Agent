// Minimal typings for the Web Speech API (not in TypeScript's DOM lib).
interface SpeechRecognitionResultLike {
  isFinal: boolean;
  0: { transcript: string; confidence: number };
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: ArrayLike<SpeechRecognitionResultLike>;
}
export interface Recognizer {
  lang: string;
  interimResults: boolean;
  continuous: boolean;
  onresult: ((e: SpeechRecognitionEventLike) => void) | null;
  onerror: ((e: { error: string }) => void) | null;
  onend: (() => void) | null;
  start(): void;
  stop(): void;
  abort(): void;
}

export function createRecognizer(lang: string): Recognizer | null {
  const w = window as unknown as Record<string, new () => Recognizer>;
  const Ctor = w.SpeechRecognition ?? w.webkitSpeechRecognition;
  if (!Ctor) return null;
  const r = new Ctor();
  r.lang = lang;
  r.interimResults = true;
  r.continuous = false;
  return r;
}

export function pickVoice(lang: string): { voice: SpeechSynthesisVoice | null; exact: boolean } {
  const voices = window.speechSynthesis.getVoices();
  const base = lang.split("-")[0];
  const aliases = base === "fil" ? ["fil", "tl"] : [base];
  const exact = voices.find((v) => v.lang.toLowerCase() === lang.toLowerCase());
  if (exact) return { voice: exact, exact: true };
  const sameLang = voices.find((v) => aliases.some((a) => v.lang.toLowerCase().startsWith(a)));
  if (sameLang) return { voice: sameLang, exact: true };
  const english = voices.find((v) => v.lang.startsWith("en"));
  return { voice: english ?? null, exact: false };
}

export function speak(text: string, lang: string): Promise<{ voiceName: string; native: boolean }> {
  return new Promise((resolve) => {
    const { voice, exact } = pickVoice(lang);
    const u = new SpeechSynthesisUtterance(text);
    u.lang = lang;
    if (voice) u.voice = voice;
    u.rate = 1.02;
    const done = () => resolve({ voiceName: voice?.name ?? "default", native: exact });
    u.onend = done;
    u.onerror = done;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(u);
  });
}
