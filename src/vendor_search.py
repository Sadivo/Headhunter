"""
廠商清單職缺爬蟲
用法：
    uv run python -m src.vendor_search vendors.csv
    uv run python -m src.vendor_search vendors.csv --max-jobs 50

輸入：CSV 廠商清單（company_name, cust_no 可選）或純文字 TXT（每行一家）
輸出：reports/vendor_search_{timestamp}/jobs.md（供 Claude /job_match 分析）
"""

import csv
import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import IntPrompt, Prompt
from rich.table import Table

from src.scraper_104 import CompanyCandidate, JobDetail, Scraper104

DEFAULT_OUTPUT = Path(__file__).parent.parent / "reports"
DEFAULT_MAX_JOBS = 50
DEFAULT_RESUME = Path(__file__).parent.parent / "resume" / "resume.md"

console = Console()


@dataclass
class VendorEntry:
    name: str
    cust_no: str | None  # None = 需要搜尋


@dataclass
class VendorResult:
    company_name: str
    company_id: str
    industry: str
    employee_count: str
    jobs: list[JobDetail]


def load_vendors(csv_path: str) -> list[VendorEntry]:
    """讀取廠商清單 CSV（company_name, cust_no 可選）或純文字 TXT。"""
    path = Path(csv_path)
    if not path.exists():
        console.print(f"[red]錯誤：找不到廠商清單檔案 {csv_path}[/red]")
        sys.exit(1)

    text = path.read_text(encoding="utf-8")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    if not lines:
        console.print("[red]錯誤：廠商清單為空[/red]")
        sys.exit(1)

    vendors: list[VendorEntry] = []

    if "," in lines[0]:
        reader = csv.DictReader(text.splitlines())
        fields = list(reader.fieldnames or [])
        name_candidates = {"company_name", "公司名稱", "公司", "廠商名稱", "廠商"}
        name_col = next((f for f in fields if f in name_candidates), None) or fields[0]
        cust_col = next((f for f in fields if f in {"cust_no", "編號", "custNo"}), None)

        for row in reader:
            name = row.get(name_col, "").strip()
            cust_no = row.get(cust_col, "").strip() if cust_col else ""
            if name:
                vendors.append(VendorEntry(name=name, cust_no=cust_no or None))
    else:
        for line in lines:
            vendors.append(VendorEntry(name=line, cust_no=None))

    return vendors


def resolve_company(scraper: Scraper104, entry: VendorEntry) -> CompanyCandidate | None:
    """解析廠商的 104 cust_no，需要時互動選擇。"""
    if entry.cust_no:
        console.print(f"[green]✓[/green] [{entry.name}] 使用指定 cust_no：{entry.cust_no}")
        return CompanyCandidate(
            cust_no=entry.cust_no,
            name=entry.name,
            industry="",
            employee_count="",
        )

    candidates = scraper.search_companies(entry.name)

    if not candidates:
        console.print(f"[yellow]⚠[/yellow]  [{entry.name}] 104 找不到符合的公司，略過")
        return None

    if len(candidates) == 1:
        c = candidates[0]
        console.print(f"[green]✓[/green] [{entry.name}] 找到：[bold]{c.name}[/bold]（{c.industry}）")
        return c

    # 多個結果 → 互動選擇
    console.print(f"\n[bold yellow]「{entry.name}」找到 {len(candidates)} 間符合公司，請選擇：[/bold yellow]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", width=3)
    table.add_column("公司名稱")
    table.add_column("產業")
    table.add_column("員工人數")
    for i, c in enumerate(candidates, 1):
        table.add_row(str(i), c.name, c.industry, c.employee_count)
    table.add_row("0", "[dim]略過此廠商[/dim]", "", "")
    console.print(table)

    choice = IntPrompt.ask("請輸入編號", default=1)
    if choice == 0 or choice > len(candidates):
        console.print(f"[dim]略過 {entry.name}[/dim]")
        return None
    return candidates[choice - 1]


