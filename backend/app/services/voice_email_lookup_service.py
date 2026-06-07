from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
import re
from typing import Iterable

from sqlalchemy.orm import Session

from app.models.email_summary import EmailSummary
from app.models.mail_summary_call_log import MailSummaryCallLog
from app.models.user import User
from app.models.voice_call_interaction import VoiceCallInteraction
from app.services.voice_intent_service import (
    LOOKUP_FIRST,
    LOOKUP_KEYWORD,
    LOOKUP_LAST,
    LOOKUP_LATEST,
    LOOKUP_NUMBER,
    LOOKUP_SENDER,
    LOOKUP_SUBJECT,
    LOOKUP_UNKNOWN,
    ParsedVoiceIntent,
)


@dataclass(slots=True)
class EmailLookupMatch:
    email_reference: int
    summary: EmailSummary
    score: float
    matched_fields: list[str]

    def to_dict(self) -> dict[str, object]:
        return {
            "email_reference": self.email_reference,
            "sender": self.summary.sender,
            "subject": self.summary.subject,
            "received_at": self.summary.email_message.received_at if self.summary.email_message else None,
            "score": round(self.score, 3),
            "matched_fields": self.matched_fields,
        }


@dataclass(slots=True)
class EmailLookupResult:
    status: str
    email_summary: EmailSummary | None
    email_reference: int | None
    matches: list[dict[str, object]]
    message: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _parse_delivered_summary_ids(payload: str | None) -> list[int]:
    if not payload:
        return []
    import json

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return []
    if isinstance(data, list):
        return [int(item) for item in data]
    return []


