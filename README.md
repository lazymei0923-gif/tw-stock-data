# tw-stock-data · 每日台股資料倉＋獲利累計帳本

GitHub Actions 每個交易日 18:05（台北）自動抓 FinMind 資料、算好技術指標、commit 成 `data.json`。

任何 Claude 雲端 session 可直接讀：

```
https://raw.githubusercontent.com/lazymei0923-gif/tw-stock-data/main/data.json
```

## 檔案

| 檔案 | 用途 |
| --- | --- |
| `.github/workflows/daily.yml` | 排程：週一至五 UTC 10:05（台北 18:05）自動抓資料並 commit |
| `fetch_daily.py` | 抓 FinMind `TaiwanStockPrice`，算 昨收／MA5／MA20／量比＋近 15 日 K |
| `data.json` | 產出資料（自動更新，勿手改） |
| `ledger.json` | 已實現損益累計帳本＋股利紀錄（手動維護，永遠累計不歸零） |

## 持股清單

改 `fetch_daily.py` 最上面的 `STOCKS` 清單即可（目前：2881 富邦金、2887 台新新光金、2891 中信金、2883 凱基金、009816 凱基台灣TOP50、0056 元大高股息、2303 聯電）。

## 注意

- repo Settings → Actions → General → Workflow permissions 需勾 **Read and write permissions**，Action 才能 commit。
- FinMind 免費額度每小時 300 次呼叫；此 Action 每天只打 7 次。
- `ledger.json` 稅費規則：ETF 證交稅 0.1%、個股 0.3%、手續費 0.1425%，皆捨去到元。
