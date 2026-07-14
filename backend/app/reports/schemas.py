from datetime import datetime
from typing import Literal

from pydantic import BaseModel

from app.core.warnings import ServiceWarning


ReportType = Literal["周报", "月报", "自定义报告"]
ReportModule = Literal["overview", "region", "ranking", "anomaly", "forecast"]


class ReportRequest(BaseModel):
    report_type: ReportType
    modules: list[ReportModule]


class ReportSection(BaseModel):
    id: ReportModule
    title: str
    content: str


class ReportResult(BaseModel):
    title: str
    period: str
    sections: list[ReportSection]
    markdown: str
    engine: Literal["local", "ai"]
    provenance: Literal["local", "local_fallback", "ai_assisted", "ai_partial"]
    warning: ServiceWarning | None = None
    generated_at: datetime
