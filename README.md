# 投資組合儀表板 Portfolio Dashboard

台股 / 台灣 ETF（證交所即時報價）+ 美股 / 美股 ETF（Yahoo Finance，依即時美元匯率換算台幣）的投資組合儀表板。

顯示：ticker、名稱、股數、台幣總額、占比、**Beta**、投組加權 Beta，以及歷史回朔三張圖（總市值走勢、各持股比例走勢、報酬日曆）。另有「借貸負債」分頁追蹤房貸/信貸還款進度。

## 兩種執行模式（同一份 `portfolio.html`）

| 模式 | 說明 | 報價 | 可否編輯持股 |
|------|------|------|--------------|
| **本機 Flask** | `python app.py` | 開頁即抓、每 30 秒即時更新 | ✅ 網頁上可新增/刪除 |
| **靜態 GitHub Pages** | `build_static.py` 烘焙快照 | 預設為建置當下快照；設定 Cloudflare Worker 代理後可開頁即時更新 | ❌ 需改 `portfolio.json` 後重建 |

> 為什麼 GitHub Pages 要用「烘焙」？因為 Pages 只服務靜態檔案、沒有後端，而瀏覽器直接抓證交所 / Yahoo 會被 CORS 擋掉。所以先在 CI 用 Python 抓好資料，注入 `index.html`。CNN Fear & Greed 例外——它允許跨網域，靜態頁一律會即時刷新。

> ⚠️ **重要限制（2026-08-11 起生效）**：`https://portfolio-proxy.vicabon.workers.dev`（見下方 Cloudflare Worker 章節）**不得再被存取或驗證**——公司 cybersecurity team 會對此網域發出警告。
> - 這條限制只影響「操作/測試」層面：**不要**用瀏覽器、curl、腳本等任何方式呼叫這個網址，包括開發時的手動驗證。
> - 程式碼與設定**保留不動**：`cloudflare-worker.js`、`portfolio.html` 裡的 `WORKER_BASE_URL` 都維持現狀，不需刪除或還原成空字串。
> - 實際影響：靜態 GitHub Pages 版目前仍會在瀏覽器端嘗試呼叫這個 Worker 網址以取得即時報價——這件事本身未被要求停止，只是**我們（開發/維運端）之後不會再主動存取或測試它**。若之後 cybersecurity team 要求連前端也不能呼叫，需另外調整 `WORKER_BASE_URL` 或改回快照模式，屆時再處理。

> ⚠️ **瀏覽器驗證規則（2026-08-12 起生效）**：本機用無頭瀏覽器驗證網頁改動時，**一律使用 Microsoft Edge**（`msedge.exe`），**不要用 Google Chrome**。
> - 原因：Chrome 常駐使用者日常操作，無頭模式啟動/關閉可能連帶影響或意外關閉使用者正在使用的 Chrome 視窗；Edge 通常閒置，用它驗證不會有這個風險。
> - Edge 執行檔路徑（此機器）：`C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe`，command line 參數與 Chrome 相容（`--headless`、`--disable-gpu`、`--screenshot=`、`--window-size=` 等皆可直接沿用）。
> - 驗證完成後記得清理暫存的截圖與測試 HTML 檔案，並確認沒有殘留的 `msedge.exe` 背景行程。

---

## 一、本機即時模式

```bash
pip install -r requirements.txt
python app.py
```
開 http://127.0.0.1:5000 —— 可即時報價、在網頁上新增/刪除持股（存進 `portfolio.json`）。

---

## 二、部署到 GitHub Pages（github.io）

### 需要上傳的檔案

```
portfolio_builder/
├── portfolio.html            ← 前端頁面（模板，同時支援兩種模式）
├── app.py                    ← Flask 後端 + build_portfolio（靜態建置也會 import）
├── portfolio_data.py         ← 報價 / 匯率 / 歷史 資料層
├── build_static.py           ← 靜態建置腳本（產生 index.html）
├── portfolio.json            ← 你的持股（含 shares / beta / 現金 / market）
├── debt.json                  ← 借貸負債資料（銀行/本金/還款日/每月還款/到期日）
├── requirements.txt          ← 相依套件
├── cloudflare-worker.js       ← （選用）跨網域代理，啟用靜態版即時報價
├── .nojekyll                 ← 讓 GitHub Pages 不要跑 Jekyll
├── .gitignore
└── .github/workflows/deploy.yml   ← GitHub Actions 自動建置 + 部署
```

> `index.html` 由 `build_static.py` 產生。可以先本機跑一次 commit 進去，或完全交給 GitHub Actions 產生（推薦後者）。

### 部署步驟

1. **建立 GitHub repo** 並推上以上檔案：
   ```bash
   git add -A
   git commit -m "Portfolio dashboard with static build"
   git branch -M main
   git remote add origin https://github.com/<你的帳號>/<repo名稱>.git
   git push -u origin main
   ```

