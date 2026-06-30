import os
import requests
import pymysql
import time
from datetime import datetime
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import urllib3
# 🔌 引入環境變數載入器
from dotenv import load_dotenv
load_dotenv() # 💡 這行會自動去尋找同目錄下的 .env 檔案並讀取它！

# 關閉政府 API 憑證到期警告
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")

# 🐬 【1. MySQL Workbench 資料庫連線設定】
DB_SETTINGS = {
    "host": os.getenv("DB_HOST", "127.0.0.1"),
    "port": int(os.getenv("DB_PORT", 3306)),
    "user": os.getenv("DB_USER", "root"),
    "password": os.getenv("DB_PASSWORD"),  # 🔒 已成功隱藏實體密碼
    "database": os.getenv("DB_DATABASE", "env_live_data"),
    "charset": "utf8mb4"
}

# 🔑 【2. 政府開放資料 API 金鑰】
ENV_API_KEY = os.getenv("ENV_API_KEY")
CWA_API_KEY = os.getenv("CWA_API_KEY")

# 💡 停車場專用的 TDX 金鑰
TDX_CLIENT_ID = os.getenv("TDX_CLIENT_ID")          # 🔒 請填入你的 TDX Client ID
TDX_CLIENT_SECRET = os.getenv("TDX_CLIENT_SECRET")  # 🔒 請填入你的 TDX Client Secret

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

def safe_convert(val, to_type):
    """安全資料型態轉換，防止政府 API 欄位拋出空值、破字導致系統崩潰"""
    if val is None or str(val).strip() in ["", "T", "X", "V", "-", "ND"]:
        return None
    try:
        return to_type(str(val).strip())
    except:
        return None
    
"""取得 TDX 平台的動態 Access Token """
def get_tdx_headers():
    
    auth_url = "https://tdx.transportdata.tw/auth/realms/TDXConnect/protocol/openid-connect/token"
    data = {
        "grant_type": "client_credentials",
        "client_id": TDX_CLIENT_ID,
        "client_secret": TDX_CLIENT_SECRET
    }
    try:
        res = requests.post(auth_url, data=data, timeout=10).json()
        token = res.get("access_token")
        return {"Authorization": f"Bearer {token}", "User-Agent": "Mozilla/5.0"}
    except Exception as e:
        print(f"❌ TDX 憑證取得失敗: {e}")
        return None


def is_cache_expired(table_name, county=None, expire_minutes=5):
    """
    ⏳ 智慧快取守門員：檢查資料庫中的資料是否過期
    回傳 True 代表過期（需要重新抓 API），回傳 False 代表新鮮（直接用資料庫快取）
    """
    try:
        conn = pymysql.connect(**DB_SETTINGS)
        cursor = conn.cursor()
        
        # 查詢該表（或該縣市）的最新一筆時間戳記
        if county:
            cursor.execute(f"SELECT MAX(timestamp) FROM {table_name} WHERE county = %s", (county,))
        else:
            cursor.execute(f"SELECT MAX(timestamp) FROM {table_name}")
            
        result = cursor.fetchone()
        conn.close()
        
        if result and result[0]:
            last_update = result[0]
            # 確保型態為 datetime
            if isinstance(last_update, str):
                last_update = datetime.strptime(last_update, '%Y-%m-%d %H:%M:%S')
            
            # 計算時間差（秒），判斷是否大於我們設定的過期時間
            if (datetime.now() - last_update).total_seconds() < (expire_minutes * 60):
                return False  # 🟢 尚未過期，觸發快取！
    except Exception as e:
        print(f"快取檢查異常 ({table_name}): {e}")
        
    return True # 🔴 過期或無資料，強制重新抓取



# ===================================================
# -- 核心 API 路由
# ===================================================

