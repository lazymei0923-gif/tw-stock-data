"""全市場（上市＋上櫃）首陰反包掃描。

維護 market_history.json（每檔近 15 個交易日 O/C/V），產出 fyb_candidates.json：
- state=streak：連續漲停 ≥2 天（人氣股成形，等首陰）
- state=yin：已出現「連板後首陰」且仍在 3 天黃金期，附五關判定

用法：
  python market_scan.py              # 只補當天（GitHub Actions 每日 18:05）
  python market_scan.py --backfill   # 往回補滿 15 個交易日（首次建庫用）

Actions 流程會先從 market 分支抓舊 market_history.json 再執行本檔。
只納入 4 位數純數字代號（排除 ETF/ETN/特別股/權證）。
"""
import json, datetime, os, re, sys, time, urllib.request

HIST = "market_history.json"
CAND = "fyb_candidates.json"
KEEP = 15
CODE_RE = re.compile(r"^[1-9]\d{3}$")
MIN_TURNOVER = 3e8  # 成交值門檻（元）：首陰日／連板中當日低於此值不上榜（2026-08-03 拍板 3 億）

def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=40) as r:
        return json.load(r)

def num(x):
    try:
        v = float(str(x).replace(",", "").replace("+", ""))
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None

def twse_day(d):
    j = get(f"https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={d:%Y%m%d}&type=ALLBUT0999&response=json")
    if j.get("stat") != "OK":
        return None
    out = {}
    for t in j.get("tables", []):
        f = t.get("fields", [])
        if "證券代號" in f:
            i = {k: f.index(k) for k in ("證券代號", "證券名稱", "成交股數", "開盤價", "收盤價")}
            for row in t["data"]:
                code = row[i["證券代號"]].strip()
                if not CODE_RE.match(code):
                    continue
                o, c, v = num(row[i["開盤價"]]), num(row[i["收盤價"]]), num(row[i["成交股數"]])
                if c is None or v is None:
                    continue
                out[code] = {"n": row[i["證券名稱"]].strip(), "m": "tse", "o": o, "c": c, "v": v}
            break
    return out or None

def tpex_day(d):
    roc = f"{d.year-1911}/{d.month:02d}/{d.day:02d}"
    j = get(f"https://www.tpex.org.tw/www/zh-tw/afterTrading/dailyQuotes?date={urllib.parse.quote(roc)}&response=json")
    if j.get("date") != f"{d:%Y%m%d}":
        return None
    out = {}
    for t in j.get("tables", []):
        f = [x.strip() for x in t.get("fields", [])]
        if f and f[0] == "代號":
            ic, inm = f.index("代號"), f.index("名稱")
            icl, iop, ivol = f.index("收盤"), f.index("開盤"), f.index("成交股數")
            for row in t["data"]:
                code = str(row[ic]).strip()
                if not CODE_RE.match(code):
                    continue
                o, c, v = num(row[iop]), num(row[icl]), num(row[ivol])
                if c is None or v is None:
                    continue
                out[code] = {"n": str(row[inm]).strip(), "m": "otc", "o": o, "c": c, "v": v}
            break
    return out or None

def load_hist():
    if os.path.exists(HIST):
        with open(HIST, encoding="utf-8") as f:
            return json.load(f)
    return {"dates": [], "stocks": {}}

def merge_day(hist, ds, day):
    if ds in hist["dates"]:
        return
    hist["dates"].append(ds)
    hist["dates"].sort()
    for code, r in day.items():
        st = hist["stocks"].setdefault(code, {"n": r["n"], "m": r["m"], "bars": []})
        st["n"], st["m"] = r["n"], r["m"]
        st["bars"].append([ds, r["o"], r["c"], r["v"]])
        st["bars"].sort(key=lambda b: b[0])
    trim(hist)

def trim(hist):
    hist["dates"] = hist["dates"][-KEEP:]
    ok = set(hist["dates"])
    dead = []
    for code, st in hist["stocks"].items():
        st["bars"] = [b for b in st["bars"] if b[0] in ok]
        if not st["bars"]:
            dead.append(code)
    for code in dead:
        del hist["stocks"][code]

