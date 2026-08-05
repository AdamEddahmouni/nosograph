#!/usr/bin/env python3
"""Static audit for stale/dead internal imports in the med_research package.

Scans every ``.py`` file under ``src/med_research/`` and ``tests/`` and
verifies two things about every import that references a med_research module:

1. **Module-level check** — the imported module resolves to a real file
   (``foo.py`` or ``foo/__init__.py``). Catches references to modules that
   were archived or renamed during the v1 -> v2 migration.

2. **Name-level check** — every name imported via ``from X import name`` is
   actually defined in ``X`` (or re-exported by one of its packages, with
   ``__all__`` respected). Catches APIs that moved from classes to functions
   (e.g. ``DrugRepurposingEngine`` -> ``score_candidates``).

The audit is **pure AST** — nothing is imported, so it is fast, has no side
effects (no caches touched, no network), and does not require the package to
be installed. Third-party imports are skipped.

Known limitations (permissive — never false-positives on the current tree):
- Names exported only through dynamic mechanisms (module-level ``__getattr__``,
  ``globals().update(...)``, or a non-literal ``__all__``) are not recognized.
- An *internal* import wrapped in ``try/except ImportError`` (an optional
  internal module) would be reported as missing. The tree's 29 fallback
  imports all target third-party packages, so they are skipped correctly.

Usage::

    python scripts/check_imports.py             # check default roots
    python scripts/check_imports.py --root .    # explicit repo root
    python scripts/check_imports.py --verbose   # per-file summary

Exit codes::

    0  no stale references
    1  stale references found (CI fails)
    2  script error (root missing, etc.)
"""
from __future__ import annotations

import argparse
import ast
import pathlib
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parent.parent


