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
        # 模擬中央氣象署 API 回傳下雨數據 (1.5mm)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "records": {
                "Station": [{
                    "StationName": "安南",
                    "ObsTime": {"DateTime": "2026-06-08T08:00:00+08:00"},
                    "RainfallElement": {
                        "Past10Min": {"Precipitation": 1.5}
                    }
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        is_raining, obs_time, precip, source = rain_monitor.get_weather("C2O950", "test-key", 23.0485, 120.186)
        self.assertTrue(is_raining)
        self.assertEqual(precip, "1.5 mm")
        self.assertIn("中央氣象署", source)

    @patch('rain_monitor.requests.get')
    def test_get_weather_no_rain(self, mock_get):
        # 模擬中央氣象署 API 回傳無雨數據 (0.0mm)
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "records": {
                "Station": [{
                    "StationName": "安南",
                    "ObsTime": {"DateTime": "2026-06-08T08:00:00+08:00"},
                    "RainfallElement": {
                        "Past10Min": {"Precipitation": 0.0}
                    }
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        is_raining, obs_time, precip, source = rain_monitor.get_weather("C2O950", "test-key", 23.0485, 120.186)
        self.assertFalse(is_raining)
        self.assertEqual(precip, "0.0 mm")
        self.assertIn("中央氣象署", source)

    def test_get_line_group_ids(self):
        group_ids = rain_monitor.get_line_group_ids("group-a, group-b,, ")
        self.assertEqual(group_ids, ["group-a", "group-b"])

    @patch('rain_monitor.send_line_message')
    def test_send_to_all_line_groups_reports_failure(self, mock_send):
        mock_send.side_effect = [True, False]
        result = rain_monitor.send_to_all_line_groups("test", "token", "group-a,group-b")
        self.assertFalse(result)

    @patch('rain_monitor.requests.get')
    def test_get_weather_description_success(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            "records": {
                "Station": [{
                    "StationName": "安南",
                    "ObsTime": {"DateTime": "2026-06-08T09:10:00+08:00"},
                    "WeatherElement": {
                        "Weather": "毛毛雨"
                    }
                }]
            }
        }
        mock_get.return_value = mock_resp
        
        weather, obs_time = rain_monitor.get_weather_description("C2O950", "test-key")
        self.assertEqual(weather, "毛毛雨")
        self.assertEqual(obs_time, "2026-06-08T09:10:00+08:00")

    @patch('rain_monitor.requests.get')
    def test_get_radar_echo_with_rain(self, mock_get):
        mock_meta_resp = MagicMock()
        mock_meta_resp.json.return_value = {
            "cwaopendata": {
                "dataset": {
                    "resource": {
                        "ProductURL": "https://dummy-url.png"
                    }
                }
            }
        }
        
        from PIL import Image
        import io
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        img.putpixel((50, 50), (0, 255, 0))
        img.putpixel((50, 51), (0, 255, 0))
        img.putpixel((51, 50), (0, 255, 0))
        
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        mock_img_resp = MagicMock()
        mock_img_resp.content = img_bytes.read()
        
        mock_get.side_effect = [mock_meta_resp, mock_img_resp]
        
        has_echo, count = rain_monitor.get_radar_echo("test-key", 50, 50, 5, 20, 3)
        self.assertTrue(has_echo)
        self.assertEqual(count, 3)

    @patch('rain_monitor.requests.get')
    def test_get_radar_echo_no_rain(self, mock_get):
        mock_meta_resp = MagicMock()
        mock_meta_resp.json.return_value = {
            "cwaopendata": {
                "dataset": {
                    "resource": {
                        "ProductURL": "https://dummy-url.png"
                    }
                }
            }
        }
        
        from PIL import Image
        import io
        img = Image.new("RGB", (100, 100), (255, 255, 255))
        img_bytes = io.BytesIO()
        img.save(img_bytes, format='PNG')
        img_bytes.seek(0)
        
        mock_img_resp = MagicMock()
        mock_img_resp.content = img_bytes.read()
        
        mock_get.side_effect = [mock_meta_resp, mock_img_resp]
        
        has_echo, count = rain_monitor.get_radar_echo("test-key", 50, 50, 5, 20, 3)
        self.assertFalse(has_echo)
        self.assertEqual(count, 0)

    @patch('rain_monitor.send_line_message')
    def test_send_to_all_line_groups_disabled(self, mock_send):
        # 測試手動關閉 LINE 通知時，是否不會呼叫 API 發送，且返回 True
        result = rain_monitor.send_to_all_line_groups("test msg", "token", "group-a", enable_line_notifications=False)
        self.assertTrue(result)
        mock_send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
