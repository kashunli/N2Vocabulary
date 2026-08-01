"""Small data models shared by the track-lyrics workflow."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class Cue:
    """One timed word or example sentence in an original CD track."""

    book: str
    track: str
    entry_id: int
    kind: str
    text: str
    start: float
    end: float
    source_audio: str
    source_clip: str | None
    alignment_method: str
    confidence: float
    example_position: int | None = None
    review_reasons: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["start"] = round(self.start, 6)
        data["end"] = round(self.end, 6)
        data["confidence"] = round(self.confidence, 6)
        return data


@dataclass
class ClipRequest:
    """Text plus a CD-derived clip that must be located in a source track."""

    entry_id: int
    kind: str
    text: str
    clip_path: str | None
    example_position: int | None = None


@dataclass
class EntryRequest:
    """All audio-bearing content for one ordered vocabulary entry."""

    entry_id: int
    unit_number: int
    headword: str
    reading: str
    word: ClipRequest
    sentences: list[ClipRequest]
    source_candidates: list[str]

