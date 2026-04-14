"""
104人力銀行搜尋結果爬蟲
用法：
    uv run python -m src.search_104
    uv run python -m src.search_104 "https://www.104.com.tw/jobs/search/?keyword=python&..."

輸入：104 搜尋頁網址（含篩選條件）
輸出：reports/search_104_{timestamp}/jobs.md（完整 JD，供 Claude /job_match 分析）
"""

import json
import time
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from playwright.sync_api import sync_playwright

DEFAULT_OUTPUT = Path(__file__).parent.parent / "reports"
DEFAULT_MAX_JOBS = 80
JD_BATCH_SIZE = 5       # 每批同時 fetch 幾個 JD
JD_BATCH_DELAY = 0.5    # 批次間隔（秒）


@dataclass
class SearchJob:
    job_id: str         # encodedJobNo（如 7cnr4）
    title: str
    company: str
    company_id: str     # encodedCustNo
    location: str
    salary: str
    experience: str
    education: str
    industry: str
    url: str
    appear_date: str
    description: str    # 完整 JD（從 job/ajax/content 抓取）


class JobSearchScraper:
    def __init__(self, max_jobs: int = DEFAULT_MAX_JOBS):
        self.max_jobs = max_jobs

    # ──────────────────────────────────────────────
    # 主流程
    # ──────────────────────────────────────────────
    def scrape(self, search_url: str) -> list[SearchJob]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 步驟 1：載入第一頁，取得職缺列表 + 分頁資訊
            print(f"  載入搜尋頁...")
            with page.expect_response(
                lambda r: "jobs/search/api/jobs" in r.url,
                timeout=20000,
            ) as resp_info:
                page.goto(search_url, wait_until="domcontentloaded")

            first_data = resp_info.value.json()
            pagination = first_data.get("metadata", {}).get("pagination", {})
            total = pagination.get("total", 0)
            last_page = pagination.get("lastPage", 1)

            print(f"  找到 {total} 筆職缺，共 {last_page} 頁，抓取前 {self.max_jobs} 筆")

            # 收集所有頁面的摘要資料
            all_items: list[dict] = list(first_data.get("data", []))
            api_base = self._build_api_base(search_url)

            # 步驟 2：用瀏覽器內 fetch 抓剩餘頁面
            pages_needed = min(last_page, -(-self.max_jobs // 20))  # ceil division
            for page_num in range(2, pages_needed + 1):
                if len(all_items) >= self.max_jobs:
                    break
                url = f"{api_base}&page={page_num}&pagesize=20"
                print(f"  抓取第 {page_num}/{pages_needed} 頁...")
                result = page.evaluate(f"""async () => {{
                    const r = await fetch('{url}');
                    return r.json();
                }}""")
                all_items.extend(result.get("data", []))
                time.sleep(0.3)

            all_items = all_items[: self.max_jobs]

            # 步驟 3：逐批抓完整 JD
            print(f"  抓取 {len(all_items)} 筆完整 JD（{JD_BATCH_SIZE} 個/批）...")
            jobs = self._build_jobs(all_items)
            jobs = self._fetch_jd_batch(page, jobs)

            browser.close()
        return jobs

    # ──────────────────────────────────────────────
    # 從原始搜尋 URL 直接組出 API base URL（保留所有篩選條件）
    # ──────────────────────────────────────────────
    def _build_api_base(self, search_url: str) -> str:
        parsed = urlparse(search_url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        # 移除前端專用參數；page/pagesize 由呼叫端自行附加
        drop = {"page", "pagesize", "isJobList", "jobsource"}
        kept = {k: v[0] for k, v in params.items() if k not in drop}
        kept["searchJobs"] = "1"   # API 需要此參數
        return "https://www.104.com.tw/jobs/search/api/jobs?" + urlencode(kept)

    # ──────────────────────────────────────────────
    # 從摘要列表建立 SearchJob（JD 暫空）
    # ──────────────────────────────────────────────
    def _build_jobs(self, items: list[dict]) -> list[SearchJob]:
        jobs = []
        for item in items:
            job_url = item.get("link", {}).get("job", "")
            job_id = job_url.rstrip("/").split("/")[-1] if job_url else ""
            cust_url = item.get("link", {}).get("cust", "")
            cust_id = cust_url.rstrip("/").split("/")[-1] if cust_url else ""

            # 薪資
            s_low = item.get("salaryLow", 0)
            s_high = item.get("salaryHigh", 0)
            if s_low and s_high:
                salary = f"{s_low:,}～{s_high:,}"
            elif s_low:
                salary = f"{s_low:,} 以上"
            else:
                salary = "待遇面議"

            jobs.append(SearchJob(
                job_id=job_id,
                title=item.get("jobName", ""),
                company=item.get("custName", ""),
                company_id=cust_id,
                location=item.get("jobAddrNoDesc", ""),
                salary=salary,
                experience=str(item.get("period", "")),
                education=self._edu_label(item.get("optionEdu", [])),
                industry=item.get("coIndustryDesc", ""),
                url=job_url,
                appear_date=str(item.get("appearDate", "")),
                description="",
            ))
        return jobs

    def _edu_label(self, codes: list) -> str:
        mapping = {1: "高中以下", 2: "高中", 3: "專科", 4: "大學", 5: "碩士", 6: "博士"}
        labels = [mapping.get(c, "") for c in codes if c in mapping]
        return "／".join(labels) if labels else ""

    # ──────────────────────────────────────────────
    # 批次 fetch 完整 JD（在瀏覽器內執行，Cloudflare 已通過）
    # ──────────────────────────────────────────────
    def _fetch_jd_batch(self, page, jobs: list[SearchJob]) -> list[SearchJob]:
        for i in range(0, len(jobs), JD_BATCH_SIZE):
            batch = jobs[i: i + JD_BATCH_SIZE]
            js_calls = ", ".join([
                f"""fetch('https://www.104.com.tw/job/ajax/content/{j.job_id}', {{
                    headers: {{ 'Referer': 'https://www.104.com.tw/job/{j.job_id}' }}
                }}).then(r => r.json()).catch(() => ({{}}))"""
                for j in batch
            ])
            results = page.evaluate(f"async () => Promise.all([{js_calls}])")
            for job, result in zip(batch, results):
                detail = result.get("data", {}).get("jobDetail", {})
                job.description = detail.get("jobDescription", job.description)
            print(f"  JD 完成 {min(i + JD_BATCH_SIZE, len(jobs))}/{len(jobs)}")
            time.sleep(JD_BATCH_DELAY)
        return jobs


# ──────────────────────────────────────────────────
# 輸出報告
# ──────────────────────────────────────────────────
def save_report(
    jobs: list[SearchJob],
    search_url: str,
    resume_path: str,
    output_dir: Path = DEFAULT_OUTPUT,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M")
    out_dir = output_dir / f"search_104_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 也存一份 JSON 方便 debug
    (out_dir / "jobs.json").write_text(
        json.dumps([j.__dict__ for j in jobs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 104 職缺搜尋結果",
        "",
        f"- **搜尋網址**：{search_url}",
        f"- **產生時間**：{datetime.now().strftime('%Y-%m-%d %H:%M')}",
        f"- **職缺數量**：{len(jobs)} 筆",
        f"- **履歷路徑**：{resume_path}",
        "",
        "---",
        "",
    ]

    for i, job in enumerate(jobs, 1):
        meta_parts = [p for p in [job.salary, job.experience, job.education, job.location] if p]
        lines += [
            f"## {i}. {job.title}",
            f"**公司**：{job.company}　**產業**：{job.industry}",
            f"**條件**：{' | '.join(meta_parts)}",
            f"**網址**：{job.url}",
            "",
        ]
        if job.description:
            lines += [job.description, ""]
        lines += ["---", ""]

    md_path = out_dir / "jobs.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return md_path


# ──────────────────────────────────────────────────
# CLI 入口
# ──────────────────────────────────────────────────
def main():
    from rich.console import Console
    from rich.prompt import Prompt, IntPrompt

    console = Console()
    console.rule("[bold cyan]104 職缺搜尋爬蟲[/bold cyan]")

    if len(sys.argv) > 1:
        search_url = sys.argv[1]
    else:
        search_url = Prompt.ask("[bold]請貼上 104 搜尋頁網址[/bold]")

    max_jobs = IntPrompt.ask("[bold]最多抓取幾筆[/bold]", default=DEFAULT_MAX_JOBS)

    default_resume = Path(__file__).parent.parent / "resume" / "resume.md"
    resume_path = Prompt.ask("[bold]履歷路徑[/bold]", default=str(default_resume))

    console.print()
    scraper = JobSearchScraper(max_jobs=max_jobs)

    from rich.progress import Progress, SpinnerColumn, TextColumn
    with Progress(SpinnerColumn(), TextColumn("{task.description}"), console=console) as progress:
        task = progress.add_task("爬取職缺中...", total=None)
        jobs = scraper.scrape(search_url)
        progress.update(task, completed=True)

    md_path = save_report(jobs, search_url, resume_path)

    console.print(f"[green]✓[/green] 完成，共 {len(jobs)} 筆")
    console.print(f"[bold]輸出檔案：[/bold][cyan]{md_path}[/cyan]")
    console.print()
    console.print("[bold yellow]下一步：[/bold yellow]在 Claude Code 執行")
    console.print(f"  [bold cyan]/job_match[/bold cyan] [dim]{md_path}[/dim]")


if __name__ == "__main__":
    main()
