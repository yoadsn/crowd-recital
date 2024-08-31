"""add light audio filename col

Revision ID: bebd8dc37433
Revises: 7bd13bfcf8f1
Create Date: 2024-08-31 17:45:30.063389

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "bebd8dc37433"
down_revision: Union[str, None] = "7bd13bfcf8f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column(
        "recital_sessions", sa.Column("light_audio_filename", sqlmodel.sql.sqltypes.AutoString(), nullable=True)
    )
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column("recital_sessions", "light_audio_filename")
    # ### end Alembic commands ###
