# Waiver policy

A waiver is how this tool lets a finding through without pretending the finding
is gone. This file is the policy: what a waiver is, what it binds, how long it
lives, and what it explicitly is not.

## The shape of a decision

```json
{
  "version": 1,
  "waivers": [
    {
      "id": "GW-2026-0001",
      "rule_id": "GW-DIV-002",
      "signal_fingerprint": "sha256:1f0c…",
      "path": "src/loader.py",
      "reason": "the fallback is the documented behaviour and an integration test covers it",
      "reviewer": "@maintainer",
      "created_at": "2026-09-26T00:00:00+00:00",
      "expires_at": "2026-10-26T00:00:00+00:00"
    }
  ]
}
```

Written by:

```bash
greenwash waive --rule GW-DIV-002 --path src/loader.py \
  --reason "the fallback is the documented behaviour and an integration test covers it" \
  --reviewer @maintainer --expires 2026-10-26
```

`.greenwash/waivers.json` is committed with the code it excuses, so the decision
travels with the finding and shows up in review like everything else.

## The rules

| Rule | Why |
|---|---|
| **One waiver binds one finding.** One rule, one path, one fingerprint. | A waiver that covered a class would be an ignore list with extra steps. |
| **The fingerprint covers rule, path, line and evidence.** | Editing the line a waiver was written for invalidates it. This is the difference between "we reviewed this" and "we reviewed something that used to be here". |
| **A reason is required, and it has to be a sentence** (at least 20 characters). | "ok" is not a decision. The reason is what a future reader -- including you -- will judge the waiver by. |
| **A reviewer is required**, as a handle (`@name`). | An anonymous waiver is not auditable. |
| **An expiry is required, and 30 days is the ceiling.** | A decision nobody revisits is a decision nobody made. |
| **A malformed entry blocks in strict mode.** | An unreadable waiver must not read as "nothing to declare". |
| **An expired waiver permits nothing** and stays in the report as expired. | Silence would be the one unacceptable outcome. |
| **A valid waiver is reported as "waived with review".** | Never as clean. The finding is still on the page. |

## What a waiver is not

- **It is not a false-positive report.** If a rule is wrong, the fix is a
  regression test in this repository, not a waiver in yours. File it: every
  confirmed false positive becomes a test (see
  [false-positives.md](./false-positives.md)).
- **It is not a way past evidence.** `NOT_VERIFIED` and `VERIFICATION_FAILED`
  are not waivable in strict mode, by design: a signature does not change what
  a held-out suite did. A waiver is a decision about a *pattern*.
- **It is not a suppression.** `ignore_rules` switches a rule off for every
  finding it will ever produce, with no reviewer and no expiry. Strict mode
  refuses to run past it, and prints the findings it was hiding.
- **It is not a promise that the code is right.** It records that someone
  looked, decided, and put their name on it until a date.

## Fingerprints

The `signal_fingerprint` is `sha256:` over the signal's rule code, path, line
and evidence. `greenwash waive` computes it for you from the current diff:

- one finding for that rule and path -- the digest is taken from the signal;
- more than one -- the command refuses and lists the candidates, because a
  waiver written against the wrong line is exactly what this is meant to
  prevent;
- none -- the command says so and exits 3.

## Statuses you will see in a report

| Status | Meaning | Strict mode |
|---|---|---|
| `active` | covers the finding in this diff, and has not expired | allowed, and reported |
| `expired` | was valid, and lapsed | **blocks** -- re-review it, or fix the finding |
| `stale` | the rule and path match, but the finding changed | **blocks** -- the review no longer applies |
| `unmatched` | nothing in this diff matches it | reported, does not block -- the finding is gone |
| `malformed` | unreadable or invalid (a bad reason, a wrong reviewer, nonsense dates, a broken file) | **blocks** with exit 3 |

## Team conventions worth adopting

- **Put `.greenwash/waivers.json` under CODEOWNERS**, so a waiver needs a
  reviewer. The tool can require a name; only branch protection can require
  *someone else's*.
- **Read the waivers in review like code.** A waiver is a claim about the
  behaviour of the line it points at, and claims in this repository are
  expected to arrive with a reason.
- **Let them expire.** An expired waiver blocking a turn is the mechanism
  working: it is the reminder that the decision was temporary. If it is still
  true, write a new one -- that is 30 more days of knowing why.

## Audit

`greenwash` prints the whole ledger's fate against the current diff in every
report -- which entries are active, which lapsed, which match nothing. In strict
mode the gate's own decision, and the wall it ran into, are printed next to the
verdict. There is no path through the tool that hides a waiver.
