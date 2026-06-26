"""
Coach Agent (step 5).

The brain of Priya's responses. Takes the student's attempt, the Assessor's
findings, and the conversation so far; produces ONE in-character message
from Priya at the right Socratic escalation level.

Critical rules this module enforces (spec §6, §14):

1. Priya NEVER gives the answer. The only exception is Level 4, which only
   fires after 3 failed attempts on the same task.
2. Coach writes IN CHARACTER as Priya — warm, direct, Indian workplace
   professional. Not generic AI feedback.
3. Students never see: the assessor's primary_gap key, the gap description
   text from the taxonomy, the reference prompt, or hidden tests. Coach
   uses these as private context only.
4. The escalation level is computed deterministically here — the LLM is
   given the level and the rubric for that specific level, so the depth of
   the question is enforced by structure, not by hoping the model picks the
   right depth on its own.

Escalation ladder (spec §6):
  L1 — Conceptual nudge ("are there inputs your prompt didn't account for?")
  L2 — Specific direction ("think about edge cases at the extremes")
  L3 — Direct hint with a specific failing input ("run with 'leetcode' — what does it return?")
  L4 — Reveal the gap, then ask why it matters

Expression is chosen deterministically based on outcome + attempt number.
The LLM only writes the body.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Optional

from backend.agents.assessor import AssessmentResult
from backend.core.code_executor import ExecutionResult
from backend.core.llm import LLMError, chat as llm_chat, extract_json


# ---------- Escalation ladder (v3 hybrid — option C) ----------
#
# Arjun fires AT MOST ONCE per task. Once he's fired, Priya's internal level
# resets to L1 with the hint as new context — the student gets a fresh
# Socratic ladder to climb. L4 reveal terminates the task with reduced XP
# (see run_pipeline.maybe_award_with_l4).
#
# Pre-Arjun (arjun_fired == False):
#   attempt 1 -> priya L1
#   attempt 2 -> priya L2
#   attempt 3 -> ARJUN (auto-triggered, once)
#
# Post-Arjun (arjun_fired == True):
#   attempt 4 -> priya L1   (reset; Priya knows hint context)
#   attempt 5 -> priya L2
#   attempt 6 -> priya L3
#   attempt 7+ -> priya L4 (reveal — terminates with reduced XP)
#
# If for some reason Arjun didn't fire (e.g. legacy attempts), the
# fallback is the original linear ladder past attempt 3.

def compute_step(
    all_passed: bool,
    attempt_number: int,
    arjun_fired: bool = False,
) -> tuple[str, int]:
    """Returns (who, level).

    who ∈ {'celebrate', 'priya', 'arjun'}
    level: for priya this is 1..4; for celebrate/arjun it is 0.
    """
    if all_passed:
        return ("celebrate", 0)
    if attempt_number <= 1:
        return ("priya", 1)
    if attempt_number == 2:
        return ("priya", 2)
    if attempt_number == 3:
        # Arjun fires once per task. If he was already fired earlier (very
        # unusual at attempt 3), continue the post-arjun ladder instead.
        if not arjun_fired:
            return ("arjun", 0)
        return ("priya", 1)
    # attempt_number >= 4
    if arjun_fired:
        post = attempt_number - 3   # 4->1, 5->2, 6->3, 7+->4
        if post <= 1:
            return ("priya", 1)
        if post == 2:
            return ("priya", 2)
        if post == 3:
            return ("priya", 3)
        return ("priya", 4)
    # Arjun never fired (legacy/edge case). Continue original linear ladder.
    if attempt_number == 4:
        return ("priya", 3)
    return ("priya", 4)


def compute_escalation_level(
    all_passed: bool,
    attempt_number: int,
    arjun_fired: bool = False,
) -> int:
    """Back-compat shim. Returns the Priya-level int for callers that don't
    yet know about Arjun. Arjun turns surface as level 0 (treated like a
    pause in the ladder).
    """
    who, level = compute_step(all_passed, attempt_number, arjun_fired)
    return level


def compute_expression(all_passed: bool, attempt_number: int) -> str:
    """Map outcome to Priya's expression (spec §13)."""
    if all_passed:
        return "excited" if attempt_number == 1 else "happy"
    return "concerned"


# ---------- Prompt construction ----------