def save_report(
    results: list[VendorResult],
    vendor_file: str,
    resume_path: str,
    output_dir: Path = DEFAULT_OUTPUT,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = output_dir / f"vendor_search_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    total_jobs = sum(len(r.jobs) for r in results)

    json_data = [
        {
            "company_name": r.company_name,
            "company_id": r.company_id,
            "industry": r.industry,
            "employee_count": r.employee_count,
            "jobs": [j.__dict__ for j in r.jobs],
        }
        for r in results
    ]
    (out_dir / "vendors_result.json").write_text(
        json.dumps(json_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    lines = [
        "# 廠商職缺整合清單",
        "",
        f"- **廠商清單**：{vendor_file}",
        f"- **廠商數量**：{len(results)} 家",
        f"- **職缺總數**：{total_jobs} 筆",
        f"- **產生時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **履歷路徑**：{resume_path}",
        "",
        "---",
        "",
    ]

    job_index = 1
    for result in results:
        for job in result.jobs:
            meta_parts = [p for p in [job.salary, job.experience, job.education] if p]
            lines += [
                f"## {job_index}. [{result.company_name}] {job.title}",
                f"**公司**：{result.company_name}　**產業**：{result.industry}",
                f"**條件**：{' | '.join(meta_parts)}",
                f"**網址**：{job.url}",
                "",
            ]
            if job.description:
                lines += [job.description, ""]
            lines += ["---", ""]
            job_index += 1

    md_path = out_dir / "jobs.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


def main():
    console.rule("[bold cyan]廠商職缺爬蟲[/bold cyan]")

    if len(sys.argv) > 1:
        vendor_file = sys.argv[1]
    else:
        vendor_file = Prompt.ask("[bold]廠商清單 CSV 路徑[/bold]")

    max_jobs = IntPrompt.ask("[bold]每家廠商最多抓取幾筆職缺（0 = 全部）[/bold]", default=DEFAULT_MAX_JOBS)
    if max_jobs <= 0:
        max_jobs = 9999
    resume_path = Prompt.ask("[bold]履歷路徑[/bold]", default=str(DEFAULT_RESUME))

    console.print()

    vendors = load_vendors(vendor_file)
    console.print(f"[green]✓[/green] 讀取廠商清單：共 {len(vendors)} 家")
    console.print()

    scraper = Scraper104(max_jobs=max_jobs)
    results: list[VendorResult] = []

    for i, entry in enumerate(vendors, 1):
        console.rule(f"[dim]廠商 {i}/{len(vendors)}：{entry.name}[/dim]")

        candidate = resolve_company(scraper, entry)
        if not candidate:
            continue

        with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
            task = progress.add_task(
                f"抓取 {candidate.name} 職缺（上限 {max_jobs} 筆）...", total=None
            )
            data = scraper.fetch_all(candidate.cust_no)
            progress.update(task, completed=True)

        console.print(f"[green]✓[/green] {data.name}：取得 {len(data.jobs)} 筆職缺")
        results.append(VendorResult(
            company_name=data.name or candidate.name,
            company_id=candidate.cust_no,
            industry=data.industry or candidate.industry,
            employee_count=data.employee_count or candidate.employee_count,
            jobs=data.jobs,
        ))

    if not results:
        console.print("[red]沒有成功抓取任何廠商職缺，結束。[/red]")
        return

    total = sum(len(r.jobs) for r in results)
    console.rule("[bold green]完成[/bold green]")
    console.print(f"[green]✓[/green] 共 {len(results)} 家廠商，{total} 筆職缺")

    md_path = save_report(results, vendor_file, resume_path)

    console.print(f"[bold]輸出檔案：[/bold][cyan]{md_path}[/cyan]")
    console.print()
    console.print("[bold yellow]下一步：[/bold yellow]在 Claude Code 執行")
    console.print(f"  [bold cyan]/job_match[/bold cyan] [dim]{md_path}[/dim]")


if __name__ == "__main__":
    main()
