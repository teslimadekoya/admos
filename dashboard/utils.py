from django.conf import settings
from twilio.rest import Client
import logging

logger = logging.getLogger(__name__)

def send_sms(phone_number, message):
    """
    Send SMS message using Twilio
    
    Args:
        phone_number (str): Recipient phone number
        message (str): Message to send
        
    Returns:
        bool: True if successful, False otherwise
    """
    try:
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        message_obj = client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=phone_number
        )
        logger.info(f"SMS sent successfully to {phone_number}. Message SID: {message_obj.sid}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SMS to {phone_number}: {str(e)}")
        return False

def send_otp_sms(phone_number, otp_code, purpose="login"):
    """
    Send OTP SMS message
    
    Args:
        phone_number (str): Recipient phone number
        otp_code (str): OTP code to send
        purpose (str): Purpose of OTP (login, password_reset, etc.)
        
    Returns:
        bool: True if successful, False otherwise
    """
    if purpose == "password_reset":
        message = f"Your Admos Place password reset OTP is: {otp_code}. This code expires in 5 minutes."
    else:
        message = f"Your Admos Place login OTP is: {otp_code}. This code expires in 5 minutes."
    
    return send_sms(phone_number, message)
