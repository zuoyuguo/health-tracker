"""create_all_tables

Revision ID: ad4a9fb2f762
Revises:
Create Date: 2026-06-22 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = 'ad4a9fb2f762'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'meals',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('recorded_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('meal_type', sa.String(length=20), nullable=True),
        sa.Column('photo_url', sa.Text(), nullable=True),
        sa.Column('foods', JSONB(), nullable=False),
        sa.Column('total_calories', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('protein_g', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('carbs_g', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('fat_g', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('user_note', sa.Text(), nullable=True),
        sa.Column('confirmed', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'sleep',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('sleep_date', sa.Date(), nullable=False),
        sa.Column('total_sleep_min', sa.Integer(), nullable=True),
        sa.Column('deep_sleep_min', sa.Integer(), nullable=True),
        sa.Column('light_sleep_min', sa.Integer(), nullable=True),
        sa.Column('rem_sleep_min', sa.Integer(), nullable=True),
        sa.Column('awake_min', sa.Integer(), nullable=True),
        sa.Column('sleep_score', sa.Integer(), nullable=True),
        sa.Column('hrv_avg', sa.Numeric(precision=6, scale=2), nullable=True),
        sa.Column('resting_hr', sa.Integer(), nullable=True),
        sa.Column('sleep_start', sa.DateTime(timezone=True), nullable=True),
        sa.Column('sleep_end', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('sleep_date', name='uq_sleep_sleep_date'),
    )
    op.create_table(
        'activities',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('activity_date', sa.Date(), nullable=False),
        sa.Column('activity_type', sa.String(length=50), nullable=True),
        sa.Column('duration_min', sa.Integer(), nullable=True),
        sa.Column('calories_burned', sa.Numeric(precision=8, scale=2), nullable=True),
        sa.Column('avg_hr', sa.Integer(), nullable=True),
        sa.Column('max_hr', sa.Integer(), nullable=True),
        sa.Column('steps', sa.Integer(), nullable=True),
        sa.Column('distance_km', sa.Numeric(precision=6, scale=3), nullable=True),
        sa.Column('hr_zone_1_min', sa.Integer(), nullable=True),
        sa.Column('hr_zone_2_min', sa.Integer(), nullable=True),
        sa.Column('hr_zone_3_min', sa.Integer(), nullable=True),
        sa.Column('hr_zone_4_min', sa.Integer(), nullable=True),
        sa.Column('hr_zone_5_min', sa.Integer(), nullable=True),
        sa.Column('garmin_activity_id', sa.BigInteger(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('garmin_activity_id', name='uq_activities_garmin_activity_id'),
    )
    op.create_table(
        'body_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('measured_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('weight_kg', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('bmi', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('body_fat_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('fat_mass_kg', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('lean_mass_kg', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('muscle_mass_kg', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('bone_mass_kg', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('water_pct', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('visceral_fat', sa.Numeric(precision=5, scale=2), nullable=True),
        sa.Column('bmr_kcal', sa.Integer(), nullable=True),
        sa.Column('renpho_record_id', sa.String(length=64), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('renpho_record_id', name='uq_body_metrics_renpho_record_id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('body_metrics')
    op.drop_table('activities')
    op.drop_table('sleep')
    op.drop_table('meals')
