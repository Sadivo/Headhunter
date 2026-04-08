# Headhunter — 求職研究工具

輸入公司名稱與目標職位，自動蒐集職缺、新聞、評價、技術資訊，
配合 Claude Code 產出個人化求職準備報告。

---

## 環境需求

- Python 3.11+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- [Tavily API Key](https://tavily.com/)（免費方案即可）
- Claude Code

---

## 初次設定

**1. 安裝依賴**

```powershell
cd C:\project\Headhunter
uv sync
```

**2. 設定 API Key**

複製範本並填入 Tavily API Key：

```powershell
copy .env.example .env
```

編輯 `.env`：

```
TAVILY_API_KEY=tvly-你的金鑰
```

**3. 準備履歷**

將履歷存為 `resume/resume.md`（Markdown 格式，建議用標題分區）：

```markdown
## 基本資料
## 工作經驗
## 技能
## 學歷
```

---

## 使用流程

### 第一步：蒐集資料

在任意目錄執行：

```powershell
uv run headhunter
```

依提示輸入：

```
目標公司: 台積電
目標職位: AI工程師
履歷路徑 (預設 resume/resume.md):   ← 直接 Enter 使用預設
```

完成後會顯示輸出路徑：

```
研究資料：reports\台積電_AI工程師_20260408_1054\research_data.md
```

### 第二步：分析報告

在 Claude Code 中執行 slash command：

```
/job_research reports\台積電_AI工程師_20260408_1054\research_data.md
```

Claude Code 會自動讀取搜尋資料與履歷，產出以下格式的報告：

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

## 搜尋策略

每次執行蒐集 5 個面向 × 各 5 筆 = **25 筆結果**，並擷取頁面全文：

| 面向 | 搜尋關鍵字 |
|------|-----------|
| 介紹 | `{公司} 公司介紹 主要業務 產品` |
| 職缺 | `{公司} {職位} 職缺 徵才 job` |
| 新聞 | `{公司} 新聞 最新消息` |
| 評價 | `{公司} 員工評價 公司文化 面試心得` |
| 技術 | `{公司} {職位} 技術棧 技能要求 tech stack` |

---

## 輸出檔案

每次執行在 `reports/` 產生一個資料夾：

```
reports/
└── 台積電_AI工程師_20260408_1054/
    ├── research_data.md   ← 傳給 Claude Code 分析用
    └── raw_search.json    ← 原始搜尋結果（debug 用）
```

---

## 目錄結構

```
Headhunter/
├── README.md
├── ARCHITECTURE.md
├── pyproject.toml
├── .env                  ← API Key（不納入 git）
├── .env.example
├── resume/
│   └── resume.md         ← 個人履歷
├── src/
│   ├── main.py           ← 程式入口
│   ├── searcher.py       ← Tavily 搜尋
│   ├── resume_loader.py  ← 履歷驗證
│   └── report_writer.py  ← 輸出格式
├── .claude/
│   └── commands/
│       └── job_research.md  ← Claude Code slash command
└── reports/              ← 輸出目錄（自動建立）
```
