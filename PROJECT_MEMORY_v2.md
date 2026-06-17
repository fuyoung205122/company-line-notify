# 廠區降雨監控系統 PROJECT_MEMORY_v2

## 1. 專案目的
提供東陽廠區現場人員一個可靠的「降雨監控與加蓋帆布決策」參考系統。透過定時掃描氣象局雨量站與雷達回波，將是否需要加蓋帆布的狀態顯示在 Web Dashboard 上。

## 2. 核心功能與架構
- **純靜態架構**：以 GitHub Actions 作為 Serverless 執行單元，將 Python 爬蟲與決策邏輯的輸出寫成 JSON/CSV，再透過 GitHub Pages 託管純靜態網頁（HTML/CSS/JS）。
- **雙軌並行決策**：同時參考「實體雨量站」與「雷達回波點數及最大 dBZ」，並具備雨量站失效時的優雅降級（單純依靠雷達）機制。
- **免除 LINE 依賴**：改以 Dashboard 面板作為單一真理來源，避免被通訊軟體 API 限制或收費影響。

## 3. 執行流程
1. **Trigger**：`cron-job.org` 根據排程發送 Webhook (呼叫 GitHub API `workflow_dispatch`)，或使用者於網頁手動輸入 GH_PAT 按下「立即執行檢查」。
2. **Workflow**：`.github/workflows/monitor.yml` 被觸發，建立 Python 環境並執行 `rain_monitor.py`。
3. **API Data Fetch**：向中央氣象署 (CWA) 獲取雨量、天氣現象，並下載雷達回波圖片。
4. **Execution**：Python 腳本根據 `config.json` 解析資料，進行加蓋 / 解除的邏輯判定。
5. **Database (File persistence)**：將判定結果與狀態寫入 `state.json`、`dashboard_data.json` 與 `history_log.csv`。
6. **Notification**：無主動推播（發生致命錯誤時寄送 Gmail 給管理員），同仁需主動查看 Dashboard，網頁每 5 分鐘自動刷新。

## 4. 專案模組 (AI 視角)
此專案並未使用 AI Agent / Skill 框架，而是傳統的腳本自動化架構。以下對應概念：
- **Agent/Tool (主程式)**：`rain_monitor.py` (核心監控)、`calendar_updater.py` (每年更新政府行事曆)。
- **Database**：`config.json` (唯讀設定)、`state.json` (後端狀態暫存)、`history_log.csv` (歷史紀錄)、`dashboard_data.json` (前端資料庫)。

## 5. GitHub Actions & 部署方式
- **Actions**：
  - `monitor.yml`：純 `workflow_dispatch` 觸發，負責執行 `rain_monitor.py`。包含 `run_mode: force-weather-check` 判斷。
  - `update_calendar.yml`：負責執行 `calendar_updater.py`。
- **部署**：透過 Git Push 直接更新 `master` 分支，由 GitHub Pages 自動讀取根目錄的 `index.html` 完成部署。

## 6. 已完成事項
- 移除 LINE Notify，全面改用 Web Dashboard (V2)。
- 建立雙軌並行邏輯與雷達退避機制。
- 移出 GitHub 原生 Schedule，改用 `cron-job.org` 達成精準觸發。
- 新增 `calendar_updater.py` 自動抓取明年度行事曆，降低維護成本。
- 修正 `last_rain_time` 與 `last_rain_timestamp` 格式分離、雷達圖單次下載效能優化 (1.6 秒內完工)、`history_log.csv` 自動修剪 5000 筆。

## 7. 待辦事項
- 目前系統已達高度穩定狀態，暫無緊急待辦事項。未來若有需求可優化 UI 視覺或新增其他氣象來源備援。

## 8. 風險與已知問題
- **CWA API 依賴**：高度依賴中央氣象署的 Opendata 穩定性。若 CWA API 更改格式，`rain_monitor.py` 需相應修改。
- **GitHub API 速率限制**：Dashboard 的「立即執行檢查」直接依賴使用者的 GitHub PAT 戳 GitHub API，若操作過於頻繁可能觸發 Abuse Rate Limit。
- **時區問題**：所有時間均以 `Asia/Taipei` (UTC+8) 為準，若 GitHub 伺服器時間異常可能造成零星錯亂（目前已用 `pytz` 強制指定）。
