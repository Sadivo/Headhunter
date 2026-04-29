# Headhunter — 求職研究工具

四個互補的求職輔助工具，均配合 Claude Code 使用：

| 工具 | 用途 | 指令 |
|------|------|------|
| **headhunter** | 研究單一目標公司（職缺 + 新聞 + 評價） | `uv run headhunter` |
| **search-104** | 爬取 104 搜尋結果清單，AI 幫你篩選適合的職缺 | `uv run search104` |
| **search-1111** | 爬取 1111 搜尋結果清單，AI 幫你篩選適合的職缺 | `uv run search1111` |
| **vendor-search** | 依廠商清單批量爬取各公司職缺，AI 幫你篩選 | `uv run vendor-search` |

---

## 初次設定

**1. 安裝依賴與瀏覽器**

```bash
uv sync
uv run playwright install chromium
```

**2. 設定 API Key**

```bash
# 只有"工具一"會用到
copy .env.example .env
```

編輯 `.env`，填入 Tavily API Key：

```
TAVILY_API_KEY=tvly-你的金鑰
```

**3. 準備履歷**

將履歷存為 `resume/resume.md`（Markdown 格式，此檔案已加入 `.gitignore`，不會上傳至 git）。

可參考範本 `resume/resume.example.md` 自行填寫，或請 AI 協助建立：

> 在 Claude Code 中貼上以下提示：
> ```
> 請參考 resume/resume.example.md 的格式，
> 根據我提供的資料幫我建立 resume/resume.md。
>
> 我的背景：
> （在此描述你的學歷、工作經歷、技能等）
> ```

---

## 工具一：headhunter（研究目標公司）

適合已鎖定特定公司，想深入了解並準備面試時使用。

### 執行

```bash
uv run headhunter
```

輸入公司名稱與目標職位，工具會：
- 從 104 抓取公司介紹、官網、完整職缺列表
- 用 Tavily 蒐集公司新聞、員工評價、技術棧資訊
- 若 104 搜尋到多間同名公司，會列表讓你選擇

### 分析報告

```
/job_research reports\台積電_AI工程師_20260408_1054\research_data.md
```

| 章節 | 內容 |
|------|------|
| 📋 公司概況 | 現況、近期動態、產業地位 |
| 💼 職缺分析 | 常見要求技能與資歷 |
| 🔍 公司文化與評價 | 員工評價、正負面反饋 |
| 🛠️ 技術棧需求 | 技術要求、已具備 / 需補強項目 |
| 🎯 契合度評估 | 與履歷的匹配程度（1-10 分） |
| 📝 面試準備建議 | 預期問題、技術考點、Portfolio |
| ⚡ 優先行動清單 | 投遞前應完成的具體行動 |

---

## 工具二：search104（批量篩選職缺）

適合廣泛搜尋、想讓 AI 從大量職缺中找出最適合自己的機會時使用。

### 步驟 1：在 104 設定篩選條件

在 104 人力銀行設定好地區、職類、薪資、年資等條件後，複製網址備用。

### 步驟 2：執行爬蟲

```bash
uv run search104
```

貼上 104 搜尋網址，設定抓取上限（預設 80 筆），工具會：
- 依篩選條件抓取所有分頁的職缺
- 逐一取得完整 JD（工作內容）
- 輸出 `jobs.md` 供 Claude 分析

也可直接傳入網址（跳過互動提示）：

```bash
uv run search104 "https://www.104.com.tw/jobs/search/?keyword=後端工程師&area=..."
```

### 步驟 3：AI 篩選比對

```
/job_match reports\search_104_20260414_1530\jobs.md
```

Claude 會逐一閱讀每筆職缺的完整 JD，對照你的履歷評分（⭐～⭐⭐⭐⭐⭐），輸出：
- 推薦職缺排名（含推薦理由與注意事項）
- 可衝刺職缺觀察（例如碩士／博士 + 0 經驗，但核心技能命中的職缺）
- 不建議投遞的原因
- 履歷優化建議（根據這批 JD 的關鍵字）

---

## 工具三：search1111（1111 批量篩選職缺）

適合在 1111 人力銀行搜尋、想讓 AI 從大量職缺中找出最適合自己的機會時使用。

### 步驟 1：在 1111 設定篩選條件

在 1111 人力銀行設定好地區、職類、薪資、年資等條件後，複製網址備用。

### 步驟 2：執行爬蟲

