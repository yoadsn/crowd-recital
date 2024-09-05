import pathlib
import re
from mimetypes import guess_extension
from typing import Annotated, Optional
from uuid import UUID

from dependency_injector.wiring import Provide, inject
from fastapi import APIRouter, Depends, File, Path, UploadFile
from fastapi.exceptions import HTTPException
from nanoid import generate
from pydantic import BaseModel

from containers import Container
from managers.recital_manager import RecitalManager
from models.recital_audio_segment import RecitalAudioSegment
from models.recital_session import RecitalSession, SessionStatus
from models.recital_text_segment import RecitalTextSegment
from resource_access.recitals_content_ra import RecitalsContentRA
from resource_access.recitals_ra import RecitalsRA

from .dependencies.analytics import Tracker
from .dependencies.users import User, get_speaker_user

router = APIRouter()


class NewRecitalSessionRequestBody(BaseModel):
    document_id: Optional[UUID]


recital_ids_alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ_abcdefghijklmnopqrstuvwxyz"


@router.put("/new-recital-session")
@inject
async def new_recital_session(
    track_event: Tracker,
    speaker_user: Annotated[User, Depends(get_speaker_user)],
    new_session_request: NewRecitalSessionRequestBody,
    recitals_ra: RecitalsRA = Depends(Provide[Container.recitals_ra]),
):
    recital_session = RecitalSession(
        id=generate(alphabet=recital_ids_alphabet),
        user_id=speaker_user.id,
        document_id=new_session_request.document_id,
    )
    recitals_ra.upsert(recital_session)

    track_event(
        "Recital Session Created",
        {"session_id": recital_session.id, "document_id": recital_session.document_id},
    )
    return {"session_id": recital_session.id}


@router.post("/end-recital-session/{session_id}")
@inject
async def end_recital_session(
    track_event: Tracker,
    session_id: Annotated[str, Path(title="Session id of the transcript")],
    speaker_user: Annotated[User, Depends(get_speaker_user)],
    recital_manager: RecitalManager = Depends(Provide[Container.recital_manager]),
    recitals_ra: RecitalsRA = Depends(Provide[Container.recitals_ra]),
):
    recital_session = recitals_ra.get_by_id_and_user_id(session_id, speaker_user.id)
    if not recital_session:
        raise HTTPException(status_code=404, detail="Recital session not found")

    if recital_session.status == SessionStatus.ACTIVE:
        recital_session.status = SessionStatus.ENDED
        recitals_ra.upsert(recital_session)
        recital_manager.schedule_session_finalization_job()

        track_event(
            "Recital Session Ended",
            {
                "session_id": session_id,
            },
        )
    return {"message": "Recital session ended successfully"}


class TextSegmentRequestBody(BaseModel):
    seek_end: float
    text: str


@router.post("/upload-text-segment/{session_id}")
@inject
async def upload_text_segment(
    track_event: Tracker,
    session_id: Annotated[str, Path(title="Session id of the transcript")],
    segment: TextSegmentRequestBody,
    speaker_user: Annotated[User, Depends(get_speaker_user)],
    recitals_ra: RecitalsRA = Depends(Provide[Container.recitals_ra]),
):
    recital_session = recitals_ra.get_by_id_and_user_id(session_id, speaker_user.id)
    if not recital_session:
        raise HTTPException(status_code=404, detail="Recital session not found")

    text_segment = RecitalTextSegment(recital_session=recital_session, seek_end=segment.seek_end, text=segment.text)
    recitals_ra.add_text_segment(text_segment)

    track_event(
        "Text Segment Uploaded",
        {
            "session_id": session_id,
            "seek_end": str(segment.seek_end),
            "text_length": len(segment.text),
        },
    )
    return {"message": "Text segment uploaded successfully"}


def parse_mime_type(mime_type: str):
    # Regular expression to extract key-value pairs from the mime type
    pattern = re.compile(r"(\w+)=([\w.]+)")
    params = dict(pattern.findall(mime_type))
    return params


@router.post("/upload-audio-segment/{session_id}/{segment_id}")
@inject
async def upload_audio_segment(
    track_event: Tracker,
    session_id: Annotated[str, Path(title="Session id of the audio segment")],
    segment_id: Annotated[str, Path(title="Id of the audio segment")],
    speaker_user: Annotated[User, Depends(get_speaker_user)],
    audio_data: UploadFile = File(...),
    recitals_ra: RecitalsRA = Depends(Provide[Container.recitals_ra]),
    recitals_content_ra: RecitalsContentRA = Depends(Provide[Container.recitals_content_ra]),
):
    recital_session = recitals_ra.get_by_id_and_user_id(session_id, speaker_user.id)
    if not recital_session:
        raise HTTPException(status_code=404, detail="Recital session not found")

    # Read the MIME type
    mime_type = audio_data.content_type

    # write the file to disk
    file_extension = guess_extension(mime_type.split(";")[0]) or ".bin"
    file_name = f"{session_id}{file_extension}.seg.{segment_id}"
    with open(str(pathlib.Path(recitals_content_ra.get_data_folder(), file_name)), "wb") as buffer:
        buffer.write(await audio_data.read())

    # Byte Size of the uploaded audio file
    audio_data_length = audio_data.size

    recitals_ra.add_audio_segment(
        RecitalAudioSegment(
            filename=file_name,
            mime_type=mime_type,
            recital_session=recital_session,
            sequential=segment_id,
        )
    )

    track_event(
        "Audio Segment Uploaded",
        {
            "session_id": session_id,
            "audio_segment_id": segment_id,
            "mime_type": mime_type,
            "size_bytes": audio_data_length,
        },
    )
    return {"message": "Audio uploaded successfully"}
