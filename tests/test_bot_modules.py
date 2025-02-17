import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Chat, Message, Bot
from telegram.ext import ContextTypes
from bot import EnergyPriceBot
import asyncio

class TestBotModules(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        # Create a mock bot instance
        self.mock_bot = MagicMock()
        self.mock_bot.send_message = AsyncMock()

        # Patch the bot creation in EnergyPriceBot
        with patch('telegram.ext.Application.builder') as mock_builder:
            mock_app = MagicMock()
            mock_app.bot = self.mock_bot
            mock_builder.return_value.token.return_value.build.return_value = mock_app
            self.bot = EnergyPriceBot()

        self.update = MagicMock(spec=Update)
        self.context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Mock chat and message
        self.chat = MagicMock(spec=Chat)
        self.chat.id = 123456789
        self.message = MagicMock(spec=Message)
        self.message.chat = self.chat
        self.update.effective_chat = self.chat
        self.update.message = self.message

        # Set up async mock for message reply
        self.message.reply_text = AsyncMock()

    async def test_module_listing(self):
        """Test that /modules command shows all modules with price_monitor as required"""
        await self.bot.cmd_list_modules(self.update, self.context)

        # Get the first call arguments
        call_args = self.message.reply_text.call_args[0][0]

        # Verify required module is listed
        self.assertIn("price_monitor (Required)", call_args)
        self.assertIn("✅ Enabled", call_args)  # Price monitor should be enabled by default

        # Verify optional modules are listed
        self.assertIn("pattern_analysis", call_args)
        self.assertIn("ml_prediction", call_args)

    async def test_cannot_disable_price_monitor(self):
        """Test that price_monitor module cannot be disabled"""
        self.context.args = ["price_monitor"]
        await self.bot.cmd_disable_module(self.update, self.context)

        # Verify warning message
        self.message.reply_text.assert_called_once_with(
            "⚠️ The price monitoring module cannot be disabled as it is required."
        )

    async def test_enable_optional_module(self):
        """Test enabling an optional module"""
        self.context.args = ["pattern_analysis"]
        await self.bot.cmd_enable_module(self.update, self.context)

        # Verify success message
        self.message.reply_text.assert_called_once_with(
            "✅ Module 'pattern_analysis' has been enabled."
        )

        # Verify module is actually enabled
        enabled_modules = self.bot.module_manager.get_enabled_modules()
        self.assertIn("pattern_analysis", enabled_modules)

    async def test_disable_optional_module(self):
        """Test disabling an optional module"""
        # First enable the module
        self.bot.module_manager.enable_module("ml_prediction")

        self.context.args = ["ml_prediction"]
        await self.bot.cmd_disable_module(self.update, self.context)

        # Verify success message
        self.message.reply_text.assert_called_once_with(
            "✅ Module 'ml_prediction' has been disabled."
        )

        # Verify module is actually disabled
        enabled_modules = self.bot.module_manager.get_enabled_modules()
        self.assertNotIn("ml_prediction", enabled_modules)

    async def test_check_price_with_modules(self):
        """Test that check_price command includes data from enabled modules"""
        # Enable all modules
        self.bot.module_manager.enable_module("pattern_analysis")
        self.bot.module_manager.enable_module("ml_prediction")

        # Mock module processing results
        self.bot.module_manager.process_with_enabled_modules = AsyncMock(return_value={})
        self.bot.module_manager.get_notification_data = AsyncMock(return_value={
            "price_monitor": {
                "current_price": "4.5",
                "five_min_price": "4.3",
                "trend": "rising"
            },
            "pattern_analysis": {
                "current_trend": "rising",
                "volatility": 0.15
            },
            "ml_prediction": {
                "predicted_price": 4.8,
                "confidence": 85
            }
        })

        # Execute the command
        await self.bot.cmd_check_price(self.update, self.context)

        # Verify initial "checking prices" message
        self.message.reply_text.assert_called_once_with("🔍 Checking current prices...")

        # Verify that send_message was called
        self.assertTrue(self.mock_bot.send_message.call_count > 0, "No messages were sent")

        # Get the final message content
        final_message = self.mock_bot.send_message.call_args_list[0][1]["text"]

        # Verify all module data is included
        self.assertIn("Current Price: 4.5¢", final_message)
        self.assertIn("Five-min Price: 4.3¢", final_message)
        self.assertIn("Pattern Analysis:", final_message)
        self.assertIn("Volatility: 0.15", final_message)
        self.assertIn("Price Prediction:", final_message)
        self.assertIn("Next Hour: 4.8¢", final_message)
        self.assertIn("Confidence: 85%", final_message)

if __name__ == '__main__':
    unittest.main()