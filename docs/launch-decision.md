# Launch decision: the three-week memo

The project has spent six weeks building an evidence program for a product no
stranger had run. This memo replaces that program with the smallest experiment
that produces a real signal: ship the thing, measure whether anyone cares, and
decide on a date instead of on a feeling.

Fill this in three weeks after the release. A missed target is published with
its gap, not replaced by a broader claim -- the rule the rest of the repository
already runs on.

## Release record

| | |
|---|---|
| Version released | |
| Date | |
| Commit | |
| Install path that worked from a clean environment | |
| Test count at release | |
| CI status at the released commit | |

## Signals

| Signal | Count | Landmark |
|---|---:|---|
| Repository stars | | |
| Forks | | |
| External issues opened | | |
| External PRs | | |
| Downloads / installs (if measurable) | | |
| People who ran it on a real repo and said so | | |
| False-positive reports | | |
| People who asked for strict mode | | |

## The three questions

1. **Did anyone run it?** Not "did anyone star it". An external issue, a
   false-positive report, or a message saying "I ran this on my repo" is the
   only evidence that the tool crossed the boundary between the author's
   machine and someone else's work.
2. **What was the first complaint?** The first complaint is the product roadmap,
   whatever the plan says. If it is the waiver queue from the
   [false-positive survey](./false-positive-survey.md), narrow
   `verifier-config-changed`. If it is runtime, measure the hook. If it is a
   false accusation, that is the highest-severity bug in the project.
3. **Would you install it on a repository you did not write?** If the answer is
   no, the tool is not ready, regardless of the star count.

## Decision

| Outcome | Condition | What happens next |
|---|---|---|
| **Continue** | ≥3 external issues or ≥20 organic installs, and no unresolved false accusation | Keep the scope narrow: fix the first complaint, re-run the detection benchmark, publish the interval. |
| **Narrow further** | Interest exists but only in the plugin / hook path | Drop the CLI-first positioning from the README, make the Claude/Codex plugin the product, and keep the CLI as the engine. |
| **Park** | 0 external issues, no installs after three weeks | Write the post-mortem into [what-did-not-work.md](./what-did-not-work.md), mark the README unmaintained, and stop. Keep the repository as a portfolio piece. |
| **Pivot to evals** | The only interested readers are people running agent benchmarks | The committed-test replay and the integrity taxonomy are the assets; propose them to an eval harness where test tampering is the measured failure. |

## What this memo refuses

- A star campaign, a paid boost, or a launch post that claims an effect the
  pilot did not measure.
- A second evidence program before the first external user.
- Re-running the 252-run study as a substitute for talking to five people.

## Open blocker at the time of writing

The behavioural re-run is blocked on a reachable model: `python
benchmark/preflight.py` reports the gateway is not logged in. The instrument fix
(classifier accepts the checker's flag shape; a passing cheat is `flagged`
rather than `genuine fix`) is merged and tested. Until the re-run happens, no
page may state a behavioural effect in either direction -- including "it does
not work".
