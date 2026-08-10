# 投資組合儀表板 Portfolio Dashboard

台股 / 台灣 ETF（證交所即時報價）+ 美股 / 美股 ETF（Yahoo Finance，依即時美元匯率換算台幣）的投資組合儀表板。

顯示：ticker、名稱、股數、台幣總額、占比、**Beta**、投組加權 Beta，以及歷史回朔三張圖（總市值走勢、各持股比例走勢、報酬日曆）。

## 兩種執行模式（同一份 `portfolio.html`）

| 模式 | 說明 | 報價 | 可否編輯持股 |
|------|------|------|--------------|
| **本機 Flask** | `python app.py` | 每 30 秒即時更新 | ✅ 網頁上可新增/刪除 |
| **靜態 GitHub Pages** | `build_static.py` 烘焙快照 | 建置當下的快照 | ❌ 需改 `portfolio.json` 後重建 |

> 為什麼 GitHub Pages 要用「烘焙」？因為 Pages 只服務靜態檔案、沒有後端，而瀏覽器直接抓證交所 / Yahoo 會被 CORS 擋掉。所以先在 CI 用 Python 抓好資料，注入 `index.html`。

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
├── portfolio.json            ← 你的持股（含 shares / beta / 現金）
├── requirements.txt          ← 相依套件
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
- `beta` 為手動指定值；投組加權 Beta = Σ(各持股占比 × 該檔 Beta)。

改完 push（或重跑 workflow）即會反映在線上頁面。
