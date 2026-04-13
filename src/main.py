from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from rich.console import Console
from rich.prompt import Prompt, IntPrompt
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from src.searcher import JobSearcher
from src.scraper_104 import Scraper104, Company104Data
from src.resume_loader import ResumeLoader
from src.report_writer import ReportWriter

console = Console()

DEFAULT_RESUME = Path(__file__).parent.parent / "resume" / "resume.md"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "reports"


def pick_company(scraper: Scraper104, company_keyword: str) -> str | None:
    """搜尋 104 公司候選名單，若有多間請使用者選擇，回傳 cust_no。"""
    candidates = scraper.search_companies(company_keyword)
    if not candidates:
        console.print("[yellow]⚠[/yellow]  104 找不到符合的公司，將略過 104 資料")
        return None

    if len(candidates) == 1:
        c = candidates[0]
        console.print(f"[green]✓[/green] 104 找到公司：[bold]{c.name}[/bold]（{c.industry}）")
        return c.cust_no

    # 多間公司 → 顯示清單讓使用者選
    console.print(f"\n[bold yellow]104 找到 {len(candidates)} 間符合的公司，請選擇：[/bold yellow]")
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("#", width=3)
    table.add_column("公司名稱")
    table.add_column("產業")
    table.add_column("員工人數")
    for i, c in enumerate(candidates, 1):
        table.add_row(str(i), c.name, c.industry, c.employee_count)
    console.print(table)

    choice = IntPrompt.ask(
        "請輸入編號（0 = 略過 104 資料）",
        default=1,
    )
    if choice == 0 or choice > len(candidates):
        return None
    return candidates[choice - 1].cust_no


def main():
    console.rule("[bold cyan]Job Research Tool[/bold cyan]")

    company = Prompt.ask("[bold]目標公司[/bold]")
    position = Prompt.ask("[bold]目標職位[/bold]")
    resume_path = Prompt.ask("[bold]履歷路徑[/bold]", default=str(DEFAULT_RESUME))

    console.print()

    # ── 步驟 1：確認 104 公司（互動式，需在並行前完成）──────────────
    scraper = Scraper104()
    cust_no = pick_company(scraper, company)

    # ── 步驟 2：並行執行 Tavily 搜尋 + 104 職缺爬取 ──────────────
    searcher = JobSearcher()

    with Progress(
        SpinnerColumn(), TextColumn("{task.description}"), console=console
    ) as progress:
        t_tavily = progress.add_task("Tavily 搜尋（介紹/新聞/評價/技術）...", total=None)
        t_104 = progress.add_task(
            f"104 抓取職缺（上限 {scraper.max_jobs} 筆）..." if cust_no else "104 略過",
            total=None,
        )

        with ThreadPoolExecutor(max_workers=2) as executor:
            f_tavily = executor.submit(searcher.search_all, company, position)
            f_104 = executor.submit(scraper.fetch_all, cust_no) if cust_no else None

            search_results = f_tavily.result()
            progress.update(t_tavily, completed=True)

            data_104: Company104Data | None = f_104.result() if f_104 else None
            progress.update(t_104, completed=True)

    # ── 摘要輸出 ──────────────────────────────────────────────────────
    total = sum(len(v) for v in search_results.values())
    console.print(f"[green]✓[/green] Tavily 搜尋完成，共 {total} 筆")
    for topic, items in search_results.items():
        console.print(f"   {topic}：{len(items)} 筆")

    if data_104:
        console.print(
            f"[green]✓[/green] 104 完成：[bold]{data_104.name}[/bold]，"
            f"職缺 {len(data_104.jobs)} 筆"
            + (f"，官網 {data_104.website}" if data_104.website else "")
        )

    # ── 步驟 3：驗證履歷 ──────────────────────────────────────────────
    loader = ResumeLoader()
    resume_data = loader.load(resume_path)
    console.print(f"[green]✓[/green] 履歷確認：{resume_data.path}")

    # ── 步驟 4：輸出報告 ──────────────────────────────────────────────
    writer = ReportWriter(str(DEFAULT_OUTPUT))
    data_path = writer.save(company, position, search_results, resume_data.path, data_104)

    console.rule("[bold green]完成[/bold green]")
    console.print(f"[bold]研究資料：[/bold][cyan]{data_path}[/cyan]")
    console.print()
    console.print("[bold yellow]下一步：[/bold yellow]在 Claude Code 執行")
    console.print(f"  [bold cyan]/job_research[/bold cyan] [dim]{data_path}[/dim]")


if __name__ == "__main__":
    main()
