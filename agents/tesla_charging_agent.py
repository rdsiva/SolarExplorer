import os
import logging
from datetime import datetime
import requests
import json
from .base_agent import BaseAgent
from models import TeslaPreferences, UserPreferences
from app import db
import uuid
from flask import url_for

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TeslaAPI:
    def __init__(self):
        self.api_base_url = "https://owner-api.teslamotors.com/api/1"
        self.oauth_url = "https://auth.tesla.com/oauth2/v3"
        self.client_id = os.environ.get("TESLA_CLIENT_ID")
        self.client_secret = os.environ.get("TESLA_CLIENT_SECRET")
        self.access_token = None
        self.refresh_token = None
        self.state = None

    def generate_auth_url(self, chat_id: str) -> str:
        """Generate OAuth authorization URL"""
        self.state = str(uuid.uuid4())

        # Store state with chat_id for verification
        with db.session.begin():
            prefs = TeslaPreferences.create_or_update(
                chat_id=chat_id,
                oauth_state=self.state
            )

        callback_url = url_for('tesla_oauth_callback', _external=True)
        params = {
            'client_id': self.client_id,
            'redirect_uri': callback_url,
            'response_type': 'code',
            'scope': 'openid email offline_access vehicle_device_data vehicle_cmds',
            'state': self.state
        }

        auth_url = f"{self.oauth_url}/authorize"
        return f"{auth_url}?{'&'.join(f'{k}={v}' for k, v in params.items())}"

    def exchange_code_for_token(self, code: str, state: str) -> dict:
        """Exchange authorization code for access token"""
        callback_url = url_for('tesla_oauth_callback', _external=True)
        token_url = f"{self.oauth_url}/token"

        data = {
            'grant_type': 'authorization_code',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
            'code': code,
            'redirect_uri': callback_url
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

    def start_charging(self, vehicle_id):
        """Start vehicle charging"""
        if not self.access_token:
            if not self.refresh_auth():
                return False

        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.post(f"{self.api_base_url}/vehicles/{vehicle_id}/command/charge_start", headers=headers)
            if response.status_code == 200:
                return True
            elif response.status_code == 401 and self.refresh_auth():
                return self.start_charging(vehicle_id)
            return False
        except Exception as e:
            logger.error(f"Error starting charging: {str(e)}")
            return False

    def stop_charging(self, vehicle_id):
        """Stop vehicle charging"""
        if not self.access_token:
            if not self.refresh_auth():
                return False

        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.post(f"{self.api_base_url}/vehicles/{vehicle_id}/command/charge_stop", headers=headers)
            if response.status_code == 200:
                return True
            elif response.status_code == 401 and self.refresh_auth():
                return self.stop_charging(vehicle_id)
            return False
        except Exception as e:
            logger.error(f"Error stopping charging: {str(e)}")
            return False


class TeslaChargingAgent(BaseAgent):
    def __init__(self):
        super().__init__("TeslaCharging")
        self.api = TeslaAPI()

    async def process(self, message):
        """Process messages according to BaseAgent interface"""
        try:
            if message.get("command") == "process_price_update":
                return await self.process_price_update(message.get("price_data", {}))
            return {
                "status": "error",
                "message": "Unknown command"
            }
        except Exception as e:
            logger.error(f"Error processing message: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to process message: {str(e)}"
            }

    async def process_price_update(self, price_data):
        """Process a price update and control charging accordingly"""
        try:
            active_preferences = TeslaPreferences.query.filter_by(enabled=True).all()
            if not active_preferences:
                logger.info("No active Tesla charging preferences found")
                return {
                    "status": "success",
                    "message": "No active Tesla charging preferences",
                    "data": {"active_users": 0}
                }

            results = []
            current_price = price_data.get('hourly_data', {}).get('price', 0)

            for prefs in active_preferences:
                try:
                    vehicle_data = self.api.get_vehicle_data(prefs.vehicle_id)
                    if not vehicle_data:
                        logger.error(f"Failed to get vehicle data for {prefs.vehicle_id}")
                        continue

                    prefs.update_vehicle_status(vehicle_data)

                    should_start = prefs.should_start_charging(current_price)
                    should_stop = prefs.should_stop_charging(current_price)
                    current_state = vehicle_data['charging_state']

                    if should_start and current_state != "Charging":
                        success = self.api.start_charging(prefs.vehicle_id)
                        if not success:
                            logger.error(f"Failed to start charging for vehicle {prefs.vehicle_id}")
                        else:
                            logger.info(f"Started charging vehicle {prefs.vehicle_id} at price {current_price}¢/kWh")

                    elif should_stop and current_state == "Charging":
                        success = self.api.stop_charging(prefs.vehicle_id)
                        if not success:
                            logger.error(f"Failed to stop charging for vehicle {prefs.vehicle_id}")
                        else:
                            logger.info(f"Stopped charging vehicle {prefs.vehicle_id} at price {current_price}¢/kWh")

                    results.append({
                        "vehicle_id": prefs.vehicle_id,
                        "battery_level": vehicle_data['battery_level'],
                        "charging_state": vehicle_data['charging_state'],
                        "should_charge": should_start,
                        "should_stop": should_stop
                    })

                except Exception as e:
                    logger.error(f"Error processing vehicle {prefs.vehicle_id}: {str(e)}")
                    continue

            return {
                "status": "success",
                "message": "Price update processed successfully",
                "data": {
                    "current_price": current_price,
                    "vehicles_processed": len(results),
                    "vehicle_states": results
                }
            }

        except Exception as e:
            logger.error(f"Error processing price update: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to process price update: {str(e)}"
            }