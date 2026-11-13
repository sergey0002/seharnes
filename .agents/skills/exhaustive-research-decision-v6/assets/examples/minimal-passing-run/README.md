# Minimal PASS fixture

Regenerate/check:

    python scripts/check_gates.py --init-v6 examples/minimal-passing-run --force
    python examples/minimal-passing-run/generate.py
    python scripts/check_gates.py examples/minimal-passing-run

Expected: PASS errors=0 warnings=0.

`fixture_overrides.json` holds the non-template artifact contents. The fixture is synthetic: it demonstrates artifact structure and validator behavior only, not a real literature review.
