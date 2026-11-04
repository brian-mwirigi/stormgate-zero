import { useRef, useState } from "react";
import type { TwinState } from "../types";

type Props = { state: TwinState };

export default function VoiceWarRoom({ state }: Props) {
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
          setHint("Live microphone transcript parsed and applied to the plant.");
        } else if (!payload.ok) {
          await fetch("/api/fault", { method: "POST" });
          setHint("Replayed recorded Muse Voice radio call (OR2 locked at 50%).");
        } else {
          setHint("Transcribed by Muse Voice and applied to the plant.");
        }
      };
      recorder.current = media;
      media.start();
      setListening(true);
      setHint("Listening for 6 seconds. Say the gate, the fault, and the percent.");
      window.setTimeout(() => {
        if (media.state === "recording") media.stop();
        setListening(false);
      }, 6000);
    } catch {
      setHint("The microphone is blocked. The jam button sends the same radio call.");
      setListening(false);
    }
  }

  const empty = state.transcript.length === 0 && state.faults.length === 0;

  return (
    <section className="panel">
      <div className="panel-head">
        <h2>Field radio</h2>
        <span>a crew reports a stuck gate</span>
      </div>
      <div className="radio-actions">
        <button className={listening ? "btn rec" : "btn"} onClick={toggleMic} type="button">
          <i className="dot" />
          {listening ? "Listening…" : "Talk to the controller"}
        </button>
        <button className="btn fault" type="button" onClick={() => fetch("/api/fault", { method: "POST" })}>
          Jam gate OR2 at 50%
        </button>
      </div>
      <div className="log">
        {empty && (
          <p className="empty">
            Quiet. Press <b>Jam gate OR2 at 50%</b> mid-storm, or say “Sluice gate 2 is jammed at 50 percent.”
          </p>
        )}
        {state.transcript.map((turn, index) => (
          <p key={`${turn.speaker}-${index}`}>
            <span className="who">
              {turn.speaker} · {turn.role}
              {turn.t_min !== undefined ? ` · T+${turn.t_min} min` : ""}
            </span>
            {turn.text}
          </p>
        ))}
        {state.faults.map((fault, index) => (
          <p key={`f-${index}`} className="fault-line">
            {fault.orifice_id} locked at {Math.round((fault.locked_setting || 0) * 100)}%. Every plan now routes around it.
          </p>
        ))}
        {hint && <p className="empty">{hint}</p>}
      </div>
    </section>
  );
}
