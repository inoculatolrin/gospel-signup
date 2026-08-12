"""境外基金資料來源轉接層。

三個公開來源：
  1. Amundi 月報 PDF        → 基金規模（AUM，月頻、月底數據）
  2. 境外基金資訊觀測站      → 每日參考淨值（T+1 公布）
  3. SITCA 投信投顧公會      → 台灣境內銷售／持有金額（月頻）

重要前提：開放式基金不在交易所掛牌，沒有「日成交量／成交金額」這種欄位。
最接近資金流的公開數據是「規模的月度變化」與 SITCA 的境內銷售統計。

各來源的 verified 旗標代表該來源的請求參數是否經過實機驗證。
撰寫當下這三個網域都被執行環境的 egress proxy 擋住，無法實跑，
因此 FundClear 與 SITCA 標記為未驗證，需先跑一次 discover 取得真實表單欄位。
"""

from __future__ import annotations

import gzip
import io
import re
import ssl
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from html.parser import HTMLParser

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TIMEOUT = 45


# --------------------------------------------------------------------------
# 基金清單
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Fund:
    key: str
    name: str
    isin: str
    nav_currency: str
    # Amundi 月報的語系／通路路徑片段，不同級別偶有差異
    factsheet_path: str = "ENG/LUX/INSTITUTIONNEL/AMUNDI"


FUNDS: dict[str, Fund] = {
    "amundi-em-bond-a-zar-hgd": Fund(
        key="amundi-em-bond-a-zar-hgd",
        name="東方匯理基金新興市場債券 A 南非幣避險 (穩定月配息)",
        isin="LU1882450999",
        nav_currency="ZAR",
    ),
}


# --------------------------------------------------------------------------
# 資料點
# --------------------------------------------------------------------------


@dataclass
class NavPoint:
    date: str          # YYYY-MM-DD
    isin: str
    nav: float
    currency: str
    source: str


@dataclass
class AumPoint:
    as_of: str         # YYYY-MM-DD
    isin: str
    aum: float
    currency: str
    scope: str         # sub_fund（整檔子基金）或 share_class（單一級別）
    source: str


@dataclass
class SalesPoint:
    month: str         # YYYY-MM
    isin: str
    amount_twd: float
    metric: str        # 國內銷售金額 / 國內投資人持有金額
    source: str


# --------------------------------------------------------------------------
# HTTP
# --------------------------------------------------------------------------


class SourceBlocked(RuntimeError):
    """網域被 proxy 擋掉，或對方拒絕連線。"""


class SourceUnavailable(RuntimeError):
    """連得到但沒拿到預期內容。"""


def http_get(url: str, params: dict[str, str] | None = None) -> tuple[bytes, str]:
    """回傳 (raw_bytes, final_url)。被擋時丟 SourceBlocked。"""
    return _request(url, params=params, data=None)


def http_post(url: str, data: dict[str, str]) -> tuple[bytes, str]:
    return _request(url, params=None, data=data)


def _request(
    url: str, params: dict[str, str] | None, data: dict[str, str] | None
) -> tuple[bytes, str]:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    body = urllib.parse.urlencode(data).encode() if data is not None else None
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "*/*",
            "Accept-Encoding": "gzip",
            "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            raw = resp.read()
            if resp.headers.get("Content-Encoding") == "gzip":
                raw = gzip.decompress(raw)
            return raw, resp.geturl()
    except urllib.error.HTTPError as exc:
        # proxy 政策拒絕時多半是 403；對方站台擋爬蟲也是 403，訊息裡一併點出
        if exc.code in (403, 407):
            raise SourceBlocked(
                f"{url} 回應 {exc.code}－可能是 egress proxy 未放行該網域，"
                f"或對方站台阻擋自動化請求"
            ) from exc
        raise SourceUnavailable(f"{url} 回應 HTTP {exc.code}") from exc
    except (urllib.error.URLError, ssl.SSLError, TimeoutError) as exc:
        raise SourceBlocked(f"{url} 連線失敗：{exc}") from exc


def decode(raw: bytes) -> str:
    """老 JSP 站台可能是 UTF-8／Big5／CP950，逐一試。"""
    match = re.search(rb'charset=["\']?\s*([\w-]+)', raw[:4096], re.I)
    candidates = []
    if match:
        candidates.append(match.group(1).decode("ascii", "ignore"))
    candidates += ["utf-8", "big5hkscs", "cp950", "latin-1"]
    for enc in candidates:
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", "replace")