"""環境部 AQI 擷取"""
@app.get("/api/aqi")
def get_aqi():
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        aqi_url = f"https://data.moenv.gov.tw/api/v2/aqx_p_432?limit=1000&api_key={ENV_API_KEY}&format=JSON"
        res = requests.get(aqi_url, headers=HEADERS, verify=False, timeout=10).json()
        aqi_list = res if isinstance(res, list) else res.get('records', [])
        
        conn = pymysql.connect(**DB_SETTINGS)
        cursor = conn.cursor()
        for rec in aqi_list:
            try:
                aqi_val = safe_convert(rec.get('aqi'), int)
                if aqi_val is not None:
                    pm25 = safe_convert(rec.get('pm2.5'), int)
                    pm10 = safe_convert(rec.get('pm10'), int)
                    o3 = safe_convert(rec.get('o3'), float)
                    co = safe_convert(rec.get('co'), float)
                    lat = safe_convert(rec.get('latitude'), float)
                    lon = safe_convert(rec.get('longitude'), float)
                    
                    sql = """
                        INSERT INTO aqi_records (county, sitename, aqi, status, pm25, pm10, o3, co, lat, lon, timestamp) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (rec.get('county'), rec.get('sitename'), aqi_val, rec.get('status'), pm25, pm10, o3, co, lat, lon, current_time))
            except: continue
        conn.commit()
        cursor.close()
        conn.close()
        print("🟢 [環境部 AQI] 資料更新完成。")
    except Exception as e: print(f"❌ AQI 失敗: {e}")

    conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("SELECT county, sitename, aqi, status, pm25, pm10, o3, co, lat, lon FROM aqi_records WHERE timestamp = (SELECT MAX(timestamp) FROM aqi_records)")
    data = cursor.fetchall()
    conn.close()
    return data

"""氣象署 雨量擷取"""
@app.get("/api/rainfall")
def get_rainfall():
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/O-A0002-001?Authorization={CWA_API_KEY}&format=JSON"
        res = requests.get(url, headers=HEADERS, verify=False, timeout=10).json()
        if isinstance(res, dict) and 'records' in res:
            stations = res['records'].get('Station', [])
            conn = pymysql.connect(**DB_SETTINGS)
            cursor = conn.cursor()
            for s in stations:
                try:
                    rain_element = s.get('RainfallElement', {})
                    raw_rain_1h = rain_element.get('Past1hr', {}).get('Precipitation', 0) if rain_element else 0
                    raw_rain_24h = rain_element.get('Past24hr', {}).get('Precipitation', 0) if rain_element else 0
                    
                    rain_1h = safe_convert(raw_rain_1h, float) or 0.0
                    rain_24h = safe_convert(raw_rain_24h, float) or 0.0
                    
                    geo = s.get('GeoInfo', {})
                    county = geo.get('CountyName', '未知')
                    st_name = s.get('StationName', '未知')
                    
                    lat, lon = 0.0, 0.0
                    for coord in geo.get('Coordinates', []):
                        if coord.get('CoordinateName') == 'WGS84':
                            lat = safe_convert(coord.get('StationLatitude'), float) or 0.0
                            lon = safe_convert(coord.get('StationLongitude'), float) or 0.0
                    
                    sql = """
                        INSERT INTO rainfall_records (county, station_name, rainfall_1h, rainfall_24h, lat, lon, timestamp) 
                        VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """
                    cursor.execute(sql, (county, st_name, rain_1h, rain_24h, lat, lon, current_time))
                except: continue
            conn.commit()
            cursor.close()
            conn.close()
            print("🔵 [氣象署 雨量] 資料更新完成。")
    except Exception as e: print(f"❌ 雨量失敗: {e}")

    conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("SELECT county, station_name, rainfall_1h, rainfall_24h, lat, lon FROM rainfall_records WHERE timestamp = (SELECT MAX(timestamp) FROM rainfall_records)")
    data = cursor.fetchall()
    conn.close()
    return data


"""氣象署 地震報告"""
@app.get("/api/earthquake")
def get_earthquake():
    
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    try:
        url = f"https://opendata.cwa.gov.tw/api/v1/rest/datastore/E-A0015-001?Authorization={CWA_API_KEY}&format=JSON"
        res = requests.get(url, headers=HEADERS, verify=False, timeout=10).json()
        eq_list = res.get('records', {}).get('Earthquake', [])
        
        conn = pymysql.connect(**DB_SETTINGS)
        cursor = conn.cursor()
        for eq in eq_list:
            try:
                info = eq.get('EarthquakeInfo', {})
                content = eq.get('ReportContent', '有感地震報告')
                mag = safe_convert(info.get('EarthquakeMagnitude', {}).get('MagnitudeValue'), float) or 0.0
                depth = safe_convert(info.get('FocalDepth'), float) or 0.0
                lat = safe_convert(info.get('Epicenter', {}).get('EpicenterLatitude'), float)
                lon = safe_convert(info.get('Epicenter', {}).get('EpicenterLongitude'), float)
                
                sql = "INSERT INTO earthquake_records (report_content, magnitude, depth, lat, lon, timestamp) VALUES (%s, %s, %s, %s, %s, %s)"
                cursor.execute(sql, (content, mag, depth, lat, lon, current_time))
            except: continue
        conn.commit()
        cursor.close()
        conn.close()
        print("⚠️ [氣象署 地震] 資料更新完成。")
    except Exception as e: print(f"❌ 地震失敗: {e}")

    conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("SELECT report_content, magnitude, depth, lat, lon FROM earthquake_records WHERE timestamp = (SELECT MAX(timestamp) FROM earthquake_records)")
    data = cursor.fetchall()
    conn.close()
    return data

"""🌟 【保留 TDX 引擎】 停車場雙流資料融合 (維持原有 1.5 秒安全減速帶)"""
@app.get("/api/parking")
def get_parking(county: str = "臺中市"):
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 💡 啟動快取守門員：如果該縣市資料在 5 分鐘內，直接跳過抓取！
    if is_cache_expired('parking_records', county, expire_minutes=5):
        headers = get_tdx_headers()
        if headers:
            TDX_CITIES = {"臺中市": "Taichung", "臺北市": "Taipei", "高雄市": "Kaohsiung"}
            en_city = TDX_CITIES.get(county)
            
            if en_city:
                try:
                    conn = pymysql.connect(**DB_SETTINGS)
                    cursor = conn.cursor()
                    print(f"🅿️ [未命中快取] 向 TDX 請求 {county} 最新停車場資料...")
                    
                    info_url = f"https://tdx.transportdata.tw/api/basic/v1/Parking/OffStreet/CarPark/City/{en_city}?$format=JSON"
                    info_res = requests.get(info_url, headers=headers, timeout=10).json()
                    park_dict = {}
                    if isinstance(info_res, dict) and 'CarParks' in info_res:
                        for p in info_res.get('CarParks', []):
                            pid = p.get('CarParkID')
                            name = p.get('CarParkName', {}).get('Zh_tw', '未知停車場')
                            lat = p.get('CarParkPosition', {}).get('PositionLat')
                            lon = p.get('CarParkPosition', {}).get('PositionLon')
                            if pid and lat and lon: park_dict[pid] = {"name": name, "lat": lat, "lon": lon}

                    avail_url = f"https://tdx.transportdata.tw/api/basic/v1/Parking/OffStreet/ParkingAvailability/City/{en_city}?$format=JSON"
                    avail_res = requests.get(avail_url, headers=headers, timeout=10).json()
                    if isinstance(avail_res, dict) and 'ParkingAvailabilities' in avail_res:
                        for a in avail_res.get('ParkingAvailabilities', []):
                            pid = a.get('CarParkID')
                            if pid in park_dict:
                                total = safe_convert(a.get('TotalSpaces'), int) or 0
                                avail = safe_convert(a.get('AvailableSpaces'), int) or 0
                                p_info = park_dict[pid]
                                sql = "INSERT INTO parking_records (county, parking_name, total_spaces, available_spaces, lat, lon, timestamp) VALUES (%s, %s, %s, %s, %s, %s, %s)"
                                cursor.execute(sql, (county, p_info['name'], total, avail, p_info['lat'], p_info['lon'], current_time))
                    conn.commit()
                    cursor.close()
                    conn.close()
                except Exception as e: print(f"❌ {county} 停車場動態同步失敗: {e}")
    else:
        print(f"⚡ [命中快取] {county} 停車場資料超新鮮，直接從資料庫載入！")

    # 無論是剛剛抓的，還是快取攔截的，統一從資料庫撈出最新一筆回傳
    conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("SELECT county, parking_name, total_spaces, available_spaces, lat, lon FROM parking_records WHERE county = %s AND timestamp = (SELECT MAX(timestamp) FROM parking_records WHERE county = %s)", (county, county))
    data = cursor.fetchall()
    conn.close()
    return data

"""🌟 地方原生 YouBike 動態單一縣市引擎 (支援北中南異質欄位)"""
@app.get("/api/youbike")
def get_youbike(county: str = "臺北市"):
    """
    🌟 YouBike 完整優化版引擎
    功能：自動檢查快取，若無效則直連政府原生 OpenData API，並進行自動欄位清洗
    """
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 💡 全台 API 軍火庫 (包含你提供的最新穩定連結)
    LOCAL_API_TARGETS = {
        "臺北市": "https://tcgbusfs.blob.core.windows.net/dotapp/youbike/v2/youbike_immediate.json",
        "新北市": "https://data.ntpc.gov.tw/api/datasets/010e5b15-3823-4b20-b401-b1cf000550c5/json?page=0&size=20000",
        "桃園市": "https://data.tycg.gov.tw/api/v1/rest/datastore/a1b4714b-3b75-47d9-b677-7d12a32a6256?format=json&limit=2000",
        "臺中市": "https://newdatacenter.taichung.gov.tw/api/v1/no-auth/resource.download?rid=a378bb83-a019-4b7b-bc05-d4d55f97ff9e",
        "高雄市": "https://openapi.kcg.gov.tw/Api/Service/Get/b4dd9c40-9027-4125-8666-06bef1756092",
        "新竹市": "https://odws.hccg.gov.tw/001/Upload/25/opendataback/9059/59/5776ed30-fa3c-48f4-9876-d8fb28df0501.json"
    }
    
    api_url = LOCAL_API_TARGETS.get(county)
    
    # 💡 檢查快取 (5分鐘有效)
    if not api_url: return []
    if is_cache_expired('youbike_records', county, expire_minutes=5):
        try:
            conn = pymysql.connect(**DB_SETTINGS)
            cursor = conn.cursor()
            print(f"🚲 [未命中快取] 正在同步 {county} 原生 API...")
            
            res = requests.get(api_url, headers=HEADERS, verify=False, timeout=15).json()
            
            # 萬能開殼機制 (相容各種 JSON 巢狀結構)
            stations = []
            if isinstance(res, list): stations = res
            elif isinstance(res, dict):
                if 'data' in res: stations = res['data']
                elif 'records' in res: stations = res['records']
                elif 'result' in res and 'records' in res['result']: stations = res['result']['records']
                else: stations = [res]
            
            success_count = 0
            for s in stations:
                try:
                    # 💡 自動化欄位清洗 (涵蓋 sbi/available_rent_bikes/servAvail 等所有可能)
                    raw_name = s.get('sna') or s.get('station_name') or s.get('arName') or ''
                    st_name = str(raw_name).replace('YouBike2.0_', '').replace('YouBike1.0_', '')
                    
                    # 抓取車輛數與空位數
                    bikes = safe_convert(s.get('sbi') or s.get('available_rent_bikes') or s.get('servAvail'), int) or 0
                    spaces = safe_convert(s.get('bemp') or s.get('available_return_bikes') or s.get('empty_spaces'), int) or 0
                    
                    # 經緯度
                    lat = safe_convert(s.get('lat') or s.get('latitude'), float)
                    lon = safe_convert(s.get('lng') or s.get('lon') or s.get('longitude'), float)
                    
                    if st_name and lat and lon:
                        sql = """INSERT INTO youbike_records (county, station_name, available_bikes, empty_spaces, lat, lon, timestamp) 
                                 VALUES (%s, %s, %s, %s, %s, %s, %s)"""
                        cursor.execute(sql, (county, st_name, bikes, spaces, lat, lon, current_time))
                        success_count += 1
                except: continue
            
            conn.commit()
            cursor.close()
            conn.close()
            print(f"   ✅ {county} 同步完成，共寫入 {success_count} 筆資料。")
        except Exception as e: 
            print(f"❌ {county} 同步失敗: {e}")
    else:
        print(f"⚡ [命中快取] {county} 資料新鮮，已跳過網路請求。")

    # 回傳資料給前端
    conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("""SELECT county, station_name, available_bikes, empty_spaces, lat, lon 
                      FROM youbike_records 
                      WHERE county = %s AND timestamp = (SELECT MAX(timestamp) FROM youbike_records WHERE county = %s)""", (county, county))
    data = cursor.fetchall()
    conn.close()
    return data

"""🌟 TDX 國道即時影像引擎"""
@app.get("/api/highway-cctv")
def get_highway_cctv():

    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    # 攝影機座標不常變動，設定 15 分鐘快取
    if is_cache_expired('highway_cctv_records', None, expire_minutes=15):
        headers = get_tdx_headers()
        if headers:
            try:
                conn = pymysql.connect(**DB_SETTINGS)
                cursor = conn.cursor()
                print("📷 [未命中快取] 正在向 TDX 同步全台國道監視器座標...")
                
                url = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/CCTV/Freeway?$format=JSON"
                res = requests.get(url, headers=headers, timeout=15).json()
                
                success_count = 0
                
                # 💡 關鍵修正：依照官方格式，從 'CCTVs' 這個鍵值中把陣列取出來
                cctv_list = []
                if isinstance(res, dict) and 'CCTVs' in res:
                    cctv_list = res['CCTVs']
                elif isinstance(res, list): # 防呆：萬一 TDX 哪天改回直接給陣列
                    cctv_list = res

                for c in cctv_list:
                    try:
                        cctv_id = c.get('CCTVID')
                        road_name = c.get('RoadName', '國道')
                        lat = safe_convert(c.get('PositionLat'), float)
                        lon = safe_convert(c.get('PositionLon'), float)
                        
                        # 💡 雙重保險：優先拿動態影像 (VideoStreamURL)，沒有的話就拿靜態截圖 (VideoImageURL)
                        video_url = c.get('VideoImageURL') or c.get('VideoStreamURL')
                        
                        if cctv_id and lat and lon and video_url:
                            sql = """INSERT INTO highway_cctv_records (cctv_id, road_name, lat, lon, video_url, timestamp) 
                                     VALUES (%s, %s, %s, %s, %s, %s)"""
                            cursor.execute(sql, (cctv_id, road_name, lat, lon, video_url, current_time))
                            success_count += 1
                    except: continue
                
                conn.commit()
                cursor.close()
                conn.close()
                print(f"   ✅ 國道 CCTV 同步完成，共載入 {success_count} 支攝影機。")
            except Exception as e:
                print(f"❌ 國道 CCTV 同步失敗: {e}")
    else:
        print("⚡ [命中快取] 國道 CCTV 座標資料新鮮，直接由資料庫載入！")

    # 回傳給前端
    conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    cursor = conn.cursor()
    cursor.execute("SELECT cctv_id, road_name, lat, lon, video_url FROM highway_cctv_records WHERE timestamp = (SELECT MAX(timestamp) FROM highway_cctv_records)")
    data = cursor.fetchall()
    conn.close()
    return data

@app.get("/api/highway-road-events")
def get_highway_road_events():
    """🚧 TDX 國道道路事件引擎 (資料庫存取版)"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 1. 檢查快取 (設定 5 分鐘更新一次)
    if is_cache_expired('highway_road_events', None, expire_minutes=5):
        headers = get_tdx_headers()
        if headers:
            try:
                print("🚧 [未命中快取] 正在向 TDX 請求最新『國道特殊事件』並寫入資料庫...")
                url = "https://tdx.transportdata.tw/api/basic/v1/Traffic/RoadEvent/LiveEvent/Freeway?$format=JSON"
                res = requests.get(url, headers=headers, timeout=15).json()
                events = res.get('LiveEvents', [])

                conn = pymysql.connect(**DB_SETTINGS)
                cursor = conn.cursor()
                success_count = 0
                
                for event in events:
                    # 解析座標
                    positions = event.get('Positions', '')
                    lat, lon = None, None
                    if positions.startswith('POINT('):
                        try:
                            coords = positions[6:-1].split()
                            lon, lat = float(coords[0]), float(coords[1])
                        except Exception:
                            pass
                    
                    if lat and lon:
                        loc = event.get('Location', {}).get('FreeExpressHighway', {})
                        road_name = f"{loc.get('Road', '未知國道')} {loc.get('Direction', '')}".strip()
                        event_type = event.get('EventTitle', '一般事件')
                        event_id = event.get('EventID') # TDX 原始唯一碼
                        desc = event.get('Description', '無詳細描述')
                        
                        # 處理影響範圍
                        impact_dict = event.get('Impact', {})
                        impact = impact_dict.get('Description', '目前無嚴重影響')
                        blocked = impact_dict.get('BlockedLanes', '-1')
                        if blocked != '-1' and blocked:
                            impact += f" (封閉: {blocked})"
                        
                        # 配色與圖示
                        color = "#f39c12" if "施工" in event_type else "#e74c3c" if "事故" in event_type or "車禍" in event_type else "#e67e22" if "壅塞" in event_type else "#9b59b6"
                        icon = "🚧" if "施工" in event_type else "💥" if "事故" in event_type or "車禍" in event_type else "🚗" if "壅塞" in event_type else "⚠️"

                        # 使用 INSERT IGNORE 避免相同的 event_id 重複寫入報錯
                        sql = """
                            INSERT IGNORE INTO highway_road_events 
                            (event_id, road_name, event_type, description, impact, color, icon, lat, lon, timestamp)
                            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """
                        cursor.execute(sql, (event_id, road_name, event_type, desc, impact, color, icon, lat, lon, current_time))
                        success_count += cursor.rowcount
                
                conn.commit()
                cursor.close()
                conn.close()
                print(f"   ✅ 國道特殊事件同步完成，成功新增 {success_count} 筆新事件！")
            except Exception as e:
                print(f"❌ 國道特殊事件同步失敗: {e}")
    else:
        print("⚡ [命中快取] 國道特殊事件資料新鮮，直接由資料庫載入！")

    # 2. 從資料庫撈取最新資料回傳給前端
    try:
        conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        
        # 撈取最近 30 分鐘內的最新事件，避免撈到昨天已經解決的舊資料
        sql = """
            SELECT road_name, description, event_type, impact, color, icon, lat, lon 
            FROM highway_road_events 
            WHERE timestamp >= DATE_SUB(NOW(), INTERVAL 30 MINUTE)
            ORDER BY timestamp DESC
        """
        cursor.execute(sql)
        data = cursor.fetchall()
        conn.close()
        return data
        
    except Exception as e:
        print(f"❌ 讀取資料庫失敗: {e}")
        return []



