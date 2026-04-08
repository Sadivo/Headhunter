import os
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from tavily import TavilyClient

load_dotenv()

MAX_CONTENT_CHARS = 3000  # 每筆全文截斷上限


@dataclass
class SearchResult:
    topic: str    # "介紹" | "職缺" | "新聞" | "評價" | "技術"
    query: str
    title: str
    url: str
    content: str  # 全文（截斷至 MAX_CONTENT_CHARS）
    score: float


class JobSearcher:
    def __init__(self):
        api_key = os.getenv("TAVILY_API_KEY")
        if not api_key or api_key.startswith("tvly-xxx"):
            raise ValueError("請在 .env 設定有效的 TAVILY_API_KEY")
        self.client = TavilyClient(api_key=api_key)

    def search_all(self, company: str, position: str) -> dict[str, list[SearchResult]]:
        queries = {
            "介紹": f"{company} 公司介紹 主要業務 產品",
            "職缺": f"{company} {position} 職缺 徵才 job",
            "新聞": f"{company} 新聞 最新消息",
            "評價": f"{company} 員工評價 公司文化 面試心得",
            "技術": f"{company} {position} 技術棧 技能要求 tech stack requirements",
        }

        results: dict[str, list[SearchResult]] = {}

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(self._search_one, query, topic): topic
                for topic, query in queries.items()
            }
            for future in as_completed(futures):
                topic = futures[future]
                results[topic] = future.result()

        return results

    def _search_one(self, query: str, topic: str) -> list[SearchResult]:
        try:
            response = self.client.search(
                query=query,
                max_results=5,
                search_depth="advanced",
                include_raw_content=True,
            )
            return [
                SearchResult(
                    topic=topic,
                    query=query,
                    title=r.get("title", ""),
                    url=r.get("url", ""),
                    content=self._pick_content(r),
                    score=r.get("score", 0.0),
                )
                for r in response.get("results", [])
            ]
        except Exception as e:
            print(f"[searcher] 搜尋「{topic}」失敗：{e}")
            return []

    def _pick_content(self, r: dict) -> str:
        """優先使用全文，fallback 到摘要，並截斷至上限。"""
        text = r.get("raw_content") or r.get("content", "")
        if len(text) > MAX_CONTENT_CHARS:
            text = text[:MAX_CONTENT_CHARS] + "\n...(截斷)"
        return text
