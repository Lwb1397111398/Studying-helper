"""单元教学资产领域 Pydantic 模型（与 UnitLearningAsset.payload_json 对齐）。"""

from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ReadinessStatus(str, Enum):
    PENDING = "pending"
    UNDERSTANDING_READY = "understanding_ready"
    TEACHABLE = "teachable"
    DEGRADED_TEACHABLE = "degraded_teachable"
    INVALID = "invalid"
    STALE = "stale"


class FreshnessStatus(str, Enum):
    CURRENT = "current"
    STALE_SOURCE = "stale_source"
    STALE_SCHEMA = "stale_schema"
    STALE_PROMPT = "stale_prompt"


class AssetStatus(str, Enum):
    DRAFT = "draft"
    VALIDATING = "validating"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    INVALID = "invalid"


class Ability(str, Enum):
    RECOGNIZE = "recognize"
    RECALL = "recall"
    EXPLAIN = "explain"
    APPLY = "apply"
    DIFFERENTIATE = "differentiate"
    TRANSFER = "transfer"


class Importance(str, Enum):
    REQUIRED = "required"
    SUPPORTING = "supporting"


class EvidenceRef(BaseModel):
    id: str
    document_revision_id: str
    block_id: str
    start_offset: int
    end_offset: int
    quote: str
    source_kind: str = "book"  # book|external_document
    validation_status: str = "unchecked"
    offset_encoding: str = "unicode_code_point"


class SourceClaim(BaseModel):
    id: str
    claim_type: str = "fact"
    importance: Importance = Importance.REQUIRED
    text: str
    evidence_ref_ids: List[str] = Field(default_factory=list)
    support_status: str = "unsupported"  # supported|partially_supported|unsupported
    # v2 深度精读字段（可选；旧资产无此字段）
    role_in_book: Optional[str] = None  # core_thesis_support|key_mechanism|supporting_detail|example|tangential
    mastery_check: Optional[str] = None
    related_concepts: List[str] = Field(default_factory=list)


class LearningObjective(BaseModel):
    id: str
    description: str
    ability: Ability = Ability.RECALL
    importance: Importance = Importance.REQUIRED
    required_score: float = 0.8
    source_claim_ids: List[str] = Field(default_factory=list)
    # v2：认知层级（与 ability 并存；旧资产可无）
    cognitive_level: Optional[str] = None  # remember|understand|apply|analyze


class AssessmentCriterion(BaseModel):
    id: str
    objective_id: str
    observable_behavior: str
    scoring_rubric: dict[str, Any] = Field(default_factory=dict)
    pass_threshold: float = 0.8


class AssessmentItem(BaseModel):
    id: str
    asset_id: Optional[str] = None
    objective_ids: List[str] = Field(default_factory=list)
    criterion_ids: List[str] = Field(default_factory=list)
    item_type: str = "multiple_choice"
    phase_usage: List[str] = Field(default_factory=lambda: ["assessment"])
    ability: Ability = Ability.RECALL
    stem: str
    options: List[str] = Field(default_factory=list)
    expected_answer: str = ""
    scoring_rubric: dict[str, Any] = Field(default_factory=dict)
    difficulty: float = 0.5
    content_origin: str = "book"
    evidence_ref_ids: List[str] = Field(default_factory=list)
    equivalence_group_id: Optional[str] = None
    status: str = "active"
    version: int = 1


class Prerequisite(BaseModel):
    id: str
    target_type: str = "concept"  # unit|concept|external_knowledge
    target_id: Optional[str] = None
    label: str = ""
    necessity: str = "recommended"  # required|recommended
    relation_type: str = "understand_before"
    source: str = "inferred"
    confidence: float = 0.5
    resolution_status: str = "unresolved"  # unresolved|resolved|unavailable
    resolved_unit_id: Optional[str] = None


class UnitLearningAssetPayload(BaseModel):
    unit_type: str = "concept"
    central_question: str = ""
    claims: List[SourceClaim] = Field(default_factory=list)
    learning_objectives: List[LearningObjective] = Field(default_factory=list)
    assessment_criteria: List[AssessmentCriterion] = Field(default_factory=list)
    assessment_items: List[AssessmentItem] = Field(default_factory=list)
    prerequisites: List[Prerequisite] = Field(default_factory=list)
    misconceptions: List[dict[str, Any]] = Field(default_factory=list)
    teaching_strategy: dict[str, Any] = Field(default_factory=dict)
    repair_strategy_map: dict[str, Any] = Field(default_factory=dict)
    evidence_refs: List[EvidenceRef] = Field(default_factory=list)
    summary: str = ""
    explanation: str = ""
    # Step2 深度精读标记
    understanding_version: str = "v1"  # v1|v2
    unit_gist: str = ""
    content_hash: str = ""
    overview_injected: bool = False
