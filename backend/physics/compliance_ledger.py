"""SHA-256 chain over the measured proof files. A changed gallon breaks the next hash."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _canon(payload: dict) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def seal(records: list[dict]) -> list[dict]:
    """Append prev and hash. `records` must not already contain those keys."""
    previous = "0" * 64
    sealed = []
    for record in records:
        body = dict(record)
        body["prev"] = previous
        digest = hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()
        body["hash"] = digest
        sealed.append(body)
        previous = digest
    return sealed


def verify(records: list[dict]) -> bool:
    previous = "0" * 64
    for record in records:
        if record.get("prev") != previous:
            return False
        body = {key: value for key, value in record.items() if key != "hash"}
        digest = hashlib.sha256(_canon(body).encode("utf-8")).hexdigest()
        if digest != record.get("hash"):
            return False
        previous = digest
    return True


def load(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))
