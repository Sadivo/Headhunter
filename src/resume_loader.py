from dataclasses import dataclass
from pathlib import Path


@dataclass
class ResumeData:
    raw: str
    path: str


class ResumeLoader:
    def load(self, path: str) -> ResumeData:
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"找不到履歷檔案：{path}")
        content = p.read_text(encoding="utf-8")
        return ResumeData(raw=content, path=str(p.resolve()))
