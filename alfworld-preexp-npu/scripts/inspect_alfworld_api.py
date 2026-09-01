#!/usr/bin/env python
"""
Run this FIRST on the NPU host, right after ALFWorld installs successfully
(spec section 38, step 1: "Inspect repository"). It does not need the vLLM
server running -- it only touches ALFWorld/TextWorld.

preexperiments/common/alfworld_runner.py hard-codes a small set of
assumptions about the installed ALFWorld version's API (which info dict keys
carry the gamefile path / admissible commands / win flag, and that
`AlfredTWEnv` exposes a public, reassignable `game_files` list plus an
`init_env(batch_size)` method). Those assumptions are correct for the
ALFWorld versions used by the well-known text-agent baselines (ReAct,
Reflexion, ExpeL, AdaMEM's own examples/prompt_agent/gpt4o_alfworld.py) at
the time this repo was written, but ALFWorld does not promise API stability,
so this script re-verifies them against whatever version pip actually
installed, and tells you exactly which line(s) in alfworld_runner.py to edit
if something has drifted.
"""
import sys


def main() -> int:
    problems = []

    try:
        from alfworld.agents.environment import AlfredTWEnv
    except ImportError as e:
        print(f"FAIL: cannot import alfworld.agents.environment.AlfredTWEnv: {e}")
        print("      -> ALFWorld is not installed correctly. Re-run "
              "scripts/setup_env_npu.sh step 8, or `pip install \"alfworld[full]\"`.")
        return 1

    print("OK: alfworld.agents.environment.AlfredTWEnv imports.")

    # Load the SAME translated config alfworld_runner.py uses at runtime, so
    # this check exercises exactly what the real pipeline will do (see
    # preexperiments/configs/alfworld_base_config.yaml and $ALFWORLD_DATA).
    from preexperiments.common.alfworld_runner import _load_alfworld_config

    config = _load_alfworld_config()

    try:
        env_wrapper = AlfredTWEnv(config, train_eval="train")
    except Exception as e:
        print(f"FAIL: AlfredTWEnv(config, train_eval='train') raised: {e}")
        print("      -> Your installed ALFWorld version may expect a differently")
        print("         shaped config dict. Find the real schema with:")
        print("         `python -c \"import alfworld, inspect; "
              "print(inspect.getsource(alfworld.agents.environment.AlfredTWEnv.__init__))\"`")
        print("         and update scripts/inspect_alfworld_api.py + any script that")
        print("         builds a config dict (they all call `load_yaml_config` on")
        print("         preexperiments/configs/alfworld_base_config.yaml, see README_NPU_SETUP.md).")
        return 1

    if not hasattr(env_wrapper, "game_files"):
        problems.append(
            "AlfredTWEnv has no `game_files` attribute. "
            "preexperiments/common/alfworld_runner.py's `build_single_game_adapter` "
            "relies on reading + reassigning this attribute before calling "
            "`init_env()`. Inspect `dir(env_wrapper)` for the real attribute name "
            "(likely still holds the game file list under a similar name) and "
            "update both `ALFWorldEnvAdapter._build` and `build_single_game_adapter` "
            "in alfworld_runner.py."
        )
    else:
        n_games = len(env_wrapper.game_files)
        print(f"OK: game_files attribute present, {n_games} games in train split.")
        if n_games == 0:
            problems.append(
                "game_files is empty -- dataset path in the config above is probably "
                "wrong for your `alfworld-download` output. Check "
                "$ALFWORLD_DATA/json_2.1.1/train exists and has content."
            )

    if not hasattr(env_wrapper, "init_env"):
        problems.append("AlfredTWEnv has no `init_env` method -- API has changed significantly.")
        print("\n".join(f"PROBLEM: {p}" for p in problems))
        return 1

    try:
        env = env_wrapper.init_env(batch_size=1)
        obs, info = env.reset()
    except Exception as e:
        print(f"FAIL: init_env(batch_size=1) / env.reset() raised: {e}")
        return 1

    print("OK: init_env(batch_size=1) + reset() succeeded.")
    print(f"    obs[0] preview: {obs[0][:200]!r}")
    print(f"    info keys: {sorted(info.keys())}")

    from preexperiments.common.alfworld_runner import _GAMEFILE_KEYS, _ADMISSIBLE_KEYS, _WON_KEYS

    for label, candidates in [
        ("gamefile", _GAMEFILE_KEYS),
        ("admissible_commands", _ADMISSIBLE_KEYS),
        ("won", _WON_KEYS),
    ]:
        if any(k in info for k in candidates):
            hit = next(k for k in candidates if k in info)
            print(f"OK: {label} field found under info[{hit!r}]")
        else:
            problems.append(
                f"None of {candidates} found in info for `{label}`. "
                f"Actual keys: {sorted(info.keys())}. Add the real key name to the "
                f"corresponding list ({label.upper()}_KEYS) near the top of "
                f"preexperiments/common/alfworld_runner.py."
            )

    obs2, scores, dones, info2 = env.step([info.get("admissible_commands", [["look"]])[0][0]
                                            if "admissible_commands" in info else "look"])
    print(f"OK: env.step() ran, done={dones[0]}")

    if problems:
        print("\n=== ACTION REQUIRED before running any experiment script ===")
        for p in problems:
            print(f" - {p}")
        return 1

    print("\nAll ALFWorld API assumptions in alfworld_runner.py check out for this install.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