# --------------------------------------------------------------------------
# HTML 解析：表格與表單
# --------------------------------------------------------------------------


class TableParser(HTMLParser):
    """抽出頁面上所有表格，巢狀表格各自成一張。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[list[list[str]]] = []
        # 三個堆疊同深度，讓內層表格不會蓋掉外層正在收集的列／格
        self._stack: list[list[list[str]]] = []
        self._rows: list[list[str] | None] = []
        self._cells: list[list[str] | None] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._stack.append([])
            self._rows.append(None)
            self._cells.append(None)
        elif tag == "tr" and self._stack:
            self._rows[-1] = []
        elif tag in ("td", "th") and self._stack and self._rows[-1] is not None:
            self._cells[-1] = []

    def handle_endtag(self, tag: str) -> None:
        if not self._stack:
            return
        if tag in ("td", "th") and self._cells[-1] is not None:
            self._rows[-1].append(" ".join("".join(self._cells[-1]).split()))
            self._cells[-1] = None
        elif tag == "tr" and self._rows[-1] is not None:
            if any(c for c in self._rows[-1]):
                self._stack[-1].append(self._rows[-1])
            self._rows[-1] = None
        elif tag == "table":
            table = self._stack.pop()
            self._rows.pop()
            self._cells.pop()
            if table:
                self.tables.append(table)

    def handle_data(self, data: str) -> None:
        if self._stack and self._cells[-1] is not None:
            self._cells[-1].append(data)


@dataclass
class FormField:
    name: str
    kind: str                       # input type 或 select/textarea
    value: str = ""
    options: list[str] = field(default_factory=list)


@dataclass
class DiscoveredForm:
    action: str
    method: str
    fields: list[FormField]


class FormParser(HTMLParser):
    """探測頁面上的表單欄位，供未驗證來源補齊參數用。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.forms: list[DiscoveredForm] = []
        self._current: DiscoveredForm | None = None
        self._select: FormField | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        a = {k: (v or "") for k, v in attrs}
        if tag == "form":
            self._current = DiscoveredForm(
                action=a.get("action", ""),
                method=(a.get("method") or "get").lower(),
                fields=[],
            )
        elif tag == "input" and self._current is not None:
            if a.get("name"):
                self._current.fields.append(
                    FormField(a["name"], a.get("type", "text"), a.get("value", ""))
                )
        elif tag == "select" and self._current is not None:
            if a.get("name"):
                self._select = FormField(a["name"], "select")
        elif tag == "option" and self._select is not None:
            self._select.options.append(a.get("value", ""))

    def handle_endtag(self, tag: str) -> None:
        if tag == "select" and self._select is not None and self._current is not None:
            self._current.fields.append(self._select)
            self._select = None
        elif tag == "form" and self._current is not None:
            self.forms.append(self._current)
            self._current = None


def parse_tables(raw: bytes) -> list[list[list[str]]]:
    parser = TableParser()
    parser.feed(decode(raw))
    return parser.tables


def parse_forms(raw: bytes) -> list[DiscoveredForm]:
    parser = FormParser()
    parser.feed(decode(raw))
    return parser.forms


# --------------------------------------------------------------------------
# 來源 1：Amundi 月報（基金規模）— URL 格式已確認
# --------------------------------------------------------------------------

AMUNDI_FACTSHEET = "https://www.amundi.com/globaldistributor/dl/doc/monthly-factsheet/{isin}/{path}"

_AUM_PATTERNS = [
    # 例：Net assets 3,830.15 (EUR million)  /  AUM: EUR 3.83 bn
    re.compile(
        r"(?:net\s+assets|total\s+net\s+assets|assets\s+under\s+management|aum)"
        r"[^\d\n]{0,40}?"
        r"(?P<cur>EUR|USD|ZAR)?\s*"
        r"(?P<num>[\d][\d,\.\s]{2,20})\s*"
        r"(?P<unit>million|bn|billion|m\b|mn)?",
        re.I,
    ),
    re.compile(
        r"(?P<cur>EUR|USD|ZAR)\s*(?P<num>[\d][\d,\.\s]{2,20})\s*"
        r"(?P<unit>million|bn|billion|mn)\s*(?:net\s+assets|aum)",
        re.I,
    ),
]


