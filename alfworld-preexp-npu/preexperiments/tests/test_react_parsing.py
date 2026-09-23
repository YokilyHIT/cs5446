"""Pure-logic tests for the new "react" reasoning mode's action parsing and
the corrected (self-report-excluded) logprob-confidence computation. No live
vLLM server or ALFWorld install is required for any of these.
"""
from preexperiments.direction_b.pipeline import _mean_logprob_in_span, parse_react_action


def test_react_parses_exact_admissible_action():
    text = "Thought: the mug is on the counter.\nAction: take mug 1 from counter 1"
    admissible = ["take mug 1 from counter 1", "go to counter 1"]
    action, forced = parse_react_action(text, admissible)
    assert action == "take mug 1 from counter 1"
    assert forced is False


def test_react_matches_case_and_whitespace_insensitively():
    text = "Thought: ...\nAction:   Take Mug 1 From Counter 1  "
    admissible = ["take mug 1 from counter 1"]
    action, forced = parse_react_action(text, admissible)
    assert action == "take mug 1 from counter 1"
    assert forced is False


def test_react_unmatched_action_is_returned_verbatim_not_fuzzy_substituted():
    """The whole point of the strict parser: a near-miss must NOT be silently
    swapped for a different, merely similar-looking admissible action."""
    text = "Thought: I should look at the drawer.\nAction: examine drawer 1"
    admissible = ["open drawer 1", "examine desk 1"]  # neither is "examine drawer 1"
    action, forced = parse_react_action(text, admissible)
    assert action == "examine drawer 1"  # verbatim model text, not e.g. "examine desk 1"
    assert forced is True


def test_react_no_action_line_falls_back_to_whole_text_not_first_admissible():
    text = "I think I should take the mug."
    admissible = ["take mug 1 from counter 1", "go to counter 1"]
    action, forced = parse_react_action(text, admissible)
    assert action == text.strip()
    assert forced is True


def test_mean_logprob_in_span_excludes_tokens_outside_the_span():
    # "AB" + "CD" reconstructs "ABCD"; span [0, 2) should only pick up "AB".
    token_logprobs = [("AB", -1.0), ("CD", -100.0)]
    result = _mean_logprob_in_span(token_logprobs, 0, 2)
    assert result == -1.0


def test_mean_logprob_in_span_matches_full_average_over_whole_text():
    token_logprobs = [("foo", -1.0), ("bar", -3.0)]
    result = _mean_logprob_in_span(token_logprobs, 0, len("foobar"))
    assert result == -2.0


def test_mean_logprob_in_span_nan_on_missing_span():
    assert _mean_logprob_in_span([("x", -1.0)], None, None) != _mean_logprob_in_span([("x", -1.0)], None, None)  # NaN != NaN
