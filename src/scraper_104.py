"""
104人力銀行爬蟲
使用 Playwright 瀏覽器攔截 XHR 回應，繞過 Cloudflare 保護。

已確認的 API 端點（只在瀏覽器環境下回傳 JSON）：
  - 公司搜尋：https://www.104.com.tw/company/ajax/list?keyword={keyword}
  - 公司資料：https://www.104.com.tw/api/companies/{encodedCustNo}/content
  - 公司職缺：https://www.104.com.tw/api/companies/{encodedCustNo}/jobs?pageSize=50&page={n}
"""

import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from playwright.sync_api import sync_playwright

MAX_JOBS = 50
PAGE_DELAY = 0.3  # 分頁請求間隔（秒）


@dataclass
class CompanyCandidate:
    cust_no: str       # encodedCustNo（如 a5h92m0）
    name: str
    industry: str
    employee_count: str


@dataclass
class JobDetail:
    job_id: str        # encodedJobNo
    title: str
    url: str
    description: str   # 工作內容（API 已整合條件）
    salary: str
    experience: str
    education: str


@dataclass
class Company104Data:
    cust_no: str
    name: str
    website: str       # custLink 欄位
    description: str   # profile 欄位
    industry: str
    employee_count: str
    jobs: list[JobDetail] = field(default_factory=list)


class Scraper104:
    def __init__(self, max_jobs: int = MAX_JOBS):
        self.max_jobs = max_jobs

    # ──────────────────────────────────────────────
    # 公開介面 1：搜尋公司候選名單
    # ──────────────────────────────────────────────
    def search_companies(self, keyword: str) -> list[CompanyCandidate]:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            # 先開始導航（非阻塞），再等候目標回應
            try:
                with page.expect_response(
                    lambda r: "company/ajax/list" in r.url and "menu" not in r.url,
                    timeout=20000,
                ) as response_info:
                    page.goto(
                        f"https://www.104.com.tw/jobs/search/?keyword={keyword}&order=14&asc=0&page=1",
                        wait_until="domcontentloaded",
                    )
                data = response_info.value.json()
            except Exception:
                data = {}
            browser.close()

        seen: dict[str, CompanyCandidate] = {}
        for item in data.get("data", []):
            cust_no = item.get("encodedCustNo", "")
            if cust_no and cust_no not in seen:
                seen[cust_no] = CompanyCandidate(
                    cust_no=cust_no,
                    name=item.get("name", ""),
                    industry=item.get("industryDesc", ""),
                    employee_count=item.get("employeeCountDesc", ""),
                )
        return list(seen.values())[:10]

    # ──────────────────────────────────────────────
    # 公開介面 2：抓公司資料 + 所有職缺（含分頁）
    # ──────────────────────────────────────────────
    def fetch_all(self, cust_no: str) -> Company104Data:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()

            with (
                page.expect_response(
                    lambda r: f"api/companies/{cust_no}/content" in r.url,
                    timeout=15000,
                ) as content_info,
                page.expect_response(
                    lambda r: f"api/companies/{cust_no}/jobs?" in r.url,
                    timeout=15000,
                ) as jobs_info,
            ):
                page.goto(
                    f"https://www.104.com.tw/company/{cust_no}",
                    wait_until="domcontentloaded",
                )

            try:
                content_data = content_info.value.json()
            except Exception:
                content_data = {}

            try:
                jobs_data = jobs_info.value.json()
                jobs_api_url = jobs_info.value.url
            except Exception:
                jobs_data = {}
                jobs_api_url = (
                    f"https://www.104.com.tw/api/companies/{cust_no}/jobs?pageSize=50"
                )

            all_raw_jobs = self._collect_all_jobs(page, jobs_data, jobs_api_url)
            browser.close()

        return self._build_result(cust_no, content_data, all_raw_jobs)

    # ──────────────────────────────────────────────
    # 收集所有頁面職缺（第一頁已攔截，其餘用 fetch）
    # ──────────────────────────────────────────────
    def _collect_all_jobs(
        self, page, first_jobs_data: dict, api_url: str
    ) -> list[dict]:
        job_list = first_jobs_data.get("data", {}).get("list", {})
        all_jobs: list[dict] = (
            job_list.get("topJobs", []) + job_list.get("normalJobs", [])
        )

        # 嘗試讀取分頁資訊（不同 API 版本路徑不同）
        pagination = (
            first_jobs_data.get("metadata", {}).get("pagination")
            or first_jobs_data.get("data", {}).get("pagination")
            or {}
        )
        last_page = pagination.get("lastPage", 1)

        if last_page <= 1 or len(all_jobs) >= self.max_jobs:
            return all_jobs

        # 解析原始 URL，保留所有既有參數
        parsed = urlparse(api_url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}

        for page_num in range(2, last_page + 1):
            if len(all_jobs) >= self.max_jobs:
                break
            params["page"] = str(page_num)
            url = urlunparse(parsed._replace(query=urlencode(params)))

            result = page.evaluate(f"""async () => {{
                const r = await fetch('{url}');
                return r.json();
            }}""")
            extra = result.get("data", {}).get("list", {})
            all_jobs.extend(extra.get("topJobs", []) + extra.get("normalJobs", []))
            time.sleep(PAGE_DELAY)

        return all_jobs

    # ──────────────────────────────────────────────
    # 組裝結果
    # ──────────────────────────────────────────────
    def _build_result(
        self,
        cust_no: str,
        content_data: dict,
        raw_jobs: list[dict],
    ) -> Company104Data:
        profile = content_data.get("data", {})

        company = Company104Data(
            cust_no=cust_no,
            name=profile.get("custName", ""),
            website=profile.get("custLink", ""),
            description=profile.get("profile", ""),
            industry=profile.get("industryDesc", ""),
            employee_count=profile.get("empNo", ""),
        )

        for item in raw_jobs[: self.max_jobs]:
            company.jobs.append(self._parse_job(item))

        return company

    def _parse_job(self, item: dict) -> JobDetail:
        return JobDetail(
            job_id=item.get("encodedJobNo", ""),
            title=item.get("jobName", ""),
            url=item.get("jobUrl", ""),
            description=item.get("jobDescription", ""),
            salary=item.get("jobSalaryDesc", ""),
            experience=item.get("periodDesc", ""),
            education=item.get("edu", ""),
        )
