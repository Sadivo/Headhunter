"""
1111人力銀行搜尋結果爬蟲
用法：
    uv run search1111
    uv run search1111 "https://www.1111.com.tw/search/job?..."

輸入：1111 搜尋頁網址（含篩選條件）
輸出：reports/search_1111_{timestamp}/jobs.md（供 Claude /job_match 分析）

實作說明：
    1111 使用 Nuxt 3 SSR，職缺資料嵌於 HTML 的 <script id="__NUXT_DATA__"> 中。
    每頁透過 Playwright goto() 重新渲染，再解析 NUXT_DATA 取得 data.apiJob.result。
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
BASE_URL = "https://www.1111.com.tw"

# 1111 教育程度代碼（can appear in require.grades list）
_GRADE_MAP = {
    1: "不限",
    2: "國中(含以下)",
    4: "高中/高職",
    8: "專科",
    16: "大學",
    32: "碩士",
    64: "博士",
}


@dataclass
class SearchJob:
    job_id: str
    title: str
    company: str
    company_id: str
    location: str
    salary: str
    experience: str
    education: str
    industry: str
    url: str
    appear_date: str
    description: str


class JobSearchScraper1111:

    def __init__(self, max_jobs: int = DEFAULT_MAX_JOBS):
        self.max_jobs = max_jobs

    # ──────────────────────────────────────────────
    # 主流程
    # ──────────────────────────────────────────────

    def scrape(self, search_url: str) -> list[SearchJob]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                )
            )
            page = context.new_page()

            all_items: list[dict] = []
            total = 0
            total_pages = 1

            # 逐頁載入（SSR 渲染），從 __NUXT_DATA__ 取得職缺資料
            pnum = 1
            while len(all_items) < self.max_jobs:
                page_url = _build_page_url(search_url, pnum)
                if pnum == 1:
                    print("  載入搜尋頁...")
                else:
                    print(f"  抓取第 {pnum}/{total_pages} 頁...")

                page.goto(page_url, wait_until="networkidle", timeout=30000)

                result = _extract_nuxt_job_list(page)
                if result is None:
                    if pnum == 1:
                        raise RuntimeError(
                            "無法從頁面提取職缺資料。請確認網址正確且頁面有職缺結果。"
                        )
                    break  # no more pages

                items, pg_total, pg_total_pages = result

                if pnum == 1:
                    total = pg_total
                    total_pages = pg_total_pages
                    print(f"  找到 {total} 筆職缺，共 {total_pages} 頁，抓取前 {self.max_jobs} 筆")

                all_items.extend(items)

                if pnum >= total_pages:
                    break
                pnum += 1
                time.sleep(0.3)

            all_items = all_items[: self.max_jobs]
            jobs = [j for item in all_items if (j := _parse_item(item)) and j.job_id]

            # 步驟：抓完整 JD（瀏覽各職缺頁取得 description.responsibilities + requirement.additional）
            print(f"  抓取 {len(jobs)} 筆完整 JD（每筆約 1-2 秒）...")
            jobs = self._fetch_jd_details(page, jobs)

            browser.close()
        return jobs

    # ──────────────────────────────────────────────
    # 抓各職缺完整 JD
    # ──────────────────────────────────────────────

    def _fetch_jd_details(self, page, jobs: list[SearchJob]) -> list[SearchJob]:
        """逐一前往職缺頁，從 __NUXT_DATA__ 提取 responsibilities + additional。"""
        for i, job in enumerate(jobs):
            if not job.job_id:
                continue
            try:
                page.goto(
                    f"{BASE_URL}/job/{job.job_id}",
                    wait_until="domcontentloaded",
                    timeout=15000,
                )
                raw = page.evaluate(
                    "() => { const el = document.getElementById('__NUXT_DATA__'); return el ? el.textContent : null; }"
                )
                if raw:
                    payload = json.loads(raw)
                    resolved = _resolve_nuxt_payload(payload)
                    detail = (resolved.get("data") or {}).get("getJobs") or {}
                    if isinstance(detail, dict):
                        desc_obj = detail.get("description") or {}
                        req_obj = detail.get("requirement") or {}
                        responsibilities = str(desc_obj.get("responsibilities") or "")
                        additional = str(req_obj.get("additional") or "")
                        full_jd = responsibilities
                        if additional:
                            full_jd += "\n\n【其他條件】\n" + additional
                        if full_jd.strip():
                            job.description = full_jd.strip()
            except Exception as e:
                pass  # keep the short description from search results
            print(f"  JD 完成 {i + 1}/{len(jobs)}")
        return jobs


# ──────────────────────────────────────────────────
# Nuxt SSR 資料解析
# ──────────────────────────────────────────────────

def _extract_nuxt_job_list(page) -> tuple[list[dict], int, int] | None:
    """從頁面 __NUXT_DATA__ 中提取職缺清單與分頁資訊。"""
    raw = page.evaluate(
        "() => { const el = document.getElementById('__NUXT_DATA__'); return el ? el.textContent : null; }"
    )
    if not raw:
        return None

    try:
        payload = json.loads(raw)
    except json.JSONDecodeError:
        return None

    resolved = _resolve_nuxt_payload(payload)
    if not isinstance(resolved, dict):
        return None

    # path: root → data → apiJob → result
    data = resolved.get("data") or {}
    api_job = data.get("apiJob") or {}
    result = api_job.get("result") or {}

    hits = result.get("hits")
    if not isinstance(hits, list) or not hits:
        return None

    pagination = result.get("pagination") or {}
    total = int(pagination.get("totalCount", len(hits)))
    total_pages = int(pagination.get("totalPage", 1))

    return hits, total, total_pages


def _resolve_nuxt_payload(payload: list) -> object:
    """
    Nuxt 3 SSR payload 格式：flat array，物件/陣列的值為指向其他元素的 index。
    特殊 marker 如 ["ShallowReactive", N] 表示包裝，直接 resolve 內部值。
    """
    if not isinstance(payload, list):
        return payload

    cache: dict[int, object] = {}

    def r(idx: int) -> object:
        if not isinstance(idx, int) or idx < 0 or idx >= len(payload):
            return idx
        if idx in cache:
            return cache[idx]

        val = payload[idx]

        if isinstance(val, list):
            # Special Nuxt markers: ["ShallowReactive", N], ["Ref", N], etc.
            if (
                len(val) == 2
                and isinstance(val[0], str)
                and isinstance(val[1], int)
            ):
                res = r(val[1])
                cache[idx] = res
                return res
            # Regular list — items are index references
            res: list = []
            cache[idx] = res
            for item in val:
                res.append(r(item) if isinstance(item, int) else item)
            return res

        if isinstance(val, dict):
            res_d: dict = {}
            cache[idx] = res_d
            for k, v in val.items():
                res_d[k] = r(v) if isinstance(v, int) else v
            return res_d

        # Primitive (str, int, float, bool, None)
        cache[idx] = val
        return val

    return r(0)


# ──────────────────────────────────────────────────
# 職缺物件解析（搜尋結果格式）
# ──────────────────────────────────────────────────

def _parse_item(item: dict) -> SearchJob | None:
    if not isinstance(item, dict):
        return None

    job_id = str(item.get("jobId", ""))
    title = str(item.get("title", ""))
    company = str(item.get("companyName", ""))
    company_id = str(item.get("companyId", ""))

    # 工作地點
    work_city = item.get("workCity") or {}
    location = work_city.get("name", "") if isinstance(work_city, dict) else str(work_city)

    # 薪資
    salary = str(item.get("salary", "")) or "待遇面議"

    # 工作年資（require.experience 為字串年數）
    require = item.get("require") or {}
    exp_val = require.get("experience", "") if isinstance(require, dict) else ""
    if str(exp_val) in ("0", "", "None"):
        experience = "不拘"
    else:
        experience = f"{exp_val} 年以上"

    # 學歷（require.grades 為代碼 list）
    grades = require.get("grades", []) if isinstance(require, dict) else []
    if grades:
        edu_names = [_GRADE_MAP.get(g, str(g)) for g in grades]
        education = "、".join(edu_names)
    else:
        education = "不拘"

    # 產業
    industry_obj = item.get("industry") or {}
    industry = industry_obj.get("name", "") if isinstance(industry_obj, dict) else str(industry_obj)

    # 職缺網址
    job_url = f"{BASE_URL}/job/{job_id}" if job_id else ""

    # 刊登日期
    appear_date = str(item.get("updateAt", ""))

    # 職缺描述（搜尋結果已包含主要工作內容）
    description = str(item.get("description", ""))

    return SearchJob(
        job_id=job_id,
        title=title,
        company=company,
        company_id=company_id,
        location=location,
        salary=salary,
        experience=experience,
        education=education,
        industry=industry,
        url=job_url,
        appear_date=appear_date,
        description=description,
    )


# ──────────────────────────────────────────────────
# URL 工具
# ──────────────────────────────────────────────────

def _build_page_url(search_url: str, page_num: int) -> str:
    parsed = urlparse(search_url)
    params = parse_qs(parsed.query, keep_blank_values=True)
    params["page"] = [str(page_num)]
    flat = {k: v[0] for k, v in params.items()}
    return urlunparse(parsed._replace(query=urlencode(flat)))


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
    out_dir = output_dir / f"search_1111_{timestamp}"
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "jobs.json").write_text(
        json.dumps([j.__dict__ for j in jobs], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# 1111 職缺搜尋結果",
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
        meta = [p for p in [job.salary, job.experience, job.education, job.location] if p]
        lines += [
            f"## {i}. {job.title}",
            f"**公司**：{job.company}　**產業**：{job.industry}",
            f"**條件**：{' | '.join(meta)}",
            f"**更新**：{job.appear_date}",
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
    console.rule("[bold cyan]1111 職缺搜尋爬蟲[/bold cyan]")

    if len(sys.argv) > 1:
        search_url = sys.argv[1]
    else:
        search_url = Prompt.ask("[bold]請貼上 1111 搜尋頁網址[/bold]")

    max_jobs = IntPrompt.ask("[bold]最多抓取幾筆[/bold]", default=DEFAULT_MAX_JOBS)

    default_resume = Path(__file__).parent.parent / "resume" / "resume.md"
    resume_path = Prompt.ask("[bold]履歷路徑[/bold]", default=str(default_resume))

    console.print()
    scraper = JobSearchScraper1111(max_jobs=max_jobs)

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
