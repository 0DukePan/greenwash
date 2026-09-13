# Recording the demo

`demo/run_demo.py` is the proof: an agent claims a fix, the static layer flags
the hardcode, and the behavioral layer shows the held-out suite failing. It
needs no model and no API key.

## The README's GIF

`assets/demo.gif` is the loop at the top of the README -- the claim, the flag,
the blocked stop, abridged. It is generated, not screen-recorded:

```bash
python assets/make_demo_gif.py                          # writes assets/demo.gif
python assets/make_demo_gif.py --preview /tmp/frames    # dump key frames as PNGs
```

Edit `assets/make_demo_gif.py` to change pacing or text. It needs Pillow, a
monospace font, and `assets/logo-mark.png` (the rasterized `assets/logo.svg`).

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
