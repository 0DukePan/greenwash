# Archived branches

Three branches existed locally and never on `origin`. Each was one commit ahead
of `main`; two were the same leftover tip. They are deleted as branches, and
their commits are preserved here as git bundles so nothing was destroyed.

Restore any of them with:

```bash
git fetch archive/branches/<name>.bundle <branch>:<branch>
```

or inspect without restoring:

```bash
git bundle list-heads archive/branches/<name>.bundle
```

| Bundle | Tip | What it held |
|---|---|---|
| `spec-dev-run-and-beta.bundle` | `237820b` | "Repin the suite count after the dev-run and trial tickets" — a suite-count repin left on a work branch. The duplicate branch `ticket/d-04-twins2` pointed at the same commit and is covered by this bundle. |
| `ticket-06-strength.bundle` | `c0aeb1d` | "Add the mutation-based test-strength advisory" — the only unmerged change: a mutation-based strength check that was never promoted past advisory. |

The `ticket/06-strength` work is the one worth reviving if the strength advisory
is ever measured; the other is bookkeeping.
