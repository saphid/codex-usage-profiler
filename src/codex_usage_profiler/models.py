from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


TokenUsage = Dict[str, int]


def empty_usage() -> TokenUsage:
    return {
        "input_tokens": 0,
        "cached_input_tokens": 0,
        "output_tokens": 0,
        "reasoning_output_tokens": 0,
        "total_tokens": 0,
    }


@dataclass
class Attribution:
    label: str
    confidence: str
    evidence: List[str] = field(default_factory=list)


@dataclass
class Estimate:
    credits: Optional[float] = None
    cost_usd: Optional[float] = None
    confidence: str = "unknown"
    evidence: List[str] = field(default_factory=list)


@dataclass
class SessionRecord:
    session_id: str
    path: str
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    cwd: Optional[str] = None
    workspace_roots: List[str] = field(default_factory=list)
    model: Optional[str] = None
    source: Optional[str] = None
    originator: Optional[str] = None
    thread_source: Optional[str] = None
    cli_version: Optional[str] = None
    model_provider: Optional[str] = None
    usage: TokenUsage = field(default_factory=empty_usage)
    usage_known: bool = False
    event_counts: Dict[str, int] = field(default_factory=dict)
    tool_counts: Dict[str, int] = field(default_factory=dict)
    tool_sequence: List[str] = field(default_factory=list)
    command_signatures: List[str] = field(default_factory=list)
    command_labels: List[str] = field(default_factory=list)
    first_request_hash: Optional[str] = None
    first_request_snippet: Optional[str] = None
    first_request_features: Dict[str, str] = field(default_factory=dict)
    file_edit_markers: int = 0
    test_markers: int = 0
    error_markers: int = 0
    warning_markers: List[str] = field(default_factory=list)
    client: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    project: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    task: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    paperclip_company: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    paperclip_project: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    paperclip_staff: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    paperclip_task: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))
    estimate: Estimate = field(default_factory=Estimate)
    outcome: Attribution = field(default_factory=lambda: Attribution("unknown", "low"))

    def to_dict(self, include_snippets: bool = False) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "session_id": self.session_id,
            "path": self.path,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "cwd": self.cwd,
            "workspace_roots": self.workspace_roots,
            "model": self.model,
            "source": self.source,
            "originator": self.originator,
            "thread_source": self.thread_source,
            "cli_version": self.cli_version,
            "model_provider": self.model_provider,
            "usage": self.usage,
            "usage_known": self.usage_known,
            "event_counts": self.event_counts,
            "tool_counts": self.tool_counts,
            "tool_sequence": self.tool_sequence,
            "command_signatures": self.command_signatures,
            "command_labels": self.command_labels,
            "first_request_hash": self.first_request_hash,
            "first_request_features": self.first_request_features,
            "file_edit_markers": self.file_edit_markers,
            "test_markers": self.test_markers,
            "error_markers": self.error_markers,
            "warnings": self.warning_markers,
            "client": self.client.__dict__,
            "project": self.project.__dict__,
            "task": self.task.__dict__,
            "paperclip_company": self.paperclip_company.__dict__,
            "paperclip_project": self.paperclip_project.__dict__,
            "paperclip_staff": self.paperclip_staff.__dict__,
            "paperclip_task": self.paperclip_task.__dict__,
            "estimate": self.estimate.__dict__,
            "outcome": self.outcome.__dict__,
        }
        if include_snippets:
            data["first_request_snippet"] = self.first_request_snippet
        return data


@dataclass
class CodexBarTelemetry:
    available: bool = False
    cli_path: Optional[str] = None
    app_version: Optional[str] = None
    config_path: Optional[str] = None
    cost_cache_paths: List[str] = field(default_factory=list)
    pricing_cache_paths: List[str] = field(default_factory=list)
    history_path: Optional[str] = None
    live_usage: Optional[Dict[str, Any]] = None
    cost_usage: Optional[Dict[str, Any]] = None
    cost_cache: Optional[Dict[str, Any]] = None
    pi_cache: Optional[Dict[str, Any]] = None
    pricing_cache: Optional[Dict[str, Any]] = None
    history: Optional[Dict[str, Any]] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "available": self.available,
            "cli_path": self.cli_path,
            "app_version": self.app_version,
            "config_path": self.config_path,
            "cost_cache_paths": self.cost_cache_paths,
            "pricing_cache_paths": self.pricing_cache_paths,
            "history_path": self.history_path,
            "live_usage": self.live_usage,
            "cost_usage": self.cost_usage,
            "cost_cache": self.cost_cache,
            "pi_cache": self.pi_cache,
            "pricing_cache": self.pricing_cache,
            "history": self.history,
            "warnings": self.warnings,
        }


@dataclass
class Finding:
    kind: str
    title: str
    confidence: str
    session_ids: List[str]
    total_tokens: int
    cost_usd: Optional[float]
    quota_share_percent: Optional[float]
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return self.__dict__.copy()
