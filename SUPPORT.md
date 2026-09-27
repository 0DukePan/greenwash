# Support

greenwash is a small project maintained by people who do this alongside other
work. This page says where to ask, and what to include so the first reply can be
useful instead of "can you paste the output".

## Before you ask

```bash
greenwash doctor          # what greenwash can and cannot see here
greenwash --version
```

`doctor` answers most "why didn't it check anything" questions by itself: no git
repository, no commits, no test command discovered, the integrity check switched
off. Its output is the thing to paste.

## Where to ask

| Question | Where |
|---|---|
| "Why did it say `VERIFICATION_FAILED`?" | [Discussions](https://github.com/0DukePan/greenwash/discussions) -- integration help |
| "It flagged my correct code" | [false-positive form](https://github.com/0DukePan/greenwash/issues/new?template=false-positive.yml) |
| "It missed a cheat" | [bypass form](https://github.com/0DukePan/greenwash/issues/new?template=bypass.yml) |
| "The hook doesn't start on my host" | [host integration form](https://github.com/0DukePan/greenwash/issues/new?template=host-integration.yml) |
| "I want to use it on a real project and tell you how it goes" | [design partner form](https://github.com/0DukePan/greenwash/issues/new?template=design-partner.yml) |
| "I want to author evaluation tasks" | [task proposal form](https://github.com/0DukePan/greenwash/issues/new?template=external-task.yml) |
| A security problem | [SECURITY.md](SECURITY.md), privately |
| Anything else | [Discussions](https://github.com/0DukePan/greenwash/discussions) |

## What to include

1. `greenwash doctor` output.
2. The command you ran, and its full output -- not a summary of it. This project
   runs on receipts, and issue reports are held to the same standard.
3. `greenwash --version`, your OS, and your Python version.
4. For a false positive: the commit and the flag, and one sentence on why the
   flagged line is correct. Every confirmed false positive becomes a test.
5. For a host integration problem: which host and version, the relevant hook or
   config file, and whether `python codex/scripts/greenwash_hook.py` (or the
   Claude equivalent) starts when you run it by hand.

## What you will get

- **A confirmed bug** gets a fix or an honest "this is a documented limit" --
  and if it is a limit, a docs change so the next person finds out sooner.
- **A false positive** becomes a regression test, or an explanation of why the
  rule fires and what to do about it. Both are outcomes; the second one usually
  comes with a `requires_review` downgrade.
- **A missed cheat** becomes a rule if the shape generalises, and a documented
  limit if it does not.
- **No promises about time.** This is not a funded project, and it does not
  pretend to be one.

## What it will not do

- Tell you your code is correct. It reports what ran and what the diff looks
  like; the confidence level says how much that is worth.
- Prevent an agent from completing a task. It can make completion *visible*, and
  in strict mode it can hand the turn back -- but a local tool cannot stop an
  agent that decides to route around it, and [SECURITY.md](SECURITY.md) says so
  rather than implying otherwise.
