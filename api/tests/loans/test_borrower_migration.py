"""Loan-borrower migration rehearsal."""

import importlib.util
from pathlib import Path
from types import ModuleType

import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations


def load_migration() -> ModuleType:
    path = Path(__file__).parents[2] / "alembic" / "versions" / "0019_loan_borrowers.py"
    spec = importlib.util.spec_from_file_location("loan_borrower_migration", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_loan_borrower_migration_upgrades_and_downgrades() -> None:
    migration = load_migration()
    engine = sa.create_engine("sqlite://")
    metadata = sa.MetaData()
    sa.Table("loans", metadata, sa.Column("id", sa.Uuid(), primary_key=True))
    sa.Table("people", metadata, sa.Column("id", sa.Uuid(), primary_key=True))

    with engine.begin() as connection:
        metadata.create_all(connection)
        migration.op = Operations(MigrationContext.configure(connection))
        migration.upgrade()
        inspector = sa.inspect(connection)
        assert "loan_borrowers" in inspector.get_table_names()
        assert {item["name"] for item in inspector.get_unique_constraints("loan_borrowers")} == {
            None
        }
        assert {item["name"] for item in inspector.get_indexes("loan_borrowers")} == {
            "ix_loan_borrowers_loan_id",
            "ix_loan_borrowers_person_id",
        }

        migration.downgrade()
        assert "loan_borrowers" not in sa.inspect(connection).get_table_names()
