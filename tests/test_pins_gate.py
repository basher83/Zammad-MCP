"""Contract tests for the version-pins gate (pre-commit hook and CI) in scripts/check-pins.sh.

Each failure must tell the reader, often an agent, what is wrong, why the rule exists and what to do instead.
"""

import shutil
import subprocess
from collections.abc import Callable
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-pins.sh"

pytestmark = pytest.mark.skipif(
    shutil.which("bash") is None or shutil.which("git") is None,
    reason="the pins gate is a bash script that reads the git index",
)

MISE_TOML = """[tools]
python = "3.13.16"
uv = "0.12.23"
prek = "0.5.4"

[env]
UV_PYTHON = { value = "{{ tools.python.path }}", tools = true }
"""

MISE_LOCK = """[[tools.python]]
version = "3.13.16"

[[tools.uv]]
version = "0.12.23"

[[tools.prek]]
version = "0.5.4"
"""

PRE_COMMIT = """repos:
  - repo: https://github.com/astral-sh/uv-pre-commit
    rev: "a1785f8e81fe9936d828bef574e6db07e8c8c374"  # 0.12.23
"""

WORKFLOW = """jobs:
  validate:
    steps:
      - uses: jdx/mise-action@2d8d4cafcbd33be2ea37d2b6f5ad595363d1f1ca # v5.1.1
"""


def _git(repo: Path, *args: str) -> None:
    """Run a git command in the fixture repository.

    Args:
        repo: Root of the fixture repository.
        *args: Arguments passed to git.

    Raises:
        subprocess.CalledProcessError: If git exits with a nonzero status.
    """
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def _replace(repo: Path, name: str, old: str, new: str) -> None:
    """Replace text in a fixture file and stage the result.

    Args:
        repo: Root of the fixture repository.
        name: Path of the file, relative to the repository root.
        old: Text to replace.
        new: Replacement text.
    """
    path = repo / name
    path.write_text(path.read_text().replace(old, new))
    _git(repo, "add", name)


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    """Create a git repository whose pins follow every rule.

    Args:
        tmp_path: Temporary directory provided by pytest.

    Returns:
        The root of the new repository, with every file staged.
    """
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text(WORKFLOW)
    (tmp_path / "mise.toml").write_text(MISE_TOML)
    (tmp_path / "mise.lock").write_text(MISE_LOCK)
    (tmp_path / ".pre-commit-config.yaml").write_text(PRE_COMMIT)
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", "-A")
    return tmp_path


def _run_gate(repo: Path) -> subprocess.CompletedProcess[str]:
    """Run the pins gate the way the pre-commit hook does.

    Args:
        repo: Root of the fixture repository.

    Returns:
        The completed process, with stdout and stderr captured as text.
    """
    return subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True, check=False)


def test_repository_that_follows_the_rules_passes(repo: Path) -> None:
    """A clean repository passes and names the pins it checked."""
    result = _run_gate(repo)

    assert result.returncode == 0, result.stdout + result.stderr
    assert "0.12.23" in result.stdout


def _add_python_version(repo: Path) -> None:
    """Commit a .python-version file to the fixture repository.

    Args:
        repo: Root of the fixture repository.
    """
    (repo / ".python-version").write_text("3.13.16\n")
    _git(repo, "add", ".python-version")


def _drop_lockfile(repo: Path) -> None:
    """Remove mise.lock from the fixture repository.

    Args:
        repo: Root of the fixture repository.
    """
    _git(repo, "rm", "-q", "-f", "mise.lock")


BREAKS: dict[str, tuple[Callable[[Path], None], str]] = {
    "python-version file": (_add_python_version, ".python-version"),
    "setup-uv step": (
        lambda r: _replace(r, ".github/workflows/ci.yml", "jdx/mise-action", "astral-sh/setup-uv"),
        "setup-uv",
    ),
    "setup-python step": (
        lambda r: _replace(r, ".github/workflows/ci.yml", "jdx/mise-action", "actions/setup-python"),
        "setup-python",
    ),
    "UV_PYTHON removed": (lambda r: _replace(r, "mise.toml", "UV_PYTHON", "# UV_PYTHON"), "UV_PYTHON"),
    "UV_PYTHON wrong value": (
        lambda r: _replace(r, "mise.toml", '"{{ tools.python.path }}"', '"/tmp/{{ tools.python.path }}"'),
        "UV_PYTHON",
    ),
    "lockfile removed": (_drop_lockfile, "mise.lock"),
    "lockfile behind mise.toml": (lambda r: _replace(r, "mise.toml", '"3.13.16"', '"3.13.17"'), "mise lock"),
    "tool missing from lockfile": (
        lambda r: _replace(r, "mise.toml", 'prek = "0.5.4"', 'prek = "0.5.4"\nfd = "10.5.0"'),
        "fd",
    ),
    "floating tool version": (lambda r: _replace(r, "mise.toml", '"0.5.4"', '"latest"'), "prek"),
    "version prefix": (lambda r: _replace(r, "mise.toml", '"0.5.4"', '"0"'), "prek"),
    "hook comment drift": (lambda r: _replace(r, ".pre-commit-config.yaml", "# 0.12.23", "# 0.12.22"), "uv-pre-commit"),
    "uv hook missing": (
        lambda r: _replace(r, ".pre-commit-config.yaml", "astral-sh/uv-pre-commit", "astral-sh/other"),
        "uv-pre-commit",
    ),
    "uv pin missing": (lambda r: _replace(r, "mise.toml", 'uv = "0.12.23"', ""), "uv pin"),
}


@pytest.mark.parametrize("name", list(BREAKS))
def test_each_break_fails_with_reason_and_remedy(repo: Path, name: str) -> None:
    """Every broken rule fails and explains what, why and what to do instead."""
    breaker, subject = BREAKS[name]
    breaker(repo)

    result = _run_gate(repo)

    assert result.returncode == 1, result.stdout + result.stderr
    assert subject in result.stdout
    assert "Why:" in result.stdout
    assert "Instead:" in result.stdout
    assert "Do not weaken" in result.stdout


def test_python_version_failure_cites_the_regression(repo: Path) -> None:
    """The .python-version failure names the matrix regression it caused."""
    _add_python_version(repo)

    result = _run_gate(repo)

    assert "#387" in result.stdout
    assert "3.10" in result.stdout


def test_untracked_python_version_is_not_blocked(repo: Path) -> None:
    """A local, uncommitted .python-version does not block commits."""
    (repo / ".python-version").write_text("3.12\n")

    result = _run_gate(repo)

    assert result.returncode == 0, result.stdout
