from typing import Optional

from pydantic import BaseModel, Field


SUPPORTED_VULNERABILITY_TYPES = (
    'SQL_INJECTION',
    'XSS',
    'AUTH_BYPASS',
    'PATH_TRAVERSAL',
    'COMMAND_INJECTION',
    'SSRF',
    'DESERIALIZATION',
    'SECRETS',
    'ACCESS_CONTROL',
    'FILE_UPLOAD',
    'TEMPLATE_INJECTION',
    'OTHER',
)


class Vulnerability(BaseModel):
    file_path: str
    line_number: int
    end_line: Optional[int] = None
    severity: str = Field(..., pattern='^(LOW|MEDIUM|HIGH|CRITICAL)$')
    title: str
    description: str
    code_snippet: str
    confidence_score: float
    ai_explanation: str


class ScanResult(BaseModel):
    findings: list[Vulnerability]


class FixResult(BaseModel):
    scope: str = Field(..., pattern='^(SNIPPET|FILE)$')
    start_line: int
    end_line: int
    fixed_code: str
    explanation: str


class VerificationResult(BaseModel):
    is_true_positive: bool
    reasoning: str


class VulnerabilitySurface(BaseModel):
    surface_id: str
    vulnerability_type: str
    title: str
    rationale: str
    entrypoints: list[str] = Field(default_factory=list)
    sinks: list[str] = Field(default_factory=list)
    evidence_paths: list[str] = Field(default_factory=list)
    recommended_files: list[str] = Field(default_factory=list)
    priority: str = Field(..., pattern='^(LOW|MEDIUM|HIGH|CRITICAL)$')


class OrchestratorSurfaceResult(BaseModel):
    surfaces: list[VulnerabilitySurface]


class SpecialistFindingResult(BaseModel):
    surface_id: str
    vulnerability_type: str
    vulnerability: Vulnerability
    fix: FixResult | None = None
    verification: VerificationResult | None = None
    specialist_metadata: dict = Field(default_factory=dict)


class ScanExecutionResult(BaseModel):
    findings: list[SpecialistFindingResult]
    metadata: dict = Field(default_factory=dict)