```bash
uv run search1111
```

貼上 1111 搜尋網址，設定抓取上限（預設 80 筆），工具會：
- 逐頁解析 Nuxt SSR 渲染的搜尋結果
- 前往各職缺頁取得完整 JD（工作內容＋其他條件）
- 輸出 `jobs.md` 供 Claude 分析

也可直接傳入網址：

```bash
uv run search1111 "https://www.1111.com.tw/search/job?page=1&..."
```

**時間預估**：每頁載入約 3-5 秒，每筆 JD 約 1-2 秒。30 筆約 90 秒，80 筆約 3-4 分鐘。

### 步驟 3：AI 篩選比對

```
/job_match reports\search_1111_20260421_1519\jobs.md
```

---

## 工具四：vendor-search（廠商清單批量爬取）

適合手上有目標廠商名單，想一次爬取所有公司的職缺並讓 AI 篩選時使用。

### 步驟 1：準備廠商清單

建立 CSV 檔（UTF-8 編碼），`cust_no` 欄位可留空讓程式自動搜尋：

```csv
company_name,cust_no
台積電,
聯發科,5a0000
鴻海精密,
ASUS,
```

也支援純文字 TXT（每行一家公司名稱）。

支援的欄位名稱：`company_name`、`公司名稱`、`公司`、`廠商名稱`、`廠商`。

### 步驟 2：執行爬蟲

```bash
uv run vendor-search vendors.csv
```

或直接傳入路徑（跳過互動提示）：

```bash
uv run vendor-search tmp\exhibitors.csv
```

程式會依序詢問：
- 每家廠商最多抓幾筆職缺（預設 50，輸入 `0` = 全部）
- 履歷路徑（預設 `resume/resume.md`）

遇到名稱模糊的公司會暫停讓你手動從清單中選擇。搜尋失敗的公司會自動略過，不影響後續流程。

### 步驟 3：AI 篩選比對

```
/job_match reports\vendor_search_20260420_1430\jobs.md
```

---

## search104 vs search1111

| | search104 | search1111 |
|---|---|---|
| **資料來源** | 104 人力銀行 | 1111 人力銀行 |
| **技術方式** | 攔截 XHR API | 解析 Nuxt SSR payload |
| **分頁速度** | 快（直接 fetch API） | 較慢（每頁需重新渲染） |
| **JD 完整度** | 完整（獨立 API 端點） | 完整（逐一前往職缺頁） |
| **輸出格式** | 相同（供 /job_match 使用） | 相同（供 /job_match 使用） |

---

## 輸出目錄

```
reports/
├── 台積電_AI工程師_20260408_1054/     ← headhunter 輸出
│   ├── research_data.md               ← 傳給 /job_research 分析
│   └── raw_search.json                ← 原始資料（debug 用）
│
├── search_104_20260414_1530/          ← search-104 輸出
│   ├── jobs.md                        ← 傳給 /job_match 分析
│   └── jobs.json                      ← 原始資料（debug 用）
│
├── search_1111_20260421_1519/         ← search-1111 輸出
│   ├── jobs.md                        ← 傳給 /job_match 分析
│   └── jobs.json                      ← 原始資料（debug 用）
│
└── vendor_search_20260420_1430/       ← vendor-search 輸出
    ├── jobs.md                        ← 傳給 /job_match 分析
    └── vendors_result.json            ← 原始資料（debug 用）
```

---

## 目錄結構

```
Headhunter/
├── README.md
├── pyproject.toml
├── .env                        ← API Key（不納入 git）
├── .env.example
├── resume/
│   └── resume.md               ← 個人履歷
├── src/
│   ├── main.py                 ← headhunter 入口
│   ├── search_104.py           ← search-104 入口
│   ├── search_1111.py          ← search-1111 入口
│   ├── vendor_search.py        ← vendor-search 入口
│   ├── scraper_104.py          ← 104 公司爬蟲（Playwright）
│   ├── searcher.py             ← Tavily 網路搜尋
│   ├── resume_loader.py        ← 履歷驗證
│   └── report_writer.py        ← 輸出格式
├── .claude/
│   └── commands/
│       ├── job_research.md     ← /job_research slash command
│       └── job_match.md        ← /job_match slash command
└── reports/                    ← 輸出目錄（自動建立）
```

---

## 環境需求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Tavily API Key](https://tavily.com/)（免費方案即可）
- Claude Code
