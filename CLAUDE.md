# CLAUDE.md

本檔案給 Claude Code 在此專案（投資組合儀表板）工作時的固定規則。

## 瀏覽器驗證規則（2026-08-12 起生效）

- 本機用無頭瀏覽器驗證網頁改動時，**一律使用 Microsoft Edge**（`msedge.exe`），**不要用 Google Chrome**。
- 原因：Chrome 常駐使用者日常操作，無頭模式啟動/關閉可能連帶影響或意外關閉使用者正在使用的 Chrome 視窗；Edge 通常閒置，用它驗證不會有這個風險。
- Edge 執行檔路徑（此機器）：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`，command line 參數與 Chrome 相容（`--headless`、`--disable-gpu`、`--screenshot=`、`--window-size=` 等皆可直接沿用）。
- 驗證完成後記得清理暫存的截圖與測試 HTML 檔案，並確認沒有殘留的 `msedge.exe` 背景行程。

## Cloudflare Worker 存取限制（2026-08-11 起生效）

- `https://portfolio-proxy.vicabon.workers.dev`（靜態頁即時報價代理，見 `cloudflare-worker.js` / README.md）**不得再被存取或驗證**——公司 cybersecurity team 會對此網域發出警告。
- 這條限制只影響「操作/測試」層面：**不要**用瀏覽器、curl、腳本等任何方式呼叫這個網址，包括開發時的手動驗證。
- 程式碼與設定**保留不動**：`cloudflare-worker.js`、`portfolio.html` 裡的 `WORKER_BASE_URL` 都維持現狀，不需刪除或還原成空字串。
- 實際影響：靜態 GitHub Pages 版目前仍會在瀏覽器端嘗試呼叫這個 Worker 網址以取得即時報價（產品行為本身未被要求停止），只是開發/維運端之後不會再主動存取或測試它。若需要驗證牽涉到即時報價的功能，改用本機 Flask 模式（`python app.py`）測試，該模式不經過這個 Worker。

更完整的部署與架構說明見 `README.md`。
