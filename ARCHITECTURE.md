# Job Research Tool — 專案架構文件

> 輸入公司名稱 + 目標職位，自動蒐集職缺/新聞/評價/技術資料，
> 結合個人履歷，由 AI 產出求職準備報告。

---

## 專案目錄結構

```
job-research-tool/
│
├── ARCHITECTURE.md          # 本文件
├── README.md
├── pyproject.toml           # 依賴管理（uv）
├── .env                     # API Keys（不納入 git）
├── .env.example
├── .gitignore
│
├── resume/                  # 放置個人履歷
│   └── resume.md            # 主要履歷（Markdown 格式，AI 易讀）
│   └── resume.pdf           # 備用（選擇性）
│
├── skills/                  # AI Prompt 範本（Skill 系統）
│   └── job_research.md      # 主要分析 Skill
│
├── src/
│   ├── main.py              # CLI 入口點
│   ├── researcher.py        # 搜尋主流程協調器
│   ├── searcher.py          # Tavily API 封裝
│   ├── analyzer.py          # Claude API 分析器
│   ├── resume_loader.py     # 履歷讀取與解析
│   └── report_writer.py     # Markdown 報告輸出
│
└── reports/                 # 輸出報告目錄（自動建立）
    └── {公司}_{職位}_{日期}/
        ├── raw_search.json      # 原始搜尋結果（debug 用）
        └── report.md            # 最終分析報告
```

---

## 核心流程

```
CLI 輸入
  ├─ --company   "台積電"
  ├─ --position  "AI 工程師"
  └─ --resume    "./resume/resume.md"（預設值）
         │
         ▼
   researcher.py（協調器）
         │
         ├─ searcher.py（4 個面向並行搜尋）
         │     ├─ 搜尋 1：{公司} {職位} 職缺 job opening
         │     ├─ 搜尋 2：{公司} 近期新聞 2024 2025
         │     ├─ 搜尋 3：{公司} 員工評價 公司文化 Glassdoor
         │     └─ 搜尋 4：{公司} {職位} 技術棧 tech stack skills
         │           │
         │           └─ 各取前 10 筆結果，彙整去重
         │
         ├─ resume_loader.py
         │     └─ 讀取 resume.md，萃取關鍵資訊
         │
         ▼
   analyzer.py
         ├─ 載入 skills/job_research.md（Skill Prompt）
         ├─ 組合：搜尋結果 + 履歷內容 + Skill
         └─ 呼叫 Claude API → 分析報告文字
         │
         ▼
   report_writer.py
         └─ 輸出 reports/{公司}_{職位}_{日期}/report.md
```

---

## 模組設計規格

### `src/searcher.py` — Tavily 搜尋封裝

```python
# 介面設計
class JobResearcher:
    def search_all(self, company: str, position: str) -> dict[str, list[SearchResult]]
    def _search_one(self, query: str, topic: str) -> list[SearchResult]

# SearchResult 資料結構
@dataclass
class SearchResult:
    topic: str        # "職缺" | "新聞" | "評價" | "技術"
    query: str        # 實際搜尋關鍵字
    title: str
    url: str
    content: str      # Tavily 回傳的摘要內容
    score: float      # 相關度分數
```

**搜尋關鍵字策略：**

| 面向 | 關鍵字範本 |
|------|-----------|
| 職缺 | `{公司} {職位} 職缺 徵才 job opening` |
| 新聞 | `{公司} 新聞 2024 2025 最新消息` |
| 評價 | `{公司} 員工評價 公司文化 面試心得 glassdoor 104` |
| 技術 | `{公司} {職位} 技術棧 技能要求 tech stack requirements` |

---

### `src/resume_loader.py` — 履歷讀取

```python
class ResumeLoader:
    def load(self, path: str) -> ResumeData
    def _extract_key_info(self, content: str) -> ResumeData

@dataclass
class ResumeData:
    raw: str              # 完整原文（傳入 prompt）
    summary: str          # 簡短摘要（由 AI 萃取，選擇性）
```

**履歷格式建議（resume.md）：**
- 使用 Markdown 標題分區（## 工作經驗、## 技能、## 學歷）
- AI 可直接讀取，無需額外解析

---

### `src/analyzer.py` — Claude 分析器

```python
class JobAnalyzer:
    def analyze(
        self,
        company: str,
        position: str,
        search_results: dict[str, list[SearchResult]],
        resume: ResumeData,
        skill_prompt: str,
    ) -> str  # 回傳完整 Markdown 報告
```

