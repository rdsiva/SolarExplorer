import os
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

class TwilioSender:
    def __init__(self):
        self.account_sid = os.environ.get("TWILIO_ACCOUNT_SID")
        self.auth_token = os.environ.get("TWILIO_AUTH_TOKEN")
        self.from_number = os.environ.get("TWILIO_PHONE_NUMBER")
        self.client = None
        
    def initialize(self):
        """Initialize Twilio client if credentials are available"""
        if all([self.account_sid, self.auth_token, self.from_number]):
            self.client = Client(self.account_sid, self.auth_token)
            return True
        return False
        
    async def send_sms(self, to_number: str, message: str) -> bool:
        """Send SMS using Twilio"""
        if not self.client:
            if not self.initialize():
                logger.error("Twilio credentials not configured")
                return False
                
        try:
            message = self.client.messages.create(
                body=message,
                from_=self.from_number,
                to=to_number
            )
            logger.info(f"SMS sent successfully. SID: {message.sid}")
            return True
        except Exception as e:
            logger.error(f"Failed to send SMS: {str(e)}")
            return False
