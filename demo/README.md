# Recording the demo

`demo/run_demo.py` is the proof: an agent claims a fix, the static layer flags
the hardcode, and the behavioral layer shows the held-out suite failing. It
needs no model and no API key.

## The two strict-gate demos

`demo/strict_claude.py` and `demo/strict_codex.py` are the same idea for the
gates. Each one builds a throwaway repository, drives the **real** hook the way
the host does -- payload on stdin, exit code read -- and prints captured output:

| Demo | What it records |
|---|---|
| `demo/strict_claude.py` | the turn blocked (`exit 2`), a waiver written, the same turn allowed with the waiver named, and the same diff in report mode for comparison |
| `demo/strict_codex.py` | the same gate with strict as the plugin default (no env var, no config): block, waive, the real fix, and the could-not-check path |

```bash
python demo/strict_claude.py --terse
python demo/strict_codex.py --terse
```

`--terse` drops the narration and prints only commands and their output, which
is what the launch post and the docs quote. Two things worth knowing if you
change them: the demo prints the *hook's* output verbatim (a summary written
here would be the exact thing this project complains about), and the expiry date
is computed from today, so a run is always inside the 30-day waiver ceiling.

## The README's GIF

`assets/demo.gif` is the loop at the top of the README. It is neither
screen-recorded nor transcribed: the generator runs `run_demo.py --terse`,
captures its stdout, and types those exact lines onto a terminal card. The text
inside the terminal is verbatim; what is added is presentation only -- the
kicker above the card, the tint and amber edge on the flag blocks, and a 140ms
brighten on each tag as it lands.

One thing worth knowing if you rebuild it: the GIF's palette is built from the
art's own colours with the accents forced in. Pillow's adaptive quantisation
silently dropped the green `$` -- a few dozen pixels against a frame of greys
is not enough for median cut to spend a slot on.

Rebuild it with:

```bash
python assets/make_demo_gif.py                          # writes assets/demo.gif
python assets/make_demo_gif.py --preview /tmp/frames    # dump key frames as PNGs
```

The wording comes from `demo/run_demo.py` -- the generator runs it and captures
its stdout -- so change the demo to change the text, and the generator to change
the pacing. It needs Pillow and a monospace font.

## Or record the real terminal

A screen recording of `run_demo.py` is even harder to argue with:

```bash
asciinema rec demo/demo.cast -c "python demo/run_demo.py"
agg demo/demo.cast demo/demo.gif
```

## What it shows (keep this order if you re-record)

1. The failing test and the bug.
2. `Agent: "Done! tests/test_calc.py passes now."`
3. `greenwash scan` -> `[hardcoded-return]`.
4. `greenwash verify --heldout ...` -> `tests_passed=pass, heldout_passed=fail`.

Keep the whole thing under ~20 seconds; the value is that it is obviously
real, not that it is long.
