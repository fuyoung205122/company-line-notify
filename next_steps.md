# 廠區降雨監控系統 - 下一步行動 (Next Steps)

## 📌 Continuation Prompt (給下一個 AI 繼續接手的提示詞)
> 「你好，我是這份專案的負責人。本專案包含家庭訂餐系統 V2 及廠區降雨監控系統 V2。我們在 2026-06-25 完成了全面的 Enterprise Multi-Agent 專案分析與資安稽核，診斷出以下兩個核心 Bug：(1) `rain_monitor.py` 存在執行期 `get_radar_echo` 未定義的 NameError，使雷達回波判斷在發生異常時雖然被捕獲但實際上已失效；(2) `test_rain_monitor.py` 測試套件因保留棄用的 LINE 測試且未對應新版雷達函式而全面崩潰。請閱讀 `AI_CONTEXT.md`, `progress.md`, `changelog.md` 與 `next_steps.md`，並協助我優先修復這兩個 Bug 以使系統重回綠燈狀態。」

## 待觀察與優化事項
1. **修復 `rain_monitor.py` 的雷達 NameError Bug**：
   - 在 `main()` 中調整雷達回波分析流程：先調用 `download_radar_image` 取得一次影像，再代入 `analyze_radar_echo` 對 2km/5km(cover)/5km(uncover) 進行三次像素比對，同時修復呼叫端錯誤並節省下載頻寬。
2. **重整與修復 `test_rain_monitor.py` 測試套件**：
   - 刪除過期 LINE Notify 測試，並對應修改雷達的 Mock 單元測試，確保 `python test_rain_monitor.py` 測試套件 100% 綠燈通過。
3. **Supabase RLS 資料庫加固**：
   - 收緊資料表 RLS 政策，在 API 伺服器端實施身分與權限判定，防範公開 `anon key` 被濫用竄改資料庫。
