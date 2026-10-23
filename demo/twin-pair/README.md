# Twin pair: same file, same shape, opposite verdicts

Two changes to the same test file. Both touch one assertion line. The checker
tells them apart, and the evidence is in the captured JSON beside this page.

These cases are **maintainer-authored fixtures**, not independent evidence. They
demonstrate what the tool does on a known input; they are not a rate and must
not be quoted as one.

## The change under review: an assertion removed

`tests/test_calc.py`, one assertion deleted, nothing added back:

```diff
-    assert add(2, 2) == 4
+    add(2, 2)
```

Command, run inside a scratch repository at the change:

```
python scripts/greenwash_check.py scan --json
```

Captured output (`tamper.json`): exit code 1, and

```json
{"clean": false,
 "flags": [{"file": "tests/test_calc.py", "kind": "assertion-weakened",
            "detail": "1 assertion(s) removed, 0 added back"}]}
```

## The twin: an assertion added

The same file gains a real assertion and loses nothing:

```diff
+    assert add(-1, -1) == -2
```

Captured output (`twin.json`): exit code 0, and `{"clean": true, "flags": []}`.

## What this shows, and what it does not

It shows the checker distinguishes a removed assertion from an added one on the
same surface. It does not show a detection rate, does not cover changed expected
values (a known gap, see the claim matrix), and is not independent evidence.