@app.get("/api/highway-speed")
def get_highway_speed():
    """🟢 TDX 國道即時車速引擎 (全車道精準掃描版)"""
    current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    if is_cache_expired('highway_speed_records', None, expire_minutes=3):
        headers = get_tdx_headers()
        if headers:
            try:
                conn = pymysql.connect(**DB_SETTINGS)
                cursor = conn.cursor()
                print("🟢 正在向 TDX 同步並聯集國道車速資料...")
                
                # 1. 抓取基本資料 (靜態座標)
                vd_basic_url = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/VD/Freeway?$format=JSON"
                basic_res = requests.get(vd_basic_url, headers=headers, timeout=15).json()
                vds_basic = basic_res.get('VDs', [])
                    
                vd_map = {}
                for v in vds_basic:
                    vd_id = v.get('VDID')
                    if vd_id:
                        section = v.get('RoadSection', {})
                        sec_name = f"{section.get('Start', '')}-{section.get('End', '')}" if section else f"偵測站 {vd_id}"
                        vd_map[vd_id] = {
                            'road': v.get('RoadName', '國道'),
                            'section': sec_name,
                            'lat': safe_convert(v.get('PositionLat'), float),
                            'lon': safe_convert(v.get('PositionLon'), float)
                        }

                # 2. 抓取即時車流資料 (動態時速)
                vd_live_url = "https://tdx.transportdata.tw/api/basic/v2/Road/Traffic/Live/VD/Freeway?$format=JSON"
                live_res = requests.get(vd_live_url, headers=headers, timeout=15).json()
                vds_live = live_res.get('VDLives') or live_res.get('VDLive') or live_res.get('VDs') or []
                if not vds_live and isinstance(live_res, list): vds_live = live_res
                    
                success_count = 0
                for live in vds_live:
                    vd_id = live.get('VDID')
                    flows = live.get('LinkFlows') or live.get('LinkFlow') or []
                    
                    if vd_id in vd_map and flows:
                        
                        # 🚨 邏輯重構：掃描所有車道，收集大於 0 的真實車速
                        valid_speeds = []
                        for flow in flows:
                            for lane in flow.get('Lanes', []):
                                lane_speed = safe_convert(lane.get('Speed'), float)
                                if lane_speed > 0:
                                    valid_speeds.append(lane_speed)
                        
                        # 計算平均真實時速
                        speed = 0
                        if valid_speeds:
                            speed = int(sum(valid_speeds) / len(valid_speeds))
                        
                        lat = vd_map[vd_id]['lat']
                        lon = vd_map[vd_id]['lon']
                        road_name = vd_map[vd_id]['road']
                        section_name = vd_map[vd_id]['section']
                        
                        # 只要平均時速 > 0 且有座標，就寫入真實資料
                        if speed > 0 and lat and lon: 
                            sql = """INSERT INTO highway_speed_records (road_name, section_name, speed, lat, lon, timestamp) 
                                     VALUES (%s, %s, %s, %s, %s, %s)"""
                            cursor.execute(sql, (road_name, section_name, speed, lat, lon, current_time))
                            success_count += 1
                
                # 防護網保留，但這次它不會被誤觸發了
                # if success_count == 0:
                #     print("💡 目前無有效車速數據。自動生成測試點以供前端驗證。")
                #     test_sql = """INSERT INTO highway_speed_records (road_name, section_name, speed, lat, lon, timestamp) 
                #                   VALUES (%s, %s, %s, %s, %s, %s)"""
                #     cursor.execute(test_sql, ('國道1號', '台北段 (測試)', 95, 25.078, 121.523, current_time))
                #     success_count += 1
                    
                conn.commit()
                print(f"   ✅ 國道車速同步完成，共寫入 {success_count} 個測速點！")
                cursor.close()
                conn.close()
            except Exception as e:
                print(f"❌ 國道車速同步失敗: {e}")
                
    try:
        conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
        cursor = conn.cursor()
        cursor.execute("SELECT road_name, section_name, speed, lat, lon FROM highway_speed_records WHERE timestamp = (SELECT MAX(timestamp) FROM highway_speed_records)")
        data = cursor.fetchall()
        conn.close()
        return data
    except Exception as e:
        return []           
    # conn = pymysql.connect(**DB_SETTINGS, cursorclass=pymysql.cursors.DictCursor)
    # cursor = conn.cursor()
    # cursor.execute("SELECT road_name, section_name, speed, lat, lon FROM highway_speed_records WHERE timestamp = (SELECT MAX(timestamp) FROM highway_speed_records)")
    # data = cursor.fetchall()
    # conn.close()
    # return data





@app.get("/", response_class=HTMLResponse)
def read_index():
    with open(os.path.join("templates", "index.html"), "r", encoding="utf-8") as f:
        return f.read()