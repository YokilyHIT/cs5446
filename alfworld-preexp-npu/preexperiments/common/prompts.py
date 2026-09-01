"""
Every fixed prompt template used across experiment A and B, copied verbatim
from the pre-experiment spec (两个方向_预实验设计_ClaudeCode可复现版.md) so that
wording changes only ever happen in one place and every script cites the same
text. Do not paraphrase these when calling the LLM -- the spec treats exact
wording as part of the fixed protocol.
"""

# ---------------------------------------------------------------------------
# Section 5.1: base ReAct action-selection prompt (shared by no-memory,
# with-lesson, and foresight-conditioned planners).
# ---------------------------------------------------------------------------
REACT_ACTION_PROMPT = """Goal:
{goal}

Current observation:
{observation}

Recent interaction history:
{history}

Available actions:
{admissible_actions}

Choose exactly one action from Available actions.
Return only the action string."""

# Section 11 (A4, Condition 1): lesson injected block appended to the base prompt.
LESSON_INJECTION_BLOCK = """
Relevant lesson from previous experience:
{lesson}

Use it only if it is relevant to the current task."""

REACT_ACTION_WITH_LESSON_PROMPT = REACT_ACTION_PROMPT + "\n" + LESSON_INJECTION_BLOCK

# ---------------------------------------------------------------------------
# Section 9 (A2): failure -> single reusable lesson.
# ---------------------------------------------------------------------------
FAILURE_LESSON_PROMPT = """You are analyzing a failed household-planning trajectory.

Task:
{goal}

Trajectory:
{trajectory}

Identify the main planning mistake and derive ONE reusable rule.

Requirements:
- The rule must describe a planning principle.
- Do not mention object instance IDs.
- Do not mention exact room or receptacle indices.
- Do not merely restate the failure.
- Maximum 35 words.

Return exactly:
Mistake: <one sentence>
Reusable rule: <one sentence>"""

# ---------------------------------------------------------------------------
# Section 14 (A7): transferability proxy signal.
# ---------------------------------------------------------------------------
TRANSFERABILITY_PROMPT = """Rate how reusable this planning lesson is across DIFFERENT household tasks.

0.0 = useful only for this exact task
1.0 = broadly reusable planning constraint

Lesson:
{lesson}

Return only one decimal number between 0.0 and 1.0."""

# ---------------------------------------------------------------------------
# Section 22 (B3): world-model next-observation prediction + self confidence.
# ---------------------------------------------------------------------------
WORLD_MODEL_PREDICTION_PROMPT = """You are a world model for an interactive household environment.

Current task:
{goal}

Current observation:
{observation}

Recent action-observation history:
{history}

Candidate action:
{base_action}

Predict the immediate NEXT observation after executing this action.

Also report your confidence that the important state changes and
preconditions in your prediction are correct.

Return exactly:
Prediction: <one concise predicted observation>
Confidence: <number from 0.0 to 1.0>"""

# ---------------------------------------------------------------------------
# Section 23 (B4): foresight-conditioned re-planning, still at state h_t.
# ---------------------------------------------------------------------------
FORESIGHT_CONDITIONED_ACTION_PROMPT = """Goal:
{goal}

Current observation:
{observation}

Available actions:
{admissible_actions}

A world model predicts the following consequence if the originally
proposed action "{base_action}" is executed:

{predicted_next_observation}

Choose the best CURRENT action.
You may keep the original action or select another available action.

Return exactly one action from Available actions."""
