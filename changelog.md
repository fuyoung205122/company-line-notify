# 廠區降雨監控系統 - 更新日誌 (Changelog)

## [2026-06-25]
### 診斷與稽核 (Audited)
- **執行期 NameError 診斷**：確認 `rain_monitor.py` 在最新優化中因將 `get_radar_echo` 拆分為 `download_radar_image` 與 `analyze_radar_echo`，但 `main()` 中的呼叫端未同步修改，導致雷達監控功能拋出 NameError。
- **單元測試崩潰排查**：確認 `test_rain_monitor.py` 保留了已過期的 LINE Notify 測試案例，且未對應新版雷達回波函式。
- **資料庫 RLS 稽核**：發現 `supabase-migration-v2.sql` 的 RLS 政策完全開放，匿名 Key 存在資料安全風險。

## [2026-06-17]
### 變更 (Changed)
- **判定邏輯放寬**：修改 `config.json` 與 `rain_monitor.py`，降低雷達判定過度敏感的問題。
  - 加蓋門檻：雷達點數 >= 30 點（原 10），最大 dBZ >= 50（原 35）。
  - 解除加蓋門檻：雷達點數 < 15 點（原 5），最大 dBZ < 40（原 30）。
  - 停雨緩衝時間：從 30 分鐘縮短為 20 分鐘（1200 秒）。

### 新增 (Added)
- **Web Dashboard 複製功能**：於 `index.html` 與 `app.js` 新增了 LINE 推播專用的預覽文字框與「一鍵複製」按鈕。
  - 支援 `is_covered` 狀態自動切換「下雨通知」與「雨停通知」的動態文案。
  - 文案排版皆將「通知本文」置頂、「即時觀測數據」移至最下方，以符合群組閱讀習慣。
