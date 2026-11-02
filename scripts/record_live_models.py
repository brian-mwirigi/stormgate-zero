"""One live pass over DS-1482. Writes traces/live_models.json.

Spark is called on every unjammed step. SAM is called on three radar
frames. Voice is called on a synthesized radio sentence. Later loops
replay the file.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from backend.agents.sam_radar_tracker import segment_frames  # noqa: E402
from backend.agents.voice_scada_bridge import transcribe_file  # noqa: E402
from backend.episode import Episode, JAM_LINE  # noqa: E402


def _speak(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        f"$synth.SetOutputToWaveFile('{path}'); "
        f"$synth.Speak('{JAM_LINE}'); "
        "$synth.Dispose()"
    )
    subprocess.run(["powershell", "-NoProfile", "-Command", script], check=True)


async def main() -> None:
    episode = Episode()
    for _ in range(18):
        await episode.step_once()
        decision = episode.decision
        print(
            f"step={episode.sim.step_index - 1} selected={decision.get('selected')} "
            f"spark={decision.get('spark_source')} ms={decision.get('spark_latency_ms')} "
            f"cso={episode.sim.stormgate.cso_mg:.4f}",
            flush=True,
        )
    sam = await segment_frames([0.0, 40.0, 55.0])
    print(f"sam ok={sam.get('ok')} frames={len(sam.get('frames') or [])} errors={sam.get('errors')}", flush=True)
    wav = ROOT / "data" / "voice" / "jam.wav"
    _speak(wav)
    voice = await transcribe_file(wav.read_bytes(), "jam.wav")
    print(f"voice ok={voice.get('ok')} text={voice.get('text', '')[:180]} detail={voice.get('detail')}", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
