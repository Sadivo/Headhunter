"""
104人力銀行爬蟲
使用 Playwright 瀏覽器攔截 XHR 回應，繞過 Cloudflare 保護。

已確認的 API 端點（只在瀏覽器環境下回傳 JSON）：
  - 公司搜尋：https://www.104.com.tw/company/ajax/list?keyword={keyword}
  - 公司資料：https://www.104.com.tw/api/companies/{encodedCustNo}/content
  - 公司職缺：https://www.104.com.tw/api/companies/{encodedCustNo}/jobs?pageSize=50
"""

from dataclasses import dataclass, field
from playwright.sync_api import sync_playwright

MAX_JOBS = 50


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
            with page.expect_response(
                lambda r: "company/ajax/list" in r.url and "menu" not in r.url,
                timeout=15000,
            ) as response_info:
                page.goto(
                    f"https://www.104.com.tw/jobs/search/?keyword={keyword}&order=14&asc=0&page=1",
                    wait_until="domcontentloaded",
                )

            try:
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
    # 公開介面 2：抓公司資料 + 所有職缺
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
            except Exception:
                jobs_data = {}

            browser.close()

        return self._build_result(cust_no, content_data, jobs_data)

    # ──────────────────────────────────────────────
    # 組裝結果
    # ──────────────────────────────────────────────
    def _build_result(
        self,
        cust_no: str,
        content_data: dict,
        jobs_data: dict,
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

        job_list = jobs_data.get("data", {}).get("list", {})
        all_jobs = job_list.get("topJobs", []) + job_list.get("normalJobs", [])

        for item in all_jobs[: self.max_jobs]:
            company.jobs.append(
                JobDetail(
                    job_id=item.get("encodedJobNo", ""),
                    title=item.get("jobName", ""),
                    url=item.get("jobUrl", ""),
                    description=item.get("jobDescription", ""),
                    salary=item.get("jobSalaryDesc", ""),
                    experience=item.get("periodDesc", ""),
                    education=item.get("edu", ""),
                )
            )

        return company
