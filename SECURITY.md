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
your repository (`.greenwash/config.json` and `.greenwash/waivers.json`).