def factsheet_url(fund: Fund) -> str:
    return AMUNDI_FACTSHEET.format(isin=fund.isin, path=fund.factsheet_path)


def pdf_to_text(pdf: bytes) -> str:
    """優先用 pypdf，退而求其次用 pdftotext；都沒有就丟錯讓呼叫端存檔。"""
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        pass
    else:
        reader = PdfReader(io.BytesIO(pdf))
        return "\n".join(page.extract_text() or "" for page in reader.pages)

    import shutil
    import subprocess
    import tempfile

    if shutil.which("pdftotext"):
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(pdf)
            tmp.flush()
            out = subprocess.run(
                ["pdftotext", "-layout", tmp.name, "-"],
                capture_output=True,
                check=True,
            )
            return out.stdout.decode("utf-8", "replace")

    raise SourceUnavailable(
        "無法解析 PDF：請先 pip install pypdf，或安裝 poppler-utils 取得 pdftotext"
    )


def parse_aum(text: str) -> tuple[float, str] | None:
    """從月報文字擷取 (金額, 幣別)，金額一律換算成百萬。"""
    for pattern in _AUM_PATTERNS:
        for m in pattern.finditer(text):
            num = m.group("num").replace(",", "").replace(" ", "")
            if num.count(".") > 1 or not num.strip("."):
                continue
            try:
                value = float(num)
            except ValueError:
                continue
            unit = (m.group("unit") or "").lower()
            if unit in ("bn", "billion"):
                value *= 1000
            return value, (m.group("cur") or "EUR").upper()
    return None


def fetch_aum(fund: Fund) -> AumPoint:
    """下載月報並取出基金規模。回傳的金額單位為百萬。"""
    raw, url = http_get(factsheet_url(fund))
    if not raw.startswith(b"%PDF"):
        raise SourceUnavailable(f"{url} 回應的不是 PDF（可能已改版或該級別無月報）")
    text = pdf_to_text(raw)
    parsed = parse_aum(text)
    if parsed is None:
        raise SourceUnavailable("月報中找不到 Net assets／AUM 欄位，請檢查版面是否改版")
    value, currency = parsed
    as_of = _factsheet_date(text)
    return AumPoint(
        as_of=as_of,
        isin=fund.isin,
        aum=value,
        currency=currency,
        scope="sub_fund",
        source="amundi-monthly-factsheet",
    )


def _factsheet_date(text: str) -> str:
    """月報封面通常寫 as of 31/05/2026 或 31 May 2026。"""
    m = re.search(r"(\d{2})[/\-.](\d{2})[/\-.](\d{4})", text)
    if m:
        return f"{m.group(3)}-{m.group(2)}-{m.group(1)}"
    months = (
        "january february march april may june july "
        "august september october november december"
    ).split()
    m = re.search(r"(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})", text)
    if m:
        name = m.group(2).lower()
        for idx, full in enumerate(months, start=1):
            if full.startswith(name[:3]):
                return f"{m.group(3)}-{idx:02d}-{int(m.group(1)):02d}"
    return ""


# --------------------------------------------------------------------------
# 來源 2：境外基金資訊觀測站（每日淨值）— 參數未驗證
# --------------------------------------------------------------------------

FUNDCLEAR_HOST = "https://announce.fundclear.com.tw"
FUNDCLEAR_SEARCH = f"{FUNDCLEAR_HOST}/MOPSFundWeb/I01.jsp"
FUNDCLEAR_VERIFIED = False


def discover_fundclear() -> list[DiscoveredForm]:
    """抓查詢頁的表單欄位。網域放行後跑一次，把真實參數名填回 fetch_nav。"""
    raw, _ = http_get(FUNDCLEAR_SEARCH)
    return parse_forms(raw)


