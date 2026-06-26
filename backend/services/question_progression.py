"""
Question progression service.

Walks the player through the catalog of `questions/p*.json` files in
question_id order (P001, P002, P003, …). Tracks completion in the
`player_completed_tasks` table.

Public API:
  list_question_ids()                       - all available question IDs, sorted
  completed_ids_for(db, player)             - set of question IDs this player has finished
  current_question_id_for(db, player)       - first un-completed; falls back to last completed
  mark_completed(db, player, qid, attempts) - idempotent; no-op if already marked
"""

from __future__ import annotations

import re
from functools import lru_cache
from pathlib import Path

from sqlalchemy.orm import Session

from backend.config import settings
from backend.db.models import Player, PlayerCompletedTask


_FILE_RE = re.compile(r"^p\d+_[a-z0-9_]+\.json$")


def _numeric_prefix(qid: str) -> int:
    m = re.match(r"p(\d+)", qid)
    return int(m.group(1)) if m else 9_999_999


def _read_sequence(path: Path) -> int:
    """Read the `sequence` field from a question file. Missing/invalid → a
    very large value so legacy files sort to the end of the list rather
    than disrupting the Bloom-mapped order.
    """
    import json
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("sequence")
        return int(raw) if raw is not None else 9_999_999
    except Exception:
        return 9_999_999


@lru_cache(maxsize=1)
def list_question_ids() -> tuple[str, ...]:
    """Return all available question IDs in **Bloom-mapped sequence order**.

    Each question file carries a `sequence` field that determines the
    student-facing order across the curriculum — not the filename prefix.
    Ties (or missing sequence values) fall back to the numeric prefix so
    the order remains deterministic.

    Cached because the catalog is filesystem-driven and effectively static
    during a process lifetime (the author script runs offline).
    """
    root = Path(settings.questions_dir).resolve()
    if not root.is_dir():
        return tuple()
    entries: list[tuple[int, int, str]] = []
    for p in root.iterdir():
        if p.is_file() and _FILE_RE.match(p.name):
            qid = p.stem
            entries.append((_read_sequence(p), _numeric_prefix(qid), qid))
    entries.sort()
    return tuple(qid for _seq, _pref, qid in entries)


def clear_cache() -> None:
    list_question_ids.cache_clear()


def completed_ids_for(db: Session, player: Player) -> set[str]:
    rows = (
        db.query(PlayerCompletedTask)
        .filter(PlayerCompletedTask.player_id == player.id)
        .all()
    )
    return {r.question_id for r in rows}


def current_question_id_for(db: Session, player: Player) -> str:
    """The question the player should see right now.

    v3 priority order:
      1. First un-completed question in the player's CURRENT phase.
      2. First un-completed question anywhere in the catalog (fallback for
         when their phase has no remaining questions but earlier phases do).
      3. Last question in the catalog (review mode when everything is done).
      4. Seed question (catalog empty).
    """
    catalog = list_question_ids()
    if not catalog:
        return settings.seed_question_id

    # Imported lazily to avoid a circular import (phase_progression imports
    # list_question_ids/completed_ids_for from this module).
    from backend.services.phase_progression import next_question_for_phase

    phase_qid = next_question_for_phase(db, player)
    if phase_qid is not None:
        return phase_qid

    done = completed_ids_for(db, player)
    for qid in catalog:
        if qid not in done:
            return qid

    # All finished — stay on the last one for review.
    return catalog[-1]


def mark_completed(
    db: Session,
    player: Player,
    question_id: str,
    attempts_taken: int,
) -> bool:
    """Mark question as completed for this player. Idempotent — returns True
    only the first time the player completes this question.
    """
    existing = (
        db.query(PlayerCompletedTask)
        .filter(
            PlayerCompletedTask.player_id == player.id,
            PlayerCompletedTask.question_id == question_id,
        )
        .first()
    )
    if existing is not None:
        return False
    db.add(
        PlayerCompletedTask(
            player_id=player.id,
            question_id=question_id,
            attempts_taken=max(1, int(attempts_taken or 1)),
        )
    )
    return True


__all__ = [
    "list_question_ids",
    "completed_ids_for",
    "current_question_id_for",
    "mark_completed",
    "clear_cache",
]
