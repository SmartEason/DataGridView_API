這是一個結合 MySQL 資料庫與多個政府開放資料 API（環境部、氣象署與交通部 TDX）的網頁應用程式，用於顯示並管理即時環境與交通資料的網格視圖 (Data Grid)。

功能特色
動態資料網格: 互動式資料視覺化與高效的管理介面。

API 整合: 與政府官方開放資料平台進行即時資料同步。

資料庫驅動: 由 MySQL 建構與驅動的穩健後端架構。

響應式介面: 使用 templates 與靜態資源 (static assets) 建構的現代化網頁版面。

環境要求
在執行此專案之前，請確保您的電腦已安裝以下軟體：

Python 3.8 或以上版本

MySQL Server (本機或遠端資料庫)

安裝與設定
請依照以下步驟建立您的開發環境：

# 下載最新版本

前往此專案首頁右側的 Releases 區塊。

下載最新版本的壓縮檔 (例如 Source code (zip))。

將下載的 .zip 檔案解壓縮。

打開終端機 (或命令提示字元) 並進入解壓縮後的資料夾：

cd path/to/your/extracted/folder

# 建立虛擬環境(名稱可自訂)
python -m venv myenv

# 啟動虛擬環境 (Windows VSC)
myenv\Scripts\activate.ps1

# 啟動虛擬環境 (macOS/Linux)
source venv/bin/activate

# 安裝依賴套件
pip install -r requirements.txt

# 設定資料庫結構
打開您慣用的 MySQL 客戶端（如 MySQL Workbench、phpMyAdmin）。

建立一個新的資料庫 (例如 env_live_data)。

匯入專案提供的 API.sql 檔案，以自動初始化所需的資料表結構：

SQL
SOURCE path/to/API.sql;
# 設定環境變數

複製 .env.example 檔案並將其重新命名為 .env。

打開新建的 .env 檔案，並將預設的提示文字替換為您真實的資料庫密碼與各項 API 金鑰。

執行應用程式
設定完成後，執行以下指令啟動應用程式：
uvicorn main:app --reload
伺服器啟動後，打開網頁瀏覽器並前往本機位址 (通常為 http://127.0.0.1:5000 或終端機顯示的特定位址)。

客製化與修改
前端修改: 您可以修改 templates/ 資料夾內的 HTML 結構，並更新 static/ 資料夾內的自訂樣式或素材。

後端修改: 可直接在 main.py 中調整 API 讀取行為、資料更新頻率或網格的後端處理邏輯。
