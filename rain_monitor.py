import os
import json
import time
import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import requests
import pytz
import holidays
import traceback
import io
from PIL import Image
import numpy as np

# 檔案路徑設定
DIR_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(DIR_PATH, "config.json")
STATE_FILE = os.path.join(DIR_PATH, "state.json")
SECRETS_FILE = os.path.join(DIR_PATH, "secrets.json")

# 讀取本機 secrets.json 作為環境變數的備援
SECRETS = {}
if os.path.exists(SECRETS_FILE):
    try:
        with open(SECRETS_FILE, 'r', encoding='utf-8') as f:
            SECRETS = json.load(f)
    except Exception as e:
        print(f"警告：讀取 secrets.json 失敗: {e}")

def get_env_or_secret(key):
    return os.environ.get(key) or SECRETS.get(key)

def load_json(filepath):
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_json(filepath, data):
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def send_line_message(message, token, group_id):
    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    data = {
        "to": group_id,
        "messages": [
            {
                "type": "text",
                "text": message
            }
        ]
    }
    try:
        response = requests.post(url, headers=headers, json=data)
        response.raise_for_status()
        print(f"LINE Messaging API 發送至 {group_id} 成功。")
        return True
    except Exception as e:
        print(f"LINE Messaging API 發送至 {group_id} 失敗: {e}")
        return False

def get_line_group_ids(line_group):
    if not line_group:
        return []
    return [gid.strip() for gid in line_group.split(',') if gid.strip()]

def send_to_all_line_groups(message, token, line_group, enable_line_notifications=True):
    if not enable_line_notifications:
        print("[手動控制] LINE 通知已手動暫停（enable_line_notifications=False），不進行實際發送。")
        return True
    group_ids = get_line_group_ids(line_group)
    print(f"LINE 目標群組數量: {len(group_ids)}")
    if not token or not group_ids:
        print("警告：LINE token 或群組 ID 未設定，無法發送 LINE 訊息。")
        return False
    results = [send_line_message(message, token, gid) for gid in group_ids]
    return all(results)

def send_error_email(error_msg, config):
    sender_email = get_env_or_secret("GMAIL_USER")
    sender_pass = get_env_or_secret("GMAIL_APP_PASSWORD")
    recipient = config['email']['recipient']
    
    if not sender_email or not sender_pass:
        print("警告：未設定 GMAIL_USER 或 GMAIL_APP_PASSWORD，無法發送錯誤通知信。")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = "[警告] 廠區降雨自動通知系統發生錯誤"
    
    body = f"系統發生錯誤，請盡速檢查：\n\n{error_msg}"
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
        print(f"錯誤通知信已發送至 {recipient}")
    except Exception as e:
        print(f"發送 email 失敗: {e}")

