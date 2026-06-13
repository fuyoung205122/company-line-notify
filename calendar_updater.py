import urllib.request
import json
import ssl
import argparse
import sys
import datetime

CONFIG_FILE = 'config.json'
CALENDAR_API_URL = 'https://cdn.jsdelivr.net/gh/ruyut/TaiwanCalendar/data/{year}.json'

def fetch_calendar(year):
    url = CALENDAR_API_URL.format(year=year)
    print(f"Downloading calendar data for {year} from {url}...")
    try:
        # Ignore SSL certificate errors
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        res = urllib.request.urlopen(req, context=ctx)
        data = json.loads(res.read().decode('utf-8'))
        return data
    except Exception as e:
        print(f"Error fetching calendar data: {e}")
        sys.exit(1)

def format_date(date_str):
    """Convert YYYYMMDD to YYYY-MM-DD"""
    if len(date_str) == 8:
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    return date_str

def process_calendar(data):
    holidays = []
    workdays = []
    
    for item in data:
        date_str = format_date(item.get('date', ''))
        is_holiday = item.get('isHoliday', False)
        week = item.get('week', '')
        
        # 國定假日 (原本是平日，但放假)
        if is_holiday and week not in ['六', '日']:
            holidays.append(date_str)
            
        # 補班日 (原本是假日，但要上班)
        if not is_holiday and week in ['六', '日']:
            workdays.append(date_str)
            
    return sorted(holidays), sorted(workdays)

def update_config(year, holidays, workdays):
    print(f"Reading {CONFIG_FILE}...")
    try:
        with open(CONFIG_FILE, 'r', encoding='utf-8') as f:
            config = json.load(f)
    except FileNotFoundError:
        print(f"Error: {CONFIG_FILE} not found.")
        sys.exit(1)
    except json.JSONDecodeError:
        print(f"Error: {CONFIG_FILE} is not a valid JSON file.")
        sys.exit(1)
        
    config_key = f"calendar_{year}"
    
    # Update config
    config[config_key] = {
        "holidays": holidays,
        "workdays": workdays
    }
    
    print(f"Writing {len(holidays)} holidays and {len(workdays)} workdays to {CONFIG_FILE}...")
    with open(CONFIG_FILE, 'w', encoding='utf-8') as f:
        json.dump(config, f, indent=4, ensure_ascii=False)
        
    print(f"Successfully updated {config_key} in {CONFIG_FILE}.")
    print("\n" + "="*50)
    print("! 重要提醒 (IMPORTANT) !")
    print("已成功抓取政府行事曆。若貴公司有特休或專屬休假日 (例如：勞動節 05-01、廠慶等)")
    print("請務必手動開啟 config.json 並將其加入 holidays 陣列中！")
    print("="*50 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Update config.json with Taiwan government calendar data.')
    parser.add_argument('--year', type=int, required=True, help='Year to update (e.g. 2027)')
    args = parser.parse_args()
    
    year = args.year
    
    # 1. Fetch data
    data = fetch_calendar(year)
    
    if not data:
        print("Received empty data from API.")
        sys.exit(1)
        
    # 2. Process data
    holidays, workdays = process_calendar(data)
    
    # 3. Update config.json
    update_config(year, holidays, workdays)

if __name__ == "__main__":
    main()
