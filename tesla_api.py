import os
import logging
import requests
import uuid
from flask import url_for

logger = logging.getLogger(__name__)

def log_banner(message):
    """Helper function to create visible log banners"""
    logger.info("\n" + "=" * 80)
    logger.info(message.center(78))
    logger.info("=" * 80 + "\n")

class TeslaAPI:
    def __init__(self):
        self.api_base_url = "https://owner-api.teslamotors.com/api/1"
        self.oauth_url = "https://auth.tesla.com/oauth2/v3"
        self.client_id = os.environ.get("TESLA_CLIENT_ID")
        self.client_secret = os.environ.get("TESLA_CLIENT_SECRET")
        self.access_token = None
        self.refresh_token = None
        self.state = None
        self.callback_url = "https://1a8446b3-198e-4458-9e5f-60fa0a94ff1f-00-1nh6gkpmzmrcg.janeway.replit.dev/tesla/oauth/callback"

        # Log the callback URL during initialization
        log_banner("TESLA OAUTH CONFIGURATION")
        logger.info("Using the following callback URL in Tesla Developer Console:")
        logger.info(f"Callback URL: {self.callback_url}")
        logger.info("\nIMPORTANT: Use this exact URL in Tesla app settings")

    def generate_auth_url(self, chat_id: str) -> str:
        """Generate OAuth authorization URL"""
        logger.info(f"Generating auth URL for chat_id: {chat_id}")

        try:
            # Generate state that includes the chat_id
            state_uuid = str(uuid.uuid4())
            self.state = f"{state_uuid}_{chat_id}"
            logger.info(f"Generated OAuth state with chat_id: {self.state}")

            params = {
                'client_id': self.client_id,
                'redirect_uri': self.callback_url,
                'response_type': 'code',
                'scope': 'openid email offline_access vehicle_device_data vehicle_cmds',
                'state': self.state
            }

            auth_url = f"{self.oauth_url}/authorize"
            final_url = f"{auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"
            logger.info(f"Final auth URL generated: {final_url}")

            return final_url

        except Exception as e:
            logger.error(f"Error generating auth URL: {str(e)}", exc_info=True)
            raise

    def exchange_code_for_token(self, code: str, state: str) -> dict:
        """Exchange authorization code for access token"""
        token_url = f"{self.oauth_url}/token"
        logger.info(f"Using callback URL for token exchange: {self.callback_url}")

        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': self.callback_url
        }

        try:
            response = requests.post(token_url, json=data)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get('access_token')
                self.refresh_token = token_data.get('refresh_token')
                return {
                    'success': True,
                    'access_token': self.access_token,
                    'refresh_token': self.refresh_token
                }
            else:
                logger.error(f"Token exchange failed: {response.text}")
                return {
                    'success': False,
                    'error': f"Token exchange failed: {response.status_code}"
                }
        except Exception as e:
            logger.error(f"Error exchanging code for token: {str(e)}")
            return {
                'success': False,
                'error': str(e)
            }

    def refresh_auth(self):
        """Refresh authentication token"""
        if not self.refresh_token:
            return False

        try:
            refresh_data = {
                "grant_type": "refresh_token",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "refresh_token": self.refresh_token,
                "scope": "openid email offline_access vehicle_device_data vehicle_cmds"
            }

            response = requests.post(f"{self.oauth_url}/token", json=refresh_data)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                return True
            return False
        except Exception as e:
            logger.error(f"Error refreshing Tesla token: {str(e)}")
            return False

    def get_vehicle_data(self, vehicle_id):
        """Get vehicle charging and battery status"""
        if not self.access_token:
            if not self.refresh_auth():
                return None

        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.get(f"{self.api_base_url}/vehicles/{vehicle_id}/vehicle_data", headers=headers)
            if response.status_code == 200:
                data = response.json()["response"]
                return {
                    "battery_level": data["charge_state"]["battery_level"],
                    "charging_state": data["charge_state"]["charging_state"],
                    "time_to_full_charge": data["charge_state"]["time_to_full_charge"]
                }
            elif response.status_code == 401:
                if self.refresh_auth():
                    return self.get_vehicle_data(vehicle_id)
            return None
        except Exception as e:
            logger.error(f"Error getting vehicle data: {str(e)}")
            return None

    def get_vehicles(self):
        """Get list of vehicles"""
        if not self.access_token:
            return None

        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.get(f"{self.api_base_url}/vehicles", headers=headers)
            if response.status_code == 200:
                return response.json().get("response", [])
            elif response.status_code == 401 and self.refresh_auth():
                return self.get_vehicles()
            return None
        except Exception as e:
            logger.error(f"Error getting vehicles: {str(e)}")
            return None