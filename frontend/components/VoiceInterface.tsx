"use client";
import { useEffect, useRef, useState, useCallback } from "react";
import { IconMic } from "@/components/ui/icons";
import { VoiceWebSocket, speakText, stopSpeaking, startBrowserSTT } from "@/lib/websocket";
import type { VoiceMessage } from "@/lib/websocket";

interface Props { userId: string; tier: string; }

type Turn = { role: "user" | "assistant"; text: string; timestamp: string };
type Status = "disconnected" | "connecting" | "ready" | "listening" | "thinking" | "speaking";

export default function VoiceInterface({ userId, tier }: Props) {
  const [status,   setStatus]   = useState<Status>("disconnected");
  const [turns,    setTurns]    = useState<Turn[]>([]);
  const [interim,  setInterim]  = useState("");
  const wsRef   = useRef<VoiceWebSocket | null>(null);
  const srRef   = useRef<SpeechRecognition | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  const addTurn = useCallback((role: "user" | "assistant", text: string) => {
    setTurns((prev) => [...prev, { role, text, timestamp: new Date().toLocaleTimeString() }]);
    setTimeout(() => scrollRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  }, []);

  // Handle incoming WebSocket messages
  const handleMessage = useCallback((msg: VoiceMessage) => {
    if (msg.type === "session_ready" || msg.type === "session_configured") {
      setStatus("ready");
    } else if (msg.type === "thinking") {
      setStatus("thinking");
    } else if (msg.type === "response" && msg.text) {
      setStatus("speaking");
      addTurn("assistant", msg.text);
      speakText(msg.text);
      setTimeout(() => setStatus("ready"), 500);
    } else if (msg.type === "error") {
      setStatus("ready");
    }
  }, [addTurn]);

  // Connect on mount
  useEffect(() => {
    setStatus("connecting");
    const ws = new VoiceWebSocket(userId, tier, handleMessage);
    wsRef.current = ws;
    ws.connect();
    return () => { ws.disconnect(); stopSpeaking(); };
  }, [userId, tier, handleMessage]);

  // Push-to-talk
  const startListening = useCallback(() => {
    if (status !== "ready") return;
    stopSpeaking();
    setStatus("listening");
    setInterim("");

    const recognition = startBrowserSTT(
      (text, isFinal) => {
        setInterim(text);
        if (isFinal && text.trim()) {
          setInterim("");
          addTurn("user", text);
          wsRef.current?.sendText(text);
        }
      },
      () => {
        setInterim("");
        // Functional form, not `if (status === "listening")`. This callback
        // fires when recognition ends — possibly seconds after
        // startListening captured `status` — and the guard above has
        // already narrowed that captured value to "ready", so the old
        // comparison could never be true and the mic never reset itself.
        setStatus((s) => (s === "listening" ? "ready" : s));
      },
    );
    srRef.current = recognition;
  }, [status, addTurn]);

  const stopListening = useCallback(() => {
    srRef.current?.stop();
    setStatus("ready");
  }, []);

  const statusLabel: Record<Status, string> = {
    disconnected: "Disconnected",
    connecting:   "Connecting",
    ready:        "Ready. Hold to speak",
    listening:    "Listening",
    thinking:     "Thinking",
    speaking:     "Speaking",
  };

  const statusColor: Record<Status, string> = {
    disconnected: "text-aureus-muted",
    connecting:   "text-aureus-muted",
    ready:        "text-aureus-emerald",
    listening:    "text-aureus-gold",
    thinking:     "text-aureus-amber",
    speaking:     "text-aureus-goldbright",
  };

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center justify-between rounded-sm p-3 border border-aureus-rule"
           style={{ background: "var(--panel)" }}>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            status === "ready" ? "bg-aureus-emerald pulse-gold" :
            status === "listening" ? "bg-aureus-gold pulse-gold" :
            "bg-aureus-muted"
          }`} />
          <span className={`text-sm font-medium ${statusColor[status]}`}>
            {statusLabel[status]}
          </span>
        </div>
        <span className="text-xs text-aureus-muted">Tier: {tier}</span>
      </div>

      {/* Conversation history */}
      <div className="rounded-sm border border-aureus-rule overflow-hidden"
           style={{ background: "var(--panel)" }}>
        <div className="h-80 overflow-y-auto p-4 space-y-3">
          {turns.length === 0 && (
            <p className="text-aureus-muted text-sm text-center mt-8">
              Press and hold the microphone to start speaking
            </p>
          )}
          {turns.map((turn, i) => (
            <div key={i} className={`flex gap-2 ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
              {turn.role === "assistant" && (
                <div className="w-6 h-6 bg-aureus-gold text-aureus-ink font-mono-num font-medium flex items-center justify-center text-[11px] shrink-0">
                  A
                </div>
              )}
              <div className={`max-w-xs rounded-sm px-3 py-2 text-sm ${
                turn.role === "user"
                  ? "bg-aureus-gold text-aureus-ink"
                  : "border border-aureus-rule text-aureus-text"
              }`} style={turn.role === "assistant" ? { background: "var(--ink)" } : {}}>
                {turn.text}
                <div className={`text-xs mt-1 ${turn.role === "user" ? "text-aureus-ink/60" : "text-aureus-muted"}`}>
                  {turn.timestamp}
                </div>
              </div>
            </div>
          ))}
          {interim && (
            <div className="flex justify-end">
              <div className="bg-aureus-gold/30 text-aureus-gold border border-aureus-gold/50
                              rounded-sm px-3 py-2 text-sm italic max-w-xs">
                {interim}
              </div>
            </div>
          )}
          <div ref={scrollRef} />
        </div>
      </div>

      {/* Waveform visual (active when listening) */}
      {status === "listening" && (
        <div className="flex items-center justify-center gap-1 h-8">
          {[1,2,3,4,5].map((i) => (
            <div key={i} className="voice-bar w-1 h-6 bg-aureus-gold" />
          ))}
        </div>
      )}

      {/* Push-to-talk. An emoji stood in for the icon here, which on an
          80px control renders at whatever size and weight the user's OS
          decided — the one element on the page guaranteed to look
          different on every machine. The disclaimer that used to sit below
          now lives on the page, so it isn't stated twice. */}
      <div className="flex flex-col items-center gap-2.5">
        <button
          onMouseDown={startListening}
          onMouseUp={stopListening}
          onTouchStart={startListening}
          onTouchEnd={stopListening}
          disabled={status === "disconnected" || status === "connecting" || status === "thinking"}
          aria-label="Hold to speak"
          className={`w-20 h-20 rounded-sm flex items-center justify-center
                      transition-all duration-150 select-none
                      ${status === "listening"
                        ? "bg-aureus-gold text-aureus-ink scale-105"
                        : "bg-aureus-panel border border-aureus-rulestrong text-aureus-soft hover:border-aureus-gold hover:text-aureus-gold"
                      }
                      disabled:opacity-40 disabled:cursor-not-allowed`}
        >
          <IconMic className="w-7 h-7" strokeWidth={1.25} />
        </button>
        <span className="text-[11px] text-aureus-muted">
          {status === "listening" ? "Release to send" : "Hold to speak"}
        </span>
      </div>
    </div>
  );
}
