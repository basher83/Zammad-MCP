"""Fixture repository and runner for the version-pins gate in scripts/check-pins.sh."""

import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check-pins.sh"

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


def git(repo: Path, *args: str) -> None:
    """Run a git command in the fixture repository.

    Args:
        repo: Root of the fixture repository.
        *args: Arguments passed to git.

    Raises:
        subprocess.CalledProcessError: If git exits with a nonzero status.
    """
    subprocess.run(["git", *args], cwd=repo, check=True, capture_output=True)


def replace(repo: Path, name: str, old: str, new: str) -> None:
    """Replace text in a fixture file and stage the result.

    Args:
        repo: Root of the fixture repository.
        name: Path of the file, relative to the repository root.
        old: Text to replace.
        new: Replacement text.
    """
    path = repo / name
    path.write_text(path.read_text().replace(old, new))
    git(repo, "add", name)


def make_repo(root: Path) -> Path:
    """Create a git repository whose pins follow every rule.

    Args:
        root: Empty directory to create the repository in.

    Returns:
        The repository root, with every file staged.
    """
    (root / ".github" / "workflows").mkdir(parents=True)
    (root / ".github" / "workflows" / "ci.yml").write_text(WORKFLOW)
    (root / "mise.toml").write_text(MISE_TOML)
    (root / "mise.lock").write_text(MISE_LOCK)
    (root / ".pre-commit-config.yaml").write_text(PRE_COMMIT)
    git(root, "init", "-q")
    git(root, "add", "-A")
    return root


def run_gate(repo: Path) -> subprocess.CompletedProcess[str]:
    """Run the pins gate the way the pre-commit hook does.

    Args:
        repo: Root of the fixture repository.

    Returns:
        The completed process, with stdout and stderr captured as text.
    """
    return subprocess.run(["bash", str(SCRIPT)], cwd=repo, capture_output=True, text=True, check=False)
