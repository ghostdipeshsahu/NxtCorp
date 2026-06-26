"""
Story event engine (step 10).

Defines the Act 1 / early Act 2 events that fire between tasks based on the
player's history. Designed deterministically (no LLM calls — the story
content is hand-authored and stable):

  - act1_day3_arjun_congrats   — fires after first passing attempt
  - act1_day5_ravi_nice_work   — fires after 3+ attempts total, post day-3 event
  - act1_day10_zara_first_qa   — fires after first failure with a primary_gap
  - act1_end_of_week           — fires after 5+ attempts, post day-3 + day-5 events

Per spec §4:
  - Each event is < 5 short messages
  - Never interrupts a task in progress
  - Appears between tasks
  - Student can skip events but misses the XP bonus
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional

from sqlalchemy.orm import Session

from backend.db.models import Attempt, Player, PlayerStoryEvent
from backend.models.schemas import StoryEvent, StoryMessage


@dataclass
class StoryEventDef:
    """Internal event definition. The condition closure inspects player + attempts
    and returns True iff this event should fire next for this player.
    """

    key: str
    title: str
    messages: list[StoryMessage]
    xp_bonus: int = 20
    story_day: Optional[int] = None
    story_act: Optional[int] = 1
    prereq_keys: tuple[str, ...] = field(default_factory=tuple)
    condition: Callable[[Player, list[Attempt]], bool] = lambda p, a: True

    def to_event(self, player: Player) -> StoryEvent:
        # Personalize message bodies with the player's display_name.
        msgs = [
            StoryMessage(
                character=m.character,
                expression=m.expression,
                body=m.body.replace("{name}", player.display_name or "you"),
            )
            for m in self.messages
        ]
        return StoryEvent(
            event_key=self.key,
            title=self.title,
            messages=msgs,
            xp_bonus=self.xp_bonus,
            story_day=self.story_day,
            story_act=self.story_act,
        )


# ----- Trigger predicates (small + named so they're testable) -----

def _has_passing_attempt(_: Player, attempts: list[Attempt]) -> bool:
    return any(a.all_passed for a in attempts)


def _has_n_attempts(n: int):
    return lambda _, attempts: len(attempts) >= n


def _has_failure_with_gap(_: Player, attempts: list[Attempt]) -> bool:
    return any((not a.all_passed) and a.primary_gap for a in attempts)


# ----- Event catalog -----

EVENTS: list[StoryEventDef] = [
    StoryEventDef(
        key="act1_day3_arjun_congrats",
        title="Arjun stops by",
        story_day=3,
        story_act=1,
        prereq_keys=("day1_arjun_intro",),
        condition=_has_passing_attempt,
        messages=[
            StoryMessage(
                character="arjun",
                expression="excited",
                body=(
                    "Yo {name} 🙌 first ticket landed and QA didn't even flinch — clean prompt, "
                    "clean code. Welcome to the productive zone, my friend!"
                ),
            ),
            StoryMessage(
                character="arjun",
                expression="happy",
                body=(
                    "Priya was right about you. Keep this up and you'll be reviewing my code "
                    "before the month's out 😅"
                ),
            ),
        ],
    ),
    StoryEventDef(
        key="act1_day5_ravi_nice_work",
        title="Ravi Sir drops a line",
        story_day=5,
        story_act=1,
        prereq_keys=("act1_day3_arjun_congrats",),
        condition=_has_n_attempts(3),
        messages=[
            StoryMessage(
                character="ravi",
                expression="proud",
                body=(
                    "{name}. Quick note — I've been watching your tickets come through. "
                    "The team has noticed."
                ),
            ),
            StoryMessage(
                character="ravi",
                expression="proud",
                body="Keep going.",
            ),
        ],
    ),
    StoryEventDef(
        key="act1_day10_zara_first_qa",
        title="Zara from QA",
        story_day=10,
        story_act=2,
        prereq_keys=("day1_arjun_intro",),
        condition=_has_failure_with_gap,
        messages=[
            StoryMessage(
                character="zara",
                expression="concerned",
                body=(
                    "Hey {name}. QA caught something on your last submission — pulled it before "
                    "it shipped, no harm done."
                ),
            ),
            StoryMessage(
                character="zara",
                expression="neutral",
                body=(
                    "Don't take it personal. We catch these so production doesn't. Priya will "
                    "walk you through what to tighten."
                ),
            ),
        ],
    ),
    StoryEventDef(
        key="act1_end_of_week",
        title="End of week one",
        story_day=7,
        story_act=1,
        prereq_keys=("act1_day3_arjun_congrats", "act1_day5_ravi_nice_work"),
        condition=_has_n_attempts(5),
        messages=[
            StoryMessage(
                character="priya",
                expression="happy",
                body=(
                    "{name} — you survived your first week 🎉 That's no small thing. Day 1 to "
                    "Day 7 is the hardest jump."
                ),
            ),
            StoryMessage(
                character="priya",
                expression="happy",
                body=(
                    "I'm proud of how you've been thinking through tasks before writing them up. "
                    "That's exactly the muscle this work needs."
                ),
            ),
            StoryMessage(
                character="priya",
                expression="happy",
                body="Take the weekend off. Real talk.",
            ),
        ],
    ),
]


# ----- Service functions -----

def _seen_keys(db: Session, player_id: int) -> set[str]:
    return {
        e.event_key
        for e in db.query(PlayerStoryEvent)
        .filter(PlayerStoryEvent.player_id == player_id)
        .all()
    }


def get_pending_events(db: Session, player: Player) -> list[StoryEvent]:
    """Return events the player hasn't seen yet whose prereqs + condition are met.

    The order matches EVENTS, so the frontend renders Day 3 before Day 5 before
    end-of-week, etc.
    """
    seen = _seen_keys(db, player.id)
    attempts = (
        db.query(Attempt)
        .filter(Attempt.player_id == player.id)
        .order_by(Attempt.id.asc())
        .all()
    )
    out: list[StoryEvent] = []
    for ev in EVENTS:
        if ev.key in seen:
            continue
        if not all(k in seen for k in ev.prereq_keys):
            continue
        if not ev.condition(player, attempts):
            continue
        out.append(ev.to_event(player))
    return out


def _event_def(key: str) -> Optional[StoryEventDef]:
    for ev in EVENTS:
        if ev.key == key:
            return ev
    return None


def advance(
    db: Session,
    player: Player,
    event_key: str,
    skipped: bool = False,
) -> tuple[int, int, int]:
    """Mark an event seen and (unless skipped) grant its XP + bump story_day/act.

    Returns (xp_awarded, story_day, story_act).
    """
    ev_def = _event_def(event_key)
    if ev_def is None:
        # Unknown event — still record so it doesn't loop. No XP, no story bump.
        if event_key not in _seen_keys(db, player.id):
            db.add(PlayerStoryEvent(player_id=player.id, event_key=event_key))
            db.commit()
        return (0, player.story_day or 1, player.story_act or 1)

    seen = _seen_keys(db, player.id)
    is_new = event_key not in seen
    if is_new:
        db.add(PlayerStoryEvent(player_id=player.id, event_key=event_key))

    # Only grant XP / advance story on the FIRST seen. Re-calling advance is
    # idempotent — no double XP, no day/act regression.
    xp = 0
    if is_new and not skipped:
        xp = ev_def.xp_bonus
        player.total_xp = (player.total_xp or 0) + xp

    if is_new:
        if ev_def.story_day and ev_def.story_day > (player.story_day or 1):
            player.story_day = ev_def.story_day
        if ev_def.story_act and ev_def.story_act > (player.story_act or 1):
            player.story_act = ev_def.story_act

    db.commit()
    db.refresh(player)
    return (xp, player.story_day or 1, player.story_act or 1)


__all__ = [
    "EVENTS",
    "StoryEventDef",
    "get_pending_events",
    "advance",
]
