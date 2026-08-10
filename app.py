"""Portfolio 後端：Flask API + 靜態頁面服務。

啟動：
    pip install -r requirements.txt
    python app.py
然後開瀏覽器： http://127.0.0.1:5000

持股存於 portfolio.json（本機檔案），透過 /api/holdings 讀寫。
"""

import json
import os

from flask import Flask, jsonify, request, send_from_directory

import portfolio_data

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PORTFOLIO_FILE = os.path.join(BASE_DIR, "portfolio.json")

app = Flask(__name__, static_folder=None)


def load_holdings():
    if not os.path.exists(PORTFOLIO_FILE):
        return []
    try:
        with open(PORTFOLIO_FILE, "r", encoding="utf-8") as handle:
            data = json.load(handle)
        return data if isinstance(data, list) else []
    except Exception as error:
        print(f"[portfolio] 讀取失敗：{error}")
        return []


def save_holdings(holdings):
    with open(PORTFOLIO_FILE, "w", encoding="utf-8") as handle:
        json.dump(holdings, handle, ensure_ascii=False, indent=2)


@app.route("/")
def index():
    return send_from_directory(BASE_DIR, "portfolio.html")


@app.route("/api/holdings", methods=["GET"])
def get_holdings():
    return jsonify(load_holdings())


@app.route("/api/holdings", methods=["POST"])
def add_holding():
    body = request.get_json(force=True, silent=True) or {}
    ticker = (body.get("ticker") or "").strip().upper()
    name = (body.get("name") or "").strip()
    shares = body.get("shares")

    if not ticker:
        return jsonify({"error": "ticker 不可為空"}), 400
    try:
        shares = float(shares)
    except (TypeError, ValueError):
        return jsonify({"error": "shares 必須為數字"}), 400

    holdings = load_holdings()
    # 同 ticker 則覆蓋股數，並補名稱
    for item in holdings:
        if item["ticker"].upper() == ticker:
            item["shares"] = shares
            if name:
                item["name"] = name
            save_holdings(holdings)
            return jsonify(holdings)

    holdings.append({"ticker": ticker, "name": name, "shares": shares})
    save_holdings(holdings)
    return jsonify(holdings)


@app.route("/api/holdings/<ticker>", methods=["DELETE"])
def delete_holding(ticker):
    ticker = ticker.strip().upper()
    holdings = [h for h in load_holdings() if h["ticker"].upper() != ticker]
    save_holdings(holdings)
    return jsonify(holdings)


@app.route("/api/portfolio", methods=["GET"])
def get_portfolio():
    """回傳目前持股的即時報價、每檔台幣總額與占比。"""
    holdings = load_holdings()
    return jsonify(build_portfolio(holdings))


def build_portfolio(holdings):
    """組出持股快照（報價、台幣總額、占比、Beta、加權 Beta）。

    抽成獨立函式，讓 Flask 端點與靜態建置腳本共用。
    """
    if not holdings:
        return {"positions": [], "totalValue": 0, "fxRate": None, "portfolioBeta": 0}

    quotes = portfolio_data.get_quotes([h["ticker"] for h in holdings])
    positions = []
    total = 0.0
    for holding in holdings:
        ticker = holding["ticker"].upper()
        quote = quotes.get(ticker, {})
        price = quote.get("price")
        shares = float(holding.get("shares") or 0)
        value = round(price * shares, 2) if price is not None else None
        if value:
            total += value
        beta = holding.get("beta")
        positions.append(
            {
                "ticker": ticker,
                "name": holding.get("name") or quote.get("name") or ticker,
                "shares": shares,
                "price": price,
                "priceUsd": quote.get("priceUsd"),
                "fxRate": quote.get("fxRate"),
                "value": value,
                "beta": float(beta) if beta is not None else None,
                "isTaiwan": portfolio_data.is_taiwan_ticker(ticker),
                "isCash": portfolio_data.is_cash(ticker),
            }
        )

    portfolio_beta = 0.0
    for position in positions:
        if position["value"] and total > 0:
            position["weight"] = round(position["value"] / total * 100, 2)
            if position["beta"] is not None:
                portfolio_beta += (position["value"] / total) * position["beta"]
        else:
            position["weight"] = 0.0

    positions.sort(key=lambda p: p["value"] or 0, reverse=True)
    return {
        "positions": positions,
        "totalValue": round(total, 2),
        "fxRate": portfolio_data.get_usd_twd_rate(),
        "portfolioBeta": round(portfolio_beta, 3),
    }


@app.route("/api/history", methods=["GET"])
def get_history():
    """歷史回朔（假設目前持股固定不變）。"""
    holdings = load_holdings()
    if not holdings:
        return jsonify({"dates": [], "totalValue": [], "perTicker": {}, "dailyReturns": []})
    start = request.args.get("start", "2022-01-01")
    return jsonify(portfolio_data.get_history(holdings, start=start))


@app.route("/api/quote/<ticker>", methods=["GET"])
def get_single_quote(ticker):
    """單檔查價，用於新增前預覽名稱與現價。"""
    return jsonify(portfolio_data.get_quote(ticker))


@app.route("/api/lohas/<ticker>", methods=["GET"])
def get_lohas(ticker):
    """樂活五線譜資料。"""
    return jsonify(portfolio_data.get_lohas(ticker))


@app.route("/api/feargreed", methods=["GET"])
def get_feargreed():
    """CNN Fear & Greed 即時分數。"""
    return jsonify(portfolio_data.get_fear_greed())


def build_lohas_bundle(holdings):
    """靜態建置用：把每檔持股（排除現金）的五線譜 + Fear&Greed 一次算好。"""
    tickers = [
        h["ticker"].upper()
        for h in holdings
        if not portfolio_data.is_cash(h["ticker"])
    ]
    charts = {}
    for ticker in tickers:
        data = portfolio_data.get_lohas(ticker)
        if data.get("chartData"):
            charts[ticker] = data
    return {
        "tickers": list(charts.keys()),
        "charts": charts,
        "fearGreed": portfolio_data.get_fear_greed(),
    }


if __name__ == "__main__":
    print("Portfolio 儀表板啟動： http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=True)
