# Social preview: verified

`assets/social-preview.png` is what GitHub, Slack, X, Discord and most link
unfurlers render when this repository's URL is pasted somewhere. The repository
showed as a grey rectangle without it, which is a poor first impression for a
project whose whole argument is "look at the evidence".

## What was checked

| Property | Requirement | Measured |
|---|---|---|
| Dimensions | 1280x640 (GitHub's social-preview aspect) | **1280x640** |
| Format | PNG or JPG | PNG, RGB |
| File size | under GitHub's 1 MB limit | **116,551 bytes (114 KB)** |
| Not blank | has content, not a flat fill | 5,927 distinct colours |
| Legible as a thumbnail | wordmark and headline readable when scaled down | checked at 1200x600 and at ~600x300 |
| Reproducible | regenerating it from its script gives the same file | **byte-identical** |

`sha256:b0a5ec9c22d7beccdda88002224f8a43472634b8d397ff24b86be31571c10e37`

## The reproducibility check, verbatim

The generator was copied to a scratch directory (so the tracked artifact was not
touched) and run there:

```
$ python make_social_preview.py
wrote .../social-preview.png -- 1280x640, 114 KB

committed sha256: b0a5ec9c22d7beccdda88002224f8a43472634b8d397ff24b86be31571c10e37
regenerated      : b0a5ec9c22d7beccdda88002224f8a43472634b8d397ff24b86be31571c10e37
byte-identical: True
```

Regenerate it yourself with:

```bash
python assets/make_social_preview.py     # writes assets/social-preview.png
```

It needs Pillow and a monospace font (Consolas, Cascadia Mono, DejaVu Sans Mono
or Menlo -- the same stack the demo GIF uses, so the two read as one product).

## Provenance and licensing

- The mark is **redrawn** in the generator from `assets/logo.svg`'s coordinates
  and its three-stop gradient, transformed the same way (`translate(0, -7)`,
  `rotate(-4, 48, 48)`); it is not a re-encoded raster. If `logo.svg` changes
  materially, the generator should change with it.
- The text is set in the same monospace stack as the demo GIF.
- The script, the mark and the layout are MIT, like the rest of this
  repository. No third-party image, font file or stock asset is embedded: the
  fonts are referenced by name from the host, never bundled.

## How to use it

In the repository settings: **Settings -> General -> Social preview -> Upload an
image**, and choose `assets/social-preview.png`. That is the one manual step;
nothing in CI can set it.

## What it does not claim

The card says "A trust report on a coding agent's `done`" -- deliberately not a
number, and deliberately not a promise. It is the one image most people will
see, so it states what the tool is and nothing it has not measured. The measured
numbers live in [benchmark-summary.md](./benchmark-summary.md), with their
intervals and their limits.