**Prompt 組合順序：**
```
[System]: skill_prompt（roles/instructions）
[User]:
  ## 目標公司與職位
  公司：{company}，職位：{position}

  ## 搜尋結果
  ### 職缺面向
  {搜尋結果列表}
  ...（其他三個面向）

  ## 我的履歷
  {resume.raw}
```

---

### `skills/job_research.md` — Skill Prompt 範本

```markdown
---
name: job_research
version: 1.0
---

# 角色設定
你是一位資深求職顧問兼技術招募專家，擅長分析科技業職缺並提供
針對個人背景的客製化建議。

# 任務
根據提供的公司資訊、網路搜尋結果與求職者履歷，產出一份完整的
求職準備報告。

# 輸出格式（嚴格遵守）
請以繁體中文輸出，格式如下：

## 📋 公司概況
（2-3 段，描述公司現況、近期動態、產業地位）

## 💼 職缺分析
（整理蒐集到的相關職缺，歸納常見要求技能與資歷）

## 🔍 公司文化與評價
（整理員工評價，列出正負面反饋，評估工作環境）

## 🛠️ 技術棧需求
（列出此職位主要技術要求，標注求職者已具備/需補強項目）

## 🎯 契合度評估
（依據求職者履歷，評估與此職位的匹配程度，給出 1-10 分並說明）

## 📝 面試準備建議
（具體建議：預期問題方向、技術考點、需準備的 Portfolio 項目）

## ⚡ 優先行動清單
（3-5 項求職者在投遞前應完成的具體行動，按優先度排序）

# 注意事項
- 請基於實際提供的搜尋結果，不要捏造資訊
- 若某面向資料不足，請明確說明「資料有限」
- 契合度評估必須具體對應履歷中的經歷，而非泛泛而談
```

---

### `src/report_writer.py` — 報告輸出

```python
class ReportWriter:
    def save(
        self,
        company: str,
        position: str,
        report_content: str,
        raw_results: dict,   # 同時儲存原始搜尋結果供 debug
    ) -> Path  # 回傳輸出路徑
```

**輸出規則：**
- 目錄：`reports/{company}_{position}_{YYYYMMDD_HHMM}/`
- 報告標頭自動加入：產生時間、公司、職位、搜尋筆數統計

---

## CLI 介面設計

```bash
# 基本用法
uv run python src/main.py --company "台積電" --position "AI 工程師"

# 指定履歷路徑
uv run python src/main.py \
  --company "Google Taiwan" \
  --position "ML Engineer" \
  --resume "./resume/resume_en.md"

# 只搜尋不分析（debug 用）
uv run python src/main.py \
  --company "聯發科" \
  --position "軟體工程師" \
  --search-only

# 輸出選項
--output-dir  ./reports   # 預設
--verbose                 # 顯示搜尋過程 log
```

---

## 環境變數（.env）

```bash
# .env.example
TAVILY_API_KEY=tvly-xxxxxxxxxxxxxxxx
ANTHROPIC_API_KEY=sk-ant-xxxxxxxxxxxxxxxx

# 可選設定
TAVILY_MAX_RESULTS=10          # 每個面向最多幾筆，預設 10
CLAUDE_MODEL=claude-opus-4-5   # 預設模型
```

---

## 依賴套件（pyproject.toml）

```toml
[project]
name = "job-research-tool"
version = "0.1.0"
requires-python = ">=3.11"

dependencies = [
    "tavily-python>=0.3.0",
    "anthropic>=0.40.0",
    "python-dotenv>=1.0.0",
    "rich>=13.0.0",         # 終端美化輸出
    "typer>=0.12.0",        # CLI 框架
]
```

---

## 實作優先順序（給 Claude Code）

> 建議依此順序逐步實作，每步驟可獨立測試：

1. **環境設定**：`pyproject.toml` + `.env` + 目錄建立
2. **`searcher.py`**：Tavily 搜尋，先能跑通單一關鍵字
3. **`resume_loader.py`**：簡單讀取 Markdown 檔案
4. **`skills/job_research.md`**：撰寫 Skill Prompt（最重要，反覆調整）
5. **`analyzer.py`**：組合 prompt 呼叫 Claude API
6. **`report_writer.py`**：存檔邏輯
7. **`main.py`**：CLI 串接所有模組
8. **整合測試**：跑完整流程，依輸出品質調整 Skill Prompt

---

## 後續擴充方向（不在初版範圍）

- [ ] 批次模式：一次輸入多家公司，逐一產報告
- [ ] 104 / LinkedIn 直接爬蟲（Playwright），補充 Tavily 找不到的職缺
- [ ] 報告比對：同職位不同公司的橫向比較報告
- [ ] FastMCP 包裝：整個工具做成 MCP server，Claude Code 可直接呼叫
