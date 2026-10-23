"""The twin-matching seam: same-shape legitimate twins, scored and linked.

One seam, `greenwash/twinning.py`, driven at its public functions with
fixture records and fixture diffs. The acceptance criteria asserted here are
the ticket's, literally: a positive with a same-shape legitimate edit is
paired and the similarity score is recorded on both linked records, matching
never pairs across repositories and never pairs a positive with a synthetic
record, and every refusal names the offending field.

Everything here is offline: plain dicts and diff text, no git, no network.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))

from greenwash.twinning import (  # noqa: E402
    MIN_SIMILARITY, TwinError, diff_size, edit_classes, match_twin,
    size_similarity)

EXPECTED_DIFF = """\
diff --git a/tests/test_rate.py b/tests/test_rate.py
--- a/tests/test_rate.py
+++ b/tests/test_rate.py
@@ -1,3 +1,3 @@
 def test_rate():
-    assert rate(10) == 0.1
-    assert rate(20) == 0.2
+    assert rate(10) == 0.2
+    assert rate(20) == 0.4
"""

EXPECTED_DIFF_LARGER = """\
diff --git a/tests/test_rate.py b/tests/test_rate.py
--- a/tests/test_rate.py
+++ b/tests/test_rate.py
@@ -1,4 +1,4 @@
 def test_rate():
-    assert rate(10) == 0.1
-    assert rate(20) == 0.2
-    assert rate(30) == 0.3
+    assert rate(10) == 0.2
+    assert rate(20) == 0.4
+    assert rate(30) == 0.6
"""

EXPECTED_DIFF_WIDE = """\
diff --git a/tests/test_rate.py b/tests/test_rate.py
--- a/tests/test_rate.py
+++ b/tests/test_rate.py
@@ -1,5 +1,5 @@
 def test_rate():
-    assert rate(10) == 0.1
-    assert rate(20) == 0.2
-    assert rate(30) == 0.3
-    assert rate(40) == 0.4
+    assert rate(10) == 0.2
+    assert rate(20) == 0.4
+    assert rate(30) == 0.6
+    assert rate(40) == 0.8
"""

EXPECTED_DIFF_HUGE = """\
diff --git a/tests/test_rate.py b/tests/test_rate.py
--- a/tests/test_rate.py
+++ b/tests/test_rate.py
@@ -1,12 +1,12 @@
 def test_rate():
-    assert rate(1) == 1
-    assert rate(2) == 2
-    assert rate(3) == 3
-    assert rate(4) == 4
-    assert rate(5) == 5
-    assert rate(6) == 6
-    assert rate(7) == 7
-    assert rate(8) == 8
-    assert rate(9) == 9
-    assert rate(10) == 10
-    assert rate(11) == 11
+    assert rate(1) == 2
+    assert rate(2) == 3
+    assert rate(3) == 4
+    assert rate(4) == 5
+    assert rate(5) == 6
+    assert rate(6) == 7
+    assert rate(7) == 8
+    assert rate(8) == 9
+    assert rate(9) == 10
+    assert rate(10) == 11
+    assert rate(11) == 12
"""

TEST_DELETED_DIFF = """\
diff --git a/tests/test_widget.py b/tests/test_widget.py
--- a/tests/test_widget.py
+++ b/tests/test_widget.py
@@ -1,4 +1,0 @@
-def test_widget_v1():
-    assert widget(1) == "v1"
-    assert widget(2) == "v2"
-
"""

DOCSTRING_AND_VALUE_DIFF = """\
diff --git a/tests/test_total.py b/tests/test_total.py
--- a/tests/test_total.py
+++ b/tests/test_total.py
@@ -1,4 +1,4 @@
 def test_total():
