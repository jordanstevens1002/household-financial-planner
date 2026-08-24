"""Legacy loan-group data repair tests."""

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa


def load_migration() -> ModuleType:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "0018_loan_group_integrity.py"
    spec = importlib.util.spec_from_file_location("loan_group_integrity_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_legacy_group_repair_normalizes_merges_and_clears_invalid_assignments() -> None:
    migration = load_migration()
    engine = sa.create_engine("sqlite://")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE loan_groups ("
                "id TEXT PRIMARY KEY, household_id TEXT NOT NULL, "
                "property_id TEXT, display_name TEXT NOT NULL)"
            )
        )
        connection.execute(
            sa.text(
                "CREATE TABLE loans (id TEXT PRIMARY KEY, household_id TEXT NOT NULL, "
                "property_id TEXT, loan_group_id TEXT)"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO loan_groups VALUES "
                "('g1', 'h1', 'p1', ' Fixed   splits '), "
                "('g2', 'h1', 'p1', 'fixed splits'), "
                "('g3', 'h1', 'p2', 'Other property'), "
                "('g4', 'h1', 'p1', '   ')"
            )
        )
        connection.execute(
            sa.text(
                "INSERT INTO loans VALUES "
                "('valid', 'h1', 'p1', 'g1'), "
                "('duplicate', 'h1', 'p1', 'g2'), "
                "('cross-property', 'h1', 'p1', 'g3')"
            )
        )

        migration.repair_loan_groups(connection)

        groups = connection.execute(
            sa.text("SELECT id, display_name FROM loan_groups ORDER BY id")
        ).all()
        loans = dict(
            connection.execute(sa.text("SELECT id, loan_group_id FROM loans ORDER BY id")).all()
        )

    assert groups == [
        ("g1", "Fixed splits"),
        ("g3", "Other property"),
        ("g4", "Unnamed loan group g4"),
    ]
    assert loans == {
        "cross-property": None,
        "duplicate": "g1",
        "valid": "g1",
    }
