import json, datetime, urllib.request

# 持股清單（要加減股票改這裡）
STOCKS = ["2881", "2887", "2891", "2883", "009816", "0056",
          "2303", "2337", "00631L", "3231",
          "2330", "3711", "6239", "3037", "8046", "3189", "6669", "2356", "3693"]  # 持股／觀察／AMD 供應鏈

BASE = "https://api.finmindtrade.com/api/v4/data"
start = (datetime.date.today() - datetime.timedelta(days=70)).isoformat()

out = {"updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "stocks": {}}
for s in STOCKS:
    url = f"{BASE}?dataset=TaiwanStockPrice&data_id={s}&start_date={start}"
    with urllib.request.urlopen(url, timeout=30) as r:
        rows = json.load(r)["data"]
    rows = [x for x in rows if x["Trading_Volume"] > 0]  # 去掉休市/無量列
    if len(rows) < 21:
        continue
    closes = [x["close"] for x in rows]
    vols = [x["Trading_Volume"] for x in rows]
    out["stocks"][s] = {
        "date": rows[-1]["date"],
        "close": closes[-1],
        "prev": closes[-2],
        "ma5": round(sum(closes[-5:]) / 5, 2),
        "ma20": round(sum(closes[-20:]) / 20, 2),
        "vol_ratio": round(vols[-1] / (sum(vols[-6:-1]) / 5), 2),
        "history": [
            {"date": x["date"], "open": x["open"], "high": x["max"], "low": x["min"],
             "close": x["close"], "volume": x["Trading_Volume"]}
            for x in rows[-15:]
        ],
    }

with open("data.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)
print(f"OK: {len(out['stocks'])} stocks")
