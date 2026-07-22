"use client";
import { useEffect, useRef, useState, useCallback } from "react";
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
        if (status === "listening") setStatus("ready");
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
    connecting:   "Connecting...",
    ready:        "Ready — hold to speak",
    listening:    "Listening...",
    thinking:     "Thinking...",
    speaking:     "Speaking...",
  };

  const statusColor: Record<Status, string> = {
    disconnected: "text-aureus-muted",
    connecting:   "text-aureus-muted",
    ready:        "text-aureus-green",
    listening:    "text-aureus-gold",
    thinking:     "text-blue-400",
    speaking:     "text-purple-400",
  };

  return (
    <div className="space-y-4">
      {/* Status bar */}
      <div className="flex items-center justify-between rounded-lg p-3 border border-aureus-border"
           style={{ background: "var(--surface)" }}>
        <div className="flex items-center gap-2">
          <div className={`w-2 h-2 rounded-full ${
            status === "ready" ? "bg-aureus-green pulse-gold" :
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
      <div className="rounded-lg border border-aureus-border overflow-hidden"
           style={{ background: "var(--surface)" }}>
        <div className="h-80 overflow-y-auto p-4 space-y-3">
          {turns.length === 0 && (
            <p className="text-aureus-muted text-sm text-center mt-8">
              Press and hold the microphone to start speaking
            </p>
          )}
          {turns.map((turn, i) => (
            <div key={i} className={`flex gap-2 ${turn.role === "user" ? "justify-end" : "justify-start"}`}>
              {turn.role === "assistant" && (
                <div className="w-6 h-6 rounded-full bg-aureus-gold flex items-center justify-center text-xs flex-shrink-0">
                  A
                </div>
              )}
              <div className={`max-w-xs rounded-lg px-3 py-2 text-sm ${
                turn.role === "user"
                  ? "bg-aureus-gold text-black"
                  : "border border-aureus-border text-white"
              }`} style={turn.role === "assistant" ? { background: "var(--bg)" } : {}}>
                {turn.text}
                <div className={`text-xs mt-1 ${turn.role === "user" ? "text-amber-800" : "text-aureus-muted"}`}>
                  {turn.timestamp}
                </div>
              </div>
            </div>
          ))}
          {interim && (
            <div className="flex justify-end">
              <div className="bg-aureus-gold/30 text-aureus-gold border border-aureus-gold/50
                              rounded-lg px-3 py-2 text-sm italic max-w-xs">
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
            <div key={i} className="voice-bar w-1 h-6 rounded-full bg-aureus-gold" />
          ))}
        </div>
      )}

      {/* Mic button */}
      <div className="flex justify-center">
        <button
          onMouseDown={startListening}
          onMouseUp={stopListening}
          onTouchStart={startListening}
          onTouchEnd={stopListening}
          disabled={status === "disconnected" || status === "connecting" || status === "thinking"}
          className={`w-20 h-20 rounded-full flex items-center justify-center text-3xl
                      transition-all duration-150 select-none
                      ${status === "listening"
                        ? "bg-aureus-gold scale-110 shadow-lg shadow-amber-500/30"
                        : "border-2 border-aureus-border hover:border-aureus-gold"
                      }
                      disabled:opacity-40 disabled:cursor-not-allowed`}
          style={status !== "listening" ? { background: "var(--surface)" } : {}}
        >
          🎤
        </button>
      </div>

      <p className="text-center text-xs text-aureus-muted">
        Nothing said here constitutes financial advice.
        Voice sessions are processed by AI and may be logged for quality purposes.
      </p>
    </div>
  );
}
