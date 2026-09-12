#!/usr/bin/env python3
"""Tests for _shared/scripts/resolve-phase.py."""

from __future__ import annotations

import importlib.util
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

_SCRIPT = Path(__file__).resolve().parent / "resolve-phase.py"
_spec = importlib.util.spec_from_file_location("resolve_phase", _SCRIPT)
assert _spec and _spec.loader
resolve_phase = importlib.util.module_from_spec(_spec)
sys.modules["resolve_phase"] = resolve_phase
_spec.loader.exec_module(resolve_phase)


# ---------------------------------------------------------------------------
# Argument parsing tests
# ---------------------------------------------------------------------------


class TestParseArgs(unittest.TestCase):
    """Verify argparse configuration."""

    def test_basic_args(self) -> None:
        """Positional arguments are parsed correctly."""
        parser = resolve_phase.build_parser()
        args = parser.parse_args(["bugfix", "assess.md"])
        self.assertEqual(args.workflow, "bugfix")
        self.assertEqual(args.phase_file, "assess.md")

    def test_workflow_with_hyphens(self) -> None:
        """Workflow names with hyphens are parsed correctly."""
        parser = resolve_phase.build_parser()
        args = parser.parse_args(["docs-writer", "gather-context.md"])
        self.assertEqual(args.workflow, "docs-writer")
        self.assertEqual(args.phase_file, "gather-context.md")

    def test_missing_workflow(self) -> None:
        """Missing workflow argument exits with code 2."""
        parser = resolve_phase.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args([])
        self.assertEqual(ctx.exception.code, 2)

    def test_missing_phase_file(self) -> None:
        """Missing phase_file argument exits with code 2."""
        parser = resolve_phase.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["bugfix"])
        self.assertEqual(ctx.exception.code, 2)

    def test_extra_args_rejected(self) -> None:
        """Extra positional arguments are rejected."""
        parser = resolve_phase.build_parser()
        with self.assertRaises(SystemExit) as ctx:
            parser.parse_args(["bugfix", "assess.md", "extra"])
        self.assertEqual(ctx.exception.code, 2)


# ---------------------------------------------------------------------------
# Exit code contract tests
# ---------------------------------------------------------------------------


class TestExitCodes(unittest.TestCase):
    """Verify the documented exit code contract."""

    def test_exit_code_constants(self) -> None:
        """Exit code constants match the documented contract."""
        self.assertEqual(resolve_phase.EXIT_SUCCESS, 0)
        self.assertEqual(resolve_phase.EXIT_ARG_ERROR, 1)


# ---------------------------------------------------------------------------
# Resolution logic tests
# ---------------------------------------------------------------------------


