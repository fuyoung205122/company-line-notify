import unittest
import datetime
from unittest.mock import patch, MagicMock

import rain_monitor

class TestRainMonitor(unittest.TestCase):
    
    def test_load_json(self):
        # 測試是否能正確讀取設定檔及行事曆設定
        config = rain_monitor.load_json(rain_monitor.CONFIG_FILE)
        self.assertIn("location", config)
        self.assertIn("calendar_2026", config)
        self.assertIn("holidays", config["calendar_2026"])

    @patch('rain_monitor.requests.get')
    def test_get_weather_rain(self, mock_get):
        # 模擬天氣 API 回傳下雨數據 (1.5mm)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "current": {
                "precipitation": 1.5
            }
        }
        mock_get.return_value = mock_resp
        
        is_raining = rain_monitor.get_weather(23.0485, 120.186)
        self.assertTrue(is_raining)

    @patch('rain_monitor.requests.get')
    def test_get_weather_no_rain(self, mock_get):
        # 模擬天氣 API 回傳無雨數據 (0.0mm)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "current": {
                "precipitation": 0.0
            }
        }
        mock_get.return_value = mock_resp
        
        is_raining = rain_monitor.get_weather(23.0485, 120.186)
        self.assertFalse(is_raining)

if __name__ == '__main__':
    unittest.main()
