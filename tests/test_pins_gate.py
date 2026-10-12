"""Contract tests for the version-pins gate (pre-commit hook and CI) in scripts/check-pins.sh.

Each failure must tell the reader, often an agent, what is wrong, why the rule exists and what to do instead.
"""

import shutil
from collections.abc import Callable
from pathlib import Path

import pytest

from tests.pins_gate_support import git, make_repo, replace, run_gate

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the pins gate is a bash script that reads the git index",
)

WORKFLOW_FILE = ".github/workflows/ci.yml"


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a git repository whose pins follow every rule.

    Args:
        tmp_path: Temporary directory provided by pytest.

    Returns:
        The root of the new repository, with every file staged.
    """
    return make_repo(tmp_path)


def test_repository_that_follows_the_rules_passes(repo: Path) -> None:
    """A clean repository passes and names the pins it checked."""
    result = run_gate(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0.12.23" in result.stdout


def _add_python_version(repo: Path) -> None:
    """Commit a .python-version file to the fixture repository.

    Args:
        repo: Root of the fixture repository.
    """
    (repo / ".python-version").write_text("3.13.16\n")
    git(repo, "add", ".python-version")


def _drop_lockfile(repo: Path) -> None:
    """Remove mise.lock from the fixture repository.

    Args:
        repo: Root of the fixture repository.
    """
    git(repo, "rm", "-q", "-f", "mise.lock")


def _setup_uv_in_yaml_workflow(repo: Path) -> None:
    """Rename the workflow to .yaml and give it a setup-uv step.

    Args:
        repo: Root of the fixture repository.
    """
    git(repo, "mv", WORKFLOW_FILE, ".github/workflows/ci.yaml")
    replace(repo, ".github/workflows/ci.yaml", "jdx/mise-action", "astral-sh/setup-uv")


BREAKS: dict[str, tuple[Callable[[Path], None], str]] = {
    "python-version file": (_add_python_version, ".python-version"),
    "setup-uv step": (lambda r: replace(r, WORKFLOW_FILE, "jdx/mise-action", "astral-sh/setup-uv"), "setup-uv"),
    "setup-uv in .yaml workflow": (_setup_uv_in_yaml_workflow, "ci.yaml"),
    "workflow scan fails": (lambda r: git(r, "rm", "-r", "-q", "-f", ".github"), "cannot scan"),
    "quoted setup-uv step": (
        lambda r: replace(r, WORKFLOW_FILE, "uses: jdx/mise-action@", 'uses: "astral-sh/setup-uv@'),
        "setup-uv",
    ),
    "setup-python step": (
        lambda r: replace(r, WORKFLOW_FILE, "jdx/mise-action", "actions/setup-python"),
        "setup-python",
    ),
    "UV_PYTHON removed": (lambda r: replace(r, "mise.toml", "UV_PYTHON", "# UV_PYTHON"), "UV_PYTHON"),
    "UV_PYTHON wrong value": (
        lambda r: replace(r, "mise.toml", '"{{ tools.python.path }}"', '"/tmp/{{ tools.python.path }}"'),
        "UV_PYTHON",
    ),
    "UV_PYTHON outside [env]": (lambda r: replace(r, "mise.toml", "[env]", "[vars]"), "UV_PYTHON"),
    "lockfile removed": (_drop_lockfile, "mise.lock"),
    "lockfile behind mise.toml": (lambda r: replace(r, "mise.toml", '"3.13.16"', '"3.13.17"'), "mise lock"),
    "tool missing from lockfile": (
        lambda r: replace(r, "mise.toml", 'prek = "0.5.4"', 'prek = "0.5.4"\nfd = "10.5.0"'),
        "fd",
    ),
    "floating tool version": (lambda r: replace(r, "mise.toml", '"0.5.4"', '"latest"'), "prek"),
    "version prefix": (lambda r: replace(r, "mise.toml", '"0.5.4"', '"0"'), "prek"),
    "hook comment drift": (lambda r: replace(r, ".pre-commit-config.yaml", "# 0.12.23", "# 0.12.22"), "uv-pre-commit"),
    "uv hook missing": (
        lambda r: replace(r, ".pre-commit-config.yaml", "astral-sh/uv-pre-commit", "astral-sh/other"),
        "uv-pre-commit",
    ),
    "uv pin missing": (lambda r: replace(r, "mise.toml", 'uv = "0.12.23"', ""), "uv pin"),
}


@pytest.mark.parametrize("name", list(BREAKS))
def test_each_break_fails_with_reason_and_remedy(repo: Path, name: str) -> None:
    """Every broken rule fails and explains what, why and what to do instead."""
    breaker, subject = BREAKS[name]
    breaker(repo)

    result = run_gate(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert subject in result.stdout
    assert "Why:" in result.stdout
    assert "Instead:" in result.stdout
    assert "Do not weaken" in result.stdout


def test_python_version_failure_cites_the_regression(repo: Path) -> None:
    """The .python-version failure names the matrix regression it caused."""
    _add_python_version(repo)

    result = run_gate(repo)

    assert "#387" in result.stdout
    assert "3.10" in result.stdout


def test_untracked_python_version_is_not_blocked(repo: Path) -> None:
    """A local, uncommitted .python-version does not block commits."""
    (repo / ".python-version").write_text("3.12\n")

    result = run_gate(repo)

    assert result.returncode == 0, result.stdout
