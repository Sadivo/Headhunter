import json
from datetime import datetime
from pathlib import Path

from src.searcher import SearchResult


class ReportWriter:
    def __init__(self, output_dir: str = "./reports"):
        self.output_dir = Path(output_dir)

    def save(
        self,
        company: str,
        position: str,
        search_results: dict[str, list[SearchResult]],
        resume_path: str,
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

        # 組合給 Claude Code 分析的 research_data.md（純資料，不含 prompt）
        total = sum(len(v) for v in search_results.values())
        lines = [
            f"# 求職研究資料",
            f"",
            f"- **公司**：{company}",
            f"- **職位**：{position}",
            f"- **產生時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"- **搜尋筆數**：{total} 筆（{', '.join(f'{t}:{len(v)}' for t, v in search_results.items())}）",
            f"- **履歷路徑**：{resume_path}",
            f"",
            f"---",
            f"",
            f"## 搜尋結果",
        ]

        for topic, results in search_results.items():
            lines += [f"", f"### {topic}面向", ""]
            for i, r in enumerate(results, 1):
                lines += [
                    f"**{i}. {r.title}**",
                    f"URL：{r.url}",
                    f"相關度：{r.score:.3f}",
                    f"",
                    r.content,
                    f"",
                    "---",
                    "",
                ]


        data_path = out_dir / "research_data.md"
        data_path.write_text("\n".join(lines), encoding="utf-8")

        return data_path
