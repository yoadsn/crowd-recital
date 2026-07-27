import os
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

S3_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-north-1")


def _s3_client():
    return boto3.client("s3", region_name=S3_REGION)


def _s3_resource():
    return boto3.resource("s3", region_name=S3_REGION)


class RecitalsContentRA:

    def __init__(
        self,
        data_folder: str,
        content_s3_bucket: str,
    ) -> None:
        self.data_folder = data_folder
        self.content_s3_bucket = content_s3_bucket

        # Create the data folder if it does not exist
        Path(self.data_folder).mkdir(parents=True, exist_ok=True)

    def _storage_s3_configured(self) -> bool:
        if not self.content_s3_bucket:
            print("Warning S3 target bucket is not configured. Aborting.")
            return False
        return True

    def get_data_folder(self) -> str:
        return self.data_folder

    def upload_to_storage(self, source: str, target: str, metadata: dict[str, str], content_type: str = None) -> bool:
        if not self._storage_s3_configured():
            return False

        # Check if the file exists
        if not os.path.isfile(source):
            print(f"Warning file {source} does not exist. Aborting.")
            return False

        # upload to S3
        s3 = _s3_client()

        # ContentType - Should we include?
        try:
            extra_args = {"Metadata": metadata}
            if content_type:
                extra_args["ContentType"] = content_type

            s3.upload_file(source, self.content_s3_bucket, target, ExtraArgs=extra_args)
        except ClientError as e:
            print(e)
            return False
        return True

    def delete_from_storage(self, targets: list[str]) -> bool:
        if not self._storage_s3_configured():
            return False

        # remove from S3
        s3 = _s3_client()

        try:
            s3.delete_object(
                Bucket=self.content_s3_bucket,
                Delete={
                    "Objects": [
                        {"Key": target for target in targets},
                    ],
                    "Quiet": True,
                },
            )
        except ClientError as e:
            print(e)
            return False
        return True

    def delete_from_storage_prefix(self, prefix: str) -> bool:
        if not self._storage_s3_configured():
            return False

        if not prefix:
            print("Warning prefix is not provided. Not deleting anything.")
            return False

        s3 = _s3_resource()

        try:
            # remove from S3 by the object prefix
            bucket = s3.Bucket(self.content_s3_bucket)
            bucket.objects.filter(Prefix=prefix).delete()

        except Exception as e:
            print(e)
            return False
        return True

    def upload_text_to_storage(self, session_id: str, filename: str) -> bool:
        filename_in_data_folder = os.path.join(self.data_folder, filename)
        target_object_name = f"{session_id}/transcript.vtt"
        return self.upload_to_storage(filename_in_data_folder, target_object_name, metadata={"session": session_id})

    def _upload_audio_to_storage(
        self, session_id: str, filename: str, target_filename_prefix: str, content_type: str = None
    ) -> bool:
        filename_in_data_folder = Path(self.data_folder, filename)
        extension_of_file = os.path.splitext(filename)[1]
        target_object_name = f"{session_id}/{target_filename_prefix}{extension_of_file}"
        return self.upload_to_storage(
            filename_in_data_folder, target_object_name, metadata={"session": session_id}, content_type=content_type
        )

    def upload_main_audio_to_storage(self, session_id: str, filename: str) -> bool:
        return self._upload_audio_to_storage(session_id, filename, "main.audio", {})

    def upload_source_audio_to_storage(self, session_id: str, filename: str) -> bool:
        return self._upload_audio_to_storage(session_id, filename, "source.audio", {})

    def upload_light_audio_to_storage(self, session_id: str, filename: str) -> bool:
        return self._upload_audio_to_storage(session_id, filename, "light.audio", content_type="audio/mp3")

    def remove_local_data_file(self, filename: str) -> None:
        filename_in_data_folder = Path(self.data_folder, filename)
        if filename_in_data_folder.exists():
            filename_in_data_folder.unlink()

    def delete_session_content_from_storage(self, session_id: str) -> bool:
        session_content_folder_name = session_id
        return self.delete_from_storage_prefix(prefix=session_content_folder_name)

    def get_url_to_storage_object(self, target: str, expires_in: int = 1200) -> str:
        if not self._storage_s3_configured():
            print("Warning S3 target bucket is not configured. Aborting.")
            return ""

        # Get presigned URL
        s3 = _s3_client()
        try:
            response = s3.generate_presigned_url(
                "get_object",
                Params={"Bucket": self.content_s3_bucket, "Key": target},
                ExpiresIn=expires_in,
            )
        except ClientError as e:
            print(e)
            return ""
        return response

    def get_url_to_light_audio(self, session_id: str, **kwargs) -> str:
        target_object_name = f"{session_id}/light.audio.mp3"
        return self.get_url_to_storage_object(target_object_name, **kwargs)

    def get_url_to_transcript(self, session_id: str, **kwargs) -> str:
        target_object_name = f"{session_id}/transcript.vtt"
        return self.get_url_to_storage_object(target_object_name, **kwargs)
