"""資料層：即時報價、匯率、歷史回朔。

環境限制：公司 SSL 代理會讓 yfinance（curl_cffi）握手失敗，但標準 requests
可正常連到 Yahoo chart API 與台灣證交所。因此本模組一律以 requests 實作：

- 台股/台灣 ETF：台灣證券交易所 (TWSE) MIS 即時 API，盤中即時、盤後最後成交價。
- 美股/美股 ETF：Yahoo Finance chart API（regularMarketPrice）取得最即時報價。
- 匯率：Google Finance USD/TWD 優先，失敗改用 Yahoo TWD=X 即時匯率。
- 歷史：Yahoo chart API 歷史收盤價，美股以歷史匯率換算台幣。
"""

import re
import time

import requests

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
    )
}
_YAHOO_CHART = "https://query1.finance.yahoo.com/v8/finance/chart/{sym}"

# 匯率快取（避免每檔報價都打一次匯率來源）
_fx_cache = {"rate": None, "ts": 0.0}
_FX_TTL_SECONDS = 300

# 名稱快取
_name_cache = {}


def is_taiwan_ticker(ticker):
    """判斷是否為台股/台灣 ETF（yfinance 慣例：.TW / .TWO）。"""
    return ticker.upper().endswith((".TW", ".TWO"))


def is_cash(ticker):
    """判斷是否為現金部位（價格恆為 1 台幣，無報價來源）。"""
    return ticker.upper() in ("TWD-CASH", "CASH", "TWD")


def _to_float(value):
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _twse_channel(ticker):
    """把代號轉成 TWSE MIS 頻道字串。

    2330.TW  -> tse_2330.tw （上市）
    6488.TWO -> otc_6488.tw （上櫃）
    """
    code = ticker.split(".")[0]
    if ticker.upper().endswith(".TWO"):
        return f"otc_{code}.tw"
    return f"tse_{code}.tw"


# ---------------------------------------------------------------- Yahoo chart

def _yahoo_chart(ticker, rng=None, interval="1d", period1=None, period2=None):
    """回傳 Yahoo chart API 的 result[0]，失敗回 None。"""
    params = {"interval": interval}
    if period1 is not None:
        # 指定起訖時間戳可取得每日granularity（range=max 會被降頻成月）
        params["period1"] = period1
        params["period2"] = period2 or int(time.time())
    else:
        params["range"] = rng or "5d"
    try:
        resp = requests.get(
            _YAHOO_CHART.format(sym=ticker), params=params, headers=_HEADERS, timeout=10
        )
        resp.raise_for_status()
        payload = resp.json()
        results = (payload.get("chart") or {}).get("result") or []
        return results[0] if results else None
    except Exception as error:
        print(f"[yahoo] chart 失敗 {ticker}：{error}")
        return None


def _yahoo_quote(ticker):
    """Yahoo 即時報價 + 名稱。回傳 (price, name)。"""
    result = _yahoo_chart(ticker, rng="5d")
    if not result:
        return None, None
    meta = result.get("meta") or {}
    price = meta.get("regularMarketPrice")
    if price is None:
        closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
        closes = [c for c in closes if c is not None]
        price = closes[-1] if closes else None
    name = meta.get("shortName") or meta.get("longName")
    if name:
        _name_cache[ticker.upper()] = name
    return (_to_float(price), name)


def _yahoo_history(ticker, start_ts):
    """回傳 {date_str: close_float}，以日為單位。"""
    result = _yahoo_chart(ticker, period1=start_ts, period2=int(time.time()), interval="1d")
    if not result:
        return {}
    timestamps = result.get("timestamp") or []
    closes = (((result.get("indicators") or {}).get("quote") or [{}])[0]).get("close") or []
    out = {}
    for ts, close in zip(timestamps, closes):
        if close is None or ts < start_ts:
            continue
        date_str = time.strftime("%Y-%m-%d", time.gmtime(ts))
        out[date_str] = float(close)
    return out


# ------------------------------------------------------------------ 匯率

def get_usd_twd_rate():
    """取得 USD -> TWD 即時匯率（Google Finance 優先，Yahoo TWD=X 備援）。"""
    now = time.time()
    if _fx_cache["rate"] and (now - _fx_cache["ts"]) < _FX_TTL_SECONDS:
        return _fx_cache["rate"]

    rate = _google_finance_usd_twd()
    if rate is None:
        rate = _yahoo_usd_twd()
    if rate is None:
        rate = 32.0  # 最終保底，避免整頁掛掉

    _fx_cache["rate"] = rate
    _fx_cache["ts"] = now
    return rate


