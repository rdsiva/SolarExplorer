import unittest
from unittest.mock import patch
from datetime import datetime
import logging
from agents.tesla_charging_agent import TeslaChargingAgent

class TestTeslaChargingAgent(unittest.TestCase):
    def setUp(self):
        self.agent = TeslaChargingAgent()
        # Configure logging for tests
        logging.basicConfig(level=logging.INFO)

    @patch('agents.tesla_charging_agent.datetime')
    def test_charging_during_preferred_hours(self, mock_datetime):
        # Set current time to 11 PM (23:00) - within preferred hours (22:00-06:00)
        mock_time = datetime(2025, 2, 17, 23, 0)
        mock_datetime.now.return_value = mock_time

        # Price below threshold (3.5) and good battery level
        should_charge = self.agent.should_charge(current_price=3.2, battery_level=50)
        self.assertTrue(should_charge, "Should charge when price is good during preferred hours")

    @patch('agents.tesla_charging_agent.datetime')
    def test_charging_outside_preferred_hours(self, mock_datetime):
        # Set current time to 2 PM (14:00) - outside preferred hours
        mock_time = datetime(2025, 2, 17, 14, 0)
        mock_datetime.now.return_value = mock_time

        # Even with good price, shouldn't charge outside hours
        should_charge = self.agent.should_charge(current_price=3.0, battery_level=50)
        self.assertFalse(should_charge, "Should not charge outside preferred hours")

    def test_emergency_charging(self):
        # Test emergency charging override with low battery
        should_charge = self.agent.should_charge(current_price=4.0, battery_level=15)
        self.assertTrue(should_charge, "Should charge when battery is critically low")

    def test_price_threshold(self):
        # Mock time to be within preferred hours
        with patch('agents.tesla_charging_agent.datetime') as mock_datetime:
            mock_time = datetime(2025, 2, 17, 23, 0)
            mock_datetime.now.return_value = mock_time

            # Test price above threshold
            should_charge = self.agent.should_charge(current_price=3.6, battery_level=50)
            self.assertFalse(should_charge, "Should not charge when price is above threshold")

            # Test price at threshold
            should_charge = self.agent.should_charge(current_price=3.5, battery_level=50)
            self.assertTrue(should_charge, "Should charge when price is at threshold")

            # Test price below threshold
            should_charge = self.agent.should_charge(current_price=3.4, battery_level=50)
            self.assertTrue(should_charge, "Should charge when price is below threshold")

if __name__ == '__main__':
    unittest.main()
