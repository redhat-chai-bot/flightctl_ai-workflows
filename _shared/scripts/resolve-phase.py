#!/usr/bin/env python3
"""Phase override resolution for ai-workflows.

Resolves the skill file for a workflow phase, checking for a
project-level override before falling back to the workflow's built-in
default.  This replaces the ~200-token AI recipe evaluation on every
phase dispatch with a deterministic file-existence check.

Usage:
  resolve-phase.py <WORKFLOW> <PHASE_FILE>

Arguments:
  WORKFLOW     Workflow name (e.g., bugfix, design, docs-writer)
  PHASE_FILE   Skill filename to resolve (e.g., assess.md, gather-context.md)

Output:
  Prints the resolved path to stdout.
  If an override exists at .workflows/{WORKFLOW}/skills/{PHASE_FILE}
  (relative to the current directory), prints that path.
  Otherwise prints the built-in default path.

Exit codes:
  0 -- success (path printed to stdout)
  1 -- missing argument or resolution failure
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import NoReturn


# ---------------------------------------------------------------------------
# Exit codes
# ---------------------------------------------------------------------------

EXIT_SUCCESS = 0
EXIT_ARG_ERROR = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def info(msg: str) -> None:
    """Print an informational message to stderr."""
    print(f"INFO: {msg}", file=sys.stderr)


def fail(msg: str, code: int = EXIT_ARG_ERROR) -> NoReturn:
    """Print an error message to stderr and exit."""
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(code)


# ---------------------------------------------------------------------------
# Resolution logic
# ---------------------------------------------------------------------------

def resolve_phase(workflow: str, phase_file: str) -> str:
    """Resolve the skill file path for a workflow phase.

    Checks for a project-level override at
    ``.workflows/{workflow}/skills/{phase_file}`` relative to the current
    working directory.  If the override exists, returns that path.
    Otherwise returns the built-in default path, resolved relative to
    this script's location in the ai-workflows repository.

    Args:
        workflow: Workflow name (e.g., 'bugfix', 'design').
        phase_file: Skill filename (e.g., 'assess.md').

    Returns:
        The resolved file path as a string.

    Raises:
        SystemExit: If the built-in fallback cannot be located.
    """
    # Check for project-level override
    override_path = Path(".workflows") / workflow / "skills" / phase_file
    if override_path.is_file():
        info(f"Using project override: {workflow}/{phase_file}.")
        return str(override_path)

    # Fall back to built-in default
    # This script is at _shared/scripts/resolve-phase.py
    # Built-in phases are at {WORKFLOW}/skills/{PHASE_FILE} from repo root
    # Relative to this script: ../../{WORKFLOW}/skills/{PHASE_FILE}
    script_dir = Path(__file__).resolve().parent
    repo_root = script_dir.parent.parent
    builtin_path = repo_root / workflow / "skills" / phase_file

    if not builtin_path.is_file():
        fail(f"Built-in phase not found: {workflow}/skills/{phase_file}")

    return str(builtin_path)


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        description="Resolve a workflow phase skill file, checking for "
                    "project-level overrides before falling back to the "
                    "built-in default.",
    )
    parser.add_argument(
        "workflow",
        help="Workflow name (e.g., bugfix, design, docs-writer)",
    )
    parser.add_argument(
        "phase_file",
        help="Skill filename to resolve (e.g., assess.md, "
             "gather-context.md)",
    )
    return parser


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    """Parse arguments and resolve the phase file path."""
    parser = build_parser()
    args = parser.parse_args(argv)

    resolved = resolve_phase(args.workflow, args.phase_file)
    print(resolved)
    return EXIT_SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