def _google_finance_usd_twd():
    try:
        resp = requests.get(
            "https://www.google.com/finance/quote/USD-TWD",
            headers=_HEADERS,
            timeout=8,
        )
        resp.raise_for_status()
        for pattern in (
            r'data-last-price="([\d.]+)"',
            r'"USD / TWD"[^}]*?\[(3[0-9]\.\d+)',
            r'class="YMlKec fxKbKc">([\d.]+)',
        ):
            match = re.search(pattern, resp.text)
            if match:
                return float(match.group(1))
    except Exception as error:
        print(f"[fx] Google Finance 匯率取得失敗：{error}")
    return None


def _yahoo_usd_twd():
    price, _ = _yahoo_quote("TWD=X")
    return price


# ------------------------------------------------------------------ 報價

def _get_tw_quote(ticker):
    """台股即時報價（盤中即時價，盤後最後成交價）。"""
    channel = _twse_channel(ticker)
    name = None
    price = None
    try:
        resp = requests.get(
            "https://mis.twse.com.tw/stock/api/getStockInfo.jsp",
            params={
                "ex_ch": channel,
                "json": "1",
                "delay": "0",
                "_": int(time.time() * 1000),
            },
            headers={**_HEADERS, "Referer": "https://mis.twse.com.tw/stock/index.jsp"},
            timeout=8,
        )
        resp.raise_for_status()
        rows = resp.json().get("msgArray") or []
        if rows:
            row = rows[0]
            name = row.get("n") or None
            price = _to_float(row.get("z"))  # 最近成交價
            if price is None and row.get("b"):  # 盤後改用最佳買價
                price = _to_float(row.get("b", "").split("_")[0])
            if price is None:
                price = _to_float(row.get("y"))  # 昨收保底
    except Exception as error:
        print(f"[tw] TWSE 即時報價失敗 {ticker}：{error}")

    if price is None:  # 最終備援：Yahoo
        price, yahoo_name = _yahoo_quote(ticker)
        name = name or yahoo_name

    if name:
        _name_cache[ticker.upper()] = name
    return {"name": name, "price": price, "currency": "TWD"}


def _get_us_quote(ticker):
    """美股即時報價（USD），回傳含美元原價與換算後台幣。"""
    price, name = _yahoo_quote(ticker)
    rate = get_usd_twd_rate()
    twd = round(price * rate, 2) if price is not None else None
    return {
        "name": name,
        "price": twd,
        "priceUsd": price,
        "currency": "TWD",
        "fxRate": rate,
    }


def get_quote(ticker):
    """單檔即時報價，價格一律回傳台幣。"""
    ticker = ticker.strip().upper()
    if is_cash(ticker):
        return {"name": "台幣現金", "price": 1.0, "currency": "TWD"}
    if is_taiwan_ticker(ticker):
        return _get_tw_quote(ticker)
    return _get_us_quote(ticker)


def get_quotes(tickers):
    """多檔報價（逐檔抓取）。"""
    return {ticker.upper(): get_quote(ticker) for ticker in tickers}


# ------------------------------------------------------------------ 歷史回朔

def get_history(holdings, start="2022-01-01"):
    """歷史回朔：以「目前持股固定不變」為假設，往回推算。

    holdings: [{"ticker": ..., "shares": ...}, ...]
    回傳：
      dates:        日期序列
      totalValue:   每日總市值（台幣）
      perTicker:    {ticker: {"value": [...], "weight": [...]}}
      dailyReturns: [{"date", "value", "ret"}]  總市值每日報酬率
    """
    import numpy as np  # noqa: F401 (保留給未來擴充)
    import pandas as pd

    shares = {}
    for holding in holdings:
        qty = _to_float(holding.get("shares"))
        if qty:
            shares[holding["ticker"].strip().upper()] = qty
    if not shares:
        return _empty_history()

    start_ts = int(time.mktime(time.strptime(start, "%Y-%m-%d")))

    close_frames = {}
    for ticker in shares:
        if is_cash(ticker):
            continue  # 現金無需抓歷史，稍後以固定值加入
        hist = _yahoo_history(ticker, start_ts)
        if hist:
            close_frames[ticker] = pd.Series(hist)
        else:
            print(f"[history] 無歷史資料：{ticker}")

    cash_total = sum(shares[t] for t in shares if is_cash(t))

    if not close_frames:
        if cash_total <= 0:
            return _empty_history()

    # 美股需要歷史匯率換算
    need_fx = any(not is_taiwan_ticker(t) for t in close_frames)
    fx_series = None
    if need_fx:
        fx_hist = _yahoo_history("TWD=X", start_ts)
        if fx_hist:
            fx_series = pd.Series(fx_hist)

    combined = pd.DataFrame(close_frames)
    combined.index = pd.to_datetime(combined.index)
    combined = combined.sort_index().ffill()

    if fx_series is not None:
        fx_series.index = pd.to_datetime(fx_series.index)
        fx_aligned = fx_series.sort_index().reindex(combined.index).ffill().bfill()
    else:
        fx_aligned = None

    value_frame = pd.DataFrame(index=combined.index)
    for ticker in close_frames:
        price_series = combined[ticker]
        if not is_taiwan_ticker(ticker) and fx_aligned is not None:
            price_series = price_series * fx_aligned
        value_frame[ticker] = price_series * shares[ticker]

    # 現金：對每個交易日皆為固定台幣金額
    if cash_total > 0:
        for ticker in shares:
            if is_cash(ticker):
                value_frame[ticker] = float(shares[ticker])

    value_frame = value_frame.dropna(how="all").fillna(0.0)
    total = value_frame.sum(axis=1)
    valid = total > 0  # 去掉早期尚未全部上市造成的 0 值段落
    value_frame = value_frame[valid]
    total = total[valid]

    if value_frame.empty:
        return _empty_history()

    per_ticker = {}
    for ticker in value_frame.columns:
        values = value_frame[ticker]
        weights = (values / total * 100).round(2)
        per_ticker[ticker] = {
            "value": [round(float(v), 2) for v in values],
            "weight": [round(float(w), 2) for w in weights],
        }

    returns = total.pct_change().fillna(0.0) * 100
    daily_returns = [
        {"date": d.strftime("%Y-%m-%d"), "value": round(float(v), 2), "ret": round(float(r), 3)}
        for d, v, r in zip(value_frame.index, total, returns)
    ]

    return {
        "dates": [d.strftime("%Y-%m-%d") for d in value_frame.index],
        "totalValue": [round(float(v), 2) for v in total],
        "perTicker": per_ticker,
        "dailyReturns": daily_returns,
    }


