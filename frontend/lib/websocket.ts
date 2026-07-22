const WS_BASE = process.env.NEXT_PUBLIC_WS_URL || "ws://localhost:8000";

export type AlertMessage = {
  type: "alert" | "connected" | "pending_alerts" | "ping" | "hitl_approval_required";
  [key: string]: unknown;
};

export type VoiceMessage = {
  type: "session_ready" | "session_configured" | "thinking" | "transcript" |
        "response" | "audio" | "error" | "ping" | "session_ended";
  text?: string;
  data?: string;  // base64 audio
  [key: string]: unknown;
};

// ── Alert WebSocket ─────────────────────────────────────────────────────────

export function connectAlertStream(
  userId: string,
  onMessage: (msg: AlertMessage) => void,
  onClose?: () => void,
): WebSocket {
  const ws = new WebSocket(`${WS_BASE}/api/v1/ws/alerts/${userId}`);

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as AlertMessage;
      if (msg.type !== "ping") onMessage(msg);
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = () => onClose?.();

  ws.onerror = (err) => {
    console.error("Alert WebSocket error:", err);
  };

  return ws;
}

// ── Voice WebSocket ─────────────────────────────────────────────────────────

export class VoiceWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private onMessage: (msg: VoiceMessage) => void;
  private userId: string;
  private tier: string;

  constructor(
    userId: string,
    tier: string,
    onMessage: (msg: VoiceMessage) => void
  ) {
    this.userId    = userId;
    this.tier      = tier;
    this.onMessage = onMessage;
  }

  connect(): void {
    if (this.ws?.readyState === WebSocket.OPEN) return;

    this.ws = new WebSocket(`${WS_BASE}/api/v1/ws/voice/${this.userId}`);

    this.ws.onopen = () => {
      // Send session configuration immediately on connect
      this.send({
        type:     "start_session",
        user_id:  this.userId,
        tier:     this.tier,
        stt_mode: "browser",   // use browser Web Speech API
        use_backend_tts: false, // use browser speechSynthesis
      });
    };

    this.ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data) as VoiceMessage;
        if (msg.type !== "ping") this.onMessage(msg);
      } catch {
        // ignore
      }
    };

    this.ws.onclose = () => {
      // Auto-reconnect after 3s
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = (err) => {
      console.error("Voice WebSocket error:", err);
    };
  }

  sendText(text: string): void {
    this.send({ type: "text_input", text });
  }

  send(data: object): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(data));
    }
  }

  disconnect(): void {
    if (this.reconnectTimer) clearTimeout(this.reconnectTimer);
    this.ws?.close();
    this.ws = null;
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

// ── Browser Speech API helpers ──────────────────────────────────────────────

export function speakText(text: string, rate = 1.05, pitch = 1.0): void {
  if (!("speechSynthesis" in window)) return;
  window.speechSynthesis.cancel();
  const utt  = new SpeechSynthesisUtterance(text);
  utt.rate   = rate;
  utt.pitch  = pitch;
  utt.volume = 1;
  // Prefer a female English voice if available
  const voices = window.speechSynthesis.getVoices();
  const preferred = voices.find(
    (v) => v.lang.startsWith("en") && v.name.toLowerCase().includes("female")
  ) || voices.find((v) => v.lang.startsWith("en")) || null;
  if (preferred) utt.voice = preferred;
  window.speechSynthesis.speak(utt);
}

export function stopSpeaking(): void {
  if ("speechSynthesis" in window) window.speechSynthesis.cancel();
}

export function startBrowserSTT(
  onResult: (text: string, isFinal: boolean) => void,
  onEnd: () => void,
): SpeechRecognition | null {
  const SR = (window as unknown as { SpeechRecognition?: typeof SpeechRecognition; webkitSpeechRecognition?: typeof SpeechRecognition }).SpeechRecognition
          || (window as unknown as { webkitSpeechRecognition?: typeof SpeechRecognition }).webkitSpeechRecognition;
  if (!SR) return null;

  const recognition         = new SR();
  recognition.lang          = "en-US";
  recognition.interimResults = true;
  recognition.continuous    = false;
  recognition.maxAlternatives = 1;

  recognition.onresult = (event) => {
    const last = event.results[event.results.length - 1];
    onResult(last[0].transcript, last.isFinal);
  };
  recognition.onend = onEnd;
  recognition.start();
  return recognition;
}
