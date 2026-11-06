"""The survey has to see the repository it is surveying.

`fp_survey.py` scans each commit's diff with `greenwash.scan.scan_diff`. The
scanner resolves parsed Python files against a repository root, and the survey
used to pass none -- so it parsed every path against whichever checkout the
script was launched from, which is the greenwash source tree. A rule that needs
the file (the AST rules, `error-path-default` among them) was structurally
blind on the surveyed repositories and reported zero.

A zero from an instrument that cannot see is not a measurement. This pins the
instrument: the fixture repository below contains a default-returning handler
and no test, and the survey must report it.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "benchmark"))

import fp_survey  # noqa: E402


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=repo, check=True,
                   capture_output=True, text=True)


def fixture_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "fixture"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "calc.py").write_text(
        "def parse(raw):\n"
        "    try:\n"
        "        return int(raw)\n"
        "    except ValueError:\n"
        "        return 0\n",
        encoding="utf-8")
    git(repo, "add", "calc.py")
    git(repo, "-c", "user.name=test", "-c", "user.email=test@example.com",
        "commit", "-q", "-m", "parse a number")
    return repo


def test_the_survey_parses_the_surveyed_repositorys_files(tmp_path):
    result = fp_survey.survey(fixture_repo(tmp_path), limit=1)
    kinds = [flag["kind"] for flag in result["detail"]]
    assert "error-path-default" in kinds, (
        "the survey reported no error-path-default for a fixture whose handler "
        "returns a default and whose path no test mentions -- it read the file "
        "from the wrong repository")


def test_the_survey_records_the_repository_it_surveyed(tmp_path):
    result = fp_survey.survey(fixture_repo(tmp_path), limit=1)
    assert result["repo"] == "fixture"
    assert result["commits"] == 1
    assert result["real_flags"] == len(result["detail"])