def _empty_history():
    return {"dates": [], "totalValue": [], "perTicker": {}, "dailyReturns": []}


# ------------------------------------------------------------ 樂活五線譜

_LOHAS_WINDOW = 875  # 約 3.5 年交易日


def get_lohas(ticker, start="2019-01-01"):
    """樂活五線譜：線性回歸中軸 TL 與 ±1SD/±2SD 通道。

    回傳：
      currencySymbol, lastDate, sentimentDescription,
      chartData: [{date, close, tl, p1sd, p2sd, m1sd, m2sd}]
    """
    import numpy as np

    ticker = ticker.strip().upper()
    start_ts = int(time.mktime(time.strptime(start, "%Y-%m-%d")))

    if is_cash(ticker):
        return {"error": "現金無五線譜資料", "chartData": []}

    hist = _yahoo_history(ticker, start_ts)
    if not hist:
        return {"error": f"找不到 {ticker} 的歷史數據", "chartData": []}

    items = sorted(hist.items())[-_LOHAS_WINDOW:]
    dates = [d for d, _ in items]
    closes = np.array([c for _, c in items], dtype=float)

    x = np.arange(len(closes))
    slope, intercept = np.polyfit(x, closes, 1)
    tl = slope * x + intercept
    sd = float(np.std(closes - tl))

    chart_data = []
    for i, date_str in enumerate(dates):
        chart_data.append(
            {
                "date": date_str,
                "close": round(float(closes[i]), 2),
                "tl": round(float(tl[i]), 2),
                "p1sd": round(float(tl[i] + sd), 2),
                "p2sd": round(float(tl[i] + 2 * sd), 2),
                "m1sd": round(float(tl[i] - sd), 2),
                "m2sd": round(float(tl[i] - 2 * sd), 2),
            }
        )

    is_tw = is_taiwan_ticker(ticker)
    return {
        "ticker": ticker,
        "currencySymbol": "NT$" if is_tw else "$",
        "lastDate": dates[-1] if dates else None,
        "sentimentDescription": (
            "統計學價格軌道與 CNN 美股市場情緒參考"
            if is_tw
            else "統計學價格軌道與美股即時情緒指標"
        ),
        "chartData": chart_data,
    }


def get_fear_greed():
    """CNN Fear & Greed 即時分數（透過 requests，避免額外套件）。"""
    try:
        resp = requests.get(
            "https://production.dataviz.cnn.io/index/fearandgreed/graphdata",
            headers=_HEADERS,
            timeout=10,
        )
        resp.raise_for_status()
        fg = resp.json().get("fear_and_greed") or {}
        score = float(fg.get("score"))
        rating = str(fg.get("rating") or "").upper()
        return {"score": round(score, 1), "rating": rating}
    except Exception as error:
        print(f"[fg] CNN Fear & Greed 取得失敗：{error}")
        return {"score": 50.0, "rating": "資料暫缺"}


def gauge_color(score):
    if score <= 25:
        return "#cc0000"
    if score <= 45:
        return "#ff9900"
    if score <= 55:
        return "#888888"
    if score <= 75:
        return "#66cc00"
    return "#008800"
