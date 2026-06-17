# 召會活動報名及統計平台

> 6/21 數算主恩聚會－回家　福音報名系統
> 最後更新：2026/6/17　Apps Script v10

---

## 系統概述

本系統為召會福音聚會的線上報名平台，提供：
- 邀約人透過網頁表單報名，填寫自己與受邀福音朋友的資料
- 填寫過姓名後可查詢並修改上次填寫的內容
- 管理員可在 Google 試算表中一鍵更新所有統計分頁
- 後台統計涵蓋：出席人數、用餐人數、帶菜品項、人位需求、代禱名單

---

## 架構總覽

前端：GitHub Pages
URL: https://inoculatolrin.github.io/gospel-signup/
檔案：index.html（單頁 HTML + 內嵌 JS）

後端：Google Apps Script Web App
FRIEND_URL: AKfycbyy3pI74Dmyqe5uC1_RAvR1hKCj9gWZIHwzmr9fbt9Rsp4lx0tdYjBIQLQnXwvfVbst4Q
Script ID:  1Y16QhZDOxmHDBhnhjA8qApJFfVdVkuP8eHN-f0OM7VTasH9gLLKqcuUW

資料庫：Google Sheets
試算表 ID: 1A051I0_OFMSqX1nS3gbzzW0tUEV_lmKFKNsiMsVy5qI

---

## 試算表結構

### 分頁清單

| 分頁名稱 | 用途 |
|---------|------|
| 報名資料 | 所有報名原始資料（主資料表）|
| 設定 | 活動資訊（標題、地點、時間、標語）|
| 統計 | 主統計（總報名/出席/用餐/各類福音朋友）|
| 出席統計 | 各區域出席明細（每邀約人一列）|
| 帶菜統計 | 帶菜品項彙整 |
| 人位統計 | 各年齡層人位需求 |
| 代禱統計 | 未出席福音朋友名單，供代禱使用 |

### 報名資料欄位（1-indexed）

Col  欄  說明
 1   A   時間戳記
 2   B   姓名（邀約人）
 3   C   區域（杭州/林森/忠孝/其它）
 4   D   邀約人出席（出席/空）
 5   E   邀約人用餐（用餐/空）
 6   F   受邀一 姓名
 7   G   受邀一 身份
 8   H   受邀一 年齡
 9   I   受邀一 出席
10   J   受邀一 用餐
11-15 K-O 受邀二（同結構）
16-20 P-T 受邀三（同結構）
21   U   備註 ★ 固定在第21欄
22   V   修改連結
23-56    受邀四以上（每人5欄）
57   BE  帶菜 ★ 固定在第57欄

★ 重要：備註固定在第21欄(U)，帶菜固定在第57欄(BE)。
doPost 用 splice(20,0,notes) 與 while-pad 確保固定位置。

---

## Apps Script 函數說明

Apps Script 連結：
https://script.google.com/u/0/home/projects/1Y16QhZDOxmHDBhnhjA8qApJFfVdVkuP8eHN-f0OM7VTasH9gLLKqcuUW/edit

### updateAllStats()
「立即更新」按鈕呼叫此函數，依序執行：
1. updateStats() 更新「統計」分頁
2. updateAttendSheet() 更新「出席統計」
3. fixDishStats() 更新「帶菜統計」
4. updateSeatStats() 更新「人位統計」
5. updatePrayerStats() 更新「代禱統計」

### updateStats()
掃描報名資料，按區域統計總報名/出席/用餐及各類福音朋友人數（青職/大專/青少年）。

### updateAttendSheet()
每位邀約人一列，含姓名/區域/出席/用餐及受邀一到三詳情。

### fixDishStats()
讀取第57欄(BE)帶菜資料，彙整輸出至「帶菜統計」。

### updateSeatStats()
依年齡層(年長/青職/大專/青少年)統計出席人位需求。

### updatePrayerStats()
篩選「身份=福音朋友且出席欄空白」者，列出代禱名單。

---

### 管理介面函數

