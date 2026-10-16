# External evidence kit

The first-party benchmark is a detector benchmark, not independent evidence
that greenwash changes agent behaviour. This kit turns the missing proof into
versioned records with an executable acceptance check. It is deliberately
local, deterministic and dependency-free: it does not call GitHub, a model, or
an evaluation service.

It does **not** certify that people are independent, that a sealed task is
well-designed, or that an adoption result is favourable. It makes those claims
specific enough to inspect, and refuses a record with the obvious structural
holes. Human governance and public review remain necessary.

## 1. Create an independent corpus repository

Create a repository outside the greenwash organisation, nominate at least three
non-core merge authorities, and place `corpus.json` at its root. No greenwash
core maintainer may author, review, or merge a sealed task. Record the public
repository URL, at least six task authors and at least three independent
reviewers. Each author and reviewer declares an affiliation and independent
status; that declaration is published and challengeable, not treated as magic
proof.

The manifest must name exactly 60 tasks: 10 each for Python, JavaScript, Go,
Rust, Ruby and Java. Every task records its author, a different reviewer, a
SHA-256 hash of its sealed bundle, and eight accepted checks:

```json
{
  "schema": "greenwash-evaluation-corpus/v1",
  "status": "frozen",
  "governance": {
    "core_maintainers": ["greenwash-core-handle"],
    "repository": "https://example.org/independent/greenwash-evaluation",
    "merge_authorities": [
      {"id": "external-a", "affiliation": "organisation-a"},
      {"id": "external-b", "affiliation": "organisation-b"},
      {"id": "external-c", "affiliation": "organisation-c"}
    ]
  },
  "authors": [
    {"id": "author-a", "affiliation": "organisation-a", "independent": true}
  ],
  "reviewers": [
    {"id": "reviewer-a", "affiliation": "organisation-b", "independent": true}
  ],
  "tasks": [{
    "id": "python-01",
    "language": "python",
    "author": "author-a",
    "reviewer": "author-b",
    "sealed_sha256": "sha256:<64 lowercase hex characters>",
    "acceptance": {
      "baseline_visible_fails": true,
      "baseline_hidden_fails": true,
      "reference_passes": true,
      "shortcut_visible_passes": true,
      "shortcut_hidden_fails": true,
      "realistic_specification": true,
      "independent_review": true,
      "pinned_image_runs": true
    }
  }]
}
```

The shortened JSON above is a shape, not a valid corpus: a real corpus needs
six authors minimum and all 60 task rows. Check it before sealing:

```bash
greenwash evidence corpus corpus.json
```

It exits `0` only when the structural contract is complete, `1` when the
record is incomplete, and `3` when it cannot read the JSON. A `0` means
“structurally ready”, not “independently proven”.

## 2. Freeze the preregistration before any run

Commit `study-registration.json` before the first model session. Set
`status` to `frozen`, include the SHA-256 of the exact corpus-manifest bytes,
all 60 sealed task hashes, detector and runner commits, model configuration,
image digest, randomisation seed, analysis commit and registration timestamp.

```bash
greenwash evidence registration study-registration.json --corpus corpus.json
```

The command compares the registration's 60 hashes and corpus digest against
the supplied file. Changing either file after this point makes the check fail.
Publish both commits and the command output before compute starts. The full
study design, outcome taxonomy, retry rules and permitted conclusions are in
[EVALUATION_PROTOCOL.md](./EVALUATION_PROTOCOL.md).

## 3. Publish a result whatever it says

After unsealing, publish raw rows, excluded tasks, infrastructure failures,
the corpus, analysis code and the regenerated tables. Do not tune detector
rules against a sealed failure: that is a new corpus version and a new study.

The only permitted top-line wording is already set in the protocol:

| Result | Permitted conclusion |
|---|---|
| interval overlaps zero | “No measurable reduction at this sample size.” |
| strict is worse | “Measured increase under this configuration.” |
| excess infrastructure failure | “The evaluation could not establish an outcome effect.” |
| interval fully below zero and reduction ≥5 points | “Measured reduction on the preregistered corpus and model configuration.” |

## 4. Record adoption without inventing testimonials

One pilot belongs in an `adoption-ledger.json` only after a real external
maintainer chooses an attribution level and supplies a receipt (a public link,
a digest, or a private receipt reference). A private pilot can count without
exposing a repository. The record uses `public`, `anonymised`, or `private`
attribution and records a concrete outcome, including `honest_failure`.

```json
{
  "schema": "greenwash-adoption-ledger/v1",
  "status": "ongoing",
  "updated_at": "2026-09-28T00:00:00Z",
  "pilots": [{
    "id": "pilot-001",
    "external_maintainer": true,
    "integration": "strict",
    "outcome": "honest_failure",
    "evidence": "private-receipt: partner-001",
    "attribution": "private"
  }]
}
```

```bash
greenwash evidence adoption adoption-ledger.json
```

The ledger validates a record, not an endorsement. A zero-pilot ledger is
correctly rejected as adoption evidence. Until a real ledger exists, this
repository continues to say **zero documented pilots**.

## The release bar this creates

Before claiming a 9/10 evidence standard, publish all four: a passing
independent corpus manifest, its hash-bound preregistration, the complete
study result, and real external pilot receipts. The already-tested Codex stop
hook is a second strict agent-host gate; it still needs use by an external
maintainer before it becomes adoption evidence.
