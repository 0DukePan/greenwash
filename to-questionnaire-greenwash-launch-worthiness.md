# Greenwash launch-worthiness questionnaire

**Purpose:** decide whether Greenwash should spend the human cost of its five-stage evidence program before any public launch, or launch a scope-limited beta now with the small wording it can already license. Your answers decide where the effort goes and what the first public artifact should be.

**From:** the Greenwash maintainer, **To:** an experienced open-source maintainer and launch advisor, **How your answers will be used:** they feed directly into the go/no-go on the evidence program and into the launch plan's sequencing. Nothing you write will be published or attributed without asking you.

## Context

Greenwash is a checker for coding agents that fake passing tests: it reads a diff plus the original tests and returns CLEAN, TAMPERED, WEAK_VERIFIER or INCONCLUSIVE with evidence, and it ships a CI gate plus hooks for coding agents. The detector currently reports 24 of 24 planted cheats caught, 11 of 11 tampers caught with 0 of 11 legitimate twins falsely flagged, and a 252-run behavior study that observed no cheating. All of that comes from cases the maintainer wrote, so the exact intervals still allow a true detection rate near 72 percent and a false-alarm rate near 28 percent.

The proposed program has five stages: (1) real suspicious test edits plus legitimate lookalikes with double-blind labels, (2) the hardest families such as changed expected values with a plausible commit message, (3) strong baselines including a pinned competitor, (4) a pre-registered frozen benchmark that produces LAUNCH or NARROW, (5) GitHub integration measured for speed, usability and friction. Stage 1 plus labeling is plausibly over one hundred hours of human work. The tool is offline, deterministic, and its reporting already refuses to claim intent.

## How to answer

Rough deadline: whenever you can. Half an hour of honest impressions is more useful than a polished page. Partial answers and "I don't know" are fine; flag anything you are unsure of rather than skipping it. Answer in the stub under each question.

## Is the evidence program worth its cost?

### Would you spend roughly one hundred hours of labeling and corpus work before the first public launch of a developer tool like this?

_Why this matters: this is the decision the whole program hangs on, and it is the one question where your experience matters more than the maintainer's preference._

>

### What is the minimum evidence you would personally need before taking a test-integrity tool seriously?

>

### Which of the five stages would you cut or defer if the budget were half of what is proposed?

>

### What would make you distrust the published numbers even if the method looked sound?

_Why this matters: knowing the disqualifiers is more actionable than knowing the ideal._

>

### Is a frozen, pre-registered benchmark overkill for a tool at this stage, or is it the thing that separates it from a weekend project?

>

## What realistically earns attention

### In your experience, what actually drives stars for a developer tool in its first month?

>

### Would a rigorous, honest benchmark with wide intervals earn attention, or does attention only follow a demo?

>

### What artifact would travel furthest: a twin-pair demo, a benchmark report, a CI integration, or a short post with one striking number?

>

### Is "GitHub Repo of the Day" a realistic target for a project like this, or a vanity goal that distorts decisions?

_Why this matters: if it is mostly luck and network effects, the program should optimize for credibility and adoption instead._

>

### What have you seen backfire when a tool launches with a small, honest claim instead of a big one?

>

## The corpus and the labels

### Would you trust labels produced by the maintainer plus one independent labeler plus an adjudicator, or does credibility require a third party?

>

### What evidence would make you believe the false-alarm rate more than a published PABAK on one hundred cases?

>

### Are there public datasets or prior audits you would rather see used than a purpose-built corpus?

>

### What would make you suspect the corpus was chosen to flatter the detector?

>

## Value against what people already use

### What would make you switch from "nothing" or from a tool like Pawl to this one?

>

### Which failure mode would kill it for you: a false accusation, an INCONCLUSIVE verdict, or slow CI?

>

### How much added value do you need to see before you would recommend a tool to a team you work with?

>

## Integration and friction

### What makes a CI gate tolerable on a real repository, and what makes you remove one?

>

### Which rollout would you accept: report-only comments, an advisory check, or a blocking check from day one?

>

### What speed overhead would be unacceptable for a check on every pull request?

>

## Positioning and honesty

### Which claim about this tool do you find most believable, and which least?

>

### Would publishing a NARROW result before a launch strengthen or weaken the project's credibility with you?

>

### What should the maintainer never say in the announcement, in your view?

>

## The launch itself

### What would you add to a launch-readiness checklist for a tool like this?

>

### What sequencing would you recommend: evidence program first, limited beta now, or integration-first?

>

### Who are the first ten people or teams you would put this in front of, and why them?

>

## Anything else?

Anything we did not ask that you think decides whether this tool is worth building and launching?

>

Thank you. Even partial answers to the first three questions change the decision.