| 函數 | 說明 |
|------|------|
| onOpen() | 開啟試算表時建立「活動管理」選單 |
| showAdminPanel() | 顯示管理側邊面板（HTML Service）|
| saveEventInfo(data) | 儲存活動資訊至「設定」分頁 |
| clearSlogan() | 清除標語 |
| setupTriggers() | 設定每小時自動執行 updateAllStats |
| getInviterList() | 讀取邀約人清單 |
| addInviter(name) | 新增邀約人 |
| getGuestsByInviter(name) | 查詢指定邀約人的受邀人 |

---

### Web App 端點

doGet(e) 根據 action 參數：

| action | 說明 |
|--------|------|
| getEventInfo | 回傳活動資訊 |
| getInviterList | 回傳邀約人清單 |
| queryByInviter | 查詢邀約人最新報名資料 |

queryByInviter_(inviterName) 回傳：
  found, name, district, attend, meal, guests[], notes, dish
  固定讀取：notes=row[20]，dish=row[56]

doPost(e) 建構 row 陣列寫入試算表：
  [timestamp, name, district, attend, meal]
  + 受邀人欄位（每人5欄）
  + while(row.length<20) push('') 補空
  + splice(20, 0, notes) 備註固定第21欄
  + while(row.length<56) push('') 補空
  + push(dish) 帶菜固定第57欄

---

## 前端 index.html 說明

URL: https://inoculatolrin.github.io/gospel-signup/
架構：單頁 HTML，CSS + JS 全部內嵌

主要 JS 函數：
- ensureGuestCount(n)：確保 DOM 有 n 個受邀人區塊
- loadFormFromData(data)：查詢結果帶入表單
- submitForm()：收集資料並 POST 送出
- queryInviter()：查詢並顯示結果

後端 URL 變數：
- FRIEND_URL：現行部署端點（v10）
- SCRIPT_URL：舊版（已停用）

---

## 部署資訊

| 版本 | 時間 | 說明 |
|-----|------|------|
| v1-v8 | 2026/6/6 | 初期版本 |
| v9 | 2026/6/17 22:37 | 修正帶菜讀寫位置 |
| v10 | 2026/6/17 23:34 | 修正備註固定在第21欄 |

現行 FRIEND_URL（v10）：
AKfycbyy3pI74Dmyqe5uC1_RAvR1hKCj9gWZIHwzmr9fbt9Rsp4lx0tdYjBIQLQnXwvfVbst4Q
（每次建立新版本部署後 URL 不變）

---

## 修復紀錄

| 問題 | 原因 | 修復版本 |
|------|------|---------|
| 查詢時帶菜為空 | queryByInviter_ 動態計算位置，多受邀人時讀錯欄 | v9 |
| 送出時帶菜未到BE欄 | doPost 未補齊空欄就 push dish | v9 |
| 備註位置浮動 | doPost 直接 push notes，3人以上時偏移 | v10 |
| 立即更新只更統計頁 | updateAllStats 只呼叫 updateStats | 新增4個函數 |

注意事項：
- 汪莉瓊未計出席：D欄（邀約人出席）為空，需手動補填。
- v10 前舊資料：若邀約人有4位以上受邀人，row[20] 可能非備註欄，新資料不受影響。

---

## 快速進入狀況

重要連結：
- 報名網頁：https://inoculatolrin.github.io/gospel-signup/
- GitHub：https://github.com/inoculatolrin/gospel-signup
- 試算表：https://docs.google.com/spreadsheets/d/1A051I0_OFMSqX1nS3gbzzW0tUEV_lmKFKNsiMsVy5qI/edit
- Apps Script：https://script.google.com/u/0/home/projects/1Y16QhZDOxmHDBhnhjA8qApJFfVdVkuP8eHN-f0OM7VTasH9gLLKqcuUW/edit

常見任務：

修改 Apps Script 並部署：
1. 開啟 Apps Script 連結
2. 修改程式碼 → Ctrl+S 儲存
3. 右上角「部署」→「管理部署作業」→ 鉛筆 → 版本選「建立新版本」→「部署」

更新統計：
- 試算表「統計」分頁 → 點擊「立即更新」

測試 API（URL前綴為 FRIEND_URL/exec）：
- 查詢邀約人：?action=queryByInviter&inviter=林昭汶
- 活動資訊：?action=getEventInfo

---

文件由 Claude AI 整理，2026/6/17