def send_quota_warning_email(remaining, config):
    sender_email = get_env_or_secret("GMAIL_USER")
    sender_pass = get_env_or_secret("GMAIL_APP_PASSWORD")
    recipient = config['email']['recipient']
    
    if not sender_email or not sender_pass:
        print("警告：未設定 GMAIL_USER 或 GMAIL_APP_PASSWORD，無法發送額度警告信。")
        return

    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = recipient
    msg['Subject'] = "[注意] 廠區天氣廣播 LINE 免費推播額度即將用盡"
    
    body = f"廠區天氣廣播 LINE 官方帳號本月的免費額度 (200則) 已經快用完了！\n\n目前剩餘免費額度：大約 {remaining} 則\n\n請留意接下來的推播可能會無法發送，或者您需要前往 LINE 官方後台升級方案。"
    msg.attach(MIMEText(body, 'plain', 'utf-8'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, sender_pass)
        server.send_message(msg)
        server.quit()
        print(f"額度警告信已發送至 {recipient}")
    except Exception as e:
        print(f"發送額度警告信失敗: {e}")

def check_quota_and_notify(line_token, config, state, current_month_str):
    if state.get('quota_warning_sent_month') == current_month_str:
        return
        
    url = "https://api.line.me/v2/bot/message/quota/consumption"
    headers = {"Authorization": f"Bearer {line_token}"}
    try:
        resp = requests.get(url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json()
            total_usage = data.get('totalUsage', 0)
            remaining = 200 - total_usage
            if remaining < 10:
                print(f"剩餘訊息少於 10 則 (剩餘 {remaining} 則)，發送警告信件。")
                send_quota_warning_email(remaining, config)
                state['quota_warning_sent_month'] = current_month_str
    except Exception as e:
        print(f"檢查 LINE 額度失敗: {e}")

def get_weather_open_meteo(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&timezone=Asia%2FTaipei"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    
    current_data = data.get('current', {})
    precip = current_data.get('precipitation', 0)
    obs_time_utc = current_data.get('time', '')
    
    # 轉換時間格式，Open-Meteo 回傳格式如 "2026-06-07T10:00"
    try:
        dt = datetime.datetime.strptime(obs_time_utc, "%Y-%m-%dT%H:%M")
        obs_time_str = dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        tw_tz = pytz.timezone('Asia/Taipei')
        obs_time_str = datetime.datetime.now(tw_tz).strftime("%Y-%m-%d %H:%M:%S")
        
    is_raining = precip > 0
    precip_display = f"{precip} mm/hr"
    
    print(f"Open-Meteo 觀測時間: {obs_time_str}, 雨量: {precip_display}")
    return is_raining, obs_time_str, precip_display, "Open-Meteo (氣象署備用源)"

def get_weather(station_id, api_key, lat, lon):
    # 優先嘗試中央氣象署 API
    try:
        if not api_key:
            raise ValueError("環境變數 CWA_API_KEY 未設定，無法查詢氣象署資料。")
            
        url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001"
        params = {
            "Authorization": api_key,
            "format": "JSON",
            "StationId": station_id
        }
        
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        stations = data.get('records', {}).get('Station', [])
        if not stations:
            raise ValueError(f"氣象署 API 回傳資料中找不到測站代號: {station_id}")
            
        station = stations[0]
        rainfall_element = station.get('RainfallElement', {})
        past_10min = rainfall_element.get('Past10Min', {})
        precip_val = past_10min.get('Precipitation', 0)
        
        obs_time_str = station.get('ObsTime', {}).get('DateTime', '未知時間')
        station_name = station.get('StationName', '安南')
        
        # 處理特殊值
        is_raining = False
        precip_display = ""
        if isinstance(precip_val, (int, float)):
            is_raining = precip_val > 0
            precip_display = f"{precip_val} mm"
        elif isinstance(precip_val, str):
            precip_str = precip_val.strip().upper()
            if precip_str == 'T':
                is_raining = True
                precip_display = "微量雨跡(T)"
            elif precip_str in ('X', '-99'):
                raise ValueError(f"氣象署測站 {station_id} 儀器異常或缺值 (雨量值為: {precip_val})")
            elif precip_str == '-98':
                is_raining = False
                precip_display = "0.0 mm"
            else:
                try:
                    val_f = float(precip_str)
                    is_raining = val_f > 0
                    precip_display = f"{val_f} mm"
                except ValueError:
                    raise ValueError(f"無法解析氣象署雨量值: {precip_val}")
        else:
            raise ValueError(f"未知的氣象署雨量資料型態: {type(precip_val)} (值: {precip_val})")
            
        print(f"氣象署觀測時間: {obs_time_str}, 測站: {station_name}({station_id}), 過去10分鐘雨量值: {precip_display}")
        return is_raining, obs_time_str, precip_display, f"中央氣象署 ({station_name}站)"
        
    except Exception as e:
        print(f"警告：中央氣象署 API 查詢失敗（原因：{e}），自動切換至備援 Open-Meteo 天氣源...")
        try:
            return get_weather_open_meteo(lat, lon)
        except Exception as fallback_err:
            raise RuntimeError(f"主要天氣源與備援天氣源皆查詢失敗。主要錯誤: {e} | 備援錯誤: {fallback_err}")

def get_weather_description(station_id, api_key):
    if not api_key:
        raise ValueError("CWA_API_KEY 未設定，無法查詢天氣現象描述。")
    url = "https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0003-001"
    params = {
        "Authorization": api_key,
        "format": "JSON",
        "StationId": station_id
    }
    response = requests.get(url, params=params, timeout=10)
    response.raise_for_status()
    data = response.json()
    stations = data.get('records', {}).get('Station', [])
    if not stations:
        raise ValueError(f"O-A0003-001 回傳資料中找不到測站代號: {station_id}")
    station = stations[0]
    weather_element = station.get('WeatherElement', {})
    weather = weather_element.get('Weather', '未知')
    obs_time = station.get('ObsTime', {}).get('DateTime', '未知時間')
    return weather.strip(), obs_time

def get_radar_echo(api_key, factory_x, factory_y, radius_px, threshold_diff=20, threshold_count=3):
    if not api_key:
        raise ValueError("CWA_API_KEY 未設定，無法查詢雷達回波圖。")
    
    # 1. 取得雷達回波圖的最新 URL
    meta_url = "https://opendata.cwa.gov.tw/fileapi/v1/opendataapi/O-A0058-001"
    params = {
        "Authorization": api_key,
        "format": "JSON"
    }
    meta_resp = requests.get(meta_url, params=params, timeout=10)
    meta_resp.raise_for_status()
    meta_data = meta_resp.json()
    
    product_url = meta_data.get('cwaopendata', {}).get('dataset', {}).get('resource', {}).get('ProductURL')
    if not product_url:
        raise ValueError("未能在 O-A0058-001 檔案資訊中找到 ProductURL")
        
    # 2. 下載雷達回波圖 PNG
    img_resp = requests.get(product_url, timeout=15)
    img_resp.raise_for_status()
    
    # 3. 讀取並分析影像像素
    img = Image.open(io.BytesIO(img_resp.content))
    img_arr = np.array(img)
    
    if len(img_arr.shape) != 3 or img_arr.shape[2] < 3:
        raise ValueError(f"雷達影像色彩通道異常，陣列形狀為: {img_arr.shape}")
        
    h, w, _ = img_arr.shape
    y_min = max(0, factory_y - radius_px)
    y_max = min(h, factory_y + radius_px + 1)
    x_min = max(0, factory_x - radius_px)
    x_max = min(w, factory_x + radius_px + 1)
    
    sub_grid = img_arr[y_min:y_max, x_min:x_max]
    
    # 使用 numpy 向量化快速計算
    y_idx, x_idx = np.ogrid[y_min - factory_y : y_max - factory_y, x_min - factory_x : x_max - factory_x]
    circle_mask = (x_idx**2 + y_idx**2 <= radius_px**2)
    
    sub_grid_int = sub_grid.astype(int)
    max_val = np.max(sub_grid_int[:, :, :3], axis=2)
    min_val = np.min(sub_grid_int[:, :, :3], axis=2)
    diff_val = max_val - min_val
    
    echo_mask = circle_mask & (diff_val >= threshold_diff)
    echo_count = np.sum(echo_mask)
    
    has_echo = echo_count >= threshold_count
    return has_echo, int(echo_count)

def main():
    try:
        # 讀取設定檔
        config = load_json(CONFIG_FILE)
        state = load_json(STATE_FILE)
        
        tw_tz = pytz.timezone('Asia/Taipei')
        now = datetime.datetime.now(tw_tz)
        today_str = now.strftime('%Y-%m-%d')
        
        print(f"--- 系統執行時間: {now.strftime('%Y-%m-%d %H:%M:%S')} ---")
        import sys
        force_run = "--force" in sys.argv
        test_line = "--test-line" in sys.argv
        enable_line = config.get("enable_line_notifications", True)
        line_token = get_env_or_secret("LINE_CHANNEL_ACCESS_TOKEN")
        line_group = get_env_or_secret("LINE_GROUP_ID")

        if test_line:
            print("偵測到 --test-line 參數，執行 LINE 測試發送。")
            test_msg = (
                f"✅ LINE 測試通知\n"
                f"系統時間：{now.strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"這是一則測試訊息，用來確認群組通知設定正常。"
            )
            sent = send_to_all_line_groups(test_msg, line_token, line_group, enable_line)
            if not sent:
                raise ValueError("LINE 測試發送失敗：請檢查 LINE token、群組 ID、官方帳號是否已加入群組。")
            return
        
        # 1. 每日跨日重置機制
        # 如果今天還沒有執行過重置（跨日後第一次執行），就重置狀態。
        if state.get('last_reset_date') != today_str:
            print(f"執行每日跨日重置 (上次重置日期: {state.get('last_reset_date')} -> 今日: {today_str})...")
            state['is_covered'] = False
            state['last_rain_time'] = None
            state['last_reset_date'] = today_str
            save_json(STATE_FILE, state)
            print("狀態檔重置完成。")
            
        # 2. 營業時間檢查 (週一至週五非國定假日 08:00-19:00)
        if force_run:
            print("偵測到 --force 參數，跳過時間、週末及國定假日限制，強制執行天氣檢查。")

        current_date = now.date()
        
        if current_date.year == 2026 and 'calendar_2026' in config:
            # 依據 config.json 中的東陽 2026 行事曆設定
            cal_config = config['calendar_2026']
            tyg_holidays_2026 = {
                datetime.datetime.strptime(d, '%Y-%m-%d').date()
                for d in cal_config.get('holidays', [])
            }
            tyg_workdays_weekend_2026 = {
                datetime.datetime.strptime(d, '%Y-%m-%d').date()
                for d in cal_config.get('workdays', [])
            }
            
            if current_date in tyg_holidays_2026 and not force_run:
                print("今天是東陽行事曆國定假日，不執行檢查。")
                return
            if now.weekday() >= 5 and current_date not in tyg_workdays_weekend_2026 and not force_run:
                print("今天是週末，不執行檢查。")
                return
        else:
            # 非 2026 年，回退使用內建台灣國定假日
            tw_holidays = holidays.TW(years=now.year)
            if (current_date in tw_holidays or now.weekday() >= 5) and not force_run:
                print("今天是週末或台灣國定假日，不執行檢查。")
                return
            
        current_time = now.time()
        start_time = datetime.time(7, 30)
        end_time = datetime.time(19, 30)
        
        if not (start_time <= current_time <= end_time) and not force_run:
            print("目前非營業時間 (07:30-19:30)，不執行檢查。")
            return

        # 檢查環境變數是否設定
        cwa_api_key = get_env_or_secret("CWA_API_KEY")
        
        if not line_token or not line_group:
            print("警告：LINE_CHANNEL_ACCESS_TOKEN 或 LINE_GROUP_ID 未設定，若觸發將無法發送 LINE 訊息。")
        else:
            print(f"LINE 設定已讀取，目標群組數量: {len(get_line_group_ids(line_group))}")
        if not cwa_api_key:
            raise ValueError("環境變數或 secrets.json 中的 CWA_API_KEY 未設定，無法查詢中央氣象署降雨資料。")
            
        if line_token:
            current_month_str = now.strftime('%Y-%m')
            check_quota_and_notify(line_token, config, state, current_month_str)

        # 3. 獲取台南市安南區天氣
        lat = config['location']['latitude']
        lon = config['location']['longitude']
        station_id = config['location'].get('cwa_station_id', 'C2O950')
        
        # 3.1 讀取雨量計資料
        try:
            is_raining_gauge, obs_time, precip, source = get_weather(station_id, cwa_api_key, lat, lon)
            print(f"雨量計觀測結果: 是否有雨: {is_raining_gauge} | 觀測時間: {obs_time} | 雨量值: {precip} | 來源: {source}")
        except Exception as e:
            print(f"警告：讀取雨量計資料失敗: {e}，雨量計判定為無雨。")
            is_raining_gauge = False
            obs_time = now.strftime('%Y-%m-%d %H:%M:%S')
            precip = "未知"
            source = "未明 (讀取失敗)"
            
        # 3.2 讀取天氣現象描述
        weather_description = "未知"
        try:
            if cwa_api_key:
                weather_description, _ = get_weather_description(station_id, cwa_api_key)
                print(f"氣象署測站天氣現象描述: '{weather_description}'")
            else:
                print("未設定 CWA_API_KEY，跳過氣象署天氣描述檢查。")
        except Exception as e:
            print(f"警告：讀取氣象署天氣現象描述失敗: {e}")
            
        # 3.3 讀取雷達回波
        has_radar_echo_cover = False
        has_radar_echo_uncover = False
        radar_pixels_cover = 0
        radar_pixels_uncover = 0
        
        r_settings = config.get('radar_settings', {})
        cov_rad = r_settings.get('cover_radius_px', 28)
        uncov_rad = r_settings.get('uncover_radius_px', 56)
        echo_pixel_thres = r_settings.get('echo_pixel_threshold', 3)
        color_diff_thres = r_settings.get('color_diff_threshold', 20)
        fact_x = config['location'].get('factory_pixel_x', 1623)
        fact_y = config['location'].get('factory_pixel_y', 1941)
        
        try:
            if cwa_api_key:
                has_radar_echo_cover, radar_pixels_cover = get_radar_echo(
                    cwa_api_key, fact_x, fact_y, cov_rad, color_diff_thres, echo_pixel_thres
                )
                has_radar_echo_uncover, radar_pixels_uncover = get_radar_echo(
                    cwa_api_key, fact_x, fact_y, uncov_rad, color_diff_thres, echo_pixel_thres
                )
                print(f"雷達回波檢測: 10km半徑內是否有回波: {has_radar_echo_cover} (回波點數: {radar_pixels_cover}) | 20km半徑內是否有回波: {has_radar_echo_uncover} (回波點數: {radar_pixels_uncover})")
            else:
                print("未設定 CWA_API_KEY，跳過雷達回波檢查。")
        except Exception as e:
            print(f"警告：讀取或解析雷達回波圖失敗: {e}")
        
        current_time_ts = now.timestamp()
        
        # 4. 核心邏輯判斷
        # 4.1 檢查是否有任何降雨訊號 (加蓋條件)
        rain_keywords = ["雨", "小雨", "細雨", "陣雨", "毛毛雨"]
        is_raining_phenomena = any(kw in weather_description for kw in rain_keywords)
        
        # 滿足以下任一條件即判定為降雨 (加蓋帆布觸發)
        # 1. 天氣現象有雨相關關鍵字
        # 2. 雨量計顯示有雨 (>0 或 T)
        # 3. 雷達回波 10km 內有降雨區
        has_rain_now = is_raining_phenomena or is_raining_gauge or has_radar_echo_cover
        
        radar_info = f"10km半徑內有回波 ({radar_pixels_cover}點)" if has_radar_echo_cover else "無回波"
        info_header = (
            f"🔔【即時觀測數據】\n"
            f"📊 觀測時間：{obs_time}\n"
            f"💧 當前雨量：{precip}\n"
            f"📝 天氣現象：{weather_description}\n"
            f"📡 雷達回波：{radar_info}\n"
            f"🌐 資料來源：{source}\n"
            f"======================\n\n"
        )
        
        if has_rain_now:
            # 只要判定有降雨，就持續更新最後降雨時間
            state['last_rain_time'] = current_time_ts
            
            if not state['is_covered']:
                # 狀態轉移: 🟢 -> 🔴
                print("👉 滿足加蓋防呆條件！準備發送【加蓋帆布】通知。")
                full_msg = info_header + config['messages']['cover']
                send_to_all_line_groups(full_msg, line_token, line_group, enable_line)
                state['is_covered'] = True
            else:
                # 狀態鎖定: 🔴 -> 🔴
                print("目前已處於加蓋狀態，且偵測到降雨訊號，不重複發送通知。")
        else:
            if state['is_covered']:
                # 4.2 檢查是否滿足解除加蓋條件 (必須全部滿足)
                # 1. 天氣現象沒有降雨相關關鍵字描述
                cond1 = not is_raining_phenomena
                # 2. 雨量計判定無雨
                cond2 = not is_raining_gauge
                # 3. 未來30分鐘無降雨接近 (雷達回波 20km 內無降雨區)
                cond3 = not has_radar_echo_uncover
                # 4. 連續60分鐘無降雨 (最後一次下雨時間已過 3600 秒)
                last_rain = state.get('last_rain_time')
                if last_rain is not None:
                    diff_seconds = current_time_ts - last_rain
                    diff_minutes = diff_seconds / 60.0
                    cond4 = diff_seconds >= 3600
                    print(f"目前無雨。距離最後一次下雨已過: {diff_minutes:.1f} 分鐘 (解除需滿 60 分鐘)。")
                else:
                    cond4 = True
                    print("異常：沒有最後降雨時間紀錄，防呆預設允許解除。")
                
                print(f"解除條件檢查: 天氣現象無雨={cond1} | 雨量計無雨={cond2} | 20km雷達無雨={cond3} | 已過60分鐘={cond4}")
                
                if cond1 and cond2 and cond3 and cond4:
                    # 狀態轉移: 🔴 -> 🟢
                    print("👉 已停雨且滿足所有解除條件！準備發送【暫不加蓋】通知。")
                    full_msg = info_header + config['messages']['uncover']
                    send_to_all_line_groups(full_msg, line_token, line_group, enable_line)
                    state['is_covered'] = False
                    state['last_rain_time'] = None
                else:
                    # 狀態鎖定: 🔴
                    print("未滿足所有解除條件，保持加蓋狀態。")
                    
        # 寫入狀態 (若被改變)
        save_json(STATE_FILE, state)
        print("本次檢查結束。")

    except Exception as e:
        error_msg = traceback.format_exc()
        print(f"發生未預期錯誤:\n{error_msg}")
        try:
            config = load_json(CONFIG_FILE)
            send_error_email(error_msg, config)
        except Exception as e2:
            print(f"無法發送錯誤通知信: {e2}")
        # 如果是在 GitHub Actions 中，我們用 exit(1) 讓腳本亮紅燈
        import sys
        sys.exit(1)

if __name__ == "__main__":
    main()
