"""Add users, billing state, and job ownership."""
from alembic import op
import sqlalchemy as sa


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("cognito_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("is_owner", sa.Boolean(), nullable=False),
        sa.Column("stripe_customer_id", sa.String(length=255), nullable=True),
        sa.Column("subscription_status", sa.String(length=30), nullable=False),
        sa.Column("plan", sa.String(length=50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("cognito_sub"),
        sa.UniqueConstraint("stripe_customer_id"),
    )
    op.create_index("ix_users_cognito_sub", "users", ["cognito_sub"])
    op.add_column(
        "recommendation_jobs",
        sa.Column("user_id", sa.String(length=36), nullable=True),
    )
    op.create_foreign_key(
        "fk_recommendation_jobs_user_id",
        "recommendation_jobs",
        "users",
        ["user_id"],
        ["id"],
        ondelete="CASCADE",
    )
    op.create_index(
        "ix_recommendation_jobs_user_id",
        "recommendation_jobs",
        ["user_id"],
    )


def downgrade():
    op.drop_column("recommendation_jobs", "user_id")
    op.drop_table("users")
