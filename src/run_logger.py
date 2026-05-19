"""Per-run debug output logger. Saves each pipeline phase output to disk."""

from __future__ import annotations

import json
import uuid
from pathlib import Path


class RunLogger:
    def __init__(self, base_dir: Path = Path("runs")):
        self.run_dir = base_dir / str(uuid.uuid4()) / "thinking path"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        print(f"Run output directory: {self.run_dir}")

    def save(self, phase: int, data: str | list) -> None:
        names = {
            1: "01_plan.md",
            2: "02_research_messages.json",
            3: "03_synthesis_output.md",
        }
        path = self.run_dir / names[phase]
        if isinstance(data, list):
            path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        else:
            path.write_text(data, encoding="utf-8")
        print(f"Phase {phase} saved: {path}")