PRIYA_IDENTITY = """You are Priya Sharma, Senior Developer and Manager at NxtCorp Hyderabad.

You are warm, direct, and have high standards. You celebrate genuine wins. You give Socratic feedback after failure. You NEVER give the answer.

You receive:
- zara_findings: Zara's full assessment
- attempt_history: all previous attempts on this task with their scores
- ladder_level: current level (L1, L2, L3, L4)
- student_name: to address personally

Your job:

Read Zara's findings carefully. Read the attempt history. Decide what ONE question to ask.

Decision making:
- If student is making progress (score improving each attempt):
  Stay at current ladder level. Ask a question that builds on what they got right.
- If student is stuck (same score two attempts in a row):
  Escalate to next ladder level. Be more specific.
- If student seems to misunderstand the concept entirely:
  Go back to basics before pointing to the specific gap.

Tone rules:
- Always address student by name
- Warm even when correcting
- Never say "that is wrong"
- Celebrate when student gets it
- Reference the meeting naturally when relevant — not formulaically
- Sound like a real manager — not a generic AI assistant

You write IN CHARACTER as Priya. Reason fresh every time. Never use a template.
"""

# Per-exercise framing. The student doesn't write code; what they submit
# differs by type. Coach must reason about THEIR submission, not invent
# code they didn't write. This block is injected into the system prompt
# whenever an exercise_type is known.
EXERCISE_TYPE_FRAMING = {
    1: """EXERCISE TYPE 1 — PROMPT AI TO BUILD. The student wrote a natural-language prompt instructing the AI to build a function from scratch. Your Socratic question must target what they told (or failed to tell) the AI to do — not what their code does. They didn't write code.""",
    2: """EXERCISE TYPE 2 — DECOMPOSE. The student broke a task into an ordered list of sub-tasks for the AI to execute. Their submission is the list of sub-tasks. Your Socratic question must target a missing or out-of-order step in their decomposition — not a prompt they didn't write.""",
    3: """EXERCISE TYPE 3 — PREDICT AI FAILURE. The student was shown a deliberately-flawed prompt and asked to predict which inputs would break the code the AI generates. Their submission is a list of the gaps they spotted. Your Socratic question must target a category of gap they missed — frame it as 'what kind of input might still slip through?'""",
    4: """EXERCISE TYPE 4 — VERIFY. The student was shown working-looking code and asked to write test cases that would expose any hidden bugs. Their submission is a list of (input, expected) test cases. Your Socratic question must target a dimension of the code's behavior their tests didn't probe — 'what kind of case is your test set silent on?'""",
    5: """EXERCISE TYPE 5 — IMPROVE AFTER FAILURE. The student was shown a failing prompt + the failures it produced, and asked to tighten the prompt so the next attempt passes. Your Socratic question must target what's still vague in their revised prompt, or a failure mode their tightening doesn't cover yet.""",
}


def _framing_for(exercise_type: Optional[int]) -> str:
    if exercise_type is None:
        return ""
    return EXERCISE_TYPE_FRAMING.get(int(exercise_type), "")


SOCRATIC_RULES = """SOCRATIC RULES (these are absolute — breaking them defeats the entire pedagogy)

1. You NEVER state the answer. Not the missing rule, not the missing case, not the fix. Not even hinted-but-obvious. Only Level 4 (final escalation, after 3 failed attempts) reveals the gap.
2. You NEVER quote or reference the internal gap name, the reference prompt, the gap taxonomy, or hidden tests. The student should never even know these exist.
3. Your response should end with a QUESTION the student can think about. Not a statement of fact, not a checklist, not instructions.
4. Length: one short paragraph. Two sentences if you can manage. Three at the absolute maximum. Long replies kill the rhythm.
5. No bullet lists. No headers. Plain prose, like you're typing it into Slack.
6. Do NOT restate what the test results showed (the student can see those). Skip the recap and go straight to the question.
7. AI-SUPERVISION FRAMING. The student's job is to TELL THE AI what to build, not write code themselves. Frame your question about what they told the AI — not about their code.
   Wrong: "Your code doesn't handle empty strings."
   Right: "Think about what you told the AI to do when it receives something unexpected. Did your prompt cover that situation?"
"""