def _normalize(text: str | None) -> str:
    text = (text or "").strip().lower()
    text = text.replace("â€™", "'")
    text = re.sub(r"[^\w\s']", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def _tokenize(text: str | None) -> list[str]:
    return [token for token in _normalize(text).split() if token]


def _score_text(query: str, *candidates: str | None) -> float:
    query_norm = _normalize(query)
    query_tokens = set(_tokenize(query_norm))
    best = 0.0
    for candidate in candidates:
        candidate_norm = _normalize(candidate)
        if not candidate_norm:
            continue
        candidate_tokens = set(_tokenize(candidate_norm))
        if query_norm == candidate_norm:
            best = max(best, 1.0)
            continue
        if query_norm in candidate_norm:
            best = max(best, 0.95)
        if candidate_norm in query_norm:
            best = max(best, 0.9)
        overlap = len(query_tokens & candidate_tokens)
        if overlap:
            best = max(best, min(0.5 + 0.1 * overlap, 0.88))
    return best


def _email_index_map(summary_ids: list[int], summaries: list[EmailSummary]) -> dict[int, EmailSummary]:
    summary_map = {summary.id: summary for summary in summaries}
    return {
        index + 1: summary_map[summary_id]
        for index, summary_id in enumerate(summary_ids)
        if summary_id in summary_map
    }


def _build_match(email_reference: int, summary: EmailSummary, score: float, matched_fields: list[str]) -> EmailLookupMatch:
    return EmailLookupMatch(
        email_reference=email_reference,
        summary=summary,
        score=score,
        matched_fields=matched_fields,
    )


def _sender_candidates(summary: EmailSummary) -> list[str]:
    sender = summary.sender or ""
    summary_sender = summary.sender or ""
    candidates = [sender, summary_sender]
    if summary_sender and "@" in summary_sender:
        candidates.append(summary_sender.split("@")[-1])
    if sender and "<" in sender and ">" in sender:
        candidates.append(sender.split("<", 1)[0].strip())
    return candidates


def _subject_candidates(summary: EmailSummary) -> list[str]:
    subject = summary.subject or ""
    return [subject]


def _keyword_candidates(summary: EmailSummary) -> list[str]:
    body = summary.short_summary or ""
    body += f" {summary.detailed_summary or ''}"
    body += f" {summary.subject or ''}"
    body += f" {summary.sender or ''}"
    return [body]


def _current_call_summaries(db: Session, call_log: MailSummaryCallLog) -> list[EmailSummary]:
    summary_ids = _parse_delivered_summary_ids(call_log.delivered_summary_ids)
    if not summary_ids:
        return []
    summaries = (
        db.query(EmailSummary)
        .filter(
            EmailSummary.user_id == call_log.user_id,
            EmailSummary.id.in_(summary_ids),
        )
        .all()
    )
    summary_map = {summary.id: summary for summary in summaries}
    return [summary_map[summary_id] for summary_id in summary_ids if summary_id in summary_map]


def _score_summary(summary: EmailSummary, lookup_type: str, lookup_query: str | None, reference: int) -> tuple[float, list[str]]:
    query = _normalize(lookup_query)
    matched_fields: list[str] = []
    score = 0.0

    if lookup_type == LOOKUP_NUMBER:
        if lookup_query and str(reference) == str(lookup_query).strip():
            return 1.0, ["email_reference"]
        return 0.0, []

    if lookup_type == LOOKUP_LATEST:
        return 0.0, []
    if lookup_type == LOOKUP_FIRST:
        return 0.0, []
    if lookup_type == LOOKUP_LAST:
        return 0.0, []

    if lookup_type == LOOKUP_SENDER:
        for candidate in _sender_candidates(summary):
            candidate_score = _score_text(query, candidate)
            if candidate_score > score:
                score = candidate_score
            if candidate_score >= 0.9:
                matched_fields.append("sender")
                break
        return score, matched_fields

    if lookup_type == LOOKUP_SUBJECT:
        for candidate in _subject_candidates(summary):
            candidate_score = _score_text(query, candidate)
            if candidate_score > score:
                score = candidate_score
            if candidate_score >= 0.9:
                matched_fields.append("subject")
                break
        if score < 0.85:
            body_score = _score_text(query, summary.short_summary, summary.detailed_summary)
            score = max(score, body_score)
            if body_score:
                matched_fields.append("summary")
        return score, matched_fields

    if lookup_type in {LOOKUP_KEYWORD, LOOKUP_UNKNOWN}:
        candidates = _keyword_candidates(summary)
        for candidate in candidates:
            candidate_score = _score_text(query, candidate)
            if candidate_score > score:
                score = candidate_score
        if score >= 0.9:
            matched_fields.append("keyword")
        elif score >= 0.7:
            matched_fields.append("summary")
        return score, matched_fields

    return 0.0, []


def resolve_email_reference_for_call(
    db: Session,
    user: User,
    call_log: MailSummaryCallLog,
    parsed_intent: ParsedVoiceIntent,
) -> dict[str, object]:
    summaries = _current_call_summaries(db, call_log)
    if not summaries:
        return EmailLookupResult(
            status="no_match",
            email_summary=None,
            email_reference=None,
            matches=[],
            message="I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call.",
        ).to_dict()

    summary_ids = _parse_delivered_summary_ids(call_log.delivered_summary_ids)
    summary_map = _email_index_map(summary_ids, summaries)

    lookup_type = parsed_intent.lookup_type or LOOKUP_UNKNOWN
    lookup_query = parsed_intent.lookup_query or parsed_intent.sender_query or parsed_intent.subject_query or parsed_intent.keyword_query

    if lookup_type == LOOKUP_UNKNOWN and not lookup_query and parsed_intent.email_reference is None:
        return EmailLookupResult(
            status="no_match",
            email_summary=None,
            email_reference=None,
            matches=[],
            message="I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call.",
        ).to_dict()

    if parsed_intent.email_reference is not None:
        ref = parsed_intent.email_reference
        if ref < 1 or ref > len(summary_map):
            return EmailLookupResult(
                status="invalid_reference",
                email_summary=None,
                email_reference=None,
                matches=[],
                message="I only read five emails in this call. Please say a number between one and five, or say no to end the call.",
            ).to_dict()
        summary = summary_map[ref]
        return EmailLookupResult(
            status="matched",
            email_summary=summary,
            email_reference=ref,
            matches=[_build_match(ref, summary, 1.0, ["email_reference"]).to_dict()],
            message="matched by number",
        ).to_dict()

    if lookup_type in {LOOKUP_LATEST, LOOKUP_FIRST, LOOKUP_LAST}:
        ordered = list(summary_map.items())
        if not ordered:
            return EmailLookupResult(
                status="no_match",
                email_summary=None,
                email_reference=None,
                matches=[],
                message="I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call.",
            ).to_dict()
        if lookup_type == LOOKUP_FIRST:
            ref, summary = ordered[0]
        elif lookup_type == LOOKUP_LAST:
            ref, summary = ordered[-1]
        else:
            ref, summary = max(
                ordered,
                key=lambda item: (
                    item[1].email_message.received_at if item[1].email_message and item[1].email_message.received_at else datetime.min,
                    item[0],
                ),
            )
        return EmailLookupResult(
            status="matched",
            email_summary=summary,
            email_reference=ref,
            matches=[_build_match(ref, summary, 0.99, [lookup_type]).to_dict()],
            message="matched by ordinal lookup",
        ).to_dict()

    matches: list[EmailLookupMatch] = []
    for ref, summary in summary_map.items():
        score, fields = _score_summary(summary, lookup_type, lookup_query, ref)
        if score > 0:
            matches.append(_build_match(ref, summary, score, fields))

    if not matches:
        return EmailLookupResult(
            status="no_match",
            email_summary=None,
            email_reference=None,
            matches=[],
            message="I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call.",
        ).to_dict()

    matches.sort(key=lambda item: (item.score, item.email_reference), reverse=True)
    top = matches[0]
    if top.score < 0.75:
        return EmailLookupResult(
            status="no_match",
            email_summary=None,
            email_reference=None,
            matches=[],
            message="I could not find a matching email from today's summaries. You can say email number one, repeat summary, or no to end the call.",
        ).to_dict()
    if len(matches) > 1 and abs(matches[0].score - matches[1].score) < 0.12:
        return EmailLookupResult(
            status="multiple_matches",
            email_summary=None,
            email_reference=None,
            matches=[match.to_dict() for match in matches[:3]],
            message="I found multiple matching emails. Please say email number one, two, or three.",
        ).to_dict()

    return EmailLookupResult(
        status="matched",
        email_summary=top.summary,
        email_reference=top.email_reference,
        matches=[top.to_dict()],
        message="matched",
    ).to_dict()


def get_last_explained_email_for_call(db: Session, call_log: MailSummaryCallLog) -> dict[str, object] | None:
    interaction = (
        db.query(VoiceCallInteraction)
        .filter(
            VoiceCallInteraction.mail_call_log_id == call_log.id,
            VoiceCallInteraction.detected_intent == "DETAIL_EMAIL",
            VoiceCallInteraction.email_reference.is_not(None),
        )
        .order_by(VoiceCallInteraction.interaction_order.desc(), VoiceCallInteraction.id.desc())
        .first()
    )
    if interaction is None or interaction.email_reference is None:
        return None

    resolved = resolve_email_reference_for_call(
        db,
        call_log.user,
        call_log,
        ParsedVoiceIntent(
            intent="DETAIL_EMAIL",
            email_reference=interaction.email_reference,
            confidence=1.0,
            normalized_transcript="",
            reason="last explained email lookup",
        ),
    )
    if resolved.get("status") != "matched":
        return None
    return resolved
