"""
backend/pipeline/temporal.py
------------------------------
Deterministic temporal parsing and alignment.
"""
from __future__ import annotations

import datetime as dt
import re
from dataclasses import dataclass
from typing import Iterable, Optional


_ISO_DATE_RE = re.compile(r"\b(20\d{2}|19\d{2})-(\d{2})-(\d{2})\b")
_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_RECENT_RE = re.compile(r"\b(today|yesterday|this week|last week|tonight|this month)\b", re.I)


@dataclass
class TemporalContext:
    event_date: Optional[dt.date]
    utterance_date: dt.date
    explicit: bool = False
    matched_text: str = ""


def parse_datetime(value) -> Optional[dt.datetime]:
    """Parse common source timestamp formats to UTC-naive datetimes."""
    if value in (None, "", 0):
        return None
    if isinstance(value, dt.datetime):
        return value.replace(tzinfo=None)
    if isinstance(value, dt.date):
        return dt.datetime.combine(value, dt.time.min)
    if isinstance(value, (int, float)):
        try:
            return dt.datetime.utcfromtimestamp(float(value))
        except Exception:
            return None

    text = str(value).strip()
    if not text:
        return None

    for parser in (
        lambda s: dt.datetime.fromisoformat(s.replace("Z", "+00:00")).replace(tzinfo=None),
        lambda s: dt.datetime.strptime(s[:14], "%Y%m%d%H%M%S"),
        lambda s: dt.datetime.strptime(s[:10], "%Y-%m-%d"),
    ):
        try:
            return parser(text)
        except Exception:
            continue
    return None


def days_ago_from_datetime(value, now: Optional[dt.datetime] = None) -> Optional[int]:
    parsed = parse_datetime(value)
    if parsed is None:
        return None
    now = now or dt.datetime.utcnow()
    return max(0, int((now - parsed).total_seconds() // 86400))


def extract_temporal_context(claim: str, now: Optional[dt.date] = None) -> TemporalContext:
    """Extract an explicit event date or a recent-time intent."""
    utterance_date = now or dt.date.today()
    if not claim:
        return TemporalContext(event_date=None, utterance_date=utterance_date)

    iso_match = _ISO_DATE_RE.search(claim)
    if iso_match:
        year, month, day = map(int, iso_match.groups())
        return TemporalContext(
            event_date=dt.date(year, month, day),
            utterance_date=utterance_date,
            explicit=True,
            matched_text=iso_match.group(0),
        )

    year_match = _YEAR_RE.search(claim)
    if year_match:
        year = int(year_match.group(1))
        return TemporalContext(
            event_date=dt.date(year, 1, 1),
            utterance_date=utterance_date,
            explicit=True,
            matched_text=year_match.group(1),
        )

    if _RECENT_RE.search(claim):
        lowered = claim.lower()
        if "yesterday" in lowered:
            event_date = utterance_date - dt.timedelta(days=1)
        elif "last week" in lowered:
            event_date = utterance_date - dt.timedelta(days=7)
        elif "this month" in lowered:
            event_date = utterance_date - dt.timedelta(days=30)
        else:
            event_date = utterance_date
        return TemporalContext(
            event_date=event_date,
            utterance_date=utterance_date,
            explicit=False,
            matched_text="recent_reference",
        )

    return TemporalContext(event_date=None, utterance_date=utterance_date)


def _alignment_for_dates(
    event_date: Optional[dt.date],
    source_dt: Optional[dt.datetime],
    explicit: bool,
    utterance_date: dt.date,
) -> tuple[float, Optional[str]]:
    if source_dt is None:
        return 1.0, None
    source_date = source_dt.date()

    if event_date is None:
        if (utterance_date - source_date).days > 180:
            return 0.70, "stale_source"
        return 1.0, None

    if source_date < event_date - dt.timedelta(days=30):
        return 0.30, "predates_event"

    if explicit:
        return 1.0, None

    age_gap = abs((source_date - event_date).days)
    if age_gap <= 3:
        return 1.0, None
    if age_gap <= 14:
        return 0.85, None
    if age_gap <= 60:
        return 0.65, "stale_source"
    return 0.40, "stale_source"


def annotate_temporal_alignment(evidence: Iterable, claim: str) -> dict:
    """Annotate each evidence item with a temporal alignment factor."""
    context = extract_temporal_context(claim)
    dated_alignments = []

    for item in evidence:
        source_dt = parse_datetime(getattr(item, "published_at", None))
        if source_dt is None:
            days_ago = getattr(item, "published_days_ago", None)
            if days_ago is not None:
                source_dt = dt.datetime.utcnow() - dt.timedelta(days=int(days_ago))

        alignment, flag = _alignment_for_dates(
            context.event_date,
            source_dt,
            context.explicit,
            context.utterance_date,
        )
        item.temporal_alignment = round(alignment, 4)
        if flag and flag not in item.risk_flags:
            item.risk_flags.append(flag)
        if source_dt is not None:
            item.published_at = item.published_at or source_dt.date().isoformat()
            item.published_days_ago = max(
                0,
                int((dt.datetime.utcnow().date() - source_dt.date()).days),
            )
            if getattr(item, "stance", "NEUTRAL") != "NEUTRAL":
                dated_alignments.append(item.temporal_alignment)

    avg_alignment = sum(dated_alignments) / len(dated_alignments) if dated_alignments else 1.0
    temporal_penalty = 1.0 - avg_alignment if dated_alignments else 0.0
    return {
        "event_date": context.event_date.isoformat() if context.event_date else None,
        "utterance_date": context.utterance_date.isoformat(),
        "temporal_penalty": round(max(0.0, temporal_penalty), 4),
        "temporal_alignment_avg": round(avg_alignment, 4),
        "temporal_has_explicit_date": context.explicit,
        "temporal_matched_text": context.matched_text,
    }
