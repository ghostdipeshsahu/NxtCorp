"""Agent eval sets — automated criteria checks + retry loops.

Each agent (Zara, Priya, Client Task Agent) has its own eval module that
codifies the self-evaluation block from its system prompt as an external,
testable harness. The agent must improve its output until every criterion
passes OR the retry cap is hit (hard ceiling to prevent infinite loops).

Usage from runtime (optional integration):
    from backend.evals.zara_eval import ZaraEvalRunner
    runner = ZaraEvalRunner()
    final = runner.run(question, student_prompt, exercise_type, generated_code)
    # final is an AssessmentResult that has either passed all criteria or
    # been returned after MAX_RETRIES with telemetry on which checks failed.

Usage from CLI:
    python -m backend.evals.zara_eval --question p001_bonus_calculator \\
        --prompt "calculate 10% bonus" --exercise-type 1
"""

from .zara_eval import ZaraEvalRunner, ZaraCriterion, ZaraEvalReport  # noqa: F401
from .priya_eval import PriyaEvalRunner, PriyaCriterion, PriyaEvalReport  # noqa: F401
