import os
import logging
from datetime import datetime
import requests
import json
from .base_agent import BaseAgent

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

    def authenticate(self):
        """Authenticate with Tesla API using OAuth"""
        try:
            if not self.client_id or not self.client_secret:
                logger.error("Tesla API credentials not found")
                return False

            auth_data = {
                "grant_type": "client_credentials",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": "openid email offline_access"
            }

            response = requests.post(f"{self.oauth_url}/token", json=auth_data)
            if response.status_code == 200:
                token_data = response.json()
                self.access_token = token_data.get("access_token")
                self.refresh_token = token_data.get("refresh_token")
                logger.info("Tesla API authentication successful")
                return True
            else:
                logger.error(f"Tesla API authentication failed: {response.text}")
                return False
        except Exception as e:
            logger.error(f"Error during Tesla authentication: {str(e)}")
            return False

    def refresh_auth(self):
        """Refresh authentication token"""
        if not self.refresh_token:
            return self.authenticate()

        try:
            refresh_data = {
                "grant_type": "refresh_token",
                "refresh_token": self.refresh_token,
                "client_id": self.client_id,
                "scope": "openid email offline_access"
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
            if not self.authenticate():
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
            elif response.status_code == 401:  # Token expired
                if self.refresh_auth():
                    return self.get_vehicle_data(vehicle_id)  # Retry with new token
            return None
        except Exception as e:
            logger.error(f"Error getting vehicle data: {str(e)}")
            return None

    def start_charging(self, vehicle_id):
        """Start vehicle charging"""
        if not self.access_token:
            if not self.authenticate():
                return False

        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.post(f"{self.api_base_url}/vehicles/{vehicle_id}/command/charge_start", headers=headers)
            if response.status_code == 200:
                logger.info(f"Successfully started charging for vehicle {vehicle_id}")
                return True
            elif response.status_code == 401:  # Token expired
                if self.refresh_auth():
                    return self.start_charging(vehicle_id)  # Retry with new token
            return False
        except Exception as e:
            logger.error(f"Error starting charging: {str(e)}")
            return False

    def stop_charging(self, vehicle_id):
        """Stop vehicle charging"""
        if not self.access_token:
            if not self.authenticate():
                return False

        headers = {"Authorization": f"Bearer {self.access_token}"}
        try:
            response = requests.post(f"{self.api_base_url}/vehicles/{vehicle_id}/command/charge_stop", headers=headers)
            if response.status_code == 200:
                logger.info(f"Successfully stopped charging for vehicle {vehicle_id}")
                return True
            elif response.status_code == 401:  # Token expired
                if self.refresh_auth():
                    return self.stop_charging(vehicle_id)  # Retry with new token
            return False
        except Exception as e:
            logger.error(f"Error stopping charging: {str(e)}")
            return False

class TeslaChargingAgent(BaseAgent):
    def __init__(self):
        super().__init__("TeslaCharging")
        self.api = TeslaAPI()
        self.price_threshold = float(os.environ.get("TESLA_CHARGE_PRICE_THRESHOLD", "3.5"))
        self.preferred_start_hour = int(os.environ.get("TESLA_CHARGE_START_HOUR", "22"))
        self.preferred_end_hour = int(os.environ.get("TESLA_CHARGE_END_HOUR", "6"))
        self.emergency_min_battery = int(os.environ.get("TESLA_EMERGENCY_MIN_BATTERY", "20"))

    def should_charge(self, current_price, battery_level):
        """Determine if charging should occur based on price and time"""
        current_hour = datetime.now().hour

        # Emergency charging override if battery is too low
        if battery_level <= self.emergency_min_battery:
            logger.info(f"Emergency charging needed - Battery at {battery_level}% (below {self.emergency_min_battery}% threshold)")
            return True

        # Check if current time is within preferred charging hours
        is_preferred_time = False
        if self.preferred_start_hour > self.preferred_end_hour:  # Handles overnight periods
            is_preferred_time = current_hour >= self.preferred_start_hour or current_hour < self.preferred_end_hour
        else:
            is_preferred_time = self.preferred_start_hour <= current_hour < self.preferred_end_hour

        logger.info(f"Time check - Current hour: {current_hour}, Preferred window: {self.preferred_start_hour}-{self.preferred_end_hour}, Within window: {is_preferred_time}")

        # Check if price is below threshold
        is_price_good = current_price <= self.price_threshold
        logger.info(f"Price check - Current: {current_price}¢/kWh, Threshold: {self.price_threshold}¢/kWh, Below threshold: {is_price_good}")

        should_charge = is_price_good and is_preferred_time
        logger.info(f"Charging decision - Should charge: {should_charge} (Price OK: {is_price_good}, Time OK: {is_preferred_time})")

        return should_charge

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
            vehicle_id = os.environ.get("TESLA_VEHICLE_ID")
            if not vehicle_id:
                logger.error("No Tesla vehicle ID configured")
                return {
                    "status": "error",
                    "message": "Tesla vehicle ID not configured"
                }

            vehicle_data = self.api.get_vehicle_data(vehicle_id)
            if not vehicle_data:
                return {
                    "status": "error",
                    "message": "Failed to get vehicle data from Tesla API"
                }

            current_price = price_data.get('hourly_data', {}).get('price', 0)
            logger.info(f"Processing price update - Vehicle: {vehicle_id}, Current battery: {vehicle_data['battery_level']}%, State: {vehicle_data['charging_state']}")

            should_be_charging = self.should_charge(
                current_price, 
                vehicle_data['battery_level']
            )

            if should_be_charging and vehicle_data['charging_state'] != "Charging":
                success = self.api.start_charging(vehicle_id)
                if not success:
                    return {
                        "status": "error",
                        "message": "Failed to start charging"
                    }
                logger.info(f"Started charging at price {current_price}¢/kWh")
            elif not should_be_charging and vehicle_data['charging_state'] == "Charging":
                success = self.api.stop_charging(vehicle_id)
                if not success:
                    return {
                        "status": "error",
                        "message": "Failed to stop charging"
                    }
                logger.info(f"Stopped charging at price {current_price}¢/kWh")
            else:
                logger.info(f"No charging state change needed - Current state: {vehicle_data['charging_state']}, Should charge: {should_be_charging}")

            return {
                "status": "success",
                "message": "Price update processed successfully",
                "data": {
                    "should_charge": should_be_charging,
                    "current_price": current_price,
                    "battery_level": vehicle_data['battery_level'],
                    "charging_state": vehicle_data['charging_state']
                }
            }

        except Exception as e:
            logger.error(f"Error processing price update: {str(e)}")
            return {
                "status": "error",
                "message": f"Failed to process price update: {str(e)}"
            }