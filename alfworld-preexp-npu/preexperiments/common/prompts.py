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
# Section 39 remedy #3: AdaMEM's own no-memory ALFWorld prompt.
#
# The spec (section 39) says that if Qwen3-4B's success rate is too low, one
# sanctioned check is whether "AdaMEM 官方 no-memory runner 的 prompt 是否可直接
# 复用". Measured on this host with the section 5.1 prompt above, the answer to
# the first two checks was: prompt already constrains to admissible actions
# (forced-action rate 0.0%), and raising max_episode_steps 30 -> 50 bought one
# extra success out of 30 for 62% more compute -- so neither is the bottleneck.
# What the trajectories actually show is an agent cycling among ~12 actions,
# stuck repeating "look"/"examine <receptacle>" instead of executing ALFWorld's
# task grammar (go to X -> open X -> take Y -> go to Z -> use/put).
#
# The one substantive difference in AdaMEM's prompt is that it gives the model
# an explicit reasoning scratchpad before committing to an action. Copied from
# AdaMEM commit 4ea93e239f8dbec2fa6013a28bc8555419037e12,
# agent_system/environments/prompts/alfworld.py::ALFWORLD_TEMPLATE (wording
# preserved; the {goal}/{observation}/{history}/{admissible_actions} field
# names are renamed to match this repo's call sites).
#
# NOTE this is AdaMEM's NO-MEMORY path (a single call emitting <think> then
# <action>). AdaMEM's two-stage strategy pathway is deliberately NOT used: its
# "strategy items accumulated from past interactions" are a memory mechanism,
# and injecting them into the no-lesson baseline would contaminate exactly the
# comparison experiment A exists to make.
# ---------------------------------------------------------------------------
ADAMEM_THINK_ACTION_PROMPT = """You are an expert agent operating in the ALFRED Embodied Environment. Your task is to: {goal}
Below are the most recent observations and the corresponding actions you took: {history}
Your current observation is: {observation}
Your admissible actions of the current situation are: [{admissible_actions}].

Now it's your turn to take an action.
You should first reason step-by-step about the current situation. This reasoning process MUST be enclosed within <think> </think> tags.
Once you've finished your reasoning, you should choose an admissible action for current step and present it within <action> </action> tags."""

ADAMEM_THINK_ACTION_WITH_LESSON_PROMPT = ADAMEM_THINK_ACTION_PROMPT + "\n" + LESSON_INJECTION_BLOCK

# Second half of the "adamem_think" two-call step: the reasoning produced by
# the prompt above is fed back, and only the action is decoded -- under the
# same guided_choice constraint the "spec" style uses.
ADAMEM_ACTION_AFTER_THINK_SUFFIX = """

<think>{reasoning}</think>

Based on that reasoning, output exactly one action from the admissible actions above, and nothing else."""

# Known-issue fix: gives B4's foresight-conditioned re-plan (spec section 23)
# the same reasoning opportunity B2's base action gets under prompt_style=
# "adamem_think", so action_changed measures only "did it see the world-model
# prediction" and not "did it get to think at all". Appended to spec's fixed
# FORESIGHT_CONDITIONED_ACTION_PROMPT text ONLY to elicit the <think> stage
# via the same two-call mechanism as ADAMEM_THINK_ACTION_PROMPT -- the spec's
# own wording above is never altered.
ADAMEM_THINK_FORESIGHT_SUFFIX = """

You should first reason step-by-step about whether to keep or change the
action given the world model's prediction. This reasoning process MUST be
enclosed within <think> </think> tags. Once you've finished your reasoning,
choose an admissible action for the current step and present it within
<action> </action> tags."""

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
