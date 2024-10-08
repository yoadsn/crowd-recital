import uuid

from sqlmodel import Field, Relationship, SQLModel

from .mixins.date_fields import DateFieldsMixin
from .recital_session import RecitalSession


class RecitalAudioSegment(SQLModel, DateFieldsMixin, table=True):

    __tablename__ = "recital_audio_segments"

    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    recital_session_id: str = Field(index=True, foreign_key="recital_sessions.id")
    sequential: int
    filename: str

    recital_session: "RecitalSession" = Relationship(back_populates="audio_segments")
