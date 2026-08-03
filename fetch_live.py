"""盤中即時報價：證交所 MIS API → live.json → push 到 live 分支（單 commit 覆寫）。

launchd 每 5 分鐘跑一次；非交易時段（週末、09:00-13:35 以外）自動跳過。
worktree 在 ~/tw-stock-data-live（live 分支，orphan、只有 live.json）。
"""
import json, datetime, subprocess, sys, urllib.request
from zoneinfo import ZoneInfo

STOCKS = ["2881", "2887", "2891", "2883", "009816", "0056",
          "2303", "2337", "00631L", "3231"]  # 前段持股、後段觀察
WORKTREE = "/Users/lazymei/tw-stock-data-live"

now = datetime.datetime.now(ZoneInfo("Asia/Taipei"))
hm = now.hour * 60 + now.minute
if now.weekday() >= 5 or not (9 * 60 <= hm <= 13 * 60 + 35):
    sys.exit(0)

ex_ch = "|".join(f"tse_{s}.tw" for s in STOCKS)
url = f"https://mis.twse.com.tw/stock/api/getStockInfo.jsp?ex_ch={ex_ch}&json=1&delay=0"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
with urllib.request.urlopen(req, timeout=20) as r:
    msg = json.load(r).get("msgArray", [])

def num(x):
    try:
        v = float(x)
        return v if v > 0 else None
    except (TypeError, ValueError):
        return None

quotes = {}
for x in msg:
    # z=最新成交價；該秒沒成交回 '-'，用買一價遞補，再用開盤價
    price = num(x.get("z")) or num((x.get("b") or "").split("_")[0]) or num(x.get("o"))
    if price is None:
        continue
    quotes[x["c"]] = {
        "name": x.get("n", ""),
        "price": price,
        "prev_close": num(x.get("y")),
        "open": num(x.get("o")),
        "high": num(x.get("h")),
        "low": num(x.get("l")),
        "vol_acc": num(x.get("v")),
        "time": x.get("t", ""),
    }

if not quotes:
    sys.exit("MIS empty response")

out = {"updated_at": now.isoformat(), "date": now.date().isoformat(), "quotes": quotes}
with open(f"{WORKTREE}/live.json", "w", encoding="utf-8") as f:
    json.dump(out, f, ensure_ascii=False, indent=1)

def git(*a):
    subprocess.run(["git", "-C", WORKTREE, *a], check=True, capture_output=True)

git("add", "live.json")
git("commit", "--amend", "-m", f"live: {now:%Y-%m-%d %H:%M}")
git("push", "-f", "origin", "live")
print(f"OK {now:%H:%M} {len(quotes)} stocks")
