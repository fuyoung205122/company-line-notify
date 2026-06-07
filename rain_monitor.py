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

def get_weather(lat, lon):
    url = f"https://api.open-meteo.com/v1/forecast?latitude={lat}&longitude={lon}&current=precipitation&timezone=Asia%2FTaipei"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    precip = data.get('current', {}).get('precipitation', 0)
    return precip > 0

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
        
        if current_date.year == 2026:
            # 依據東陽 2026 行事曆
            tyg_holidays_2026 = {
                datetime.date(2026, 1, 1),   # 元旦
                datetime.date(2026, 2, 16),  # 除夕
                datetime.date(2026, 2, 17),  # 春節
                datetime.date(2026, 2, 18),  # 初二
                datetime.date(2026, 2, 19),  # 初三
                datetime.date(2026, 2, 20),  # 補假(小年夜)
                datetime.date(2026, 2, 27),  # 補假(和平紀念日)
                datetime.date(2026, 4, 3),   # 補假(兒童節)
                datetime.date(2026, 4, 6),   # 補假(清明節)
                datetime.date(2026, 5, 1),   # 勞動節
                datetime.date(2026, 6, 19),  # 端午節
                datetime.date(2026, 9, 25),  # 中秋節
                datetime.date(2026, 9, 28),  # 教師節
                datetime.date(2026, 10, 9),  # 補假(國慶日)
                datetime.date(2026, 10, 26), # 補假(光復節)
                datetime.date(2026, 12, 25), # 行憲紀念日
                datetime.date(2026, 12, 31), # 盤點休假
            }
            # 週末補班日
            tyg_workdays_weekend_2026 = {
                datetime.date(2026, 12, 19), # 現場上班
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
            
        if now.hour < 8 or now.hour >= 19:
            print("目前非營業時間 (08:00-19:00)，不執行檢查。")
            return

        # 檢查 LINE Token 與 Group ID 是否已設定
        line_token = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
        line_group = os.environ.get("LINE_GROUP_ID")
        if not line_token or not line_group:
            print("警告：LINE_CHANNEL_ACCESS_TOKEN 或 LINE_GROUP_ID 未設定，若觸發將無法發送 LINE 訊息。")
            
        # 3. 獲取台南市安南區天氣
        lat = config['location']['latitude']
        lon = config['location']['longitude']
        is_raining = get_weather(lat, lon)
        print(f"天氣檢查完畢。目前是否降雨(或毛毛雨): {is_raining}")
        
        current_time_ts = now.timestamp()
        
        # 4. 核心邏輯判斷
        if is_raining:
            # 只要有下雨，就不斷更新「最後下雨時間」
            state['last_rain_time'] = current_time_ts
            
            if not state['is_covered']:
                # 如果原本沒蓋，現在下雨了 -> 觸發蓋帆布通知
                print("👉 偵測到開始下雨！準備發送【蓋上帆布】通知。")
                if line_token and line_group:
                    for gid in line_group.split(','):
                        gid = gid.strip()
                        if gid:
                            send_line_message(config['messages']['cover'], line_token, gid)
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
                            for gid in line_group.split(','):
                                gid = gid.strip()
                                if gid:
                                    send_line_message(config['messages']['uncover'], line_token, gid)
                        state['is_covered'] = False
                        state['last_rain_time'] = None # 重置下雨時間
                else:
                    # 異常狀態防呆：有蓋帆布卻沒有記錄時間，直接解除
                    print("異常：帆布為蓋上狀態，但無下雨時間紀錄。直接重置狀態。")
                    if line_token and line_group:
                        for gid in line_group.split(','):
                            gid = gid.strip()
                            if gid:
                                send_line_message(config['messages']['uncover'], line_token, gid)
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
