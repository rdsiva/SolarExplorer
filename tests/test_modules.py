import asyncio
import unittest
from datetime import datetime, timedelta
from modules import ModuleManager, PriceMonitorModule, PatternAnalysisModule

class TestModuleSystem(unittest.TestCase):
    def setUp(self):
        self.module_manager = ModuleManager()
        self.price_module = PriceMonitorModule()
        self.pattern_module = PatternAnalysisModule()

    def test_module_registration(self):
        """Test module registration process"""
        # Register modules
        result = self.module_manager.register_module(self.price_module)
        self.assertTrue(result)
        result = self.module_manager.register_module(self.pattern_module)
        self.assertTrue(result)

        # Verify modules are registered
        modules = self.module_manager.get_all_modules()
        self.assertEqual(len(modules), 2)
        module_names = [m["name"] for m in modules]
        self.assertIn("price_monitor", module_names)
        self.assertIn("pattern_analysis", module_names)

    def test_enable_disable_module(self):
        """Test enabling and disabling modules"""
        # Register and enable modules
        self.module_manager.register_module(self.price_module)
        self.module_manager.register_module(self.pattern_module)

        result = self.module_manager.enable_module("price_monitor")
        self.assertTrue(result)
        result = self.module_manager.enable_module("pattern_analysis")
        self.assertTrue(result)

        # Verify modules are enabled
        enabled_modules = self.module_manager.get_enabled_modules()
        self.assertIn("price_monitor", enabled_modules)
        self.assertIn("pattern_analysis", enabled_modules)

        # Disable modules
        result = self.module_manager.disable_module("price_monitor")
        self.assertTrue(result)
        result = self.module_manager.disable_module("pattern_analysis")
        self.assertTrue(result)

        # Verify modules are disabled
        enabled_modules = self.module_manager.get_enabled_modules()
        self.assertEqual(len(enabled_modules), 0)

    async def async_test_price_monitor(self):
        """Test price monitor module functionality"""
        result = await self.price_module.initialize()
        self.assertTrue(result)

        data = await self.price_module.process({})
        self.assertIn("status", data)
        self.assertTrue(isinstance(data, dict))
        self.assertIn("hourly_data", data)
        self.assertIn("five_min_data", data)

        notif_data = await self.price_module.get_notification_data()
        self.assertIsNotNone(notif_data, "Notification data should not be None")
        if notif_data:  # Type guard for None
            self.assertIn("current_price", notif_data)

    async def async_test_pattern_analysis(self):
        """Test pattern analysis module functionality"""
        result = await self.pattern_module.initialize()
        self.assertTrue(result)

        test_data = {
            'current_price': 2.5,
            'timestamp': datetime.now()
        }

        # Process multiple data points
        for i in range(24):
            test_data['timestamp'] = datetime.now() - timedelta(hours=i)
            test_data['current_price'] = 2.5 + (i % 6) * 0.1  # Create a pattern
            result = await self.pattern_module.process(test_data)
            self.assertEqual(result["status"], "success")
            self.assertIn("analysis", result)

        # Verify analysis results
        if "analysis" in result and result["status"] == "success":
            analysis = result["analysis"]
            self.assertIn("volatility", analysis)
            self.assertIn("trend", analysis)
            self.assertIn("patterns", analysis)

        # Test notification data
        notif_data = await self.pattern_module.get_notification_data()
        self.assertIsNotNone(notif_data, "Pattern analysis notification data should not be None")
        if notif_data:  # Type guard for None
            self.assertIn("current_trend", notif_data)
            self.assertIn("volatility", notif_data)

    def test_price_monitor(self):
        """Runner for async price monitor tests"""
        asyncio.run(self.async_test_price_monitor())

    def test_pattern_analysis(self):
        """Runner for async pattern analysis tests"""
        asyncio.run(self.async_test_pattern_analysis())

if __name__ == '__main__':
    unittest.main()