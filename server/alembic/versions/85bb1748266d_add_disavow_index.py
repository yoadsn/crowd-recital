"""add disavow index

Revision ID: 85bb1748266d
Revises: 33ebc0607ac1
Create Date: 2024-09-14 18:36:59.590546

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel.sql.sqltypes


# revision identifiers, used by Alembic.
revision: str = "85bb1748266d"
down_revision: Union[str, None] = "33ebc0607ac1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f("ix_recital_sessions_disavowed_status"), "recital_sessions", ["disavowed", "status"], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f("ix_recital_sessions_disavowed_status"), table_name="recital_sessions")
    # ### end Alembic commands ###
