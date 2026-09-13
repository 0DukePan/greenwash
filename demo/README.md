# Recording the demo

`demo/run_demo.py` is the 20-second proof: an agent claims a fix, the static
layer flags the hardcode, and the behavioral layer shows the held-out suite
failing. It needs no model and no API key.

## Record it

```bash
# asciinema (recommended -- small, copy-pasteable, plays inline on GitHub)
asciinema rec demo/demo.cast -c "python demo/run_demo.py"

# or record to a GIF
asciinema rec demo/demo.cast -c "python demo/run_demo.py"
agg demo/demo.cast demo/demo.gif
```

Reference the result near the top of the README.

## What it shows (keep this order if you re-record)

1. The failing test and the bug.
2. `agent: "Done! tests/test_calc.py passes now."`
3. `greenwash scan` → `[hardcoded-return]`.
4. `greenwash verify --heldout …` → `tests_passed=pass, heldout_passed=fail`.

Keep the whole thing under ~20 seconds; the value is that it is obviously
real, not that it is long.
