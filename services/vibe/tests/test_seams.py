"""Architecture guardrails: the seams that make scaling a change, not a rewrite.

Each test fails when someone re-introduces a shortcut, and each one proves it can
fail by scanning a planted offender it builds itself. A green run with no control
would only prove the scanner is broken.

These are the R6 guardrails (plan section 11). Zero allowlist entries: a real
offender is moved behind its seam, never excused here.

Coordination note for the owner_id migration (R6-T1): a schema default may be
written inside the DDL text, as the plan's DEFAULT 'local' does, or bound from
auth.LOOPBACK_OWNER_ID. A bare Python "local" literal in store/ or events/ trips
test_identity_comes_from_the_principal_not_a_literal, and that is the point:
identity has exactly one home.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src" / "vibe"
_ROUTES = SRC / "api" / "routes"
_PROTOCOL_MODULE = "vibe.executor.base"
_CONCRETE_CLASS = re.compile(r"^[A-Z]\w*Executor$")


def _modules(root: Path) -> list[Path]:
    return sorted(p for p in root.rglob("*.py") if "__pycache__" not in p.parts)


def _rel(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def concrete_executor_importers(root: Path) -> list[str]:
    """Modules naming a concrete executor instead of depending on the protocol.

    Everything under executor/ owns the implementations, and container.py is the
    composition root -- the one place allowed to choose one. Anywhere else the
    dependency has to be Executor, or swapping executors stops being a one-file
    change.
    """
    offenders: list[str] = []
    for path in _modules(root):
        rel = _rel(path, root)
        if rel.startswith("executor/") or path.name == "container.py":
            continue
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.ImportFrom) and node.module:
                if node.module.startswith("vibe.executor.") and node.module != _PROTOCOL_MODULE:
                    names = [a.name for a in node.names if a.name.endswith("Executor")]
                    if names:
                        offenders.append(f"{rel}:{node.lineno} imports {node.module}")
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("vibe.executor.") and alias.name != _PROTOCOL_MODULE:
                        offenders.append(f"{rel}:{node.lineno} imports {alias.name}")
    return offenders


def named_concrete_executors(tree: ast.Module) -> list[str]:
    """CamelCase executor class names referenced anywhere in a module."""
    found: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and _CONCRETE_CLASS.match(node.id):
            found.append(f"{node.lineno}:{node.id}")
        elif isinstance(node, ast.Attribute) and _CONCRETE_CLASS.match(node.attr):
            found.append(f"{node.lineno}:{node.attr}")
    return found


def identity_literals(root: Path, *, skip_auth: bool = True) -> list[str]:
    """Bare "local" string constants, which is a hard-coded identity."""
    offenders: list[str] = []
    for path in _modules(root):
        if skip_auth and path.name == "auth.py":
            continue
        for node in ast.walk(_parse(path)):
            if isinstance(node, ast.Constant) and node.value == "local":
                offenders.append(f"{_rel(path, root)}:{node.lineno}")
    return offenders


# --- R6-T3 (L-3): the executor stays a protocol -----------------------------


def test_only_the_container_imports_a_concrete_executor(tmp_path: Path) -> None:
    (tmp_path / "leaky.py").write_text(
        "from vibe.executor.local import LocalSubprocessExecutor\n", encoding="utf-8"
    )
    assert concrete_executor_importers(tmp_path) == ["leaky.py:1 imports vibe.executor.local"]
    assert concrete_executor_importers(SRC) == []


def test_routes_never_name_a_concrete_executor() -> None:
    control = ast.parse("ex = LocalSubprocessExecutor(workspace=w)\n")
    assert named_concrete_executors(control) == ["1:LocalSubprocessExecutor"]
    offenders = [
        f"{_rel(path, _ROUTES)}:{hit}"
        for path in _modules(_ROUTES)
        for hit in named_concrete_executors(_parse(path))
    ]
    assert offenders == []


def test_the_local_executor_satisfies_the_protocol() -> None:
    from vibe.executor.base import Executor
    from vibe.executor.local import LocalSubprocessExecutor

    members = sorted(m for m in dir(Executor) if not m.startswith("_"))
    assert members, "the protocol is empty -- this test would pass vacuously"
    missing = [m for m in members if not hasattr(LocalSubprocessExecutor, m)]
    assert missing == []


# --- R6-T4 (L-4): identity is read only from the principal ------------------


def test_identity_comes_from_the_principal_not_a_literal(tmp_path: Path) -> None:
    (tmp_path / "route.py").write_text('principal = Principal(id="local")\n', encoding="utf-8")
    assert identity_literals(tmp_path) == ["route.py:1"]
    # auth.py is the one allowed home, and the scanner sees the literal there --
    # otherwise an empty result below could just mean a blind scanner.
    in_auth = identity_literals(SRC, skip_auth=False)
    assert len(in_auth) == 1, f"expected exactly one literal (auth.py's constant): {in_auth}"
    assert in_auth[0].startswith("auth.py:")
    assert identity_literals(SRC) == []


# --- R6-T2 (L-2): SQL lives inside the store providers ----------------------
#
# The store providers are the two modules that own sqlite in this app: store.py
# (sessions) and events.py (the event log). Everything else talks to them through
# SessionStore/EventStore, which is what lets a different backing store drop in
# without touching a route, a service or the runtime. A stray "SELECT" in a
# handler is the first thread of a rewrite, so it fails here instead.

_STORE_PROVIDERS = {"store.py", "events.py"}

def _normalize(text: str) -> str:
    """Collapse whitespace so one statement has one shape.

    Without this the same query written across two source lines reads as a
    different string, and a log message like "could not update %s: %s" reads as
    an UPDATE. That is why every pattern below also demands a table name -- and
    for UPDATE, a SET clause -- so a statement matches and an English word does
    not.
    """
    return " ".join(text.split())


# A SQL statement, not the word: "could not update %s" is a log message, while
# "UPDATE sessions SET ..." is SQL that only the store providers may own.
_SQL = re.compile(
    r"(SELECT .+ FROM |INSERT INTO [A-Za-z_]|UPDATE [A-Za-z_][A-Za-z0-9_.]* SET "
    r"|DELETE FROM [A-Za-z_]|CREATE TABLE [A-Za-z_]|ALTER TABLE [A-Za-z_]"
    r"|DROP TABLE [A-Za-z_]|CREATE (UNIQUE )?INDEX [A-Za-z_])",
    re.IGNORECASE,
)

# Schema shape changes: the narrower rule R6-T8 enforces.
_DDL = re.compile(
    r"(CREATE TABLE [A-Za-z_]|ALTER TABLE [A-Za-z_]|DROP TABLE [A-Za-z_]"
    r"|CREATE (UNIQUE )?INDEX [A-Za-z_])",
    re.IGNORECASE,
)


def sql_sites(root: Path) -> list[str]:
    """String constants containing SQL, in any module that is not a provider."""
    offenders: list[str] = []
    for path in _modules(root):
        if path.parent == root and path.name in _STORE_PROVIDERS:
            continue
        for node in ast.walk(_parse(path)):
            if (isinstance(node, ast.Constant) and isinstance(node.value, str)
                    and _SQL.search(_normalize(node.value))):
                offenders.append(f"{_rel(path, root)}:{node.lineno}")
    return offenders


def test_no_sql_outside_the_store_providers(tmp_path: Path) -> None:
    (tmp_path / "route.py").write_text('QUERY = "SELECT id FROM sessions"', encoding="utf-8")
    assert sql_sites(tmp_path) == ["route.py:1"]
    assert sql_sites(SRC) == []


# --- R6-T6 (L-6): config.py is the only reader of the environment -----------
#
# A hidden env var is configuration a hosted deploy cannot set and an installer
# cannot record. os.environ.copy() is not configuration -- it is inheritance
# handed to a child process -- so the executor's spawn is allowed by the rule
# itself rather than by a name on a list.
#
# The map is empty, which is the R6 exit gate. It stays as the one visible place
# an exception would have to be declared, and
# test_the_environment_exemptions_are_still_live keeps any future entry honest by
# failing the moment its module stops reading the environment. The doctor used to
# be on it for LOCALAPPDATA; that read now goes through config.local_app_data(),
# because machine discovery is a reason to ask config, not to bypass it.

_ENV_READ = re.compile(r"os\.environ(?!\.copy\s*\()")

_ENV_EXEMPTIONS: dict[str, str] = {}


def env_readers(root: Path, exemptions: dict[str, str]) -> list[str]:
    """Lines reading os.environ outside config.py, minus the named exemptions."""
    offenders: list[str] = []
    for path in _modules(root):
        rel = _rel(path, root)
        if path.name == "config.py" or rel in exemptions:
            continue
        text = path.read_text(encoding="utf-8")
        for number, line in enumerate(text.splitlines(), start=1):
            if _ENV_READ.search(line):
                offenders.append(f"{rel}:{number}")
    return offenders


def test_only_settings_reads_the_environment(tmp_path: Path) -> None:
    (tmp_path / "leaky.py").write_text('port = os.environ.get("VIBE_PORT")', encoding="utf-8")
    (tmp_path / "spawn.py").write_text("env = os.environ.copy()", encoding="utf-8")
    assert env_readers(tmp_path, {}) == ["leaky.py:1"]
    assert env_readers(SRC, _ENV_EXEMPTIONS) == []


def test_the_environment_exemptions_are_still_live() -> None:
    for name in _ENV_EXEMPTIONS:
        path = SRC / name
        assert path.is_file(), f"{name} no longer exists; delete its exemption entry"
        assert _ENV_READ.search(path.read_text(encoding="utf-8")), (
            f"{name} no longer reads os.environ; delete its exemption entry"
        )


# --- R6-T8 (L-8): schema changes go only through the migration runner -------
#
# Two modules own a database, each with one migration path that reads
# PRAGMA user_version and applies only the steps still missing. DDL anywhere
# else would be a second schema writer: it would run on every open, and on a
# database that already has the change it would raise or drift.

_MIGRATION_FUNCTIONS = {
    "store.py": {"_migrate", "_add_owner_column"},
    "events.py": {"_open", "_add_owner_column"},
}


class _DdlVisitor(ast.NodeVisitor):
    """DDL string constants, tagged with the function that encloses them."""

    def __init__(self) -> None:
        self.function: str | None = None
        self.hits: list[tuple[str, int]] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        previous, self.function = self.function, node.name
        self.generic_visit(node)
        self.function = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and _DDL.search(_normalize(node.value)):
            self.hits.append((self.function or "<module>", node.lineno))


def ddl_sites(root: Path, allowed: dict[str, set[str]]) -> list[str]:
    offenders: list[str] = []
    for name, functions in allowed.items():
        path = root / name
        if not path.is_file():
            continue
        visitor = _DdlVisitor()
        visitor.visit(_parse(path))
        offenders += [
            f"{name}:{line}:{function}"
            for function, line in visitor.hits
            if function not in functions
        ]
    return offenders


def test_schema_changes_only_through_the_migration_runner(tmp_path: Path) -> None:
    (tmp_path / "store.py").write_text('DDL = "CREATE TABLE later (id TEXT)"', encoding="utf-8")
    assert ddl_sites(tmp_path, {"store.py": {"_migrate"}}) == ["store.py:1:<module>"]
    assert ddl_sites(SRC, _MIGRATION_FUNCTIONS) == []
