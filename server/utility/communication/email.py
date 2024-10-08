import logging

import boto3
from botocore.exceptions import ClientError
from dependency_injector.wiring import Provide, inject

from models.user import User

logger = logging.getLogger(__name__)


class SesDestination:
    """Contains data about an email destination."""

    def __init__(self, tos, ccs=None, bccs=None):
        """
        :param tos: The list of recipients on the 'To:' line.
        :param ccs: The list of recipients on the 'CC:' line.
        :param bccs: The list of recipients on the 'BCC:' line.
        """
        self.tos = tos
        self.ccs = ccs
        self.bccs = bccs

    def to_service_format(self):
        """
        :return: The destination data in the format expected by Amazon SES.
        """
        svc_format = {"ToAddresses": self.tos}
        if self.ccs is not None:
            svc_format["CcAddresses"] = self.ccs
        if self.bccs is not None:
            svc_format["BccAddresses"] = self.bccs
        return svc_format


class SesMailSender:
    """Encapsulates functions to send emails with Amazon SES."""

    def __init__(self, ses_client):
        """
        :param ses_client: A Boto3 Amazon SES client.
        """
        self.ses_client = ses_client

    def send_email(self, source, destination, subject, text, html, reply_tos=None):
        """
        Sends an email.

        Note: If your account is in the Amazon SES  sandbox, the source and
        destination email accounts must both be verified.

        :param source: The source email account.
        :param destination: The destination email account.
        :param subject: The subject of the email.
        :param text: The plain text version of the body of the email.
        :param html: The HTML version of the body of the email.
        :param reply_tos: Email accounts that will receive a reply if the recipient
                          replies to the message.
        :return: The ID of the message, assigned by Amazon SES.
        """
        send_args = {
            "Source": source,
            "Destination": destination.to_service_format(),
            "Message": {
                "Subject": {"Data": subject},
                "Body": {"Text": {"Data": text}, "Html": {"Data": html}},
            },
        }
        if reply_tos is not None:
            send_args["ReplyToAddresses"] = reply_tos
        try:
            response = self.ses_client.send_email(**send_args)
            message_id = response["MessageId"]
            logger.info("Sent mail %s from %s to %s.", message_id, source, destination.tos)
        except ClientError:
            logger.exception("Couldn't send mail from %s to %s.", source, destination.tos)
            raise
        else:
            return message_id


class Emailer:
    def __init__(self, email_sender_address: str, email_reply_to_address: str):
        ses_client = boto3.client("ses")
        self.ses_client = ses_client
        self.sesSender = SesMailSender(ses_client)
        self.configured = True
        if email_sender_address:
            self.default_email_sender_address = email_sender_address
            self.default_email_reply_to_address = email_reply_to_address
        else:
            self.configured = False

    def _get_single_address_ses_dest(self, email: str):
        return SesDestination([email])

    def send_to_user(
        self,
        user: User,
        subject: str,
        content_html: str,
        content_text: str = "",
    ):
        if not self.configured:
            logger.warning("Skipping email send - no mailer is configured.")
            return
        if not user:
            return

        try:
            dest = self._get_single_address_ses_dest(user.email)
            self.sesSender.send_email(
                self.default_email_sender_address,
                dest,
                subject,
                content_text,
                content_html,
                [self.default_email_reply_to_address],
            )
        except ClientError as e:
            logger.warning("Failed to send email to %s - Silent error.", user.email)
            logger.exception(e)
