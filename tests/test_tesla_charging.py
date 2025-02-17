import unittest
from unittest.mock import patch
from datetime import datetime
import logging
from agents.tesla_charging_agent import TeslaChargingAgent
from models import TeslaPreferences, UserPreferences, db
from app import app

class TestTeslaChargingAgent(unittest.TestCase):
    def setUp(self):
        self.agent = TeslaChargingAgent()
        # Configure logging for tests
        logging.basicConfig(level=logging.INFO)

        # Set up application context
        self.app = app
        self.app_context = self.app.app_context()
        self.app_context.push()

        # Create test user preferences first
        self.test_chat_id = "test_user_123"
        self.user_prefs = UserPreferences.create_or_update(
            chat_id=self.test_chat_id,
            price_threshold=3.0,
            alert_frequency='immediate'
        )

        # Now create Tesla preferences
        self.tesla_prefs = TeslaPreferences.create_or_update(
            chat_id=self.test_chat_id,
            enabled=True,
            vehicle_id="test_vehicle_1",
            min_battery_level=20,
            max_battery_level=80,
            price_threshold=3.5
        )

    def tearDown(self):
        # Clean up test data - delete in correct order due to foreign key
        TeslaPreferences.query.filter_by(chat_id=self.test_chat_id).delete()
        UserPreferences.query.filter_by(chat_id=self.test_chat_id).delete()
        db.session.commit()
        self.app_context.pop()

    @patch('models.datetime')
    def test_charging_during_preferred_hours(self, mock_datetime):
        # Set current time to 11 PM (23:00) - within preferred hours (22:00-06:00)
        mock_time = datetime(2025, 2, 17, 23, 0)
        mock_datetime.now.return_value = mock_time
        mock_datetime.utcnow.return_value = mock_time

        # Update vehicle status
        self.tesla_prefs.update_vehicle_status({
            'battery_level': 50,
            'charging_state': 'Stopped'
        })

        # Price below threshold (3.5) and good battery level
        should_charge = self.tesla_prefs.should_start_charging(current_price=3.2)
        self.assertTrue(should_charge, "Should charge when price is good and battery below max")

    def test_emergency_charging(self):
        # Update vehicle status with low battery
        self.tesla_prefs.update_vehicle_status({
            'battery_level': 15,
            'charging_state': 'Stopped'
        })

        # Test emergency charging override with low battery
        should_charge = self.tesla_prefs.should_start_charging(current_price=4.0)
        self.assertTrue(should_charge, "Should charge when battery is critically low")

    def test_stop_charging_when_full(self):
        # Update vehicle status with high battery
        self.tesla_prefs.update_vehicle_status({
            'battery_level': 82,
            'charging_state': 'Charging'
        })

        # Test stopping charge when battery is full
        should_stop = self.tesla_prefs.should_stop_charging(current_price=3.0)
        self.assertTrue(should_stop, "Should stop charging when battery is above max level")

    def test_disabled_preferences(self):
        # Disable Tesla integration
        self.tesla_prefs.enabled = False
        db.session.commit()

        # Update vehicle status
        self.tesla_prefs.update_vehicle_status({
            'battery_level': 50,
            'charging_state': 'Stopped'
        })

        # Test that charging decisions are always false when disabled
        should_charge = self.tesla_prefs.should_start_charging(current_price=2.0)
        self.assertFalse(should_charge, "Should not charge when Tesla integration is disabled")

    @patch('models.datetime')
    def test_price_threshold(self, mock_datetime):
        # Set time to preferred charging hours
        mock_time = datetime(2025, 2, 17, 23, 0)
        mock_datetime.now.return_value = mock_time
        mock_datetime.utcnow.return_value = mock_time

        # Update vehicle status
        self.tesla_prefs.update_vehicle_status({
            'battery_level': 50,
            'charging_state': 'Stopped'
        })

        # Test price above threshold
        should_charge = self.tesla_prefs.should_start_charging(current_price=3.6)
        self.assertFalse(should_charge, "Should not charge when price is above threshold")

        # Test price at threshold
        should_charge = self.tesla_prefs.should_start_charging(current_price=3.5)
        self.assertTrue(should_charge, "Should charge when price is at threshold")

        # Test price below threshold
        should_charge = self.tesla_prefs.should_start_charging(current_price=3.4)
        self.assertTrue(should_charge, "Should charge when price is below threshold")

    @patch('models.datetime')
    def test_charging_outside_preferred_hours(self, mock_datetime):
        # Set current time to 2 PM (14:00) - outside preferred hours
        mock_time = datetime(2025, 2, 17, 14, 0)
        mock_datetime.now.return_value = mock_time
        mock_datetime.utcnow.return_value = mock_time

        # Update vehicle status
        self.tesla_prefs.update_vehicle_status({
            'battery_level': 50,
            'charging_state': 'Stopped'
        })

        # Even with good price, shouldn't charge outside hours
        should_charge = self.tesla_prefs.should_start_charging(current_price=3.0)
        self.assertFalse(should_charge, "Should not charge outside preferred hours")


if __name__ == '__main__':
    unittest.main()