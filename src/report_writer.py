import json
from datetime import datetime
from pathlib import Path

from src.searcher import SearchResult
from src.scraper_104 import Company104Data


class ReportWriter:
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)

    def save(
        self,
        company: str,
        position: str,
        search_results: dict[str, list[SearchResult]],
        resume_path: str,
        data_104: Company104Data | None = None,
    ) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M")
        folder_name = f"{company}_{position}_{timestamp}"
        out_dir = self.output_dir / folder_name
        out_dir.mkdir(parents=True, exist_ok=True)

        # 原始搜尋結果（debug 用）
        raw_data = {
            topic: [
                {"title": r.title, "url": r.url, "content": r.content, "score": r.score}
                for r in results
            ]
            for topic, results in search_results.items()
        }
        (out_dir / "raw_search.json").write_text(
            json.dumps(raw_data, ensure_ascii=False, indent=2), encoding="utf-8"
        )

        # ── research_data.md ────────────────────────────────────────────
        total = sum(len(v) for v in search_results.values())
        lines = [
            "# 求職研究資料",
            "",
            f"- **公司**：{company}",
            f"- **職位**：{position}",
            f"- **產生時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"- **Tavily 搜尋筆數**：{total} 筆（{', '.join(f'{t}:{len(v)}' for t, v in search_results.items())}）",
        ]

        if data_104:
            lines.append(f"- **104 職缺筆數**：{len(data_104.jobs)} 筆")
            if data_104.website:
                lines.append(f"- **官方網站**：{data_104.website}")

        lines += [
            f"- **履歷路徑**：{resume_path}",
            "",
            "---",
        ]

        # ── 104 公司資料區塊（放在最前面，屬於第一手資料）──────────────
        if data_104:
            lines += [
                "",
                "## 104 公司資料",
                "",
                f"**公司名稱**：{data_104.name}",
                f"**產業**：{data_104.industry}",
                f"**員工人數**：{data_104.employee_count}",
            ]
            if data_104.website:
                lines.append(f"**官方網站**：{data_104.website}")
            if data_104.description:
                lines += ["", "### 公司介紹", "", data_104.description]

            lines += ["", "---", "", "## 104 職缺列表", ""]

            for i, job in enumerate(data_104.jobs, 1):
                meta = " | ".join(filter(None, [job.salary, job.experience, job.education]))
                lines += [
                    f"### {i}. {job.title}",
                    f"URL：{job.url}",
                ]
                if meta:
                    lines.append(f"條件：{meta}")
                if job.description:
                    lines += ["", job.description]
                lines += ["", "---", ""]

        # ── Tavily 搜尋結果 ─────────────────────────────────────────────
        lines += ["", "## Tavily 搜尋結果", ""]

        for topic, results in search_results.items():
            lines += [f"", f"### {topic}面向", ""]
            for i, r in enumerate(results, 1):
                lines += [
                    f"**{i}. {r.title}**",
                    f"URL：{r.url}",
                    f"相關度：{r.score:.3f}",
                    "",
                    r.content,
                    "",
                    "---",
                    "",
                ]

        data_path = out_dir / "research_data.md"
        data_path.write_text("\n".join(lines), encoding="utf-8")

        return data_path
