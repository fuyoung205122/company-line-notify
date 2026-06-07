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

# 檔案路徑設定
DIR_PATH = os.path.dirname(os.path.abspath(__file__))
CONFIG_FILE = os.path.join(DIR_PATH, "config.json")
STATE_FILE = os.path.join(DIR_PATH, "state.json")

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
    except Exception as e:
        print(f"LINE Messaging API 發送至 {group_id} 失敗: {e}")

def send_error_email(error_msg, config):
    sender_email = os.environ.get("GMAIL_USER")
    sender_pass = os.environ.get("GMAIL_APP_PASSWORD")
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
    sender_email = os.environ.get("GMAIL_USER")
    sender_pass = os.environ.get("GMAIL_APP_PASSWORD")
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

def main():
    try:
        # 讀取設定檔
        config = load_json(CONFIG_FILE)
        state = load_json(STATE_FILE)
        
        tw_tz = pytz.timezone('Asia/Taipei')
        now = datetime.datetime.now(tw_tz)
        today_str = now.strftime('%Y-%m-%d')
        
        print(f"--- 系統執行時間: {now.strftime('%Y-%m-%d %H:%M:%S')} ---")
        
        # 1. 每日 23:00 重置機制
        # 如果時間是 23:00 之後，且今天還沒執行過重置，就立刻重置。
        if now.hour >= 23 and state.get('last_reset_date') != today_str:
            print("執行每日 23:00 重置...")
            state['is_covered'] = False
            state['last_rain_time'] = None
            state['last_reset_date'] = today_str
            save_json(STATE_FILE, state)
            print("狀態檔重置完成。")
            return
            
        # 2. 營業時間檢查 (週一至週五非國定假日 08:00-19:00)
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
            
            if current_date in tyg_holidays_2026:
                print("今天是東陽行事曆國定假日，不執行檢查。")
                return
            if now.weekday() >= 5 and current_date not in tyg_workdays_weekend_2026:
                print("今天是週末，不執行檢查。")
                return
        else:
            # 非 2026 年，回退使用內建台灣國定假日
            tw_holidays = holidays.TW(years=now.year)
            if current_date in tw_holidays or now.weekday() >= 5:
                print("今天是週末或台灣國定假日，不執行檢查。")
                return
            
        current_time = now.time()
        start_time = datetime.time(7, 30)
        end_time = datetime.time(19, 30)
        
        if not (start_time <= current_time <= end_time):
            print("目前非營業時間 (07:30-19:30)，不執行檢查。")
            return

        # 檢查環境變數是否設定
        line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        line_group = os.environ.get("LINE_GROUP_ID")
        cwa_api_key = os.environ.get("CWA_API_KEY")
        
        if not line_token or not line_group:
            print("警告：LINE_CHANNEL_ACCESS_TOKEN 或 LINE_GROUP_ID 未設定，若觸發將無法發送 LINE 訊息。")
        if not cwa_api_key:
            raise ValueError("環境變數 CWA_API_KEY 未設定，無法查詢中央氣象署降雨資料。")
            
        if line_token:
            current_month_str = now.strftime('%Y-%m')
            check_quota_and_notify(line_token, config, state, current_month_str)

        # 3. 獲取台南市安南區天氣
        lat = config['location']['latitude']
        lon = config['location']['longitude']
        station_id = config['location'].get('cwa_station_id', 'C2O950')
        is_raining, obs_time, precip, source = get_weather(station_id, cwa_api_key, lat, lon)
        print(f"天氣檢查完畢。目前是否降雨(或毛毛雨): {is_raining} (資料來源: {source})")
        
        current_time_ts = now.timestamp()
        
        # 4. 核心邏輯判斷
        info_header = (
            f"🔔【即時觀測數據】\n"
            f"📊 觀測時間：{obs_time}\n"
            f"💧 降雨量：{precip}\n"
            f"🌐 資料來源：{source}\n"
            f"======================\n\n"
        )
        
        if is_raining:
            # 只要有下雨，就不斷更新「最後下雨時間」
            state['last_rain_time'] = current_time_ts
            
            if not state['is_covered']:
                # 如果原本沒蓋，現在下雨了 -> 觸發蓋帆布通知
                print("👉 偵測到開始下雨！準備發送【蓋上帆布】通知。")
                if line_token and line_group:
                    full_msg = info_header + config['messages']['cover']
                    for gid in line_group.split(','):
                        gid = gid.strip()
                        if gid:
                            send_line_message(full_msg, line_token, gid)
                state['is_covered'] = True
        else:
            if state['is_covered']:
                # 目前沒下雨，但帆布是蓋著的 -> 開始計算是否超過 30 分鐘
                last_rain = state.get('last_rain_time')
                if last_rain is not None:
                    diff_minutes = (current_time_ts - last_rain) / 60.0
                    print(f"目前無雨。距離最後一次下雨已過: {diff_minutes:.1f} 分鐘。")
                    if diff_minutes >= 30:
                        print("👉 停雨已達 30 分鐘！準備發送【不蓋帆布】通知。")
                        if line_token and line_group:
                            full_msg = info_header + config['messages']['uncover']
                            for gid in line_group.split(','):
                                gid = gid.strip()
                                if gid:
                                    send_line_message(full_msg, line_token, gid)
                        state['is_covered'] = False
                        state['last_rain_time'] = None # 重置下雨時間
                else:
                    # 異常狀態防呆：有蓋帆布卻沒有記錄時間，直接解除
                    print("異常：帆布為蓋上狀態，但無下雨時間紀錄。直接重置狀態。")
                    if line_token and line_group:
                        full_msg = info_header + config['messages']['uncover']
                        for gid in line_group.split(','):
                            gid = gid.strip()
                            if gid:
                                send_line_message(full_msg, line_token, gid)
                    state['is_covered'] = False
                    
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
