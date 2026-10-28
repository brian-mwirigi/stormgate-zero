import { useRef, useState } from "react";
import type { TwinState } from "../types";

type Props = {
  state: TwinState;
  onOutfall: () => void;
  onReset: () => void;
  onToggle: () => void;
};

export default function VoiceWarRoom({ state, onOutfall, onReset, onToggle }: Props) {
  const [listening, setListening] = useState(false);
  const [hint, setHint] = useState("");
  const recorder = useRef<MediaRecorder | null>(null);
  const chunks = useRef<Blob[]>([]);
  const spoken = useRef("");

  async function toggleMic() {
    if (listening) {
      recorder.current?.stop();
      setListening(false);
      return;
    }
    spoken.current = "";
    const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    if (Recognition) {
      const rec = new Recognition();
      rec.lang = "en-US";
      rec.onresult = (event) => {
        spoken.current = event.results[0]?.[0]?.transcript || "";
      };
      rec.start();
      window.setTimeout(() => rec.stop(), 6000);
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const media = new MediaRecorder(stream);
      chunks.current = [];
      media.ondataavailable = (event) => {
        if (event.data.size) chunks.current.push(event.data);
      };
      media.onstop = async () => {
        stream.getTracks().forEach((track) => track.stop());
        const blob = new Blob(chunks.current, { type: media.mimeType || "audio/webm" });
        const body = new FormData();
        body.append("file", blob, "war-room.webm");
        const response = await fetch("/api/voice/transcribe", { method: "POST", body });
        const payload = await response.json();
        if (!payload.ok && spoken.current) {
          await fetch("/api/voice/text", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ text: spoken.current }),
          });
          setHint("Muse Voice offline — browser transcript parsed.");
        } else if (!payload.ok) {
          setHint(payload.detail || "No transcript. Use the jam injector.");
        } else {
          setHint("Muse Voice Transcribe applied.");
        }
      };
      recorder.current = media;
      media.start();
      setListening(true);
      setHint("Listening. State the gate, the fault, and the percent.");
      window.setTimeout(() => {
        if (media.state === "recording") media.stop();
        setListening(false);
      }, 6000);
    } catch {
      setHint("Microphone blocked. The jam injector still parses a radio call.");
      setListening(false);
    }
  }

  return (
    <div className="sg-bar-bottom">
      <button className="sg-btn primary" onClick={toggleMic} type="button">
        {listening ? "● Listening…" : "🎙️ Live SCADA Voice Override"}
      </button>
      <button
        className="sg-btn danger"
        type="button"
        onClick={() => fetch("/api/fault", { method: "POST" })}
      >
        ⚠️ Inject Gate #2 Mechanical Jam (50%)
      </button>
      <button className="sg-btn" type="button" onClick={onOutfall}>
        🖼️ Render Outfall Visual Twin
      </button>
      <button className="sg-btn" type="button" onClick={onToggle}>
        {state.running ? "Pause" : state.done ? "Replay" : "Run"}
      </button>
      <button className="sg-btn" type="button" onClick={onReset}>
        Reset storm
      </button>
      <div className="sg-transcript">
        {state.transcript.length === 0 && <p>War room quiet. {hint}</p>}
        {state.transcript.map((turn, index) => (
          <p key={`${turn.speaker}-${index}`}>
            <b>
              {turn.speaker} [{turn.role}]
            </b>{" "}
            {turn.text}
          </p>
        ))}
        {state.faults.map((fault, index) => (
          <p key={`f-${index}`} style={{ color: "#ff3355" }}>
            FAULT {fault.orifice_id} locked at {Math.round((fault.locked_setting || 0) * 100)}%
          </p>
        ))}
      </div>
    </div>
  );
}