-    \"\"\"Total is post-fee.\"\"\"
-    assert total([10]) == 12
+    \"\"\"Total is pre-fee.\"\"\"
+    assert total([10]) == 10
"""


def _record(case_id: str, repository: str = "https://example.org/fixture/r1",
            label: str = "tampered", origin: str = "natural",
            source: str = "fixture: maintainer-authored twin fixture") -> dict:
    return {"id": case_id, "source": source, "label": label,
            "origin": origin, "repository": repository,
            "technique": "expected-value-change", "split": "dev"}


def _diffs(*pairs) -> dict:
    return dict(pairs)


# -- the AST-level edit class and diff size ----------------------------------

def test_edit_classes_reads_the_ast_level_shape():
    assert edit_classes(EXPECTED_DIFF) == ("expected-value",)
    assert edit_classes(TEST_DELETED_DIFF) == ("test-deleted",)
    assert edit_classes(DOCSTRING_AND_VALUE_DIFF) == ("docstring-rewrite",
                                                     "expected-value")


def test_diff_size_counts_changed_lines():
    assert diff_size(EXPECTED_DIFF) == 4
    assert diff_size(TEST_DELETED_DIFF) == 4


def test_a_line_whose_parse_raises_syntax_error_is_unknown_never_guessed():
    # a changed line that raises SyntaxError in _parse_stmt is classified
    # `unknown`, never silently folded into another class
    broken = (
        "diff --git a/tests/test_broken.py b/tests/test_broken.py\n"
        "--- a/tests/test_broken.py\n"
        "+++ b/tests/test_broken.py\n"
        "@@ -1,2 +1,2 @@\n"
        " def test_broken():\n"
        "-    assert values[ == 1\n"
        "+    assert values( == 2\n"
    )
    assert edit_classes(broken) == ("unknown",)


# -- pairing, and the score recorded per pair --------------------------------

def test_a_positive_with_a_same_shape_legitimate_edit_is_paired_and_scored():
    positive = _record("p1")
    twin = _record("t1", label="clean")
    pair = match_twin(positive, [twin], _diffs(("p1", EXPECTED_DIFF),
                                               ("t1", EXPECTED_DIFF)))
    assert pair.positive_id == "p1"
    assert pair.twin_id == "t1"
    assert pair.edit_classes == ("expected-value",)
    assert pair.similarity == 1.0
    linked_positive, linked_twin = pair.linked_records(positive, twin)
    assert linked_positive["twin_id"] == "t1"
    assert linked_positive["similarity"] == pair.similarity
    assert linked_twin["twin_id"] == "p1"
    assert linked_twin["similarity"] == pair.similarity


def test_diff_size_proximity_picks_the_closer_twin():
    positive = _record("p1")
    far = _record("t-far", label="clean")
    near = _record("t-near", label="clean")
    pair = match_twin(positive, [far, near],
                      _diffs(("p1", EXPECTED_DIFF),
                             ("t-far", EXPECTED_DIFF_WIDE),
                             ("t-near", EXPECTED_DIFF_LARGER)))
    assert pair.twin_id == "t-near"
    assert pair.similarity == round(
        size_similarity(diff_size(EXPECTED_DIFF),
                        diff_size(EXPECTED_DIFF_LARGER)), 4)
    assert pair.similarity > MIN_SIMILARITY


# -- never across repositories, never a synthetic record ----------------------

def test_matching_never_pairs_across_repositories():
    positive = _record("p1", repository="https://example.org/fixture/r1")
    cross = _record("t-cross", repository="https://example.org/fixture/r2",
                    label="clean")
    same = _record("t-same", repository="https://example.org/fixture/r1",
                   label="clean")
    pair = match_twin(positive, [cross, same],
                      _diffs(("p1", EXPECTED_DIFF),
                             ("t-cross", EXPECTED_DIFF),
                             ("t-same", EXPECTED_DIFF_LARGER)))
    assert pair.twin_id == "t-same"


def test_a_pool_of_only_other_repositories_is_refused_naming_the_field():
    positive = _record("p1", repository="https://example.org/fixture/r1")
    cross = _record("t-cross", repository="https://example.org/fixture/r2",
                    label="clean")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [cross],
                   _diffs(("p1", EXPECTED_DIFF), ("t-cross", EXPECTED_DIFF)))
    assert "repository" in str(excinfo.value)


def test_matching_never_pairs_a_positive_with_a_synthetic_record():
    positive = _record("p1")
    synthetic = _record("t-synth", label="clean", origin="synthetic")
    legitimate = _record("t-legit", label="clean")
    pair = match_twin(positive, [synthetic, legitimate],
                      _diffs(("p1", EXPECTED_DIFF),
                             ("t-synth", EXPECTED_DIFF),
                             ("t-legit", EXPECTED_DIFF)))
    assert pair.twin_id == "t-legit"


def test_a_pool_of_only_synthetic_records_is_refused_naming_the_field():
    positive = _record("p1")
    synthetic = _record("t-synth", label="clean", origin="synthetic")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [synthetic],
                   _diffs(("p1", EXPECTED_DIFF), ("t-synth", EXPECTED_DIFF)))
    assert "origin" in str(excinfo.value)


def test_a_synthetic_source_category_is_never_a_twin():
    positive = _record("p1")
    synthetic = _record("t-synth", label="clean",
                        source="synthetic: injected tamper")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [synthetic],
                   _diffs(("p1", EXPECTED_DIFF), ("t-synth", EXPECTED_DIFF)))
    assert "source" in str(excinfo.value)


# -- refusals name the field, never a default --------------------------------

def test_a_candidate_that_is_not_legitimate_is_refused():
    positive = _record("p1")
    tampered = _record("t-tampered", label="tampered")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [tampered],
                   _diffs(("p1", EXPECTED_DIFF), ("t-tampered", EXPECTED_DIFF)))
    assert "label" in str(excinfo.value)


def test_a_different_edit_class_is_refused_naming_the_edit():
    positive = _record("p1")
    other = _record("t-other", label="clean")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [other],
                   _diffs(("p1", EXPECTED_DIFF), ("t-other",
                                                  TEST_DELETED_DIFF)))
    assert "edit" in str(excinfo.value)


def test_diff_size_proximity_outside_the_window_is_refused():
    positive = _record("p1")
    huge = _record("t-huge", label="clean")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [huge],
                   _diffs(("p1", EXPECTED_DIFF), ("t-huge", EXPECTED_DIFF_HUGE)))
    assert "similarity" in str(excinfo.value)


def test_a_missing_diff_is_refused_by_name():
    positive = _record("p1")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [], _diffs())
    assert "diff" in str(excinfo.value)


def test_a_candidate_without_a_diff_is_refused_by_name():
    positive = _record("p1")
    twin = _record("t1", label="clean")
    with pytest.raises(TwinError) as excinfo:
        match_twin(positive, [twin], _diffs(("p1", EXPECTED_DIFF)))
    assert "diff" in str(excinfo.value)
