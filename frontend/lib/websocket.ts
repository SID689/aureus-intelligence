/**
 * Where the sockets connect.
 *
 * The fallback used to be the literal `ws://localhost:8000`, which is only
 * correct on the machine running the stack. On any other device — a phone
 * on the same demo, a laptop reached through a tunnel — localhost is that
 * device itself, so voice and the alert stream connected to nothing and
 * failed silently.
 *
 * Same origin is the right default instead: next.config.ts proxies
 * /api/v1/* to FastAPI, and that rewrite carries the WebSocket upgrade, so
 * one public hostname serves the app and its sockets. Set
 * NEXT_PUBLIC_WS_URL only where the two halves are on different hosts and
 * the proxy in front of the app does not forward upgrades (Vercel, for
 * one): point it straight at the backend.
 */
function wsBase(): string {
  const env = process.env.NEXT_PUBLIC_WS_URL;
  if (env) return env.replace(/\/$/, "");
  if (typeof window === "undefined") return "";
  return `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`;
}

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
  const url = `${wsBase()}/api/v1/ws/alerts/${userId}`;
  const ws = new WebSocket(url);

  // Tracks a close WE asked for, so an aborted handshake can be told
  // apart from a genuine connection failure.
  //
  // Why this is needed: React StrictMode (enabled in next.config.ts)
  // deliberately runs every effect twice in development — mount,
  // cleanup, mount. AlertFeed's cleanup is `ws.close()`, so the very
  // first socket gets closed while still CONNECTING. Per the WebSocket
  // spec, closing during the handshake fires `error` and then `close`,
  // which is what produced the console error on every page load.
  //
  // The same thing happens in production whenever someone navigates away
  // mid-handshake, so this is not a dev-only workaround.
  let closeRequested = false;
  const nativeClose = ws.close.bind(ws);
  ws.close = (code?: number, reason?: string) => {
    closeRequested = true;
    if (ws.readyState === WebSocket.CONNECTING) {
      // Aborting a handshake is what the browser itself warns about
      // ("WebSocket is closed before the connection is established"), and
      // that warning is emitted natively — no JS handler can suppress it.
      // So don't abort: let the handshake finish, then close cleanly on
      // the open event. The socket lives a few extra milliseconds and the
      // console stays quiet.
      ws.addEventListener("open", () => nativeClose(code, reason), { once: true });
      return;
    }
    nativeClose(code, reason);
  };

  ws.onmessage = (event) => {
    try {
      const msg = JSON.parse(event.data) as AlertMessage;
      if (msg.type !== "ping") onMessage(msg);
    } catch {
      // ignore malformed frames
    }
  };

  ws.onclose = (event) => {
    // 1000 is a normal closure and 1005 means no status was supplied —
    // neither is worth reporting. Anything else ended unexpectedly, and
    // unlike the error event this one carries a usable code.
    if (!closeRequested && event.code !== 1000 && event.code !== 1005) {
      console.warn(
        `Alert stream closed unexpectedly (code ${event.code}` +
        `${event.reason ? `: ${event.reason}` : ""}). Live alerts are paused until reload.`
      );
    }
    onClose?.();
  };

  ws.onerror = () => {
    // A WebSocket ErrorEvent carries no detail whatsoever — the spec
    // withholds it so a page cannot probe internal networks by reading
    // failure reasons. Logging the event object only ever prints `{}`,
    // which is what the old `console.error("...", err)` did. The close
    // handler above reports the code instead, which is actionable.
    if (closeRequested || ws.readyState === WebSocket.CLOSING) return;
    console.warn(`Alert stream could not connect to ${url}. Is the backend running?`);
  };

  return ws;
}

// ── Voice WebSocket ─────────────────────────────────────────────────────────

export class VoiceWebSocket {
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  /** Set by disconnect() so onclose knows not to schedule a reconnect. */
  private intentionalClose = false;
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
    this.intentionalClose = false;

    this.ws = new WebSocket(`${wsBase()}/api/v1/ws/voice/${this.userId}`);

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

    this.ws.onclose = (event) => {
      // Do NOT reconnect a socket we deliberately closed. Previously
      // this scheduled unconditionally, so disconnect() — which clears
      // the timer and then calls close() — triggered onclose, which set
      // a fresh timer, and the socket reopened three seconds later. The
      // voice session could not actually be ended.
      if (this.intentionalClose) return;
      if (event.code === 1000) return;   // normal server-side closure
      this.reconnectTimer = setTimeout(() => this.connect(), 3000);
    };

    this.ws.onerror = () => {
      // See connectAlertStream: the error event carries no detail, so
      // there is nothing worth printing from it. An abandoned handshake
      // (StrictMode remount, navigation) is expected and silent.
      if (this.intentionalClose) return;
      console.warn("Voice stream connection failed: retrying in 3s.");
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
    // Order matters: flag first, so the onclose handler fired by close()
    // below sees it and skips the reconnect.
    this.intentionalClose = true;
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    this.ws?.close(1000, "client disconnect");
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