def scan(hist):
    items = []
    for code, st in hist["stocks"].items():
        bars = st["bars"]
        n = len(bars)
        if n < 3:
            continue
        chg = [None] + [(bars[i][2] - bars[i-1][2]) / bars[i-1][2] * 100 for i in range(1, n)]
        lim = [c is not None and c >= 9.4 for c in chg]
        tail = 0
        i = n - 1
        while i >= 1 and lim[i]:
            tail += 1
            i -= 1
        j = -1
        for k in range(n - 1, 1, -1):
            if chg[k] is not None and chg[k] <= -5 and lim[k-1]:
                j = k
                break
        if j >= 0 and (n - 1 - j) <= 3:
            streak = 0
            m = j - 1
            while m >= 1 and lim[m]:
                streak += 1
                m -= 1
            vr = None
            if j >= 5:
                avg = sum(b[3] for b in bars[j-5:j]) / 5
                if avg > 0:
                    vr = round(bars[j][3] / avg, 2)
            if bars[j][2] * bars[j][3] < MIN_TURNOVER:
                continue
            open2 = bars[j+1][1] if j + 1 < n else None
            days = n - 1 - j
            conds = [
                {"k": "連續漲停 ≥2 天", "ok": streak >= 2, "why": f"連 {streak} 板"},
                {"k": "首陰跌幅 ≥5%", "ok": True, "why": f"{bars[j][0][5:]} 跌 {chg[j]:.1f}%"},
                {"k": "首陰量比 ≥1.5", "ok": None if vr is None else vr >= 1.5,
                 "why": "量資料不足" if vr is None else f"量比 {vr}"},
                {"k": "隔天開盤不破首陰收盤", "ok": None if open2 is None else open2 >= bars[j][2],
                 "why": "等下個交易日開盤" if open2 is None else f"開 {open2} vs 收 {bars[j][2]}"},
                {"k": "首陰後 3 天內", "ok": days <= 3, "why": "首陰當天" if days == 0 else f"第 {days} 天"},
            ]
            items.append({
                "code": code, "name": st["n"], "market": st["m"], "state": "yin",
                "close": bars[-1][2], "yinClose": bars[j][2], "yinDate": bars[j][0],
                "days": days, "conds": conds,
                "allPass": all(c["ok"] is True for c in conds),
                "pend": sum(1 for c in conds if c["ok"] is None),
            })
        elif tail >= 2:
            if bars[-1][2] * bars[-1][3] < MIN_TURNOVER:
                continue
            items.append({"code": code, "name": st["n"], "market": st["m"], "state": "streak",
                          "tail": tail, "close": bars[-1][2]})
    items.sort(key=lambda x: (
        0 if x["state"] == "yin" and x.get("allPass") else
        1 if x["state"] == "yin" and x.get("pend") else
        2 if x["state"] == "yin" else 3,
        -(x.get("tail") or 0)))
    return items[:60]

def main():
    hist = load_hist()
    today = datetime.date.today()
    if "--backfill" in sys.argv:
        d, tried = today, 0
        while len(hist["dates"]) < KEEP and tried < 35:
            ds = d.isoformat()
            if d.weekday() < 5 and ds not in hist["dates"]:
                tw = twse_day(d)
                if tw:
                    tp = tpex_day(d) or {}
                    tw.update(tp)
                    merge_day(hist, ds, tw)
                    print(f"{ds}: {len(tw)} stocks")
                time.sleep(2.5)
            d -= datetime.timedelta(days=1)
            tried += 1
    elif today.isoformat() in hist["dates"]:
        print(f"{today}: already in history, rescan only")
    else:
        try:
            tw = twse_day(today)
        except Exception as e:
            tw = None
            print(f"{today}: TWSE fetch failed ({e}), rescan with existing history")
        if tw:
            try:
                tp = tpex_day(today) or {}
            except Exception:
                tp = {}
            tw.update(tp)
            merge_day(hist, today.isoformat(), tw)
            print(f"{today}: {len(tw)} stocks")
        elif tw is not None:
            print(f"{today}: no market data (holiday?)")
    with open(HIST, "w", encoding="utf-8") as f:
        json.dump(hist, f, ensure_ascii=False, separators=(",", ":"))
    cands = scan(hist)
    with open(CAND, "w", encoding="utf-8") as f:
        json.dump({"updated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   "asof": hist["dates"][-1] if hist["dates"] else None,
                   "items": cands}, f, ensure_ascii=False, indent=1)
    print(f"candidates: {len(cands)} (yin: {sum(1 for x in cands if x['state']=='yin')})")

if __name__ == "__main__":
    main()
