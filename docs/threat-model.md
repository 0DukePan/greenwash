# Threat model (Phase 1 audit)

What greenwash trusts, what it does not, and which risks remain open. This page
is the Phase 1 security pass; `THREAT_MODEL.md` at the repository root remains
the short user-facing statement.

## Assets

- The verdict a user acts on (a false pass is the product failing).
- The repository under inspection and anything reachable from it.
- The machine's environment: credentials, network, files outside the repository.
- The checker's own inputs: its code, config and pinned tests.
- Captured test output, which can contain secrets.

## Adversaries and untrusted inputs

- **The agent under review.** It controls the diff, the working tree, commit
  messages and any text in the repository. It may try to make the suite pass
  dishonestly or to steer the checker.
- **Repository content.** Hooks, filters, `git` config, paths, file sizes and
  filenames are untrusted. Corpus and stall detection read git objects, never
  execute them.
- **A pull request author** in CI, including a fork.
- **Supply chain**: workflow actions, the competitor binary used as a baseline,
  and the interpreter itself.

## Surfaces and what is in place

### Subprocess execution

- Test commands run through one runner with a timeout, captured output capped
  and passed through secret redaction before it reaches a report.
- A string command is executed through a shell by design, because users supply
  commands like `pytest -q`. A list is executed without a shell.
- Repository-supplied code is never executed by the corpus builder; replay runs
  in the integrity-checked sandbox or uses a recorded, hashed result.
- **Fix in this phase:** the composite action no longer interpolates workflow
  inputs into its shell script. Inputs arrive as environment variables and are
  passed as argv elements, closing a shell-injection route through
  `action.yml` inputs.

### Paths

- The corpus builder rejects absolute paths, `..` traversal, `.git` internals,
  control characters and symlink escapes, and bounds file sizes and counts.
- The hooks take no file path from tool input; they scan the repository they
  run in.
- Worktrees and baseline copies are created under the system temp directory and
  removed in a `finally`.

### Temporary files and worktrees

- JUnit reports use `mkstemp` and are removed in a `finally`; baseline
  worktrees use `mkdtemp` and are dropped after the run.
- A hard kill can leave a temp worktree behind. They are named
  `greenwash-base-*` and never contain secrets beyond the repository's own
  content.

### Logs and captured output

- `greenwash/verify/redact.py` replaces credential-shaped strings before output
  can appear in a report, and the report counts the redactions.
- Failure excerpts are capped in length.

### CI shape

- The provided report-only workflow uses `pull_request`, read-only permissions,
  no secrets, and uploads an artifact instead of posting a comment.
- The checker, config and pinned tests are hash-verified and loaded from the
  base ref; a branch cannot grade itself.

## Larger issues, listed rather than fixed

1. **Actions are referenced by tag, not by full commit SHA.** Pinning requires
   verifying SHAs from the network; until then a compromised tag could move.
2. **Local runs are not sandboxed.** The tool documents that replay executes
   the project's tests; running it on untrusted code needs the container the
   spec describes. Nothing in the tool enforces that.
3. **Shell execution of user-supplied commands** is deliberate. Quoting is the
   user's responsibility; the tool does not parse the command.
4. **The redaction list is heuristic.** Unusual secret shapes can pass through.
5. **The competitor baseline is a subprocess at a pinned version.** Its own
   supply chain is trusted.
6. **No telemetry exists**, so there is no outbound channel to abuse today;
   adding any would need its own threat review.

## Out of scope here

Retrieval and leakage, training-time reward hacking, and any claim about
RL-trained agents. Those are scope exclusions in the launch spec, not controls
this phase can add.
