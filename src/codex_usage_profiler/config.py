from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from .util import safe_json_load


@dataclass
class Config:
    path_aliases: Dict[str, str] = field(default_factory=dict)
    client_aliases: Dict[str, str] = field(default_factory=dict)
    task_aliases: Dict[str, str] = field(default_factory=dict)
    rates: Dict[str, Dict[str, float]] = field(default_factory=dict)
    dollars_per_credit: Optional[float] = None
    monthly_plan_price_usd: Optional[float] = None
    codexbar_enabled: bool = True
    paperclip_enabled: bool = True
    paperclip_root: str = "~/.paperclip/instances/default"


def load_config(path: Optional[str]) -> Config:
    if not path:
        default = Path.cwd() / "codex-usage-profiler.json"
        if not default.exists():
            return Config()
        path = str(default)
    data = safe_json_load(Path(path).expanduser())
    if not isinstance(data, dict):
        return Config()
    return Config(
        path_aliases=dict(data.get("path_aliases") or {}),
        client_aliases=dict(data.get("client_aliases") or {}),
        task_aliases=dict(data.get("task_aliases") or {}),
        rates=dict(data.get("rates") or {}),
        dollars_per_credit=_num(data.get("dollars_per_credit")),
        monthly_plan_price_usd=_num(data.get("monthly_plan_price_usd")),
        codexbar_enabled=bool(data.get("codexbar_enabled", True)),
        paperclip_enabled=bool(data.get("paperclip_enabled", True)),
        paperclip_root=str(data.get("paperclip_root") or "~/.paperclip/instances/default"),
    )


def _num(value: Any) -> Optional[float]:
    if isinstance(value, (int, float)):
        return float(value)
    return None
