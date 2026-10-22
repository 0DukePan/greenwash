# Security policy

## Supported versions

The latest release gets fixes. Older releases get a note in the changelog
pointing at the fix if the issue is serious.

## Reporting a vulnerability

Open a [private security
advisory](https://github.com/0DukePan/greenwash/security/advisories/new) rather
than a public issue. If you cannot use advisories, open an issue that says only
"security report -- please contact me" and nothing about the content; a
maintainer will move it to a private channel.

Please include: what you ran, what happened, what you expected, and the version
(`greenwash --version`). A proof of concept is welcome; so is a sentence
describing the shape of the problem if that is all you have.

Expect an acknowledgement within a few days. This is a small project with no
paid maintainers, and the honest version of that is: a fix may take a while,
and you will be told if nobody is working on it.

## What counts as a vulnerability here

greenwash runs on a developer's machine, reads a diff, and executes the
project's own test command. That shape has specific risks, and the ones that
matter are:

- **Command execution.** Any way to make greenwash run something other than the
  test command it was configured or discovered with -- a config value, a
  repository file, a crafted diff, a path in a test name.
- **Secret disclosure.** Captured test output is redacted and capped before it
  is printed or written to JSON. A way to get a credential into a report, a
  log, or an error message is a vulnerability.
- **Path traversal.** Reading or writing outside the repository, including
  through the baseline worktree, the held-out suite path, or the waiver ledger.
- **Resource exhaustion.** A diff or an output stream that makes a scan or a
  verify consume unbounded memory or disk. The static scan has a budget
  assertion (500 files in under 2s) and output is capped per stream; a way past
  either is a bug worth reporting.
- **Waiver bypass.** Any way to make an expired, stale, mismatched or malformed
  waiver permit a completion in strict mode -- or to make a waiver apply to a
  finding it was not written for.

## What is not a vulnerability

- **A false positive.** That is a bug, and it goes in the
  [false-positive form](https://github.com/0DukePan/greenwash/issues/new?template=false-positive.yml).
  Every confirmed one becomes a test.
- **A false negative** -- a cheat the detector misses. That is the tool's
  documented limit, not a breach: it is a smell detector, not a prover. Report
  the shape of the miss through the
  [bypass form](https://github.com/0DukePan/greenwash/issues/new?template=bypass.yml),
  because a miss that generalises is worth a rule.
- **Routing around the gate deliberately.** Editing the hook, disabling the
  plugin, or running `git commit --no-verify` are all things a local tool cannot
  prevent, and the docs say so rather than pretending otherwise. If you need an
  enforcement boundary an agent cannot edit, that is branch protection and
  CODEOWNERS, not this.

## The trust boundary, stated plainly

A Stop hook installed as a trusted plugin is a **workflow gate**, not an
administrative enforcement boundary. It stops an agent that is cooperating with
the host. It does not stop an agent that edits the hook, works outside the host,
or pushes from somewhere else. Nothing local can, and this project does not
claim otherwise.

greenwash makes no network calls, has no telemetry, and stores nothing outside
your repository (`.greenwash/config.json` and `.greenwash/waivers.json`), plus
session state inside your git directory (`.git/greenwash/`): the session anchor
and the Stop hook's block budget. The one exception is a hook that runs outside
a git repository, which keeps its block budget in the system temp directory.
That budget, like the session anchor, is a guard and not a security boundary:
an agent that can run git and write files can rewrite it, which is why the
report always prints what it found and the anchor carries tamper evidence.

## What is pinned, and what a sandbox can move

The diff under inspection is untrusted, and so is everything an agent can write
inside the working tree -- including the files the verifier reads to decide
what gets checked and what may pass. Three classes of input are pinned at the
**base ref** (the session base locally, the merge target in CI) and
hash-verified before use, which is what "loaded from outside the agent's
writable sandbox" means here: the git object at the base ref, not the working
copy.

- **The checker's own code** (`greenwash/`, `scripts/greenwash_check.py`,
  `scripts/greenwash_hook.py`) as tracked in the repository -- the self-check
  case. A copy that is edited, deleted, or introduced where the base ref had
  none stops the run before any verdict, with exit code 4. When the checker
  runs from outside the repository (the pinned GitHub Action path), it is
  outside the sandbox entirely and pinning it is the installer's job.
- **The configuration** (`.greenwash/config.json`). A pinned copy that moved
  stops the run the same way, so a branch cannot lower its own bar. The one
  deliberate exception: a config that *appears* mid-session is honoured and
  flagged (`verifier-config-changed`, requires review) rather than refused --
  it cannot move a pinned policy, because a pinned policy that moves stops the
  run first. The waiver ledger (`.greenwash/waivers.json`) is not config: it
  has its own lifecycle, and a forged waiver reads "waived with review", never
  clean.
- **The pinned original tests.** An edited or deleted test file is detected
  before the run starts and named in the report with the digest of the base
  copy, which is what counts as evidence. A test edit is diff content for the
  verdict to judge (`test-weakened`, `test-deleted`), never a moved pin.

Digests are taken over newline-normalised text, because a checkout's CRLF
translation is not a modification. An integrity failure is its own exit code
(4), is printed before any verdict exists, and says in so many words that it
is not a verdict about the diff.

This is a guard, not a security boundary. An agent with git access can rewrite
the base ref or run the checker from somewhere else; that is the same class of
deliberate routing-around described above. What the guard removes is the
unnoticed move: a checker input cannot change under a run without either
stopping it or being named in its report. A scripted integrity suite
(`tests/test_verifier_integrity.py`) attempts these alterations from inside a
sandbox -- config, checker code, pinned tests, and the run's output -- and
requires zero successes.
