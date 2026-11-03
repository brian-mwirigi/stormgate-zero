"""Runtime configuration: Meta endpoints, model IDs, and GIS polygons."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

DATA_DIR = ROOT / "data"
RADAR_DIR = DATA_DIR / "radar"
OUTFALL_DIR = DATA_DIR / "outfall"
SWMM_DIR = DATA_DIR / "swmm"


class Settings:
    """Process-wide settings. Environment variables override the defaults."""

    META_API_KEY: str = os.getenv("MODEL_API_KEY", "")
    META_BASE_URL: str = os.getenv("META_BASE_URL", "https://api.meta.ai/v1").rstrip("/")

    OPEN_WEIGHT_API_KEY: str = os.getenv("OPEN_WEIGHT_API_KEY", os.getenv("MODEL_API_KEY", ""))
    OPEN_WEIGHT_BASE_URL: str = os.getenv(
        "OPEN_WEIGHT_BASE_URL",
        os.getenv("META_BASE_URL", "https://api.meta.ai/v1"),
    ).rstrip("/")

    MODEL_WONDER: str = os.getenv("MODEL_WONDER", "muse-wonder-1.0")
    MODEL_SPARK: str = os.getenv("MODEL_SPARK", "muse-spark-1.3")
    MODEL_SPARK_CONTRIB: str = os.getenv("MODEL_SPARK_CONTRIB", "muse-spark-1.3-contributor")
    # Partner id from Meta's deploy page (Baseten, Groq, Together). api.meta.ai
    # returns model_not_found for it. Point OPEN_WEIGHT_BASE_URL at the partner.
    MODEL_SPARK_OPEN: str = os.getenv("MODEL_SPARK_OPEN", "meta-models/muse-spark-open")
    MODEL_GLIMMER: str = os.getenv("MODEL_GLIMMER", "meta-models/Muse-Glimmer-30B")
    MODEL_SAM: str = "sam-3.1"
    MODEL_IMAGE: str = "muse-image-1.0"
    MODEL_VOICE: str = "muse-voice-transcribe-1.0"

    # Normalized radar coordinates (x1, y1, x2, y2), origin at the top-left.
    SUBCATCHMENT_POLYGONS = {
        "Basin_1_North": (0.10, 0.10, 0.45, 0.45),
        "Basin_2_Central": (0.30, 0.30, 0.70, 0.65),
        "Basin_3_East": (0.55, 0.15, 0.90, 0.55),
        "Basin_4_Downstream_Critical": (0.45, 0.55, 0.92, 0.92),
    }

    BASIN_IDS = (
        "Basin_1_North",
        "Basin_2_Central",
        "Basin_3_East",
        "Basin_4_Downstream_Critical",
    )
    BASIN_SHORT = ("SU1", "SU2", "SU3", "SU4")
    ORIFICE_IDS = ("OR1", "OR2", "OR3", "OR4")

    STEP_MINUTES: int = 5
    HORIZON_STEPS: int = 12  # 60-minute MPC horizon
    EPISODE_STEPS: int = 18  # 90-minute design storm
    LOOKAHEAD_STEPS: int = 9  # 45-minute SAM nowcast
    EPISODE_STEP_SECONDS: float = float(os.getenv("EPISODE_STEP_SECONDS", "1.15"))
    OFFLINE: bool = os.getenv("STORMGATE_OFFLINE", "0") == "1"
    # Hosted Wonder calls for the whole process. The looping storm stays local.
    HOSTED_BUDGET: int = int(os.getenv("STORMGATE_HOSTED_BUDGET", "1"))
    # Second-turn Spark calls. Cache hits replay even when this is off.
    REFINE: bool = os.getenv("STORMGATE_REFINE", "0") == "1"

    @property
    def refine_enabled(self) -> bool:
        return self.REFINE and self.meta_enabled

    @property
    def meta_enabled(self) -> bool:
        return bool(self.META_API_KEY) and not self.OFFLINE

    @property
    def brev_configured(self) -> bool:
        """True when a NVIDIA Brev OpenAI-compatible endpoint is in the environment."""
        return bool(os.getenv("BREV_BASE_URL", "").strip()) and bool(os.getenv("BREV_API_KEY", "").strip())

    @property
    def open_weight_base_url(self) -> str:
        brev = os.getenv("BREV_BASE_URL", "").strip().rstrip("/")
        return brev or self.OPEN_WEIGHT_BASE_URL

    @property
    def open_weight_api_key(self) -> str:
        return os.getenv("BREV_API_KEY", "").strip() or self.OPEN_WEIGHT_API_KEY

    @property
    def open_weight_model(self) -> str:
        return os.getenv("BREV_MODEL", "").strip() or self.MODEL_SPARK_OPEN

    @property
    def open_weight_enabled(self) -> bool:
        if self.OFFLINE:
            return False
        return self.brev_configured or bool(self.OPEN_WEIGHT_API_KEY)


settings = Settings()