class ImportAuditor:
    """Finds stale internal imports across the configured source roots."""

    def __init__(self, repo_root: pathlib.Path, verbose: bool = False) -> None:
        self.root = repo_root
        self.roots = {
            "med_research": repo_root / "src" / "med_research",
            "tests": repo_root / "tests",
        }
        self.verbose = verbose
        self.errors: list[str] = []
        self.imports_checked = 0
        self.files_checked = 0
        self._src_cache: dict[str, ast.Module | None] = {}

    # ── module → file mapping ────────────────────────────────────────────

    def module_file(self, module: str) -> pathlib.Path | None:
        """Return the file implementing *module*, or None if not under our roots."""
        top = module.split(".", 1)[0]
        root = self.roots.get(top)
        if root is None:
            return None  # external module — not auditable
        rel = module[len(top):].lstrip(".")
        base = root / rel.replace(".", "/") if rel else root
        for candidate in (base.with_suffix(".py"), base / "__init__.py"):
            if candidate.is_file():
                return candidate
        return None

    def module_name_of(self, path: pathlib.Path) -> str:
        """Dotted module name for a file inside one of the audited roots."""
        for prefix, root in self.roots.items():
            try:
                rel = path.relative_to(root)
            except ValueError:
                continue
            parts = list(rel.with_suffix("").parts)
            if parts and parts[-1] == "__init__":
                parts = parts[:-1]  # __init__.py belongs to the package itself
            return ".".join([prefix, *parts])
        return ""

    def module_src(self, module: str) -> ast.Module | None:
        """Parse (and cache) the AST for *module*; None if not in our roots."""
        if module in self._src_cache:
            return self._src_cache[module]
        path = self.module_file(module)
        if path is None:
            self._src_cache[module] = None
            return None
        try:
            src = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            src = None
        self._src_cache[module] = src
        return src

    def is_package(self, module: str) -> bool:
        path = self.module_file(module)
        return bool(path and path.name == "__init__.py")

    def display_path(self, path: pathlib.Path) -> str:
        """Repo-relative path for readable CI output."""
        try:
            return str(path.relative_to(self.root))
        except ValueError:
            return str(path)

    # ── relative import resolution ───────────────────────────────────────

    @staticmethod
    def resolve_relative(package: str, level: int, tail: str) -> str:
        """Resolve a PEP 328 relative import to an absolute dotted module.

        ``package`` is the dotted package the import statement lives in
        (for ``__init__.py`` files this is the module itself).
        ``level`` is the number of leading dots; ``tail`` is the suffix
        after the dots (empty for ``from . import x``).
        """
        parts = package.split(".") if package else []
        drop = max(level - 1, 0)
        if drop >= len(parts):
            return ""
        base = ".".join(parts[: len(parts) - drop])
        return f"{base}.{tail}" if tail else base

    # ── definition discovery ─────────────────────────────────────────────

    @staticmethod
    def _target_names(node: ast.AST) -> set[str]:
        """Names bound by an assignment-style node."""
        if isinstance(node, ast.Name):
            return {node.id}
        if isinstance(node, (ast.Tuple, ast.List)):
            names: set[str] = set()
            for elt in node.elts:
                names |= ImportAuditor._target_names(elt)
            return names
        if isinstance(node, ast.Starred):
            return ImportAuditor._target_names(node.value)
        return set()

    @classmethod
    def find_defining_node(cls, body: list[ast.stmt], name: str):
        """Find the top-level statement defining *name*.

        Returns ``("def", ...)`` for direct definitions, ``("reexport", orig, node)``
        for ``from X import orig as name``, or None. Conditional blocks
        (``if TYPE_CHECKING:``, ``try/except ImportError`` fallbacks, ``else``
        branches) are traversed so guarded definitions are treated as valid.
        """
        for node in body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and node.name == name:
                return ("def", name, node)
            if isinstance(node, (ast.Assign, ast.AnnAssign, ast.AugAssign)):
                targets = node.targets if isinstance(node, ast.Assign) else [node.target]
                if any(name in cls._target_names(t) for t in targets):
                    return ("def", name, node)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if (alias.asname or alias.name.split(".", 1)[0]) == name:
                        return ("def", name, node)
            if isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    if alias.name != "*" and (alias.asname or alias.name) == name:
                        return ("reexport", alias.name, node)
            if isinstance(node, ast.If):
                found = cls.find_defining_node([*node.body, *node.orelse], name)
                if found:
                    return found
            if isinstance(node, (ast.Try, getattr(ast, "TryStar", ast.Try))):
                branches = [node.body, node.orelse, node.finalbody, *[h.body for h in node.handlers]]
                for branch in branches:
                    found = cls.find_defining_node(branch, name)
                    if found:
                        return found
        return None

    @classmethod
    def module_all(cls, src: ast.Module) -> set[str] | None:
        """Names listed in a top-level literal ``__all__``, if present."""
        for node in src.body:
            if not isinstance(node, ast.Assign):
                continue
            is_all = any(isinstance(t, ast.Name) and t.id == "__all__" for t in node.targets)
            if is_all and isinstance(node.value, (ast.List, ast.Tuple, ast.Set)):
                return {
                    elt.value
                    for elt in node.value.elts
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                }
        return None

    # ── name-level resolution ────────────────────────────────────────────

    def name_defined(self, module: str, orig_name: str, stack: frozenset) -> bool:
        """True if *orig_name* is defined in *module* (following re-exports)."""
        key = (module, orig_name)
        if key in stack:
            return True  # re-export cycle — assume resolved
        if self.is_package(module) and self.module_file(f"{module}.{orig_name}") is not None:
            return True  # ``from package import submodule`` needs no re-export
        src = self.module_src(module)
        if src is None:
            return True  # external module — not auditable
        found = self.find_defining_node(src.body, orig_name)
        if found is None:
            all_names = self.module_all(src)
            return all_names is not None and orig_name in all_names
        kind, orig, node = found
        if kind == "def":
            return True
        # re-export: from <X> import <orig>. For relative imports the leading
        # dots live in ``node.level``, not in ``node.module``.
        if node.module is None:  # ``from . import orig`` → submodule or attribute
            sub = f"{module}.{orig}"
            if self.module_file(sub) is not None:
                return True
            return self.name_defined(module, orig, stack | {key})
        if node.level:
            tail = node.module or ""
            package = module if self.is_package(module) else module.rsplit(".", 1)[0]
            target = self.resolve_relative(package, node.level, tail)
        else:
            target = node.module or ""  # absolute re-export
        if self.module_file(target) is None:
            return True  # re-export from an external module
        return self.name_defined(target, orig, stack | {key})

    # ── scanning ─────────────────────────────────────────────────────────

    def run(self) -> int:
        for root in self.roots.values():
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*.py")):
                self._scan_file(path)
        self._print_report()
        return 1 if self.errors else 0

    def _scan_file(self, path: pathlib.Path) -> None:
        try:
            src = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError) as exc:
            self.errors.append(f"{self.display_path(path)}: cannot parse: {exc}")
            return
        module = self.module_name_of(path)
        if not module:
            return
        self._src_cache[module] = src
        self.files_checked += 1
        package = module if path.name == "__init__.py" else module.rsplit(".", 1)[0]
        for node in ast.walk(src):  # includes lazy imports inside functions
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                self._check_from(package, node, path)
            elif isinstance(node, ast.ImportFrom):  # ``from . import x``
                self._check_from_dot(package, node, path)
            elif isinstance(node, ast.Import):
                self._check_import(node, path)
        if self.verbose:
            print(f"  checked {self.display_path(path)}")

    def _check_from(self, package: str, node: ast.ImportFrom, path: pathlib.Path) -> None:
        assert node.module is not None
        # For relative imports the leading dots are encoded in node.level, so
        # node.module is already the dot-free suffix.
        target = self.resolve_relative(package, node.level, node.module) if node.level else node.module
        file = self.module_file(target)
        if file is None:
            if target.split(".", 1)[0] in self.roots:
                self.errors.append(f"{self.display_path(path)}:{node.lineno}: stale import: module '{target}' does not exist")
            return  # external module — nothing more to verify
        for alias in node.names:
            if alias.name == "*":
                continue
            self.imports_checked += 1
            if not self.name_defined(target, alias.name, frozenset()):
                self.errors.append(
                    f"{self.display_path(path)}:{node.lineno}: stale import: '{alias.name}' is not defined in '{target}'"
                )

    def _check_from_dot(self, package: str, node: ast.ImportFrom, path: pathlib.Path) -> None:
        # ``from . import x`` — x may be a submodule or a package attribute
        target = self.resolve_relative(package, node.level, "")
        for alias in node.names:
            if alias.name == "*":
                continue
            self.imports_checked += 1
            sub = f"{target}.{alias.name}"
            if self.module_file(sub) is not None:
                continue
            if target and target.split(".", 1)[0] in self.roots and not self.name_defined(
                target, alias.name, frozenset()
            ):
                self.errors.append(
                    f"{self.display_path(path)}:{node.lineno}: stale import: '{alias.name}' is neither a submodule of "
                    f"'{target}' nor defined there"
                )

    def _check_import(self, node: ast.Import, path: pathlib.Path) -> None:
        for alias in node.names:
            if alias.name.split(".", 1)[0] not in self.roots:
                continue  # external module — exact top-level component match
            self.imports_checked += 1
            if self.module_file(alias.name) is None:
                self.errors.append(f"{self.display_path(path)}:{node.lineno}: stale import: module '{alias.name}' does not exist")

    def _print_report(self) -> None:
        if not self.errors:
            print(
                f"OK: {self.imports_checked} internal imports across "
                f"{self.files_checked} files — no stale references"
            )
            return
        print(f"FAILED: {len(self.errors)} stale reference(s):")
        for error in sorted(self.errors):
            print(f"  {error}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="check_imports",
        description="Audit med_research sources for stale/dead internal imports.",
    )
    parser.add_argument(
        "--root",
        type=pathlib.Path,
        default=REPO_ROOT,
        help="repository root (default: parent of this script)",
    )
    parser.add_argument("--verbose", action="store_true", help="print every file as it is scanned")
    args = parser.parse_args(argv)

    if not (args.root / "src" / "med_research").is_dir():
        print(f"error: '{args.root}' does not look like a repo root (no src/med_research)", file=sys.stderr)
        return 2

    return ImportAuditor(args.root, verbose=args.verbose).run()


if __name__ == "__main__":
    sys.exit(main())
