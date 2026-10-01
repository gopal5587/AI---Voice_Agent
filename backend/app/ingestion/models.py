from dataclasses import dataclass, field
from typing import Any


class ExtractionError(Exception):
    """Raised when a source cannot be parsed; recorded in the ingestion report instead of aborting the build."""


@dataclass
class Section:
    heading: str
    text: str
    locator: str
    structured: dict[str, Any] | None = None
    raw_text: str | None = None  # full original text when `text` is a derived extract; used for the PII audit


@dataclass
class ParsedDoc:
    title: str
    sections: list[Section]
    meta: dict[str, Any] = field(default_factory=dict)
    removed_boilerplate: list[str] = field(default_factory=list)
    quality_flags: list[dict[str, Any]] = field(default_factory=list)
