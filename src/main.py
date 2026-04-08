from pathlib import Path
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn

from src.searcher import JobSearcher
from src.resume_loader import ResumeLoader  # 只用於驗證路徑存在
from src.report_writer import ReportWriter

console = Console()

DEFAULT_RESUME = Path(__file__).parent.parent / "resume" / "resume.md"
DEFAULT_OUTPUT = Path(__file__).parent.parent / "reports"


def main():
    console.rule("[bold cyan]Job Research Tool[/bold cyan]")

    company = Prompt.ask("[bold]目標公司[/bold]")
    position = Prompt.ask("[bold]目標職位[/bold]")
    resume_path = Prompt.ask("[bold]履歷路徑[/bold]", default=str(DEFAULT_RESUME))

    console.print()

    # 1. 搜尋
    searcher = JobSearcher()
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("並行搜尋五個面向（介紹/職缺/新聞/評價/技術）...", total=None)
        results = searcher.search_all(company, position)
        progress.update(task, completed=True)

    total = sum(len(v) for v in results.values())
    console.print(f"[green]✓[/green] 搜尋完成，共 {total} 筆（含全文）")
    for topic, items in results.items():
        console.print(f"   {topic}：{len(items)} 筆")

    # 2. 驗證履歷路徑存在
    loader = ResumeLoader()
    resume_data = loader.load(resume_path)
    console.print(f"[green]✓[/green] 履歷確認：{resume_data.path}")

    # 3. 輸出
    writer = ReportWriter(str(DEFAULT_OUTPUT))
    data_path = writer.save(company, position, results, resume_data.path)

    console.rule("[bold green]完成[/bold green]")
    console.print(f"[bold]研究資料：[/bold][cyan]{data_path}[/cyan]")
    console.print()
    console.print("[bold yellow]下一步：[/bold yellow]在 Claude Code 執行")
    console.print(f"  [bold cyan]/job_research[/bold cyan] [dim]{data_path}[/dim]")


if __name__ == "__main__":
    main()
