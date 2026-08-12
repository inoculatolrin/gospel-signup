# 境外基金公開資料抓取工具

抓取 **東方匯理基金新興市場債券 A 南非幣避險（穩定月配息）**（ISIN `LU1882450999`）
的公開資料。與本 repo 的報名系統無關，獨立於 `tools/` 下，不影響 `index.html`。

---

## 先讀這段：沒有「每日交易金額」

這檔是**盧森堡註冊的開放式基金**，不在交易所掛牌，沒有集中市場撮合，
因此**沒有日成交量／成交金額**——任何平台、任何權限都查不到，那個欄位不存在。

公開可得的只有三種，全部收錄在本工具：

| 想要的東西 | 實際可得 | 頻率 | 來源 |
|---|---|---|---|
| 即時報價 | 每日淨值（T+1 公布） | 日 | 境外基金資訊觀測站 |
| 資產規模總額 | 子基金 AUM（月底） | 月 | Amundi 月報 PDF |
| 交易金額 | 台灣境內銷售／持有金額 | 月 | SITCA 投信投顧公會 |

最接近「資金流」的公開指標是**規模的月度變化**加上 SITCA 的境內銷售統計。

---

## 使用

```bash
cd tools/fund-data

python3 fetch_fund_data.py funds       # 列出已設定的基金
python3 fetch_fund_data.py check       # 檢查三個來源網域是否連得到
python3 fetch_fund_data.py aum         # 抓月報規模 → data/aum.csv
python3 fetch_fund_data.py discover    # 探測 FundClear／SITCA 表單欄位
python3 fetch_fund_data.py nav --param fundId=XXX --param year=2026
```

只依賴 Python 3.10+ 標準函式庫。PDF 解析需要 `pypdf`（或系統的 `pdftotext`）：

```bash
pip install -r requirements.txt
```

輸出為 `data/aum.csv`、`data/nav.csv`，重複執行會依 `(isin, 日期)` 去重合併，
可以安全地排程重跑。

---

## 目前狀態：三個網域都被擋

撰寫當下，執行環境的 egress proxy 拒絕連線到全部三個來源：

```
Amundi 月報（規模）          BLOCKED  Tunnel connection failed: 403 Forbidden
境外基金觀測站（日淨值）      BLOCKED  Tunnel connection failed: 403 Forbidden
SITCA（台灣銷售金額）        BLOCKED  Tunnel connection failed: 403 Forbidden
```

要實際取數，請先把這三個網域加入環境的網路允許清單：

```
www.amundi.com
announce.fundclear.com.tw
www.sitca.org.tw
```

（設定位置見 <https://code.claude.com/docs/en/claude-code-on-the-web>）

放行後先跑 `check`，三個都 OK 再往下。

---

## 各來源的驗證狀態

誠實標註哪些是確認過的、哪些還沒：

| 來源 | 狀態 | 說明 |
|---|---|---|
| Amundi 月報 | **URL 格式已確認** | `.../monthly-factsheet/{ISIN}/ENG/LUX/INSTITUTIONNEL/AMUNDI`，`aum` 指令可直接用 |
| AUM／日期解析 | **已離線測過** | 三種常見寫法（`3,830.15 (EUR million)`／`USD 4,285.85 million`／`EUR 3.83 bn`）都能解析 |
| 表格／表單解析 | **已離線測過** | 含巢狀表格、Big5／CP950 編碼偵測 |
| FundClear 查詢參數 | **未驗證** | 老 JSP 站台，表單欄位名稱無法從外部確認 |
| SITCA 查詢參數 | **未驗證** | ASP.NET WebForms，需 `__VIEWSTATE`／`__EVENTVALIDATION` |

後兩者刻意**不預設任何欄位名**。與其猜一組參數送出去、拿回看似成功實則查錯基金的結果，
不如讓它明確報錯。網域放行後執行：

```bash
python3 fetch_fund_data.py discover
```

會列出頁面上真實的 form action、method 與所有欄位（含 select 的選項值與隱藏欄位），
再把參數用 `--param key=value` 帶進 `nav` 即可。確認後可把預設值寫回
`fund_sources.py` 的 `fetch_nav()`，並將 `FUNDCLEAR_VERIFIED` 改為 `True`。

---

## 新增基金

編輯 `fund_sources.py` 的 `FUNDS`：

```python
FUNDS = {
    "your-key": Fund(
        key="your-key",
        name="基金中文名稱",
        isin="LU0000000000",
        nav_currency="USD",
    ),
}
```

再用 `--fund your-key` 指定。Amundi 以外的基金公司月報路徑不同，
需另外調整 `factsheet_path` 或新增來源轉接函式。

---

## 檔案

| 檔案 | 用途 |
|---|---|
| `fund_sources.py` | 來源轉接層：HTTP、編碼偵測、HTML 表格／表單解析、PDF 解析、三個來源 |
| `fetch_fund_data.py` | CLI 與 CSV 寫入（去重合併） |
| `data/` | 輸出目錄，執行後產生 |
