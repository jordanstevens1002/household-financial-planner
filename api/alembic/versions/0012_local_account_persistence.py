"""Add local accounts, sessions, throttling, and legacy identity mappings."""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0012_local_account_persistence"
down_revision: str | None = "0011_loan_repayment_payers"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    bind = op.get_bind()
    global_role = sa.Enum("ADMIN", "USER", name="global_role")
    global_role.create(bind, checkfirst=True)

    op.alter_column("application_users", "oidc_subject", nullable=True)
    op.add_column("application_users", sa.Column("username", sa.String(320)))
    op.add_column("application_users", sa.Column("password_hash", sa.String(512)))
    op.add_column(
        "application_users",
        sa.Column("global_role", global_role, server_default="USER", nullable=False),
    )
    op.add_column(
        "application_users",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "application_users",
        sa.Column("must_change_password", sa.Boolean(), server_default=sa.false(), nullable=False),
    )
    op.add_column(
        "application_users",
        sa.Column("password_expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_application_users_username",
        "application_users",
        ["username"],
        unique=True,
    )

    op.create_table(
        "application_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("session_token_hash", sa.String(64), nullable=False),
        sa.Column("csrf_token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("idle_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("absolute_expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.CheckConstraint("idle_expires_at <= absolute_expires_at"),
    )
    op.create_index(
        "ix_application_sessions_application_user_id",
        "application_sessions",
        ["application_user_id"],
    )
    op.create_index(
        "ix_application_sessions_session_token_hash",
        "application_sessions",
        ["session_token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_application_sessions_idle_expires_at",
        "application_sessions",
        ["idle_expires_at"],
    )
    op.create_index(
        "ix_application_sessions_absolute_expires_at",
        "application_sessions",
        ["absolute_expires_at"],
    )

    op.create_table(
        "password_reset_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("token_hash", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True)),
    )
    op.create_index(
        "ix_password_reset_tokens_application_user_id",
        "password_reset_tokens",
        ["application_user_id"],
    )
    op.create_index(
        "ix_password_reset_tokens_token_hash",
        "password_reset_tokens",
        ["token_hash"],
        unique=True,
    )
    op.create_index(
        "ix_password_reset_tokens_expires_at",
        "password_reset_tokens",
        ["expires_at"],
    )

    op.create_table(
        "login_throttles",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("username", sa.String(320), nullable=False),
        sa.Column("failed_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("window_started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("blocked_until", sa.DateTime(timezone=True)),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("failed_attempts >= 0"),
    )
    op.create_index(
        "ix_login_throttles_username",
        "login_throttles",
        ["username"],
        unique=True,
    )
    op.create_index(
        "ix_login_throttles_blocked_until",
        "login_throttles",
        ["blocked_until"],
    )

    op.create_table(
        "legacy_identities",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "source_application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("oidc_subject", sa.String(255), nullable=False),
        sa.Column("email", sa.String(320)),
        sa.Column("display_name", sa.String(200)),
        sa.Column(
            "captured_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_legacy_identities_source_application_user_id",
        "legacy_identities",
        ["source_application_user_id"],
        unique=True,
    )
    op.create_index(
        "ix_legacy_identities_oidc_subject",
        "legacy_identities",
        ["oidc_subject"],
        unique=True,
    )

    op.execute(
        sa.text(
            "INSERT INTO legacy_identities "
            "(id, source_application_user_id, oidc_subject, email, display_name) "
            "SELECT id, id, oidc_subject, email, display_name "
            "FROM application_users WHERE oidc_subject IS NOT NULL"
        )
    )

    op.create_table(
        "legacy_identity_mappings",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "legacy_identity_id",
            sa.Uuid(),
            sa.ForeignKey("legacy_identities.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mapped_by_application_user_id",
            sa.Uuid(),
            sa.ForeignKey("application_users.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column(
            "mapped_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_legacy_identity_mappings_legacy_identity_id",
        "legacy_identity_mappings",
        ["legacy_identity_id"],
        unique=True,
    )
    op.create_index(
        "ix_legacy_identity_mappings_application_user_id",
        "legacy_identity_mappings",
        ["application_user_id"],
    )
    op.create_index(
        "ix_legacy_identity_mappings_mapped_by_application_user_id",
        "legacy_identity_mappings",
        ["mapped_by_application_user_id"],
    )


def downgrade() -> None:
    op.drop_table("legacy_identity_mappings")
    op.drop_table("legacy_identities")
    op.drop_table("login_throttles")
    op.drop_table("password_reset_tokens")
    op.drop_table("application_sessions")

    op.drop_index("ix_application_users_username", table_name="application_users")
    op.drop_column("application_users", "password_expires_at")
    op.drop_column("application_users", "must_change_password")
    op.drop_column("application_users", "is_active")
    op.drop_column("application_users", "global_role")
    op.drop_column("application_users", "password_hash")
    op.drop_column("application_users", "username")
    # The preceding OIDC-only schema requires every user to have a subject. Preserve
    # local-only user rows and their household memberships under a deterministic
    # placeholder instead of deleting financial-data relationships on rollback.
    op.execute(
        sa.text(
            "UPDATE application_users "
            "SET oidc_subject = 'local-account:' || id::text "
            "WHERE oidc_subject IS NULL"
        )
    )
    op.alter_column("application_users", "oidc_subject", nullable=False)

    sa.Enum(name="global_role").drop(op.get_bind(), checkfirst=True)