_LEVEL_RUBRICS = {
    1: """LEVEL 1 — Conceptual nudge. Point toward the general AREA of the gap. Do not name the specific rule or value. You may reference the meeting in a general way.

Example: "Think about what was said about limits in the meeting — is there anything your prompt does not account for?" """,

    2: """LEVEL 2 — Specific direction. Point more precisely. NAME THE CHARACTER who mentioned the relevant constraint in the meeting if it helps (e.g. "what Sneha said", "what Rahul mentioned"). Still do not state the rule or value.

Example: "Think about what Sneha said specifically. She mentioned something about a maximum — does your prompt say what to do when that maximum is reached?" """,

    3: """LEVEL 3 — Direct hint. Give a CONCRETE pointer without the answer. You may quote a specific failing input or numeric value the student already saw.

Example: "Your prompt says the bonus cannot exceed Rs 50,000. But what does the function actually return when the calculated bonus is Rs 60,000? Did you specify that?" """,

    4: """LEVEL 4 — Reveal. After 3 failed attempts. State exactly what was missing in plain English, then ask the student to explain WHY it matters in their own words.

Example: "Let me show you what was missing: when bonus exceeds Rs 50,000 the function needs to return exactly 50000. Now — why is that important? Can you explain it in your own words?" """,
}

def _rubric_for(level: int) -> str:
    return _LEVEL_RUBRICS.get(level, _LEVEL_RUBRICS[1])

OUTPUT_RULES = """OUTPUT FORMAT

Return JSON only, no markdown fences:

{
  "body": "<Priya's message — one short paragraph, ends with a question (except possibly L4 where the question is at the end of the second sentence)>"
}

The body field is the entire message. Do not include the student's name as a salutation header. Address them naturally in the prose if you want to.
"""

CELEBRATION_BLOCK = """CELEBRATION MODE — the student passed every hidden test on this attempt.

Write a short, genuine, in-character congratulations. If this was their FIRST attempt at this task, be visibly impressed (this is rare — most students need iterations). If it took a few attempts, celebrate the breakthrough.

Rules:
- One short paragraph. Two sentences max.
- One emoji is fine (🎯, 🙌, 🚀). Don't overdo.
- Optionally end with a forward-looking nudge: "Ready for the next one?" — but don't force it.
- Do NOT lecture them on what they did right. They know. Just acknowledge it warmly.
"""


_extract_json = extract_json


_BODY_KEY_RE = re.compile(
    r'"(?:body|message|response|reply|content|text)"\s*:\s*"((?:[^"\\]|\\.)*)',
    re.IGNORECASE | re.DOTALL,
)


def _strip_json_artifacts(text: str) -> str:
    """Last-resort cleanup when the response is JSON-shaped but unparseable
    (most commonly because the model output was truncated mid-string).

    Strips leading `{"key":` framing, trailing `"}` framing, JSON-escape
    sequences (\\n, \\", \\\\), and the noisy delimiter chars (|, *) that
    some free models prepend to string values.
    """
    s = text.strip()
    # Pull the value of a known key if one is partially present.
    m = _BODY_KEY_RE.search(s)
    if m:
        s = m.group(1)
    # Replace common JSON escapes with their literal characters.
    s = (
        s.replace('\\n', '\n')
         .replace('\\t', '\t')
         .replace('\\"', '"')
         .replace("\\'", "'")
         .replace('\\\\', '\\')
    )
    # Drop dangling JSON framing left at the ends.
    s = s.strip().lstrip('{').rstrip('}').strip()
    s = s.strip('"').strip("'").strip()
    # A few free models prepend |*, ||, *- as a marker — strip leading
    # punctuation that wouldn't start a real coach line.
    s = re.sub(r'^[|*`>\s]+', '', s)
    return s.strip()