def fetch_nav(fund: Fund, params: dict[str, str]) -> list[NavPoint]:
    """以 discover 得到的參數送出查詢，解析淨值表。

    params 必須由呼叫端提供，因為 FundClear 的表單欄位名稱尚未實機確認；
    這裡刻意不預設任何欄位名，避免送出看似成功卻查錯基金的請求。
    """
    if not params:
        raise SourceUnavailable(
            "FundClear 查詢參數未提供。請先執行：\n"
            "    python3 fetch_fund_data.py discover\n"
            "取得表單欄位後，用 --param key=value 帶入。"
        )
    raw, url = http_post(FUNDCLEAR_SEARCH, params)
    points = _nav_points_from_tables(parse_tables(raw), fund)
    if not points:
        raise SourceUnavailable(f"{url} 的回應中找不到淨值資料列，請確認查詢參數")
    return points


_DATE_RE = re.compile(r"(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})")
_NUM_RE = re.compile(r"^-?[\d,]+\.?\d*$")


def _nav_points_from_tables(
    tables: list[list[list[str]]], fund: Fund
) -> list[NavPoint]:
    """在所有表格中找出「日期 + 數字」的列，視為淨值資料。"""
    points: list[NavPoint] = []
    seen: set[str] = set()
    for table in tables:
        for row in table:
            date_iso = None
            value = None
            for cell in row:
                m = _DATE_RE.search(cell)
                if m and date_iso is None:
                    date_iso = f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
                    continue
                text = cell.replace(",", "")
                if value is None and _NUM_RE.match(cell.strip()) and "." in text:
                    value = float(text)
            if date_iso and value is not None and date_iso not in seen:
                seen.add(date_iso)
                points.append(
                    NavPoint(
                        date=date_iso,
                        isin=fund.isin,
                        nav=value,
                        currency=fund.nav_currency,
                        source="fundclear",
                    )
                )
    return sorted(points, key=lambda p: p.date)


# --------------------------------------------------------------------------
# 來源 3：SITCA 境外基金統計（台灣境內銷售金額）— 參數未驗證
# --------------------------------------------------------------------------

SITCA_HOST = "https://www.sitca.org.tw"
SITCA_OFFSHORE_STATS = f"{SITCA_HOST}/ROC/Industry/IN3001.aspx?PGMID=IN0301"
SITCA_VERIFIED = False


def discover_sitca() -> list[DiscoveredForm]:
    raw, _ = http_get(SITCA_OFFSHORE_STATS)
    return parse_forms(raw)


def fetch_sales(fund: Fund, params: dict[str, str]) -> list[SalesPoint]:
    """SITCA 是 ASP.NET WebForms，需帶 __VIEWSTATE 等隱藏欄位。

    discover_sitca() 會把隱藏欄位一併帶出來，實作時直接把整包送回去即可。
    """
    if not params:
        raise SourceUnavailable(
            "SITCA 查詢參數未提供（ASP.NET 需要 __VIEWSTATE / __EVENTVALIDATION）。"
            "請先執行 discover 取得隱藏欄位。"
        )
    raw, url = http_post(SITCA_OFFSHORE_STATS, params)
    tables = parse_tables(raw)
    rows: list[SalesPoint] = []
    for table in tables:
        for row in table:
            if fund.isin not in " ".join(row):
                continue
            for cell in row:
                text = cell.replace(",", "")
                if _NUM_RE.match(cell.strip()):
                    rows.append(
                        SalesPoint(
                            month="",
                            isin=fund.isin,
                            amount_twd=float(text),
                            metric="國內銷售金額",
                            source="sitca",
                        )
                    )
                    break
    if not rows:
        raise SourceUnavailable(f"{url} 的回應中找不到 {fund.isin} 的資料列")
    return rows


# --------------------------------------------------------------------------
# 連線檢查
# --------------------------------------------------------------------------

SOURCE_HOSTS = {
    "Amundi 月報（規模）": "https://www.amundi.com/",
    "境外基金觀測站（日淨值）": f"{FUNDCLEAR_HOST}/",
    "SITCA（台灣銷售金額）": f"{SITCA_HOST}/",
}


def check_hosts() -> dict[str, str]:
    """回傳 {來源: 狀態}，用來一眼看出哪些網域還沒放行。"""
    results: dict[str, str] = {}
    for label, url in SOURCE_HOSTS.items():
        try:
            http_get(url)
        except SourceBlocked as exc:
            results[label] = f"BLOCKED  {exc}"
        except SourceUnavailable as exc:
            results[label] = f"REACHABLE (非預期回應) {exc}"
        else:
            results[label] = "OK"
    return results