2. **開啟 Pages**：repo → **Settings → Pages → Build and deployment → Source** 選 **GitHub Actions**。

3. **等 Actions 跑完**：`.github/workflows/deploy.yml` 會自動
   - 安裝相依套件 → `python build_static.py` 產生 `index.html` → 部署到 Pages。
   - 網址：`https://<你的帳號>.github.io/<repo名稱>/`

4. **自動更新**：workflow 設定為
   - **每個工作日台灣時間 16:00（收盤後）** 自動重建（cron `0 8 * * 1-5`，UTC）。
   - push 到 `main` 時重建。
   - 也可在 Actions 頁面手動 **Run workflow**。

### 本機先預覽靜態版

```bash
python build_static.py            # 產生 index.html
python -m http.server 8000        # 或直接用瀏覽器開 index.html
```
開 http://localhost:8000 檢查靜態快照。

---

## 修改持股與 Beta

編輯 `portfolio.json`：

```json
{"ticker": "2330.TW", "name": "台積電", "shares": 3000, "beta": 2}
```

- **台股**：`.TW`（上市）或 `.TWO`（上櫃）。**美股**：直接代號。
- **現金**：`{"ticker": "TWD-CASH", "name": "台幣現金", "shares": 23500000, "type": "cash", "beta": 0}`
- **同一 ticker 可出現多筆**（例如美股 QQQM + 台股複委託買的 QQQM）：加上 `"market": "TW"` 可強制歸類為台股資產（分類用途），報價來源仍依 ticker 本身命名規則（`.TW`/`.TWO` 才走證交所，其餘一律走 Yahoo 美股報價）。
- `beta` 為手動指定值；投組加權 Beta = Σ(各持股占比 × 該檔 Beta)。

改完 push（或重跑 workflow）即會反映在線上頁面。

---

## 修改借貸負債

編輯 `debt.json`：

```json
{"bank": "中國信託", "principal": 1078453, "dueDay": 13, "monthlyPayment": 26686, "maturityDate": "2030-01-13"}
```

- `principal`：目前借貸剩餘金額（本金餘額，非最初貸款金額）。
- `dueDay`：每月幾號扣款還款。
- `monthlyPayment`：每期固定還款金額（本金+利息）。
- `maturityDate`：貸款到期日（`YYYY-MM-DD`）。
- **剩餘還款期數**由前端依「今天日期」即時計算（今天若正好是還款日，當天算未扣款、計入 1 期），不需要每次手動更新，開頁自動反映最新剩餘期數。
- **實際還款金額** = 每月還款金額 × 剩餘還款期數，因為每期還款含本金與利息，這個數字會大於 `principal`（借貸剩餘金額）。

`debt.json` 是純靜態檔案，本機 Flask 與 GitHub Pages 都直接讀取同一份，改完 push 即生效，不需要跑 `build_static.py`。

---

## 讓 GitHub Pages 靜態版也能「開頁即時更新報價」

> ⚠️ **目前 `https://portfolio-proxy.vicabon.workers.dev` 不得被存取或驗證**（會觸發公司 cybersecurity team 警告）。以下步驟與說明保留供參考、程式碼保留不動，但**不要**重新測試、curl、或用瀏覽器打開這個網址來驗證。

台股（證交所）與美股（Yahoo Finance）不允許瀏覽器直接跨網域 fetch，靜態頁預設只能顯示建置當下的快照。要在**不架設自己伺服器**的前提下讓它開頁即時刷新，需要一個小型跨網域代理——用 **Cloudflare Worker**（免費額度足夠個人使用）：

1. 到 https://dash.cloudflare.com → **Workers & Pages → Create Worker**
2. 貼上 `cloudflare-worker.js` 的內容，**Deploy**
3. 部署後會拿到網址，例如 `https://portfolio-proxy.<你的帳號>.workers.dev`
4. 打開 `portfolio.html`，找到這一行並填入你的 Worker 網址：
   ```js
   const WORKER_BASE_URL = ""; // 填入 "https://portfolio-proxy.<你的帳號>.workers.dev"
   ```
5. 重新 `python build_static.py` 並 push（或直接改 `index.html` 裡同一行）

設定好之後，靜態頁一開啟就會：
- 透過 Worker 即時抓每檔台股/美股報價與 USD/TWD 匯率，覆蓋快照數字並重算總資產/占比/Beta。
- CNN Fear & Greed 本身允許跨網域，**不需 Worker** 即可即時更新。
- 若抓取失敗（額度用盡、網路問題等）會自動退回顯示快照值，不會讓頁面壞掉。

**未設定 `WORKER_BASE_URL`** 時（預設空字串），靜態頁行為不變，仍是每日快照。

> 這個 Worker 是**唯讀轉發代理**，只允許轉發到 TWSE / Yahoo 白名單網域，不是任意網址的開放代理，不會被濫用成別的用途。