class TestResolvePhaseOverride(unittest.TestCase):
    """Verify override detection: .workflows/{WORKFLOW}/skills/{PHASE_FILE}."""

    def test_override_found(self) -> None:
        """When an override file exists, its path is returned."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create the override file
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            override_file = override_dir / "assess.md"
            override_file.write_text("# Custom assess phase\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(
                    result,
                    str(Path(".workflows") / "bugfix" / "skills" / "assess.md"),
                )
            finally:
                os.chdir(original_cwd)

    def test_override_info_message(self) -> None:
        """Override resolution prints an INFO message to stderr."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "design" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "draft.md").write_text("# Custom\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf):
                    resolve_phase.resolve_phase("design", "draft.md")
                self.assertIn(
                    "Using project override: design/draft.md",
                    buf.getvalue(),
                )
            finally:
                os.chdir(original_cwd)

    def test_no_override_directory(self) -> None:
        """When .workflows/ does not exist, falls back to built-in."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                # resolve_phase will look for a built-in; mock is_file
                # to verify it falls through the override check
                with mock.patch.object(
                    Path, "is_file",
                    side_effect=lambda self=None: (  # type: ignore[assignment]
                        False  # override doesn't exist
                    ),
                ):
                    # This will try the built-in and also get False
                    # -> fail() is called
                    with self.assertRaises(SystemExit):
                        resolve_phase.resolve_phase("bugfix", "assess.md")
            finally:
                os.chdir(original_cwd)


class TestResolvePhaseBuiltin(unittest.TestCase):
    """Verify built-in fallback resolution."""

    def test_builtin_fallback(self) -> None:
        """When no override exists, the built-in path is returned."""
        # The script lives at _shared/scripts/resolve-phase.py
        # Built-in phases are at {repo_root}/{workflow}/skills/{phase_file}
        # Use a real workflow/phase that exists in the repo
        script_dir = Path(__file__).resolve().parent
        repo_root = script_dir.parent.parent

        # Verify a known built-in exists (bugfix/skills/assess.md)
        builtin = repo_root / "bugfix" / "skills" / "assess.md"
        self.assertTrue(
            builtin.is_file(),
            f"Expected built-in at {builtin}",
        )

        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                self.assertEqual(result, str(builtin))
            finally:
                os.chdir(original_cwd)

    def test_builtin_not_found_exits_1(self) -> None:
        """Missing built-in phase exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.resolve_phase(
                        "nonexistent-workflow", "nonexistent.md",
                    )
                self.assertEqual(
                    ctx.exception.code, resolve_phase.EXIT_ARG_ERROR,
                )
            finally:
                os.chdir(original_cwd)

    def test_builtin_error_message(self) -> None:
        """Missing built-in prints an ERROR message with the phase path."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stderr", buf):
                    with self.assertRaises(SystemExit):
                        resolve_phase.resolve_phase("nope", "nope.md")
                err = buf.getvalue()
                self.assertIn("ERROR:", err)
                self.assertIn("nope/skills/nope.md", err)
            finally:
                os.chdir(original_cwd)


class TestResolvePhaseOverridePriority(unittest.TestCase):
    """Verify that override takes priority over built-in."""

    def test_override_preferred_over_builtin(self) -> None:
        """Override path is returned even when built-in also exists."""
        with tempfile.TemporaryDirectory() as tmp:
            # Create the override file
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                result = resolve_phase.resolve_phase("bugfix", "assess.md")
                # Should return the override, not the built-in
                self.assertTrue(
                    result.startswith(".workflows"),
                    f"Expected override path, got: {result}",
                )
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# End-to-end main() tests
# ---------------------------------------------------------------------------


class TestMain(unittest.TestCase):
    """Verify main() end-to-end behaviour."""

    def test_main_prints_builtin_path(self) -> None:
        """main() prints the resolved path to stdout and exits 0."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = resolve_phase.main(["bugfix", "assess.md"])
                self.assertEqual(code, 0)
                output = buf.getvalue().strip()
                self.assertIn("bugfix", output)
                self.assertIn("assess.md", output)
            finally:
                os.chdir(original_cwd)

    def test_main_prints_override_path(self) -> None:
        """main() prints the override path when it exists."""
        with tempfile.TemporaryDirectory() as tmp:
            override_dir = Path(tmp) / ".workflows" / "bugfix" / "skills"
            override_dir.mkdir(parents=True)
            (override_dir / "assess.md").write_text("# Override\n")

            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                buf = io.StringIO()
                with mock.patch("sys.stdout", buf):
                    code = resolve_phase.main(["bugfix", "assess.md"])
                self.assertEqual(code, 0)
                output = buf.getvalue().strip()
                self.assertEqual(
                    output,
                    str(Path(".workflows/bugfix/skills/assess.md")),
                )
            finally:
                os.chdir(original_cwd)

    def test_main_missing_args_exits_2(self) -> None:
        """main() with no arguments exits with code 2 (argparse)."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.main([])
        self.assertEqual(ctx.exception.code, 2)

    def test_main_nonexistent_workflow_exits_1(self) -> None:
        """main() with a nonexistent workflow exits with code 1."""
        with tempfile.TemporaryDirectory() as tmp:
            original_cwd = os.getcwd()
            try:
                os.chdir(tmp)
                with self.assertRaises(SystemExit) as ctx:
                    resolve_phase.main([
                        "nonexistent-workflow", "nonexistent.md",
                    ])
                self.assertEqual(
                    ctx.exception.code, resolve_phase.EXIT_ARG_ERROR,
                )
            finally:
                os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Helper function tests
# ---------------------------------------------------------------------------


class TestHelpers(unittest.TestCase):
    """Verify helper functions."""

    def test_info_writes_to_stderr(self) -> None:
        """info() writes an INFO-prefixed message to stderr."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            resolve_phase.info("test message")
        self.assertIn("INFO: test message", buf.getvalue())

    def test_fail_exits_with_code(self) -> None:
        """fail() exits with the specified code."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.fail("something broke", code=1)
        self.assertEqual(ctx.exception.code, 1)

    def test_fail_writes_to_stderr(self) -> None:
        """fail() writes an ERROR-prefixed message to stderr."""
        buf = io.StringIO()
        with mock.patch("sys.stderr", buf):
            with self.assertRaises(SystemExit):
                resolve_phase.fail("bad thing")
        self.assertIn("ERROR: bad thing", buf.getvalue())

    def test_fail_default_code(self) -> None:
        """fail() defaults to EXIT_ARG_ERROR."""
        with self.assertRaises(SystemExit) as ctx:
            resolve_phase.fail("error")
        self.assertEqual(ctx.exception.code, resolve_phase.EXIT_ARG_ERROR)


if __name__ == "__main__":
    unittest.main()
