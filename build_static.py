"""靜態建置腳本：把即時報價 + 歷史回朔烘焙進 index.html。

GitHub Pages 只服務靜態檔案、前端又受 CORS 限制無法直接抓報價，
因此在 CI（或本機）先跑這支腳本抓好資料，注入 portfolio.html 產生
可直接部署的 index.html。

用法：
    python build_static.py
產出：
    index.html   （自包含，含 window.STATIC_DATA）
"""

import datetime
import json
import os

import app  # 重用 build_portfolio / load_holdings
import portfolio_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATE = os.path.join(BASE_DIR, "portfolio.html")
OUTPUT = os.path.join(BASE_DIR, "index.html")


def main():
    holdings = app.load_holdings()
    if not holdings:
        raise SystemExit("portfolio.json 沒有任何持股，無法建置。")

    print(f"抓取 {len(holdings)} 檔即時報價…")
    portfolio = app.build_portfolio(holdings)

    print("計算歷史回朔…")
    history = portfolio_data.get_history(holdings)

    print("計算樂活五線譜 + Fear & Greed…")
    lohas = app.build_lohas_bundle(holdings)

    generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    static_data = {
        "portfolio": portfolio,
        "history": history,
        "lohas": lohas,
        "generatedAt": generated_at,
    }

    with open(TEMPLATE, "r", encoding="utf-8") as handle:
        html = handle.read()

    # 在 <script> 前注入 window.STATIC_DATA
    payload = (
        "<script>window.STATIC_DATA = "
        + json.dumps(static_data, ensure_ascii=False)
        + ";</script>\n<script>"
    )
    if "<script>\nconst API" in html:
        html = html.replace("<script>\nconst API", payload + "\nconst API", 1)
    else:
        # 後援：注入第一個裸 <script> 標籤（Plotly 之後）
        html = html.replace("<script>\n        const dashboards", payload, 1)

    with open(OUTPUT, "w", encoding="utf-8") as handle:
        handle.write(html)

    print(f"已產生 {OUTPUT}")
    print(f"  總資產：NT${portfolio['totalValue']:,.0f}")
    print(f"  加權 Beta：{portfolio['portfolioBeta']}")
    print(f"  歷史區間：{history['dates'][0]} ~ {history['dates'][-1]}"
          if history["dates"] else "  （無歷史資料）")
    print(f"  資料時間：{generated_at}")


if __name__ == "__main__":
    main()