def _extract_coach_body(raw: str) -> str:
    """Pull the actual coach message out of a model response.

    Models vary in how strictly they obey the JSON-only contract. We try,
    in order:
      1. JSON parse → take `body` (the documented key)
      2. JSON parse → fall back to other common keys (message, response,
         reply, content, text) that lower-tier models sometimes use
      3. Regex-extract the value of a body-ish key when the JSON itself
         is truncated/malformed (common when max_tokens cuts mid-string)
      4. Markdown-fence strip if the model returned fenced prose
      5. Raw text otherwise

    Never silently swallows an empty response — the caller decides what
    to do with `""`.
    """
    raw = (raw or "").strip()
    if not raw:
        return ""
    try:
        parsed = _extract_json(raw)
    except ValueError:
        parsed = None

    if isinstance(parsed, dict):
        for key in ("body", "message", "response", "reply", "content", "text"):
            v = parsed.get(key)
            if isinstance(v, str) and v.strip():
                # Some free models prepend artifacts like "|*", "||", "*-"
                # to the string value. Strip leading non-letter noise so the
                # coffee corner / chat UI shows clean prose.
                cleaned = re.sub(r'^[|*`>\s]+', '', v.strip())
                return cleaned.strip() or v.strip()

    # JSON-shaped but unparseable / no known key → regex pull + cleanup.
    if raw.lstrip().startswith("{") or '"body"' in raw or '"message"' in raw:
        cleaned = _strip_json_artifacts(raw)
        if cleaned:
            return cleaned

    # Fenced prose → strip the fence.
    m = re.search(r"```(?:json|markdown)?\s*\n?(.*?)```", raw, re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    return raw.strip()


# ---------- Public API ----------

@dataclass
class CoachReply:
    body: str
    expression: str         # "happy" | "excited" | "concerned" | "thinking" | "neutral"
    escalation_level: int   # 0 = celebration; 1..4 = Socratic ladder
    raw_response: str
    input_tokens: int
    output_tokens: int


def _gap_description_for(question: dict[str, Any], gap_key: Optional[str]) -> Optional[str]:
    if not gap_key:
        return None
    for g in (question.get("gap_taxonomy") or []):
        if g.get("key") == gap_key:
            return g.get("description")
    return None


def _failing_inputs(execution: ExecutionResult, limit: int = 6) -> list[Any]:
    if execution.setup_error or execution.timed_out:
        return []
    return [o.input for o in execution.outcomes if not o.passed][:limit]


def build_system_prompt(level: int, exercise_type: Optional[int] = None) -> str:
    """Compose the right system prompt for the given escalation level.

    Per-level focused — only the relevant level's rubric is sent. This keeps
    the prompt small enough to fit tight token budgets and reduces the
    chance the model accidentally cribs from a different level's style.
    """
    framing = _framing_for(exercise_type)
    if level == 0:
        parts = [PRIYA_IDENTITY, CELEBRATION_BLOCK, OUTPUT_RULES]
    else:
        parts = [PRIYA_IDENTITY, SOCRATIC_RULES, _rubric_for(level), OUTPUT_RULES]
    if framing:
        # Insert exercise framing right after identity so it shapes the Socratic question.
        parts.insert(1, framing)
    return "\n\n".join(parts)


_SUBMISSION_LABELS = {
    1: "STUDENT'S PROMPT (this attempt) — natural-language instruction to the AI",
    2: "STUDENT'S DECOMPOSITION (this attempt) — sub-tasks they listed",
    3: "STUDENT'S IDENTIFIED GAPS (this attempt) — what they spotted in the flawed prompt",
    4: "STUDENT'S TEST CASES (this attempt) — the (input, expected) cases they wrote",
    5: "STUDENT'S REVISED PROMPT (this attempt) — their tightened prompt after the failure",
}


def build_user_message(
    *,
    student_display_name: str,
    question: dict[str, Any],
    student_prompt: str,
    execution: ExecutionResult,
    assessment: AssessmentResult,
    attempt_number: int,
    level: int,
    conversation_history: Optional[list[dict[str, str]]],
    exercise_type: Optional[int] = None,
    attempt_history: Optional[list[dict[str, Any]]] = None,
) -> str:
    parts: list[str] = []
    parts.append(f"STUDENT NAME: {student_display_name}")
    parts.append(f"TASK: {question.get('title', '(untitled)')}")
    if exercise_type is not None:
        parts.append(f"EXERCISE TYPE: {exercise_type}")
    parts.append(f"ATTEMPT NUMBER: {attempt_number}")
    parts.append(f"ASSIGNED ESCALATION LEVEL: {level}")
    parts.append("")

    label = _SUBMISSION_LABELS.get(int(exercise_type)) if exercise_type else "STUDENT'S PROMPT (this attempt)"
    parts.append(f"{label}:")
    parts.append(student_prompt.strip())
    parts.append("")

    # v4: include the MEETING_SCRIPT so Priya can reference what specific
    # team members said. She should weave the briefing in naturally, not
    # paste it back at the student.
    script = question.get("meeting_script") or []
    if script:
        parts.append("MEETING_SCRIPT (what was actually said in the briefing — reference characters by name when natural):")
        for entry in script[:12]:
            if not isinstance(entry, dict):
                continue
            who = entry.get("name") or entry.get("character") or "?"
            role = entry.get("role") or ""
            msg = (entry.get("message") or "").strip()
            head = f"{who} ({role})" if role else who
            parts.append(f"  [{head}]: {msg}")
        parts.append("")

    # v6: ATTEMPT_HISTORY — feeds Priya's decision-making rule (progress /
    # stuck / misunderstand). One line per prior attempt with the three
    # scores. Most recent last.
    if attempt_history:
        parts.append("ATTEMPT_HISTORY (most recent last):")
        for h in attempt_history[-5:]:
            parts.append(
                f"  attempt {h.get('attempt_number','?')}: "
                f"requirement={h.get('requirement_quality',0):.1f} "
                f"output={h.get('output_quality',0):.1f} "
                f"overall={h.get('overall_score',0):.1f}"
            )
        parts.append("")

    if level == 0:
        parts.append(f"OUTCOME: All {execution.num_total} tests passed.")
    else:
        parts.append(
            f"OUTCOME: {execution.num_passed}/{execution.num_total} passed."
        )
        fi = _failing_inputs(execution)
        if fi:
            parts.append(f"FAILING INPUTS (for L3 you may quote ONE of these literally): {fi!r}")
        parts.append("")
        # v4 ZARA_FINDINGS — replaces the older PRIVATE CONTEXT block.
        # Priya gets the full assessment: gaps_missing, primary_gap, zara_note.
        parts.append("ZARA_FINDINGS (internal — never quote Zara directly to the student):")
        gaps_missing = getattr(assessment, "gaps_missing", None) or []
        gaps_covered = getattr(assessment, "gaps_covered", None) or []
        if gaps_covered:
            parts.append(f"  gaps_covered: {gaps_covered}")
        if gaps_missing:
            parts.append(f"  gaps_missing: {gaps_missing}")
        if assessment.primary_gap:
            parts.append(f"  primary_gap: {assessment.primary_gap}")
            desc = _gap_description_for(question, assessment.primary_gap)
            if desc:
                parts.append(f"  primary_gap description (internal): {desc}")
        parts.append(f"  zara_note: {assessment.zara_note}")
        parts.append("")
        parts.append(f"WRITE A LEVEL {level} MESSAGE.")
        parts.append("Follow the rubric for that level exactly. Do not borrow language from a different level.")
        if level == 3 and _failing_inputs(execution):
            parts.append("You MUST quote one failing input literally inside the message.")
        if level == 4 and assessment.primary_gap:
            parts.append("You MUST name the missing rule plainly. Then ask one 'why does this matter' question.")

    if conversation_history:
        parts.append("")
        parts.append("RECENT CONVERSATION (most recent last) — keep your tone continuous:")
        # Keep just the most recent turn for tone continuity. Long histories
        # blow input budget on every call.
        for m in conversation_history[-2:]:
            who = m.get("character", "?")
            body = (m.get("body") or "").strip()
            parts.append(f"  [{who}]: {body}")

    parts.append("")
    parts.append("Return JSON only.")
    return "\n".join(parts)


def coach(
    *,
    student_display_name: str,
    question: dict[str, Any],
    student_prompt: str,
    execution: ExecutionResult,
    assessment: AssessmentResult,
    attempt_number: int,
    conversation_history: Optional[list[dict[str, str]]] = None,
    exercise_type: Optional[int] = None,
    arjun_fired: bool = False,
    attempt_history: Optional[list[dict[str, Any]]] = None,
    all_passed_override: Optional[bool] = None,
    max_tokens: int = 220,
) -> CoachReply:
    """Generate Priya's reply for one student attempt.

    v6: pass `all_passed_override` so the caller (run_pipeline) can supply
    the Zara-driven pass state. Without an override we fall back to the
    raw execution result, which is sample-test-only — not authoritative
    after the v6 scoring switch.
    """
    if all_passed_override is not None:
        all_passed = all_passed_override
    else:
        all_passed = execution.all_passed
    level = compute_escalation_level(all_passed, attempt_number, arjun_fired)
    expression = compute_expression(all_passed, attempt_number)

    if exercise_type is None:
        exercise_type = question.get("exercise_type")

    system_prompt = build_system_prompt(level, exercise_type=exercise_type)
    user_text = build_user_message(
        student_display_name=student_display_name,
        question=question,
        student_prompt=student_prompt,
        execution=execution,
        assessment=assessment,
        attempt_number=attempt_number,
        level=level,
        conversation_history=conversation_history,
        exercise_type=exercise_type,
        attempt_history=attempt_history,
    )

    result = llm_chat(
        system=system_prompt,
        user=user_text,
        max_tokens=max_tokens,
        temperature=0.5,
        response_format_json=True,
    )
    raw = result.text or ""
    body = _extract_coach_body(raw)
    if not body:
        # No silent placeholder. Surface the failure so the chat panel's
        # error path renders a real Zara-style notice instead of a fake
        # Priya line that pretends coaching happened.
        raise LLMError(
            f"Coach Agent (Priya) returned no usable content. raw={raw[:300]!r}"
        )

    return CoachReply(
        body=body,
        expression=expression,
        escalation_level=level,
        raw_response=raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


FOLLOWUP_SYSTEM = """You are Priya Sharma replying to a student message in chat. You already asked a Socratic question on their last attempt. The student is now responding — either with an idea, a question, or a guess about what they might be missing.

Your job: stay in character, stay Socratic. One short paragraph.

- If the student articulated the gap correctly: celebrate briefly ("Yes! That's exactly it 🎯") and ask them to think about a follow-up — for example, what tests they'd add now, or what their fix would look like. ONE sentence of celebration, ONE question.
- If the student is close but not quite there: acknowledge what's right ("Good direction — you're seeing X..."), then ask one more focused question. Don't reveal the answer.
- If the student is off-track: gently redirect with another question. Do not state the missing rule. Do not escalate to a deeper hint than the last Priya message in the conversation. Match the depth of the most recent Priya message.
- If the student is stuck or asking you for the answer: stay warm, push back gently ("I'd rather you figure this one out — try walking through input X mentally"). Still no reveal.

Length: two sentences absolute max. End with a question (except the celebration case, where ending with a forward-looking nudge is fine).

Return JSON only:
{ "body": "<your message>" }
"""


def coach_followup(
    *,
    student_display_name: str,
    student_text: str,
    question: dict[str, Any],
    conversation_history: list[dict[str, str]],
    primary_gap: Optional[str] = None,
    max_tokens: int = 200,
) -> CoachReply:
    """Generate a Priya reply to a student conversational message (not a new attempt)."""
    parts = [
        f"STUDENT NAME: {student_display_name}",
        f"TASK: {question.get('title', '(untitled)')}",
        "",
        "STUDENT JUST SAID:",
        student_text.strip(),
        "",
    ]
    if primary_gap:
        desc = _gap_description_for(question, primary_gap)
        parts.append("PRIVATE CONTEXT (DO NOT REVEAL):")
        parts.append(f"  internal gap key: {primary_gap}")
        if desc:
            parts.append(f"  gap description: {desc}")
        parts.append("")
    if conversation_history:
        parts.append("RECENT CONVERSATION (most recent last):")
        for m in conversation_history[-3:]:
            who = m.get("character", "?")
            body = (m.get("body") or "").strip()
            parts.append(f"  [{who}]: {body}")
        parts.append("")
    parts.append("Return JSON only.")
    user_text = "\n".join(parts)

    result = llm_chat(
        system="\n\n".join([PRIYA_IDENTITY, FOLLOWUP_SYSTEM]),
        user=user_text,
        max_tokens=max_tokens,
        temperature=0.5,
        response_format_json=True,
    )
    raw = result.text
    try:
        parsed = _extract_json(raw)
        body = str(parsed.get("body") or "").strip()
    except ValueError:
        body = raw.strip()
    if not body:
        body = "Hmm — give me a second on that one."

    return CoachReply(
        body=body,
        expression="neutral",
        escalation_level=0,  # respond is not an attempt; no level applies
        raw_response=raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


ARJUN_HINT_SYSTEM = """You are Arjun Mehta — a friendly senior developer at NxtCorp, whispering a hint to a junior in the pantry by the coffee machine. You stand in for Priya here: this is the off-the-record version of what she'd ask.

VOICE
- Casual, conspiratorial. Lean in. Speak in 2-3 sentences max.
- Indian workplace English, slightly playful. Acceptable: "yaar", "between us", "off the record", "okay so listen", "🤫".
- One emoji max.

ABSOLUTE RULES
- You NEVER state the answer. Not the rule, not the case, not the fix. Hint at a CATEGORY or DIMENSION only ("think about empty inputs", "what about negatives?", "check the output shape").
- You NEVER name internal jargon: no taxonomy, no gap_taxonomy, no reference_prompt, no hidden_test.
- Start lines like "Hey, between us…" or "Off the record…" or "Okay so listen, yaar…"

OUTPUT
Return JSON only:
{ "body": "<2-3 sentence whispered hint>" }
"""


def coach_hint_arjun(
    *,
    student_display_name: str,
    question: dict[str, Any],
    primary_gap: Optional[str],
    last_attempt_prompt: Optional[str] = None,
    max_tokens: int = 220,
) -> CoachReply:
    """Generate Arjun's coffee-machine hint. Same Socratic restraint as Priya;
    casual conspiratorial voice. Backend already charged the player; this
    function just produces the message.
    """
    parts = [
        f"STUDENT NAME: {student_display_name}",
        f"TASK: {question.get('title', '(untitled)')}",
        "",
    ]
    if primary_gap:
        desc = _gap_description_for(question, primary_gap)
        parts.append("PRIVATE CONTEXT (DO NOT REVEAL):")
        parts.append(f"  internal gap key: {primary_gap}")
        if desc:
            parts.append(f"  gap description: {desc}")
        parts.append("")
    elif question.get("gap_taxonomy"):
        # No primary_gap yet (player hasn't attempted) — pick the first gap
        # as a starting nudge category.
        g0 = question["gap_taxonomy"][0]
        parts.append("PRIVATE CONTEXT (DO NOT REVEAL):")
        parts.append(f"  most likely gap to nudge: {g0['key']}")
        if g0.get("description"):
            parts.append(f"  description: {g0['description']}")
        parts.append("")
    if last_attempt_prompt:
        parts.append("STUDENT'S LAST PROMPT (so you can target your hint):")
        parts.append(last_attempt_prompt.strip()[:600])
        parts.append("")
    parts.append("Whisper one hint. Return JSON only.")

    result = llm_chat(
        system=ARJUN_HINT_SYSTEM,
        user="\n".join(parts),
        max_tokens=max_tokens,
        temperature=0.6,
        response_format_json=True,
    )
    raw = result.text or ""
    # BUG 2 fix: route Arjun's reply through the same JSON-resilient
    # extractor as Priya's so the coffee corner UI never receives a raw
    # `{"body": "..."}` string — even when the response is truncated.
    body = _extract_coach_body(raw)
    if not body:
        body = "Hey, between us — think about the edge cases you didn't write a rule for. 🤫"

    return CoachReply(
        body=body,
        expression="happy",
        escalation_level=0,
        raw_response=raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


# ---------- Arjun multi-turn coffee corner (v3 conversation flow) ----------
#
# All Arjun voices are INTERNAL functions of the Priya Coach Agent — Arjun
# is a casual voice register, not a separate agent. The coffee corner is
# a 3-step conversation:
#
#   Round 0 — static opener: "Hey {name}! Rough one? Come, take a break."
#             (no LLM call — fixed copy)
#   Round 1 — casual reaction to student's first option pick. NO HINT yet.
#             LLM-generated, Arjun's voice, ends with another casual question.
#   Round 2 — directional hint informed by Zara's primary_gap (without
#             ever naming the gap key). NOT Socratic — Arjun TELLS them
#             what to look at. Followed by static closing line.
#
# The student picks from fixed option strings (verbatim per spec). Backend
# is stateless across turns — it computes a reply from (round, choice,
# task, primary_gap) on each /api/coffee/turn call.

ROUND_1_OPTIONS = (
    "Yeah, this one is tricky",
    "I don't even know where to start",
    "I think I'm close but something's off",
)

ROUND_2_OPTIONS = (
    "I think I'm missing something in the rules",
    "I'm not sure what cases to handle",
    "The output doesn't seem right",
)

ARJUN_GREETING_TEMPLATE = "Hey {name}! Rough one? Come, take a break."
ARJUN_CLOSING_LINE = "Anyway — go crack it. You've got this."


ARJUN_CASUAL_SYSTEM = """You are Arjun Mehta — a friendly senior developer at NxtCorp, chatting with a junior dev who's stuck on a task. You're standing in the coffee corner, mug in hand. This is SMALL TALK, not coaching — you do NOT give a hint yet.

VOICE
- Casual Indian workplace English. Warm, slightly playful. Acceptable: "yaar", "ha", "okay so listen", "between us", "🙂", "😅".
- 2 sentences max. One emoji max.
- Empathetic — acknowledge what they said before steering the conversation.

ABSOLUTE RULES
- Do NOT give a hint. Do NOT mention edge cases, rules, output shapes, or anything tactical.
- Do NOT name internal jargon (Zara, gap, taxonomy, reference prompt, hidden test).
- End with a friendly question or invitation that nudges them toward describing what's hard — but keep it open.

OUTPUT
Return JSON only:
{ "body": "<your reply, max 2 sentences>" }
"""


def coach_arjun_greeting(student_display_name: str) -> CoachReply:
    """Round 0 — fixed opener. No LLM call. The script verbatim from spec
    so the experience is consistent across sessions.
    """
    body = ARJUN_GREETING_TEMPLATE.format(name=student_display_name)
    return CoachReply(
        body=body,
        expression="happy",
        escalation_level=0,
        raw_response="",
        input_tokens=0,
        output_tokens=0,
    )


def coach_arjun_round1_reply(
    *,
    student_display_name: str,
    question: dict[str, Any],
    student_choice: str,
    max_tokens: int = 140,
) -> CoachReply:
    """Round 1 — casual reaction to the student's first option pick. No
    hint. Stays small-talk. Ends with a question to draw them out.
    """
    parts = [
        f"STUDENT NAME: {student_display_name}",
        f"TASK: {question.get('title', '(untitled)')}",
        "",
        "STUDENT JUST PICKED THIS OPTION:",
        student_choice.strip(),
        "",
        "Reply casually — NO HINT, just colleague chit-chat. Two sentences max.",
        "End with a friendly open question that invites them to describe what's hard.",
        "Return JSON only.",
    ]

    result = llm_chat(
        system=ARJUN_CASUAL_SYSTEM,
        user="\n".join(parts),
        max_tokens=max_tokens,
        temperature=0.6,
        response_format_json=True,
    )
    raw = result.text or ""
    body = _extract_coach_body(raw)
    if not body:
        body = "Ha, I know that feeling. What part is getting you?"

    return CoachReply(
        body=body,
        expression="happy",
        escalation_level=0,
        raw_response=raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


ARJUN_DIRECTIONAL_HINT_SYSTEM = """You are Arjun Mehta — friendly senior dev at NxtCorp, finally giving a junior a real directional pointer at the coffee machine. This is NOT a Socratic question — Arjun TELLS them WHERE to look, plainly, in his own voice.

VOICE
- Casual, conspiratorial. "Between us…", "okay so listen…", "yaar…". One emoji max.
- 2-3 sentences. End on a confident note.

RULES
- POINT to a category or dimension the student should look at — driven by the private context below. e.g. "check the boundaries first — zero, max values, empty inputs."
- NEVER state the exact rule, fix, or answer. Direction only.
- NEVER name internal jargon (Zara, gap key, taxonomy, reference prompt, hidden test).

OUTPUT
Return JSON only:
{ "body": "<your directional hint, 2-3 sentences>" }
"""


def coach_arjun_hint(
    *,
    student_display_name: str,
    question: dict[str, Any],
    primary_gap: Optional[str],
    student_choice: str,
    max_tokens: int = 200,
) -> CoachReply:
    """Round 2 — directional hint shaped by primary_gap + the student's
    second option pick. Not Socratic. Followed (in the route) by the
    static closing encouragement.
    """
    parts = [
        f"STUDENT NAME: {student_display_name}",
        f"TASK: {question.get('title', '(untitled)')}",
        "",
        "STUDENT JUST PICKED THIS OPTION:",
        student_choice.strip(),
        "",
    ]
    if primary_gap:
        desc = _gap_description_for(question, primary_gap)
        parts.append("PRIVATE CONTEXT (DO NOT REVEAL):")
        parts.append(f"  internal gap key: {primary_gap}")
        if desc:
            parts.append(f"  gap description: {desc}")
        parts.append("")
    elif question.get("gap_taxonomy"):
        g0 = question["gap_taxonomy"][0]
        parts.append("PRIVATE CONTEXT (DO NOT REVEAL):")
        parts.append(f"  most likely gap to nudge: {g0.get('key', '')}")
        if g0.get("description"):
            parts.append(f"  description: {g0['description']}")
        parts.append("")
    parts.append("Give a directional hint. NOT a question — tell them where to look.")
    parts.append("Return JSON only.")

    result = llm_chat(
        system=ARJUN_DIRECTIONAL_HINT_SYSTEM,
        user="\n".join(parts),
        max_tokens=max_tokens,
        temperature=0.55,
        response_format_json=True,
    )
    raw = result.text or ""
    body = _extract_coach_body(raw)
    if not body:
        body = "Between us — whenever I'm stuck I check the boundaries first. Zero, max values, empty inputs. Usually that's where the gap hides."

    return CoachReply(
        body=body,
        expression="happy",
        escalation_level=0,
        raw_response=raw,
        input_tokens=result.input_tokens,
        output_tokens=result.output_tokens,
    )


__all__ = [
    "coach",
    "coach_followup",
    "coach_hint_arjun",
    "coach_arjun_greeting",
    "coach_arjun_round1_reply",
    "coach_arjun_hint",
    "ROUND_1_OPTIONS",
    "ROUND_2_OPTIONS",
    "ARJUN_CLOSING_LINE",
    "CoachReply",
    "compute_escalation_level",
    "compute_expression",
]
