import unittest
import asyncio
from datetime import datetime
from unittest.mock import patch, AsyncMock
from agents.live_price_agent import LivePriceAgent

class TestLivePriceAgent(unittest.TestCase):
    def setUp(self):
        self.config = {
            'price_threshold': 3.0,
            'check_interval': 300
        }
        self.agent = LivePriceAgent(config=self.config)

    def test_initialization(self):
        self.assertEqual(self.agent.name, "LivePrice")
        self.assertEqual(self.agent.price_threshold, 3.0)
        self.assertEqual(self.agent.check_interval, 300)

    def test_format_alert_message(self):
        test_data = {
            'current_hour': 4.5,
            'day_ahead': 3.8,
            'five_min': 4.2,
            'timestamp': datetime.utcnow().isoformat()
        }
        message = self.agent.format_alert_message(test_data)
        self.assertIn("ComEd Energy Price Update", message)
        self.assertIn("4.50¢/kWh", message)
        self.assertIn("3.80¢/kWh", message)
        self.assertIn("4.20¢/kWh", message)

    def test_empty_price_data(self):
        message = self.agent.format_alert_message({})
        self.assertEqual(message, "⚠️ Error fetching price data")

    @patch('aiohttp.ClientSession')
    async def async_test_get_current_price(self, mock_session):
        # Create mock session context manager
        session_instance = AsyncMock()
        mock_session.return_value.__aenter__.return_value = session_instance

        # Create mock response
        mock_response = AsyncMock()
        mock_response.status = 200
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.json.return_value = [{'price': '4.5', 'millisUTC': '1613577600000'}]

        # Set up response's context manager
        mock_response.__aenter__.return_value = mock_response
        session_instance.get.return_value = mock_response

        # Test successful price data fetch
        price_data = await self.agent.get_current_price()
        self.assertIsInstance(price_data, dict)
        self.assertIn('current_hour', price_data)
        self.assertIn('day_ahead', price_data)
        self.assertIn('five_min', price_data)
        self.assertIn('timestamp', price_data)

        # Verify the values
        self.assertEqual(price_data['current_hour'], 4.5)
        self.assertEqual(price_data['day_ahead'], 4.5)
        self.assertEqual(price_data['five_min'], 4.5)

        # Test error handling with invalid content type
        mock_response.headers = {'content-type': 'text/html'}
        price_data = await self.agent.get_current_price()
        self.assertEqual(price_data, {})

        # Test error handling with invalid response format
        mock_response.headers = {'content-type': 'application/json'}
        mock_response.json.return_value = []
        price_data = await self.agent.get_current_price()
        self.assertEqual(price_data, {})

        # Test error handling with invalid JSON data
        mock_response.json.return_value = [{'invalid': 'data'}]
        price_data = await self.agent.get_current_price()
        self.assertEqual(price_data, {})

    def test_get_current_price(self):
        loop = asyncio.get_event_loop()
        loop.run_until_complete(self.async_test_get_current_price())

if __name__ == '__main__':
    unittest.main()