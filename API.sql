-- ===================================================
-- 1. 建立專案專用資料庫與編碼設定
-- ===================================================
CREATE DATABASE IF NOT EXISTS env_live_data 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

USE env_live_data;

-- ===================================================
-- 2. 清理舊有資料表 (若需保留舊資料請將這區塊註解掉)
-- ===================================================
DROP TABLE IF EXISTS aqi_records;
DROP TABLE IF EXISTS rainfall_records;
DROP TABLE IF EXISTS youbike_records;
DROP TABLE IF EXISTS parking_records;
DROP TABLE IF EXISTS earthquake_records;
DROP TABLE IF EXISTS highway_cctv_records;
DROP TABLE IF EXISTS highway_speed_records;
DROP TABLE IF EXISTS highway_incident_records;
DROP TABLE IF EXISTS highway_road_events;

-- ===================================================
-- 3. 建立各維度物聯網監測資料表
-- ===================================================

-- 🌬️ 環境部：空氣品質監測
CREATE TABLE IF NOT EXISTS aqi_records (
    id INT AUTO_INCREMENT,
    county VARCHAR(50) NOT NULL,
    sitename VARCHAR(50) NOT NULL,
    aqi INT,
    status VARCHAR(20),
    pm25 INT,
    pm10 INT,
    o3 DECIMAL(5,1),
    co DECIMAL(5,2),
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 🌧️ 氣象署：即時累積雨量
CREATE TABLE IF NOT EXISTS rainfall_records (
    id INT AUTO_INCREMENT,
    county VARCHAR(50) NOT NULL,
    station_name VARCHAR(50) NOT NULL,
    rainfall_1h DECIMAL(5,2),
    rainfall_24h DECIMAL(5,2),
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 🚲 地方政府 OpenData：YouBike 2.0 即時車況
CREATE TABLE IF NOT EXISTS youbike_records (
    id INT AUTO_INCREMENT,
    county VARCHAR(50) NOT NULL,
    station_name VARCHAR(100) NOT NULL,
    available_bikes INT,
    empty_spaces INT,
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 🅿️ 交通部 TDX：路外停車場即時車位
CREATE TABLE IF NOT EXISTS parking_records (
    id INT AUTO_INCREMENT,
    county VARCHAR(50) NOT NULL,
    parking_name VARCHAR(100) NOT NULL,
    total_spaces INT,
    available_spaces INT,
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- ⚠️ 氣象署：顯著有感地震警報
CREATE TABLE IF NOT EXISTS earthquake_records (
    id INT AUTO_INCREMENT,
    report_content VARCHAR(255),
    magnitude DECIMAL(4,2),
    depth DECIMAL(6,2),
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 📷 交通部 TDX：高公局國道即時影像監視器 (CCTV)
CREATE TABLE IF NOT EXISTS highway_cctv_records (
    id INT AUTO_INCREMENT,
    cctv_id VARCHAR(50) NOT NULL,
    road_name VARCHAR(50),
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    video_url VARCHAR(255),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 🟢 交通部 TDX：高公局國道即時車速
CREATE TABLE IF NOT EXISTS highway_speed_records (
    id INT AUTO_INCREMENT,
    road_name VARCHAR(50) NOT NULL,
    section_name VARCHAR(150),
    speed INT,
    lat DECIMAL(10,6),
    lon DECIMAL(10,6),
    timestamp DATETIME NOT NULL,
    PRIMARY KEY (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- 🚨 交通部 TDX：高公局國道即時路況事件 (壅塞狀態)
CREATE TABLE IF NOT EXISTS `highway_incident_records` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '系統唯一流水號',
  `incident_id` VARCHAR(50) NOT NULL COMMENT '路段或事件的唯一識別碼 (例: SEC-0001)',
  `road_name` VARCHAR(50) NOT NULL COMMENT '國道名稱',
  `description` TEXT NOT NULL COMMENT '包含 HTML 格式的彈出視窗描述',
  `lat` DOUBLE NOT NULL COMMENT '緯度',
  `lon` DOUBLE NOT NULL COMMENT '經度',
  `timestamp` DATETIME NOT NULL COMMENT '資料同步時間',
  INDEX `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='國道壅塞路況紀錄表';

-- 🚧 交通部 TDX：國道特殊事件 (車禍、施工、散落物等)
CREATE TABLE IF NOT EXISTS `highway_road_events` (
  `id` INT AUTO_INCREMENT PRIMARY KEY COMMENT '系統唯一流水號',
  `event_id` VARCHAR(100) NOT NULL UNIQUE COMMENT 'TDX 原始 EventID (避免重複寫入)',
  `road_name` VARCHAR(100) NOT NULL COMMENT '國道名稱與方向',
  `event_type` VARCHAR(50) NOT NULL COMMENT '事件類型 (例: 施工事件、壅塞事件)',
  `description` TEXT NOT NULL COMMENT '事件詳細描述',
  `impact` VARCHAR(255) COMMENT '影響範圍與封閉車道',
  `color` VARCHAR(20) DEFAULT '#9b59b6' COMMENT '前端渲染顏色',
  `icon` VARCHAR(10) DEFAULT '⚠️' COMMENT '前端渲染圖示',
  `lat` DOUBLE NOT NULL COMMENT '緯度',
  `lon` DOUBLE NOT NULL COMMENT '經度',
  `timestamp` DATETIME NOT NULL COMMENT '資料同步時間',
  INDEX `idx_timestamp` (`timestamp`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='國道特殊事件紀錄表';


-- ===================================================
-- 4. 大數據複合索引優化 (防止 API 查詢卡頓)
-- ===================================================
-- 針對 WHERE 過濾條件與 MAX(timestamp) 排序進行底層加速
ALTER TABLE aqi_records ADD INDEX idx_county_timestamp (county, timestamp);
ALTER TABLE rainfall_records ADD INDEX idx_county_timestamp (county, timestamp);
ALTER TABLE youbike_records ADD INDEX idx_county_timestamp (county, timestamp);
ALTER TABLE parking_records ADD INDEX idx_county_timestamp (county, timestamp);
ALTER TABLE earthquake_records ADD INDEX idx_timestamp (timestamp);
ALTER TABLE highway_cctv_records ADD INDEX idx_timestamp (timestamp);
ALTER TABLE highway_speed_records ADD INDEX idx_road_timestamp (road_name, timestamp);