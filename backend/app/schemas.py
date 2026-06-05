from __future__ import annotations

from enum import StrEnum
import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, model_validator


class BreakdownStatus(StrEnum):
    PENDING = "pending"
    IMPORTING = "importing"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


FORBIDDEN_RESULT_KEYS = {
    "category_slots",
    "combination_matrix",
    "effectiveness_analysis",
    "ai_reproduction_judgment",
    "learning_card",
    "trend_type",
    "audience_moras_fit",
    "moras_adaptation",
    "risk_quality_check",
    "selected_component_set",
    "selected_component_sets",
    "shot_plan",
    "shot_plans",
    "executable_video_generation_prompt",
    "video_generation_prompt",
    "final_script",
    "storyboard",
    "video_prompt",
    "manual_review",
    "approval",
    "top_category",
    "secondary_tags",
    "classification_reason",
    "primary_label",
    "tags",
    "reasoning",
}


class BreakdownCreate(BaseModel):
    video_url: str = Field(min_length=1)
    provider: str | None = None


class SourceVideo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=500)
    original_url: str = Field(min_length=1)
    imported_video_url: str = Field(min_length=1)
    platform: str | None = Field(default=None, max_length=120)
    creator_handle: str | None = Field(default=None, max_length=200)
    duration_seconds: int | None = Field(default=None, gt=0)
    observed_metrics: dict[str, Any] = Field(default_factory=dict)
    content_summary: str = Field(min_length=1)


class Classification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    taxonomy_version: str = "moras_viral_factor_v1"
    hook_type: str | None = Field(default=None, min_length=1, max_length=80)
    emotion_factors: list[str] = Field(default_factory=list)
    persona_factors: list[str] = Field(default_factory=list)
    scene_factors: list[str] = Field(default_factory=list)
    conflict_factors: list[str] = Field(default_factory=list)
    pain_factors: list[str] = Field(default_factory=list)
    itch_factors: list[str] = Field(default_factory=list)
    value_factors: list[str] = Field(default_factory=list)
    proof_factors: list[str] = Field(default_factory=list)
    cta_factors: list[str] = Field(default_factory=list)
    structure_factors: list[str] = Field(default_factory=list)
    visual_rhythm_factors: list[str] = Field(default_factory=list)
    audience_segments: list[str] = Field(default_factory=list)
    general_templates: list[str] = Field(default_factory=list)
    vertical_templates: list[str] = Field(default_factory=list)
    factor_reasoning: str = Field(min_length=1)
    confidence: float | None = Field(default=None, ge=0, le=1)
    evidence: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_factor_labels(self):
        factor_values = [
            *self.emotion_factors,
            *self.persona_factors,
            *self.scene_factors,
            *self.conflict_factors,
            *self.pain_factors,
            *self.itch_factors,
            *self.value_factors,
            *self.proof_factors,
            *self.cta_factors,
            *self.structure_factors,
            *self.visual_rhythm_factors,
            *self.audience_segments,
            *self.general_templates,
            *self.vertical_templates,
        ]
        invalid = [tag for tag in factor_values if not tag.strip() or len(tag) > 120]
        if invalid:
            raise ValueError("factor labels must be non-empty strings shorter than 120 characters")
        return self


class DecompositionSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_no: int = Field(ge=1)
    start_second: int | None = Field(default=None, ge=0)
    end_second: int | None = Field(default=None, gt=0)
    role: str = Field(min_length=1)
    content: str = Field(min_length=1)
    technique: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_time_range(self):
        if self.start_second is not None and self.end_second is not None and self.end_second <= self.start_second:
            raise ValueError("end_second must be greater than start_second")
        return self


class Decomposition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    one_sentence_summary: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    narrative_structure: list[str] = Field(min_length=1)
    segments: list[DecompositionSegment] = Field(min_length=1)
    key_takeaways: list[str] = Field(default_factory=list)
    visual_language: str | None = Field(default=None, min_length=1)
    audio_language: str | None = Field(default=None, min_length=1)
    interaction_or_cta: str | None = Field(default=None, min_length=1)
    performance_logic: str | None = Field(default=None, min_length=1)

    @model_validator(mode="after")
    def validate_hook_depth(self):
        labels = ["【视觉】", "【听觉】", "【字幕】", "【心理机制】", "【留人问题】"]
        missing = [label for label in labels if label not in self.hook]
        if missing:
            raise ValueError(f"decomposition.hook missing required labels: {', '.join(missing)}")
        return self


class StructureSlot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    slot_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    start_second: int | None = Field(default=None, ge=0)
    end_second: int | None = Field(default=None, gt=0)
    role: str = Field(min_length=1)
    observable_evidence: str = Field(min_length=1)
    required_assets: list[str] = Field(default_factory=list)
    transfer_rule: str = Field(min_length=1)


class StructureProtocol(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: int = 1
    source: str = "k2lab_social_video_breakdown"
    core_pattern: str = Field(min_length=1)
    timeline_slots: list[StructureSlot] = Field(min_length=1)
    reuse_rules: list[str] = Field(default_factory=list)
    risk_flags: list[str] = Field(default_factory=list)


class ScriptAgentBridge(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reusable_pattern: str = Field(min_length=1)
    script_agent_instructions: list[str] = Field(min_length=1)
    variables_to_collect: list[str] = Field(default_factory=list)
    do_not_copy: list[str] = Field(default_factory=list)
    adaptation_notes: list[str] = Field(default_factory=list)


class ReferenceStoryboardShot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    character_action: str = Field(min_length=1)
    facial_expression: str = Field(min_length=1)
    background: str = Field(min_length=1)
    props: list[str] = Field(default_factory=list)
    voiceover: str = Field(min_length=1)
    overlay: str = Field(default="")
    sound: str = Field(min_length=1)
    bgm: str = Field(default="")
    sound_effects: list[str] = Field(default_factory=list)
    subtitle_logic: str = Field(default="")
    visual_elements: list[str] = Field(default_factory=list)
    visual_element_logic: str = Field(default="")
    transition: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    localized: dict[str, Any] = Field(default_factory=dict)


class BreakdownResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_video: SourceVideo
    classification: Classification
    decomposition: Decomposition
    structure_protocol: StructureProtocol
    script_agent_bridge: ScriptAgentBridge
    reference_storyboard: list[ReferenceStoryboardShot] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def reject_raw_forbidden_result_keys(cls, value: Any) -> Any:
        forbidden = find_forbidden_keys(value)
        if forbidden:
            raise ValueError(f"Legacy or out-of-scope keys are not allowed: {', '.join(sorted(forbidden))}")
        return value

    @model_validator(mode="after")
    def validate_result_keys(self):
        forbidden = find_forbidden_keys(self.model_dump(mode="json"))
        if forbidden:
            raise ValueError(f"Legacy or out-of-scope keys are not allowed: {', '.join(sorted(forbidden))}")
        return self


class BreakdownRecord(BaseModel):
    id: str
    status: BreakdownStatus
    provider: str
    reused_existing: bool = False
    error_message: str | None = None
    source_video: dict[str, Any] | None = None
    classification: dict[str, Any] | None = None
    decomposition: dict[str, Any] | None = None
    structure_protocol: dict[str, Any] | None = None
    script_agent_bridge: dict[str, Any] | None = None
    reference_storyboard: list[dict[str, Any]] = Field(default_factory=list)
    raw_response_text: str | None = None
    created_at: str
    updated_at: str


class ScriptStatus(StrEnum):
    READY = "ready"
    EDITING = "editing"
    FAILED = "failed"


class ScriptGenerationJobStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class PersonaGenerationJobStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


ALLOWED_SCRIPT_TYPES = {
    "all",
    "POV",
    "Mistake List",
    "Contrarian Take",
    "Secret / Exposed",
    "Comment Reply",
    "Product Picking",
    "Shoppable Video Workflow",
    "Product-to-Video Workflow",
    "Faceless Creator",
    "Beginner Trap",
}

BANNED_SCRIPT_CLAIM_PATTERNS = {
    "guaranteed income",
    "passive income guaranteed",
    "$10k easily",
    "automatic money",
    "ai guarantees sales",
    "guarantees $",
    "guaranteed $",
    "guarantee $",
    "guaranteed sales",
    "guarantee sales",
    "bypass tiktok",
    "绕过平台",
    "保证收益",
    "保证出单",
    "保证赚钱",
    "躺赚",
    "自动赚钱",
    "固定结算",
}

BANNED_SCRIPT_STYLE_PATTERNS = {
    "look at this quality",
    "video quality",
    "high quality",
    "high-quality",
    "better quality",
    "better video",
    "doesn't look fake",
    "does not look fake",
    "looks fake",
    "realistic output",
    "polished output",
    "ready-to-publish instantly",
    "publish-ready instantly",
    "instantly ready",
    "content volume is the real bottleneck",
    "optimize",
    "optimization",
    "leverage",
    "framework",
    "mechanism",
    "conversion baseline",
    "efficiency bottleneck",
    "scale your workflow",
    "maximize output",
    "revolutionary",
    "game changer",
    "seamless experience",
    "niche",
    "market segment",
    "vertical market",
    "random inventory",
    "hoard inventory",
    "inventory",
    "product card",
    "ready-to-post",
    "ready to post",
    "shoppable",
    "cart attached",
    "with the cart attached",
    "video with cart",
    "with cart",
    "buy samples",
    "buy sample",
    "buying samples",
    "sample excuse",
    "samples first",
    "before i buy samples",
    "before i spend on samples",
    "spend on samples",
    "sample decision",
    "sample box",
    "no samples",
    "samples cost",
    "sample",
    "test products",
    "testing products",
    "product tests",
    "product testing",
    "test every day",
    "product to test",
    "want to test",
    "one more test",
    "another test",
    "test before",
    "to test today",
    "test smarter",
    "testing routine",
    "testing",
    "test list",
    "0 conversions",
    "0 conversion",
    "0 sales",
    "0 orders",
    "0 posts",
    "zero conversions",
    "zero conversion",
    "zero sales",
    "zero orders",
    "zero posts",
    "no conversions",
    "no sales",
    "no orders",
    "细分市场",
    "细分领域",
    "赛道",
    "库存",
    "囤货",
    "商品卡",
    "可发布视频",
    "可发布可购物视频",
    "可购物视频",
    "可购物",
    "带购物车的可发布",
    "带购物车视频",
    "带车成片",
    "买样品",
    "样品",
    "先测再买",
    "测试清单",
    "测试习惯",
    "测试流程",
    "想测试",
    "下个测试",
    "多测",
    "cheat code",
    "unlock",
    "transform your",
    "boost your",
    "supercharge",
    "level up",
    "all-in-one",
    "ultimate",
    "must-have",
    "try it out",
    "prove me wrong",
    "link is right there",
    "doing it the hard way",
    "rough cut",
    "rough edit",
    "edited rough cut",
    "editable rough cut",
    "editable cut",
    "instant draft",
    "instantly get",
    "paste product info",
    "paste product data",
    "plug in your product data",
    "drop product data",
    "product data into",
    "dump product info",
    "drop the product info",
    "drop it into moras",
    "turns product links into videos",
    "script and visuals already mapped out",
    "pulls the angles",
    "pulls the hooks",
    "straight to testing",
    "in minutes",
    "exactly twelve minutes",
    "edit the text and publish",
    "modify the copy and publish",
    "grow faster",
    "drive engagement",
    "monetize effortlessly",
    "视频效果好",
    "效果很好",
    "高质量",
    "不像假的",
    "不假",
    "真实输出",
    "精致成片",
    "优化转化",
    "粗剪",
    "粗剪草稿",
    "剪辑草稿",
    "可编辑视频",
    "可直接编辑",
    "直接上手改",
    "瞬间拿到",
    "马上拿到",
    "立刻拿到",
    "立即拿到",
    "立刻生成",
    "立即生成",
    "拍一整天",
    "修改文案并发布",
    "改文案并发布",
    "输入商品数据",
    "把产品信息丢进",
    "直接把产品信息丢进",
    "随便把产品信息",
    "把商品信息放进",
    "把商品信息丢进",
    "把它丢给 moras",
    "商品链接变成视频",
    "爆款神器",
    "马上变现",
    "点击链接",
}

DEFAULT_NEGATIVE_OPENING_PATTERNS = {
    "0 conversions",
    "0 conversion",
    "0 sales",
    "0 orders",
    "0 posts",
    "zero conversions",
    "zero conversion",
    "zero sales",
    "zero orders",
    "zero posts",
    "no conversions",
    "no sales",
    "no orders",
    "still no post",
    "six months of zero",
}

GENERIC_CAPTION_HIGHLIGHTS = {
    "listen up",
    "hey",
    "watch this",
    "pay attention",
    "听我说",
    "注意看",
}

BANNED_SCRIPT_STYLE_REGEX_PATTERNS = (
    r"\btest(?:ing|s|ed)?\b",
)

UGC_TEXTURE_TERMS = {
    "i ",
    "i'm",
    "i’ve",
    "i've",
    "my ",
    "me ",
    "honestly",
    "so ",
    "the annoying part",
    "i used to",
    "i almost",
    "i don't",
    "i do not",
    "i had",
    "pov:",
    "that's what",
    "that is what",
}

MORAS_RECOMMENDATION_PERSONAL_TERMS = {
    "i ",
    "i'm",
    "i’ve",
    "i've",
    "my ",
    "me ",
    "before i",
    "so i",
    "you ",
    "your ",
}

MORAS_RECOMMENDATION_WORKFLOW_TERMS = {
    "discover",
    "pick",
    "choose",
    "product card",
    "create video",
    "custom create",
    "generate",
    "tap",
    "hit",
    "ready-to-post",
    "ready to post",
    "cart",
    "posting",
    "publish entry",
    "draft",
    "video draft",
    "output",
    "generated",
    "check",
    "review",
    "pre-check",
    "edit",
    "split",
    "delete",
    "regen",
    "regenerate",
    "posts",
    "catalog",
}

PERSONA_TYPES = {
    "Beginner KOC",
    "Mom Creator",
    "Tutorial Learner",
    "Skeptical Creator",
    "Lazy-but-Ambitious Creator",
}

PERSONA_QUALITY_CHECKS = {
    "target_audience_clear",
    "role_task_clear",
    "three_layer_problem_complete",
    "recurring_scenes_present",
    "memory_symbols_present",
    "trust_assets_defined",
    "endorsement_boundary_safe",
    "not_overprofessionalized",
    "distinct_from_existing_personas",
    "script_agent_ready",
}

PERSONA_QUALITY_PASS_SCORE = 75

BANNED_DIGITAL_HUMAN_SAMPLE_CLAIMS = (
    "voice clone",
    "voice cloning",
    "cloned voice",
    "clone voice",
    "real voice",
    "voice sample",
    "audio sample",
    "extracted audio",
    "extracted from video",
    "source video sample",
    "真人声音",
    "声音克隆",
    "克隆声音",
    "声音样本",
    "音频样本",
    "提取声音",
    "原视频声音",
    "真人样本",
)

HOOK_PATTERN_LABELS = {
    "[absurd visual]",
    "[contrarian]",
    "[curiosity gap]",
    "[question]",
    "[story opener]",
    "[list preview]",
    "[bold claim]",
    "[empathy]",
    "[before/after]",
    "[confession]",
    "[pattern interrupt]",
    "[direct callout]",
    "[demo setup]",
    "[psychological trigger]",
    "[relatable weirdness]",
    "[pov]",
    "[open loop]",
    "[mini drama]",
    "[funny overstatement]",
    "[unexpected analogy]",
}

ATTENTION_FIRST_HOOK_LABELS = {
    "[absurd visual]",
    "[curiosity gap]",
    "[psychological trigger]",
    "[relatable weirdness]",
    "[pov]",
    "[open loop]",
    "[mini drama]",
    "[funny overstatement]",
    "[unexpected analogy]",
    "[story opener]",
    "[empathy]",
}

HOOK_PROHIBITION_TERMS = {
    "stop ",
    "don't ",
    "do not ",
    "never ",
    "wrong",
    "mistake",
    "trap",
    "别",
    "不要",
    "别再",
    "错",
    "误区",
}

PRODUCTION_ASSET_TYPES = {
    "real_moras_screen_recording",
    "real_moras_screenshot",
    "moras_product_workflow",
    "ai_generated_broll",
    "digital_human_avatar",
    "live_creator_footage",
    "post_production_overlay",
    "sound_design",
}

REAL_MORAS_ASSET_TYPES = {
    "real_moras_screen_recording",
    "real_moras_screenshot",
    "moras_product_workflow",
}

MORAS_ASSET_CATEGORIES = {
    "workflow_screen_recording",
    "product_card_to_video_draft_before_after",
    "product_to_script_before_after",
    "time_saved_comparison",
    "product_selection_logic",
    "published_content_feedback",
    "approved_feature_screenshot",
    "none",
}

PRODUCTION_ASSET_LAYERS = {
    "base_track",
    "cutaway",
    "overlay",
    "audio",
}

MAX_VEO_SEGMENT_DURATION_SEC = 8.0
MAX_VEO_SEGMENT_COUNT = 7
VEO_BASE_DURATION_SEC = 8.0
VEO_GENERATION_MODE = "text_to_video_9x16"

MAX_STORYBOARD_ROW_DURATION_SEC = 8.0
MIN_STORYBOARD_VOICEOVER_DURATION_SEC = 2.0
STORYBOARD_VOICEOVER_DURATION_TOLERANCE_SEC = 0.35
STORYBOARD_VOICEOVER_HOLD_ALLOWANCE_SEC = 1.5
MIN_SCRIPT_VOICEOVER_LINES = 11
MIN_SCRIPT_VOICEOVER_TOTAL_ENGLISH_WORDS = 90
MIN_SCRIPT_SPOKEN_DURATION_SEC = 35.0
MAX_SCRIPT_VOICEOVER_ENGLISH_WORDS = 14
MAX_STORYBOARD_VOICEOVER_ENGLISH_WORDS = 14
MAX_VOICEOVER_SENTENCE_CHUNKS = 2
MAX_OVERLAY_HIGHLIGHT_ENGLISH_WORDS = 10
MAX_OVERLAY_HIGHLIGHT_CJK_CHARS = 24
MAX_OVERLAY_HIGHLIGHT_CHARS = 80
MIN_VEO_PROMPT_ENGLISH_WORDS = 45
MIN_VEO_PROMPT_CJK_CHARS = 80

VEO_PROMPT_COMPONENT_KEYWORDS = {
    "subject_action": [
        "creator",
        "person",
        "hands",
        "gesture",
        "expression",
        "moves",
        "movement",
        "looks",
        "holds",
        "points",
        "创作者",
        "人物",
        "手部",
        "动作",
        "表情",
        "指向",
    ],
    "camera": [
        "camera",
        "shot",
        "framing",
        "portrait",
        "vertical",
        "close-up",
        "medium",
        "handheld",
        "dolly",
        "push",
        "镜头",
        "机位",
        "竖屏",
        "近景",
        "中景",
        "推进",
    ],
    "lighting_style": [
        "light",
        "lighting",
        "daylight",
        "cinematic",
        "realistic",
        "high fidelity",
        "mood",
        "tone",
        "depth of field",
        "光",
        "自然光",
        "电影感",
        "真实",
        "氛围",
        "景深",
    ],
    "audio": [
        "audio",
        "ambience",
        "ambient",
        "room tone",
        "sound",
        "desk sounds",
        "music",
        "声音",
        "环境声",
        "音效",
        "桌面声",
        "音乐",
    ],
}

VEO_PROMPT_FORBIDDEN_TERMS = {
    "screen recording",
    "screenshot",
    "user interface",
    "ui label",
    "subtitle",
    "caption",
    "typography",
    "readable words",
    "readable text",
    "written words",
    "call-to-action",
    "cta",
    "overlay text",
    "moras app ui",
    "录屏",
    "截图",
    "界面",
    "字幕",
    "界面文案",
    "可读文字",
    "文字",
    "标语",
}

GENERIC_STORYBOARD_TERMS = {
    "",
    "none",
    "n/a",
    "na",
    "not applicable",
    "screen recording",
    "screenrecording",
    "dynamic product shots",
    "dynamic shots",
    "product shots",
    "b-roll",
    "broll",
    "cutaway",
    "various aesthetic product scenes",
    "moras app ui",
    "app ui",
    "ui",
    "无",
    "无动作",
    "不适用",
    "屏幕录制",
    "动态产品镜头",
    "产品镜头",
    "各种唯美的产品场景",
    "moras app 界面",
}

DIRECTOR_VIDEO_LAYERS = {
    "base_track",
    "cutaway",
    "overlay",
}

DIRECTOR_AUDIO_LAYERS = {
    "audio",
}

DIRECTOR_VIDEO_SOURCE_TYPES = {
    "veo_generation",
    "seedance_generation",
    "library_asset",
    "hyperframes_overlay",
}

DIRECTOR_AUDIO_SOURCE_TYPES = {
    "tts_voiceover",
    "sound_design",
    "bg_music",
}

DIRECTOR_TOOL_NAMES = {
    "asset_resolver",
    "manual_veo_generation",
    "manual_veo_upload",
    "manual_seedance_generation",
    "manual_seedance_upload",
    "fetch_library_asset",
    "render_hyperframes_subtitle",
    "synthesize_tts",
    "run_ffmpeg_mix",
    "run_quality_check",
}

DIRECTOR_ASSET_RESOLUTION_STATUS = {
    "ready",
    "resolved",
    "missing_placeholder",
    "blocked",
}

DIRECTOR_MANUAL_BINDING_STATUS = {
    "not_required",
    "pending_binding",
    "pending_generation",
    "pending_upload",
    "bound",
}


class ScriptGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_count: int = Field(default=3, ge=1, le=10)
    script_type: str = Field(default="all", min_length=1, max_length=80)
    source_breakdown_ids: list[str] = Field(default_factory=list)
    persona_id: str | None = Field(default=None, min_length=1, max_length=160)
    persona_hint: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_script_type(self):
        if self.script_type == "全部":
            self.script_type = "all"
        if self.script_type not in ALLOWED_SCRIPT_TYPES:
            raise ValueError(f"unsupported script_type: {self.script_type}")
        return self


class ScriptEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=2000)


class PersonaGenerationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_count: int = Field(default=3, ge=1, le=10)
    topic_or_brand_context: str = Field(default="Moras social-commerce creator workflow", max_length=600)
    target_audience: str = Field(default="TikTok Shop creators, sellers, and MCN operators", max_length=300)
    required_demographic: str | None = Field(default=None, max_length=160)


class PersonaEditRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: str = Field(min_length=1, max_length=1200)


class ScriptTopicPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    content_angle: str = Field(min_length=1)
    trend_source: str = Field(min_length=1)
    template: str = Field(min_length=1)
    persona: str = Field(min_length=1)
    hook_candidates: list[str] = Field(min_length=1)
    cta_candidates: list[str] = Field(min_length=1)
    recommended_platform: str = Field(min_length=1)
    moras_relevance_score: int = Field(ge=0, le=100)
    risk_score: int = Field(ge=0, le=100)
    localized: dict[str, Any] = Field(default_factory=dict)


class StructuredScript(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_title: str = Field(min_length=1)
    target_audience: str = Field(min_length=1)
    persona: str = Field(min_length=1)
    template: str = Field(min_length=1)
    core_pain: str = Field(min_length=1)
    emotional_angle: str = Field(min_length=1)
    hook: str = Field(min_length=1)
    voiceover: list[str] = Field(min_length=1)
    visual: str = Field(min_length=1)
    overlay: list[str] = Field(default_factory=list)
    sound_effect: str = Field(min_length=1)
    proof_insert: str = Field(min_length=1)
    cta: str = Field(min_length=1)
    compliance_note: str = Field(min_length=1)
    version: str = Field(min_length=1)
    localized: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_overlay_highlights(self):
        for index, overlay in enumerate(self.overlay):
            validate_overlay_highlight_text(overlay, f"script.overlay[{index}]")
        localized_zh_overlay = localized_zh_value(self.localized, "overlay")
        if isinstance(localized_zh_overlay, list):
            for index, overlay in enumerate(localized_zh_overlay):
                validate_overlay_highlight_text(str(overlay), f"script.localized.zh.overlay[{index}]")
        elif isinstance(localized_zh_overlay, str):
            validate_overlay_highlight_text(localized_zh_overlay, "script.localized.zh.overlay")
        return self


class StoryboardShot(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shot_id: str = Field(min_length=1)
    timestamp: str = Field(min_length=1)
    duration: str = Field(min_length=1)
    camera: str = Field(min_length=1)
    character_action: str = Field(min_length=1)
    facial_expression: str = Field(min_length=1)
    background: str = Field(min_length=1)
    props: list[str] = Field(default_factory=list)
    voiceover: str = Field(min_length=1)
    overlay: str = Field(default="")
    sound: str = Field(min_length=1)
    bgm: str = Field(default="")
    sound_effects: list[str] = Field(default_factory=list)
    subtitle_logic: str = Field(default="")
    visual_elements: list[str] = Field(default_factory=list)
    visual_element_logic: str = Field(default="")
    transition: str = Field(min_length=1)
    purpose: str = Field(min_length=1)
    localized: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_editor_ready_alignment(self):
        duration_sec = storyboard_duration_seconds(self.timestamp, self.duration)
        if duration_sec is not None:
            if duration_sec > MAX_STORYBOARD_ROW_DURATION_SEC + STORYBOARD_VOICEOVER_DURATION_TOLERANCE_SEC:
                raise ValueError(
                    f"storyboard row {self.shot_id} is {duration_sec:g}s; split rows longer than "
                    f"{MAX_STORYBOARD_ROW_DURATION_SEC:g}s into smaller visual beats"
                )
            required_duration = storyboard_voiceover_min_duration_sec(self.voiceover)
            if duration_sec + STORYBOARD_VOICEOVER_DURATION_TOLERANCE_SEC < required_duration:
                raise ValueError(
                    f"storyboard row {self.shot_id} is {duration_sec:g}s, but voiceover needs about "
                    f"{required_duration:g}s; increase duration or split the row"
                )
            natural_max_duration = storyboard_voiceover_natural_max_duration_sec(self.voiceover)
            if (
                duration_sec > natural_max_duration + STORYBOARD_VOICEOVER_DURATION_TOLERANCE_SEC
                and not storyboard_has_explicit_visual_hold(
                    self.character_action,
                    self.facial_expression,
                    self.background,
                    self.camera,
                    self.sound,
                    self.subtitle_logic,
                    self.visual_element_logic,
                    self.transition,
                    self.purpose,
                )
            ):
                raise ValueError(
                    f"storyboard row {self.shot_id} is {duration_sec:g}s, but this short voiceover only supports "
                    f"about {natural_max_duration:g}s without an explicit visual hold; shorten duration or describe "
                    "the non-speaking action"
                )
        validate_storyboard_visual_detail("camera", self.camera, self.shot_id, minimum_words=3, minimum_cjk_chars=6)
        validate_storyboard_visual_detail("character_action", self.character_action, self.shot_id)
        validate_storyboard_visual_detail("facial_expression", self.facial_expression, self.shot_id, minimum_words=3, minimum_cjk_chars=4)
        validate_storyboard_visual_detail("background", self.background, self.shot_id, minimum_words=5, minimum_cjk_chars=8)
        validate_storyboard_before_now_alignment(self.voiceover, self.character_action, self.background, self.camera, self.shot_id)
        validate_overlay_highlight_text(self.overlay, f"storyboard {self.shot_id}.overlay")
        localized_zh_overlay = localized_zh_value(self.localized, "overlay")
        if isinstance(localized_zh_overlay, str):
            validate_overlay_highlight_text(localized_zh_overlay, f"storyboard {self.shot_id}.localized.zh.overlay")
        return self


class VeoPromptSegment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    segment_index: int = Field(ge=1, le=MAX_VEO_SEGMENT_COUNT)
    timeline_start_sec: float = Field(ge=0, le=50)
    timeline_end_sec: float = Field(gt=0, le=50)
    duration_sec: float = Field(gt=0, le=MAX_VEO_SEGMENT_DURATION_SEC)
    time_range: str = Field(default="", max_length=30)
    veo_prompt: str = Field(min_length=1)
    requires_extension: bool = False
    localized: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_segment_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        prompt = (
            migrated.pop("visual_prompt", None)
            or migrated.pop("visualPrompt", None)
            or migrated.pop("segment_generation_prompt", None)
            or migrated.pop("segmentGenerationPrompt", None)
            or migrated.pop("generation_prompt", None)
            or migrated.pop("generationPrompt", None)
            or migrated.pop("prompt", None)
        )
        if prompt and not migrated.get("veo_prompt"):
            migrated["veo_prompt"] = prompt
        localized = migrated.get("localized")
        zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else None
        if zh is not None:
            legacy_prompt = zh.pop("visual_prompt", None) or zh.pop("visualPrompt", None)
            if legacy_prompt and not zh.get("veo_prompt"):
                zh["veo_prompt"] = legacy_prompt
        return migrated

    @model_validator(mode="after")
    def validate_veo_segment(self):
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("timeline_end_sec must be greater than timeline_start_sec")
        expected_duration = self.timeline_end_sec - self.timeline_start_sec
        if abs(expected_duration - self.duration_sec) > 0.05:
            raise ValueError("duration_sec must equal timeline_end_sec - timeline_start_sec")
        if self.duration_sec > MAX_VEO_SEGMENT_DURATION_SEC:
            raise ValueError("Veo 3.1 segment duration must not exceed 8 seconds")
        if not self.time_range:
            self.time_range = f"{format_prompt_seconds(self.timeline_start_sec)}s-{format_prompt_seconds(self.timeline_end_sec)}s"
        validate_veo_prompt_ready(self.veo_prompt, f"video_prompt.segments[{self.segment_index}].veo_prompt")
        hits = [term for term in VEO_PROMPT_FORBIDDEN_TERMS if term in self.veo_prompt.lower()]
        if hits:
            raise ValueError(f"Veo 3.1 prompts must not include UI/text/overlay instructions: {', '.join(sorted(hits))}")
        if any(mark in self.veo_prompt for mark in ['"', "“", "”", "「", "」", "『", "』"]):
            raise ValueError("Veo 3.1 prompts must not use quotation marks; they can be rendered as text")
        return self


class VideoPromptPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    prompt_title: str = Field(min_length=1)
    aspect_ratio: str = Field(pattern=r"^vertical 9:16$")
    target_model: str = Field(default="Veo 3.1", min_length=1)
    veo_model_id: str = Field(default="veo-3.1-generate-001", min_length=1)
    veo_generation_mode: str = Field(default=VEO_GENERATION_MODE, min_length=1)
    veo_base_duration_sec: float = Field(default=VEO_BASE_DURATION_SEC, ge=4, le=8)
    character_lock: str = Field(min_length=1)
    scene_lock: str = Field(min_length=1)
    generation_prompt: str = Field(min_length=1)
    negative_prompt: str | None = None
    overlay_exclusion_note: str = Field(min_length=1)
    consistency_notes: list[str] = Field(default_factory=list)
    target_duration_sec: float = Field(default=38, ge=25, le=50)
    veo_generation_duration_sec: float = Field(default=0, ge=0, le=50)
    segments: list[VeoPromptSegment] = Field(min_length=1, max_length=MAX_VEO_SEGMENT_COUNT)
    localized: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_video_prompt_fields(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        migrated = dict(value)
        legacy_duration = migrated.pop("seedance_generation_duration_sec", None) or migrated.pop("seedanceGenerationDurationSec", None)
        if legacy_duration is not None and not migrated.get("veo_generation_duration_sec"):
            migrated["veo_generation_duration_sec"] = legacy_duration
        return migrated

    @model_validator(mode="after")
    def validate_overlay_is_excluded(self):
        text = self.generation_prompt.lower()
        if any(term in text for term in ["overlay", "screen recording", "screenshot", "user interface"]) or any(term in self.generation_prompt for term in ["字幕", "录屏", "截图", "界面"]):
            raise ValueError("video generation prompt must not include overlay, UI, screenshot, or screen-recording instructions")
        previous_end = -1.0
        for expected_index, segment in enumerate(self.segments, start=1):
            if segment.segment_index != expected_index:
                raise ValueError("Veo 3.1 segment_index must be sequential")
            if segment.timeline_start_sec < previous_end - 0.05:
                raise ValueError("Veo 3.1 segments must not overlap on the final video timeline")
            if segment.timeline_end_sec > self.target_duration_sec + 0.05:
                raise ValueError("Veo 3.1 segment timeline must stay within target_duration_sec")
            previous_end = segment.timeline_end_sec
        total_veo_duration = sum(segment.duration_sec for segment in self.segments)
        if self.veo_generation_duration_sec <= 0:
            self.veo_generation_duration_sec = round(total_veo_duration, 2)
        elif abs(total_veo_duration - self.veo_generation_duration_sec) > 0.5:
            raise ValueError("veo_generation_duration_sec must match the sum of segment durations")
        return self


class ProductionAssetPlanEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    plan_id: str = Field(min_length=1)
    time_range: str = Field(min_length=1)
    shot_ids: list[str] = Field(default_factory=list)
    narrative_phase: str = Field(min_length=1)
    asset_type: str = Field(min_length=1)
    moras_asset_category: str = "none"
    layer: str = Field(min_length=1)
    usage_reason: str = Field(min_length=1)
    editor_note: str = Field(min_length=1)
    localized: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_asset_contract(self):
        if self.asset_type not in PRODUCTION_ASSET_TYPES:
            raise ValueError(f"unsupported production asset type: {self.asset_type}")
        if self.moras_asset_category not in MORAS_ASSET_CATEGORIES:
            raise ValueError(f"unsupported Moras asset category: {self.moras_asset_category}")
        if self.layer not in PRODUCTION_ASSET_LAYERS:
            raise ValueError(f"unsupported production asset layer: {self.layer}")
        if self.asset_type in REAL_MORAS_ASSET_TYPES and self.moras_asset_category == "none":
            raise ValueError("real Moras asset plan entries must specify moras_asset_category")
        if self.asset_type == "sound_design" and self.layer != "audio":
            raise ValueError("sound_design entries must use audio layer")
        return self


class PersonaTargetProblemProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    explicit_pains: list[str] = Field(min_length=1)
    inner_conflict: str = Field(min_length=1)
    desired_state: str = Field(min_length=1)


class PersonaTrustBasis(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_trust_angle: str = Field(min_length=1)
    usable_proof_assets: list[str] = Field(min_length=1)
    proof_insertion_rule: str = Field(min_length=1)


class PersonaScenePair(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_scene: str = Field(min_length=1)
    secondary_scenes: list[str] = Field(min_length=1)
    scene_logic: str = Field(min_length=1)


class PersonaMemorySymbols(BaseModel):
    model_config = ConfigDict(extra="forbid")

    fixed_opening_pattern: str = Field(min_length=1)
    visual_anchor: str = Field(min_length=1)
    recurring_prop: str = Field(min_length=1)
    wardrobe_anchor: str = Field(min_length=1)
    column_name: str = Field(min_length=1)


class PersonaEndorsementBoundary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    allowed_claims: list[str] = Field(min_length=1)
    banned_claims: list[str] = Field(min_length=1)
    experience_rule: str = Field(min_length=1)


class PersonaQualityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    score: int = Field(ge=0, le=100)
    checks: dict[str, bool] = Field(default_factory=dict)
    review_notes: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_required_checks(self):
        missing = sorted(PERSONA_QUALITY_CHECKS - set(self.checks))
        if missing:
            raise ValueError(f"persona_quality_score.checks missing required checks: {', '.join(missing)}")
        failed = sorted(key for key in PERSONA_QUALITY_CHECKS if self.checks.get(key) is not True)
        if failed:
            raise ValueError(f"persona_quality_score.checks failed: {', '.join(failed)}")
        if self.score < PERSONA_QUALITY_PASS_SCORE:
            raise ValueError(f"persona_quality_score.score must be >= {PERSONA_QUALITY_PASS_SCORE}")
        return self


class PersonaScriptAgentHandoff(BaseModel):
    model_config = ConfigDict(extra="forbid")

    primary_directive: str = Field(min_length=1)
    opening_scene_rules: list[str] = Field(min_length=1)
    hook_rules: list[str] = Field(min_length=1)
    proof_asset_rules: list[str] = Field(min_length=1)
    forbidden_claims: list[str] = Field(min_length=1)
    cta_rule: str = Field(min_length=1)
    compliance_note_rule: str = Field(min_length=1)


class DigitalHumanPromptAssets(BaseModel):
    model_config = ConfigDict(extra="ignore")

    visual_reference_prompt: str = Field(min_length=1)
    avatar_motion_prompt: str = Field(min_length=1)
    voice_style_prompt: str = Field(min_length=1)
    script_delivery_rules: list[str] = Field(min_length=3)
    sample_requirement: str = Field(default="no_real_sample_required", pattern=r"^no_real_sample_required$")
    synthetic_disclosure_note: str = Field(min_length=1)
    keep_consistent: list[str] = Field(min_length=3)
    avoid: list[str] = Field(min_length=3)

    @model_validator(mode="before")
    @classmethod
    def normalize_prompt_asset_aliases(cls, value: Any):
        if not isinstance(value, dict):
            return value
        aliases = {
            "visualReferencePrompt": "visual_reference_prompt",
            "visualPrompt": "visual_reference_prompt",
            "referencePrompt": "visual_reference_prompt",
            "avatarMotionPrompt": "avatar_motion_prompt",
            "motionPrompt": "avatar_motion_prompt",
            "voiceStylePrompt": "voice_style_prompt",
            "voicePrompt": "voice_style_prompt",
            "scriptDeliveryRules": "script_delivery_rules",
            "deliveryRules": "script_delivery_rules",
            "sampleRequirement": "sample_requirement",
            "syntheticDisclosureNote": "synthetic_disclosure_note",
            "keepConsistent": "keep_consistent",
        }
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            normalized[aliases.get(str(key), str(key))] = child
        normalized["sample_requirement"] = "no_real_sample_required"
        return normalized

    @model_validator(mode="after")
    def validate_prompt_assets_are_prompt_defined(self):
        payload = json_text(self.model_dump(mode="json"))
        lowered = payload.lower()
        hits = [
            term
            for term in BANNED_DIGITAL_HUMAN_SAMPLE_CLAIMS
            if term in lowered or term in payload
        ]
        if hits:
            raise ValueError(
                "digital_human_prompt_assets must be Persona-Agent-defined prompts, not sample extraction or real-person mimicry claims: "
                + ", ".join(sorted(set(hits)))
            )
        return self


class CreatorPersonaProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    persona_id: str = Field(min_length=1)
    display_name: str = Field(min_length=1)
    persona_type: str = Field(min_length=1)
    role_task: str = Field(min_length=1)
    audience_callout: str = Field(min_length=1)
    target_problem_profile: PersonaTargetProblemProfile
    trust_basis: PersonaTrustBasis
    proof_policy: str = Field(min_length=1)
    persona_scene_pair: PersonaScenePair
    recurring_scenes: list[str] = Field(min_length=1)
    memory_symbols: PersonaMemorySymbols
    content_pillars: list[str] = Field(min_length=3, max_length=5)
    hook_preferences: list[str] = Field(default_factory=list)
    cta_style: str = Field(min_length=1)
    endorsement_boundary: PersonaEndorsementBoundary
    persona_quality_score: PersonaQualityScore
    script_agent_handoff: PersonaScriptAgentHandoff
    role: str = Field(min_length=1)
    demographic: str = Field(min_length=1)
    creator_background: str = Field(min_length=1)
    personality: str = Field(min_length=1)
    trust_stance: str = Field(min_length=1)
    speech_style: str = Field(min_length=1)
    hobbies_interests: list[str] = Field(min_length=1)
    appearance: str = Field(min_length=1)
    face_hair_makeup: str = Field(min_length=1)
    wardrobe: str = Field(min_length=1)
    styling_details: str = Field(min_length=1)
    distinctive_marks_or_tattoos: str = Field(min_length=1)
    props: list[str] = Field(min_length=1)
    consistency_rules: list[str] = Field(min_length=3)
    veo_identity_string: str | None = Field(default=None, min_length=1, max_length=700)
    reference_image_prompt: str = Field(min_length=1)
    reference_image_negative_prompt: str | None = None
    digital_human_prompt_assets: DigitalHumanPromptAssets
    localized: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_reference_image_prompt(self):
        validate_reference_image_prompt_ready(self.reference_image_prompt, "creator_persona.reference_image_prompt")
        required_profile_fields = {
            "appearance": self.appearance,
            "face_hair_makeup": self.face_hair_makeup,
            "wardrobe": self.wardrobe,
            "styling_details": self.styling_details,
        }
        for field_name, value in required_profile_fields.items():
            if not has_enough_visual_detail(value, minimum_words=7, minimum_cjk_chars=12):
                raise ValueError(f"creator_persona.{field_name} is too brief for a reusable character reference")
        return self

    @model_validator(mode="after")
    def validate_operational_persona_contract(self):
        if self.persona_type not in PERSONA_TYPES:
            raise ValueError(f"creator_persona.persona_type must be one of: {', '.join(sorted(PERSONA_TYPES))}")
        if self.persona_scene_pair.primary_scene not in self.recurring_scenes:
            raise ValueError("creator_persona.recurring_scenes must include persona_scene_pair.primary_scene")
        if len(set(scene.strip().lower() for scene in self.recurring_scenes if scene.strip())) != len(self.recurring_scenes):
            raise ValueError("creator_persona.recurring_scenes must be distinct")
        banned_hits = [
            claim
            for claim in self.endorsement_boundary.banned_claims
            if claim.strip().lower() in BANNED_SCRIPT_CLAIM_PATTERNS
        ]
        if len(banned_hits) < 3:
            raise ValueError("creator_persona.endorsement_boundary.banned_claims must include core banned income/sales claims")
        handoff_claims = {claim.strip().lower() for claim in self.script_agent_handoff.forbidden_claims}
        missing_handoff_claims = [
            claim
            for claim in self.endorsement_boundary.banned_claims
            if claim.strip().lower() and claim.strip().lower() not in handoff_claims
        ]
        if missing_handoff_claims:
            raise ValueError("creator_persona.script_agent_handoff.forbidden_claims must mirror endorsement_boundary.banned_claims")
        return self


class ScriptRiskCheck(BaseModel):
    model_config = ConfigDict(extra="forbid")

    risk_level: str = Field(pattern=r"^(low|medium|high)$")
    forbidden_claims_checked: list[str] = Field(default_factory=list)
    compliance_notes: list[str] = Field(default_factory=list)
    allowed_for_video_factory: bool


class ScriptAgentItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic_plan: ScriptTopicPlan
    script: StructuredScript
    storyboard: list[StoryboardShot] = Field(min_length=1)
    creator_persona: CreatorPersonaProfile
    video_prompt: VideoPromptPackage
    production_asset_plan: list[ProductionAssetPlanEntry] = Field(min_length=1)
    risk_check: ScriptRiskCheck
    source_breakdown_ids: list[str] = Field(default_factory=list)
    source_component_summary: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_safe_claims(self):
        text = json_text(publishable_script_claim_payload(self)).lower()
        hits = [pattern for pattern in BANNED_SCRIPT_CLAIM_PATTERNS if pattern in text]
        if hits:
            raise ValueError(f"banned claims found in script output: {', '.join(sorted(hits))}")
        opening_text = json_text(
            {
                "hook": self.script.hook,
                "opening_voiceover": self.script.voiceover[:2],
                "localized_zh_hook": localized_zh_value(self.script.localized, "hook"),
                "localized_zh_opening_voiceover": localized_zh_value(self.script.localized, "voiceover"),
            }
        ).lower()
        opening_hits = [
            pattern
            for pattern in DEFAULT_NEGATIVE_OPENING_PATTERNS
            if pattern in opening_text
        ]
        if opening_hits:
            raise ValueError(
                "Hook must not default to negative failure metrics; use curiosity, creator routine, "
                f"or workflow pressure instead: {', '.join(sorted(opening_hits))}"
            )
        style_text = json_text(publishable_script_style_payload(self)).lower()
        style_hits = [pattern for pattern in BANNED_SCRIPT_STYLE_PATTERNS if pattern in style_text]
        style_hits.extend(
            pattern
            for pattern in BANNED_SCRIPT_STYLE_REGEX_PATTERNS
            if re.search(pattern, style_text)
        )
        if style_hits:
            raise ValueError(f"off-brand Script Agent copy found in script output: {', '.join(sorted(style_hits))}")
        return self

    @model_validator(mode="after")
    def validate_storyboard_granularity(self):
        if len(self.storyboard) < 5:
            raise ValueError("storyboard must contain at least 5 editor-ready rows for a 25-50s script")
        return self

    @model_validator(mode="after")
    def validate_storyboard_visual_element_diversity(self):
        repeated_en = repeated_storyboard_visual_element_signatures(
            [(shot.shot_id, shot.visual_elements) for shot in self.storyboard]
        )
        repeated_zh = repeated_storyboard_visual_element_signatures(
            [
                (shot.shot_id, localized_zh_value(shot.localized, "visual_elements"))
                for shot in self.storyboard
            ]
        )
        repeated = repeated_en or repeated_zh
        if repeated:
            signature, shot_ids = repeated
            raise ValueError(
                "storyboard visual_elements must change by shot instead of reusing the same element list; "
                f"{signature} repeats in {', '.join(shot_ids)}"
            )
        return self

    @model_validator(mode="after")
    def validate_hook_candidates_have_patterns(self):
        candidates = self.topic_plan.hook_candidates
        if len(candidates) < 6:
            raise ValueError("topic_plan.hook_candidates must include at least 6 hook variants")
        labels = {
            label
            for candidate in candidates
            for label in HOOK_PATTERN_LABELS
            if candidate.strip().lower().startswith(label)
        }
        if len(labels) < 4:
            raise ValueError("topic_plan.hook_candidates must represent at least 4 labeled hook patterns")
        attention_labels = labels & ATTENTION_FIRST_HOOK_LABELS
        if len(attention_labels) < 4:
            raise ValueError("topic_plan.hook_candidates must prioritize attention-first or psychology-first hooks")
        contrarian_count = sum(
            1 for candidate in candidates if candidate.strip().lower().startswith("[contrarian]")
        )
        if contrarian_count > 1:
            raise ValueError("topic_plan.hook_candidates must not overuse contrarian hooks")
        prohibition_count = sum(
            1
            for candidate in candidates
            if any(term in candidate.strip().lower() for term in HOOK_PROHIBITION_TERMS)
        )
        if prohibition_count > 2:
            raise ValueError("topic_plan.hook_candidates must not be dominated by prohibition-style hooks")
        if self.script.hook.strip().lower().startswith("["):
            raise ValueError("script.hook must be publishable copy without a bracketed hook pattern label")
        return self

    @model_validator(mode="after")
    def validate_ugc_voiceover_texture(self):
        hook = self.script.hook.strip().lower()
        voiceover_source_lines = [line.strip() for line in self.script.voiceover if line.strip()]
        voiceover_lines = [line.lower() for line in voiceover_source_lines]
        first_voiceover = voiceover_lines[0] if voiceover_lines else ""
        if "moras" in hook or "moras" in first_voiceover:
            raise ValueError("Hook must not start from Moras as the hero")
        brand_mentions = sum(line.count("moras") for line in voiceover_lines)
        if brand_mentions < 1:
            raise ValueError("UGC voiceover must mention Moras in spoken copy")
        if brand_mentions > 3:
            raise ValueError("UGC voiceover must not overuse Moras in spoken copy")
        voiceover_text = " ".join(voiceover_lines)
        if len(voiceover_lines) < MIN_SCRIPT_VOICEOVER_LINES:
            raise ValueError(
                "UGC voiceover must use at least 11 short spoken lines so short sentences do not remove content"
            )
        spoken_lines = script_spoken_lines_for_length(voiceover_source_lines, self.script.cta)
        total_english_words = sum(english_word_count(line) for line in spoken_lines)
        if total_english_words < MIN_SCRIPT_VOICEOVER_TOTAL_ENGLISH_WORDS:
            raise ValueError(
                "UGC voiceover is too short; use at least 90 spoken English words across short creator-native lines"
            )
        spoken_duration_sec = script_voiceover_estimated_duration_sec(spoken_lines)
        if spoken_duration_sec < MIN_SCRIPT_SPOKEN_DURATION_SEC:
            raise ValueError(
                "UGC voiceover is too short for a 35-45s ad; add more spoken beats instead of padding silence"
            )
        has_personal_context = any(term in voiceover_text for term in MORAS_RECOMMENDATION_PERSONAL_TERMS)
        has_real_workflow_context = any(term in voiceover_text for term in MORAS_RECOMMENDATION_WORKFLOW_TERMS)
        if not has_personal_context or not has_real_workflow_context:
            raise ValueError(
                "Moras recommendation must sound like creator usage of the real product-card/Create video or Custom Create workflow"
            )
        long_script_lines = [
            line
            for line in self.script.voiceover
            if english_word_count(line) > MAX_SCRIPT_VOICEOVER_ENGLISH_WORDS
        ]
        if long_script_lines:
            raise ValueError(
                "UGC script voiceover lines must stay under 14 words; group consecutive lines in storyboard only when the visual state stays the same"
            )
        return self


class ScriptAgentBatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scripts: list[ScriptAgentItem] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_batch_diversity(self):
        if len(self.scripts) < 2:
            return self
        require_distinct_batch_values("script titles", [script.script.script_title for script in self.scripts])
        require_distinct_batch_values("topic titles", [script.topic_plan.title for script in self.scripts])
        require_distinct_batch_values(
            "Chinese script titles",
            [localized_zh_field(script.script.localized, "script_title") for script in self.scripts],
            ignore_empty=True,
        )
        require_distinct_batch_values(
            "Chinese topic titles",
            [localized_zh_field(script.topic_plan.localized, "title") for script in self.scripts],
            ignore_empty=True,
        )
        require_distinct_batch_values("selected hooks", [script.script.hook for script in self.scripts])
        require_distinct_batch_values(
            "opening voiceover signatures",
            [" ".join(script.script.voiceover[:2]) for script in self.scripts],
        )
        require_distinct_batch_values(
            "source component summaries",
            [" ".join(script.source_component_summary[:4]) for script in self.scripts],
            ignore_empty=True,
        )
        for first_index, first_script in enumerate(self.scripts):
            first_body = " ".join(first_script.script.voiceover)
            for second_index, second_script in enumerate(self.scripts[first_index + 1 :], start=first_index + 2):
                second_body = " ".join(second_script.script.voiceover)
                if token_overlap_ratio(first_body, second_body) >= 0.94:
                    raise ValueError(
                        "script batch must contain substantially different voiceover bodies; "
                        f"scripts {first_index + 1} and {second_index} are too similar"
                    )
        return self


class ScriptRevisionRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    submitted_at: str = Field(min_length=1)
    previous_script: dict[str, Any] = Field(default_factory=dict)


class ScriptRecord(BaseModel):
    id: str
    status: ScriptStatus
    provider: str
    model_name: str
    script_type: str
    source_breakdown_ids: list[str] = Field(default_factory=list)
    topic_plan: dict[str, Any]
    script: dict[str, Any]
    storyboard: list[dict[str, Any]]
    creator_persona: dict[str, Any] = Field(default_factory=dict)
    video_prompt: dict[str, Any]
    production_asset_plan: list[dict[str, Any]] = Field(default_factory=list)
    risk_check: dict[str, Any]
    source_component_summary: list[str] = Field(default_factory=list)
    revision_history: list[dict[str, Any]] = Field(default_factory=list)
    error_message: str | None = None
    created_at: str
    updated_at: str


class ScriptGenerationJobRecord(BaseModel):
    id: str
    status: ScriptGenerationJobStatus
    script_count: int
    script_type: str
    source_breakdown_ids: list[str] = Field(default_factory=list)
    persona_id: str | None = None
    persona_hint: dict[str, Any] = Field(default_factory=dict)
    completed_count: int = 0
    script_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: str
    updated_at: str


class PersonaGenerationJobRecord(BaseModel):
    id: str
    status: PersonaGenerationJobStatus
    persona_count: int
    topic_or_brand_context: str
    target_audience: str
    required_demographic: str | None = None
    completed_count: int = 0
    persona_ids: list[str] = Field(default_factory=list)
    error_message: str | None = None
    created_at: str
    updated_at: str


class CreatorPersonaRecord(BaseModel):
    id: str
    status: str
    provider: str
    model_name: str
    creator_persona: dict[str, Any]
    source_script_ids: list[str] = Field(default_factory=list)
    created_at: str
    updated_at: str


class DirectorPlanStatus(StrEnum):
    READY = "ready"
    FAILED = "failed"


class DirectorGenerationJobStatus(StrEnum):
    QUEUED = "queued"
    GENERATING = "generating"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELED = "canceled"


class DirectorRenderJobStatus(StrEnum):
    QUEUED = "queued"
    RENDERING = "rendering"
    BLOCKED = "blocked"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DirectorPlanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    script_id: str = Field(min_length=1)


class DirectorPlanMetadata(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_aspect_ratio: str = Field(pattern=r"^9:16$")
    total_duration_sec: float = Field(ge=25, le=50)
    render_intent: str = Field(default="plan_only", pattern=r"^plan_only$")
    director_model: str = Field(min_length=1)
    provider_route: str = Field(min_length=1)


class DirectorCropAndScale(BaseModel):
    model_config = ConfigDict(extra="forbid")

    x_offset: float = 0
    y_offset: float = 0
    width: float = 1080
    height: float = 1920


class DirectorVideoClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    source_reference_id: str = Field(min_length=1)
    timeline_start_sec: float = Field(ge=0, le=50)
    timeline_end_sec: float = Field(gt=0, le=50)
    duration_sec: float = Field(gt=0, le=50)
    layer_role: str = Field(default="primary_visual", min_length=1)
    crop_and_scale: DirectorCropAndScale = Field(default_factory=DirectorCropAndScale)
    manual_binding_status: str = "not_required"
    manual_prompt_text: str = ""
    bound_asset_url: str | None = None
    notes: str = Field(default="")

    @model_validator(mode="after")
    def validate_video_clip(self):
        if self.source_type not in DIRECTOR_VIDEO_SOURCE_TYPES:
            raise ValueError(f"unsupported director video source_type: {self.source_type}")
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("timeline_end_sec must be greater than timeline_start_sec")
        expected_duration = self.timeline_end_sec - self.timeline_start_sec
        if abs(expected_duration - self.duration_sec) > 0.05:
            raise ValueError("duration_sec must equal timeline_end_sec - timeline_start_sec")
        if self.source_type == "veo_generation" and self.duration_sec > MAX_VEO_SEGMENT_DURATION_SEC:
            raise ValueError("Veo 3.1 clips must not exceed 8 seconds")
        if self.source_type == "seedance_generation" and self.duration_sec > 15:
            raise ValueError("Legacy Seedance clips must not exceed 15 seconds")
        if self.manual_binding_status not in DIRECTOR_MANUAL_BINDING_STATUS:
            raise ValueError(f"unsupported manual binding status: {self.manual_binding_status}")
        if self.source_type in {"veo_generation", "seedance_generation"}:
            if self.manual_binding_status == "not_required":
                self.manual_binding_status = "pending_upload"
            if not self.manual_prompt_text:
                self.manual_prompt_text = self.notes
        return self


class DirectorVideoTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str = Field(min_length=1)
    clips: list[DirectorVideoClip] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_video_track(self):
        if self.layer not in DIRECTOR_VIDEO_LAYERS:
            raise ValueError(f"unsupported director video layer: {self.layer}")
        validate_non_overlapping_intervals(
            [(clip.timeline_start_sec, clip.timeline_end_sec, clip.clip_id) for clip in self.clips],
            f"video layer {self.layer}",
        )
        return self


class DirectorAudioClip(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clip_id: str = Field(min_length=1)
    source_type: str = Field(min_length=1)
    timeline_start_sec: float = Field(ge=0, le=50)
    timeline_end_sec: float = Field(gt=0, le=50)
    duration_sec: float = Field(gt=0, le=50)
    volume_db: float = Field(default=0)
    text_content: str = Field(default="")
    voice_prompt: str = Field(default="")
    voice_asset_ref: str = Field(default="")
    notes: str = Field(default="")

    @model_validator(mode="after")
    def validate_audio_clip(self):
        if self.source_type not in DIRECTOR_AUDIO_SOURCE_TYPES:
            raise ValueError(f"unsupported director audio source_type: {self.source_type}")
        if self.timeline_end_sec <= self.timeline_start_sec:
            raise ValueError("timeline_end_sec must be greater than timeline_start_sec")
        expected_duration = self.timeline_end_sec - self.timeline_start_sec
        if abs(expected_duration - self.duration_sec) > 0.05:
            raise ValueError("duration_sec must equal timeline_end_sec - timeline_start_sec")
        prompt_payload = f"{self.voice_prompt} {self.notes}"
        prompt_lowered = prompt_payload.lower()
        prompt_hits = [
            term
            for term in BANNED_DIGITAL_HUMAN_SAMPLE_CLAIMS
            if term in prompt_lowered or term in prompt_payload
        ]
        if prompt_hits:
            raise ValueError("director audio clips must use synthetic voice direction, not sample extraction claims")
        return self


class DirectorAudioTrack(BaseModel):
    model_config = ConfigDict(extra="forbid")

    layer: str = Field(pattern=r"^audio$")
    clips: list[DirectorAudioClip] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_audio_track(self):
        if self.layer not in DIRECTOR_AUDIO_LAYERS:
            raise ValueError(f"unsupported director audio layer: {self.layer}")
        return self


class DirectorTimelineTracks(BaseModel):
    model_config = ConfigDict(extra="forbid")

    video_tracks: list[DirectorVideoTrack] = Field(min_length=1)
    audio_tracks: list[DirectorAudioTrack] = Field(default_factory=list)


class DirectorTimeline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tracks: DirectorTimelineTracks


class DirectorAssetResolution(BaseModel):
    model_config = ConfigDict(extra="forbid")

    asset_ref: str = Field(min_length=1)
    source_plan_id: str = Field(default="")
    required_asset_type: str = Field(min_length=1)
    moras_asset_category: str = "none"
    resolution_status: str = Field(min_length=1)
    resolver_note: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_asset_resolution(self):
        if self.resolution_status not in DIRECTOR_ASSET_RESOLUTION_STATUS:
            raise ValueError(f"unsupported asset resolution status: {self.resolution_status}")
        if self.moras_asset_category not in MORAS_ASSET_CATEGORIES:
            raise ValueError(f"unsupported Moras asset category: {self.moras_asset_category}")
        return self


class DirectorToolDispatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence_order: int = Field(ge=1)
    tool_name: str = Field(min_length=1)
    status: str = Field(default="planned", pattern=r"^(planned|blocked|skipped)$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    expected_output: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_tool_dispatch(self):
        if self.tool_name not in DIRECTOR_TOOL_NAMES:
            raise ValueError(f"unsupported director tool: {self.tool_name}")
        return self


class DirectorValidationSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    timeline_continuity: str = Field(min_length=1)
    layer_collision_check: str = Field(min_length=1)
    veo_limit_check: str = Field(min_length=1)
    asset_readiness: str = Field(min_length=1)
    render_scope: str = Field(min_length=1)

    @model_validator(mode="before")
    @classmethod
    def migrate_legacy_summary_fields(cls, value: Any) -> Any:
        if isinstance(value, dict) and "seedance_limit_check" in value and "veo_limit_check" not in value:
            migrated = dict(value)
            migrated["veo_limit_check"] = migrated.pop("seedance_limit_check")
            return migrated
        return value


class DirectorAgentOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: str = Field(pattern=r"^director-agent-v1\.0\.0$")
    metadata: DirectorPlanMetadata
    timeline: DirectorTimeline
    asset_resolution: list[DirectorAssetResolution] = Field(default_factory=list)
    tool_dispatches: list[DirectorToolDispatch] = Field(min_length=1)
    validation_summary: DirectorValidationSummary

    @model_validator(mode="after")
    def validate_director_plan(self):
        validate_sequential_orders([dispatch.sequence_order for dispatch in self.tool_dispatches])
        total_duration = self.metadata.total_duration_sec
        for track in self.timeline.tracks.video_tracks:
            for clip in track.clips:
                if clip.timeline_end_sec > total_duration + 0.05:
                    raise ValueError("video clips must stay within metadata.total_duration_sec")
        for track in self.timeline.tracks.audio_tracks:
            for clip in track.clips:
                if clip.timeline_end_sec > total_duration + 0.05:
                    raise ValueError("audio clips must stay within metadata.total_duration_sec")
        validate_base_track_continuity(self.timeline.tracks.video_tracks, total_duration)
        return self


class DirectorPlanRecord(BaseModel):
    id: str
    script_id: str
    status: DirectorPlanStatus
    provider: str
    model_name: str
    prompt_version: str
    metadata: dict[str, Any]
    timeline: dict[str, Any]
    asset_resolution: list[dict[str, Any]] = Field(default_factory=list)
    tool_dispatches: list[dict[str, Any]] = Field(default_factory=list)
    validation_summary: dict[str, Any]
    error_message: str | None = None
    created_at: str
    updated_at: str


class DirectorGenerationJobRecord(BaseModel):
    id: str
    status: DirectorGenerationJobStatus
    script_id: str
    director_plan_id: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class ManualFactoryAssetRecord(BaseModel):
    id: str
    director_plan_id: str
    script_id: str
    clip_id: str
    source_reference_id: str
    asset_role: str
    original_filename: str
    stored_asset_url: str
    mime_type: str
    file_size_bytes: int = Field(ge=0)
    duration_sec: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    validation_status: str = Field(default="validated")
    review_status: str = Field(default="pending_review")
    review_notes: str = Field(default="")
    reviewed_at: str | None = None
    semantic_review_status: str = Field(default="pending_review")
    semantic_review_notes: str = Field(default="")
    semantic_review_method: str = Field(default="human_prompt_match_v1")
    semantic_review_reviewer: str = Field(default="")
    semantic_reviewed_at: str | None = None
    created_at: str
    updated_at: str


class MorasAssetLibraryRecord(BaseModel):
    id: str
    asset_type: str
    moras_asset_category: str
    title: str
    original_filename: str
    stored_asset_url: str
    mime_type: str
    file_size_bytes: int = Field(ge=0)
    duration_sec: float = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)
    validation_status: str = Field(default="uploaded")
    review_status: str = Field(default="pending_review")
    review_notes: str = Field(default="")
    reviewed_at: str | None = None
    semantic_review_status: str = Field(default="pending_review")
    semantic_review_notes: str = Field(default="")
    semantic_review_method: str = Field(default="human_prompt_match_v1")
    semantic_review_reviewer: str = Field(default="")
    semantic_reviewed_at: str | None = None
    created_at: str
    updated_at: str


class AssetReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    review_status: str = Field(min_length=1)
    review_notes: str = ""

    @model_validator(mode="after")
    def validate_review_status(self):
        if self.review_status not in {"pending_review", "approved", "rejected"}:
            raise ValueError("review_status must be pending_review, approved, or rejected")
        return self


class AssetSemanticReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: str = Field(min_length=1)
    notes: str = ""
    reviewer: str = ""
    method: str = "human_prompt_match_v1"

    @model_validator(mode="after")
    def validate_status(self):
        if self.status not in {"pending_review", "passed", "failed"}:
            raise ValueError("status must be pending_review, passed, or failed")
        return self


class DirectorPlanAssetBindingRequest(BaseModel):
    asset_ref: str = Field(min_length=1)
    library_asset_id: str = Field(min_length=1)


class DirectorPlanAssetBindingRecord(BaseModel):
    id: str
    director_plan_id: str
    script_id: str
    asset_ref: str
    source_plan_id: str
    library_asset_id: str
    created_at: str
    updated_at: str


class DirectorRenderJobRecord(BaseModel):
    id: str
    director_plan_id: str
    script_id: str
    status: DirectorRenderJobStatus
    output_asset_url: str | None = None
    output_filename: str | None = None
    output_audio_url: str | None = None
    output_subtitle_url: str | None = None
    file_size_bytes: int = Field(default=0, ge=0)
    duration_sec: float = Field(default=0, ge=0)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    readiness_summary: dict[str, Any] = Field(default_factory=dict)
    qa_summary: dict[str, Any] = Field(default_factory=dict)
    qa_review_status: str = Field(default="pending_review")
    qa_review_notes: str = Field(default="")
    qa_reviewed_at: str | None = None
    error_message: str | None = None
    created_at: str
    updated_at: str


class DirectorRenderArtifactRecord(BaseModel):
    id: str
    render_job_id: str
    director_plan_id: str
    script_id: str
    artifact_type: str
    asset_url: str
    filename: str
    mime_type: str
    file_size_bytes: int = Field(default=0, ge=0)
    duration_sec: float = Field(default=0, ge=0)
    width: int = Field(default=0, ge=0)
    height: int = Field(default=0, ge=0)
    storage_status: str = Field(default="active")
    retention_expires_at: str | None = None
    deleted_at: str | None = None
    created_at: str
    updated_at: str

    @model_validator(mode="after")
    def validate_lifecycle_fields(self):
        if self.artifact_type not in {"video", "audio", "subtitle", "metadata", "caption_composition", "caption_overlay"}:
            raise ValueError("artifact_type must be video, audio, subtitle, metadata, caption_composition, or caption_overlay")
        if self.storage_status not in {"active", "retention_expired", "deleted"}:
            raise ValueError("storage_status must be active, retention_expired, or deleted")
        return self


class DirectorRenderUsageRecord(BaseModel):
    id: str
    render_job_id: str
    director_plan_id: str
    script_id: str
    input_clip_count: int = Field(default=0, ge=0)
    output_duration_sec: float = Field(default=0, ge=0)
    output_bytes: int = Field(default=0, ge=0)
    subtitle_cue_count: int = Field(default=0, ge=0)
    tts_character_count: int = Field(default=0, ge=0)
    render_engine: str
    audio_engine: str
    caption_engine: str
    created_at: str
    updated_at: str


class DirectorRenderQaReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    qa_review_status: str = Field(min_length=1)
    qa_review_notes: str = ""

    @model_validator(mode="after")
    def validate_qa_review_status(self):
        if self.qa_review_status not in {"pending_review", "approved", "rejected"}:
            raise ValueError("qa_review_status must be pending_review, approved, or rejected")
        return self


class DirectorPublishRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    render_job_id: str = Field(min_length=1)
    channel: str = Field(default="manual_upload", min_length=1)
    publish_status: str = Field(default="ready_for_upload", min_length=1)
    caption: str = ""
    scheduled_at: str | None = None
    published_url: str | None = None
    notes: str = ""

    @model_validator(mode="after")
    def validate_publish_status(self):
        if self.publish_status not in {"ready_for_upload", "published", "canceled"}:
            raise ValueError("publish_status must be ready_for_upload, published, or canceled")
        return self


class DirectorPublishRecord(BaseModel):
    id: str
    director_plan_id: str
    script_id: str
    render_job_id: str
    channel: str
    publish_status: str
    caption: str = ""
    scheduled_at: str | None = None
    published_url: str | None = None
    notes: str = ""
    created_at: str
    updated_at: str


def format_prompt_seconds(value: float) -> str:
    rounded = round(value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:g}"


def publishable_script_claim_payload(item: ScriptAgentItem) -> dict[str, Any]:
    return {
        "topic_plan": {
            "title": item.topic_plan.title,
            "target_audience": item.topic_plan.target_audience,
            "content_angle": item.topic_plan.content_angle,
            "template": item.topic_plan.template,
            "persona": item.topic_plan.persona,
            "hook_candidates": item.topic_plan.hook_candidates,
            "cta_candidates": item.topic_plan.cta_candidates,
            "recommended_platform": item.topic_plan.recommended_platform,
            "localized_zh": {
                "title": localized_zh_value(item.topic_plan.localized, "title"),
                "content_angle": localized_zh_value(item.topic_plan.localized, "content_angle"),
                "hook_candidates": localized_zh_value(item.topic_plan.localized, "hook_candidates"),
                "cta_candidates": localized_zh_value(item.topic_plan.localized, "cta_candidates"),
            },
        },
        "script": {
            "script_title": item.script.script_title,
            "target_audience": item.script.target_audience,
            "persona": item.script.persona,
            "template": item.script.template,
            "core_pain": item.script.core_pain,
            "emotional_angle": item.script.emotional_angle,
            "hook": item.script.hook,
            "voiceover": item.script.voiceover,
            "visual": item.script.visual,
            "overlay": item.script.overlay,
            "sound_effect": item.script.sound_effect,
            "proof_insert": item.script.proof_insert,
            "cta": item.script.cta,
            "localized_zh": {
                "script_title": localized_zh_value(item.script.localized, "script_title"),
                "hook": localized_zh_value(item.script.localized, "hook"),
                "voiceover": localized_zh_value(item.script.localized, "voiceover"),
                "overlay": localized_zh_value(item.script.localized, "overlay"),
                "proof_insert": localized_zh_value(item.script.localized, "proof_insert"),
                "cta": localized_zh_value(item.script.localized, "cta"),
            },
        },
        "storyboard": [
            {
                "voiceover": shot.voiceover,
                "overlay": shot.overlay,
                "localized_zh": {
                    "voiceover": localized_zh_value(shot.localized, "voiceover"),
                    "overlay": localized_zh_value(shot.localized, "overlay"),
                },
            }
            for shot in item.storyboard
        ],
        "creator_persona": {
            "display_name": item.creator_persona.display_name,
            "role": item.creator_persona.role,
            "creator_background": item.creator_persona.creator_background,
            "personality": item.creator_persona.personality,
            "trust_stance": item.creator_persona.trust_stance,
            "speech_style": item.creator_persona.speech_style,
        },
    }


def publishable_script_style_payload(item: ScriptAgentItem) -> dict[str, Any]:
    return {
        "topic_plan": {
            "title": item.topic_plan.title,
            "target_audience": item.topic_plan.target_audience,
            "content_angle": item.topic_plan.content_angle,
            "trend_source": item.topic_plan.trend_source,
            "template": item.topic_plan.template,
            "persona": item.topic_plan.persona,
            "hook_candidates": item.topic_plan.hook_candidates,
            "cta_candidates": item.topic_plan.cta_candidates,
            "localized_zh": {
                "title": localized_zh_value(item.topic_plan.localized, "title"),
                "target_audience": localized_zh_value(item.topic_plan.localized, "target_audience"),
                "content_angle": localized_zh_value(item.topic_plan.localized, "content_angle"),
                "trend_source": localized_zh_value(item.topic_plan.localized, "trend_source"),
                "template": localized_zh_value(item.topic_plan.localized, "template"),
                "persona": localized_zh_value(item.topic_plan.localized, "persona"),
                "hook_candidates": localized_zh_value(item.topic_plan.localized, "hook_candidates"),
                "cta_candidates": localized_zh_value(item.topic_plan.localized, "cta_candidates"),
            },
        },
        "script": {
            "script_title": item.script.script_title,
            "target_audience": item.script.target_audience,
            "persona": item.script.persona,
            "template": item.script.template,
            "core_pain": item.script.core_pain,
            "emotional_angle": item.script.emotional_angle,
            "hook": item.script.hook,
            "voiceover": item.script.voiceover,
            "visual": item.script.visual,
            "overlay": item.script.overlay,
            "sound_effect": item.script.sound_effect,
            "proof_insert": item.script.proof_insert,
            "cta": item.script.cta,
            "compliance_note": item.script.compliance_note,
            "localized_zh": {
                "script_title": localized_zh_value(item.script.localized, "script_title"),
                "target_audience": localized_zh_value(item.script.localized, "target_audience"),
                "persona": localized_zh_value(item.script.localized, "persona"),
                "template": localized_zh_value(item.script.localized, "template"),
                "core_pain": localized_zh_value(item.script.localized, "core_pain"),
                "emotional_angle": localized_zh_value(item.script.localized, "emotional_angle"),
                "hook": localized_zh_value(item.script.localized, "hook"),
                "voiceover": localized_zh_value(item.script.localized, "voiceover"),
                "visual": localized_zh_value(item.script.localized, "visual"),
                "overlay": localized_zh_value(item.script.localized, "overlay"),
                "sound_effect": localized_zh_value(item.script.localized, "sound_effect"),
                "proof_insert": localized_zh_value(item.script.localized, "proof_insert"),
                "cta": localized_zh_value(item.script.localized, "cta"),
                "compliance_note": localized_zh_value(item.script.localized, "compliance_note"),
            },
        },
        "storyboard": [
            {
                "camera": shot.camera,
                "character_action": shot.character_action,
                "background": shot.background,
                "props": shot.props,
                "voiceover": shot.voiceover,
                "overlay": shot.overlay,
                "subtitle_logic": shot.subtitle_logic,
                "visual_elements": shot.visual_elements,
                "visual_element_logic": shot.visual_element_logic,
                "transition": shot.transition,
                "purpose": shot.purpose,
                "localized_zh": {
                    "camera": localized_zh_value(shot.localized, "camera"),
                    "character_action": localized_zh_value(shot.localized, "character_action"),
                    "background": localized_zh_value(shot.localized, "background"),
                    "props": localized_zh_value(shot.localized, "props"),
                    "voiceover": localized_zh_value(shot.localized, "voiceover"),
                    "overlay": localized_zh_value(shot.localized, "overlay"),
                    "subtitle_logic": localized_zh_value(shot.localized, "subtitle_logic"),
                    "visual_elements": localized_zh_value(shot.localized, "visual_elements"),
                    "visual_element_logic": localized_zh_value(shot.localized, "visual_element_logic"),
                    "transition": localized_zh_value(shot.localized, "transition"),
                    "purpose": localized_zh_value(shot.localized, "purpose"),
                },
            }
            for shot in item.storyboard
        ],
        "production_asset_plan": [
            {
                "narrative_phase": asset.narrative_phase,
                "usage_reason": asset.usage_reason,
                "editor_note": asset.editor_note,
                "localized_zh": {
                    "narrative_phase": localized_zh_value(asset.localized, "narrative_phase"),
                    "usage_reason": localized_zh_value(asset.localized, "usage_reason"),
                    "editor_note": localized_zh_value(asset.localized, "editor_note"),
                },
            }
            for asset in item.production_asset_plan
        ],
        "creator_persona": {
            "persona_type": item.creator_persona.persona_type,
            "role_task": item.creator_persona.role_task,
            "audience_callout": item.creator_persona.audience_callout,
            "explicit_pains": item.creator_persona.target_problem_profile.explicit_pains,
            "inner_conflict": item.creator_persona.target_problem_profile.inner_conflict,
            "desired_state": item.creator_persona.target_problem_profile.desired_state,
            "trust_angle": item.creator_persona.trust_basis.primary_trust_angle,
            "proof_assets": item.creator_persona.trust_basis.usable_proof_assets,
            "proof_policy": item.creator_persona.proof_policy,
            "scene_logic": item.creator_persona.persona_scene_pair.scene_logic,
            "content_pillars": item.creator_persona.content_pillars,
            "cta_style": item.creator_persona.cta_style,
            "role": item.creator_persona.role,
            "creator_background": item.creator_persona.creator_background,
        },
    }


def json_text(value: Any) -> str:
    import json

    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def localized_zh_value(localized: dict[str, Any], field_name: str) -> Any:
    zh = localized.get("zh") if isinstance(localized, dict) else None
    if not isinstance(zh, dict):
        return None
    return zh.get(field_name)


def localized_zh_field(localized: dict[str, Any], field_name: str) -> str:
    value = localized_zh_value(localized, field_name)
    if isinstance(value, list):
        return " ".join(str(item) for item in value if item)
    return str(value or "")


def require_distinct_batch_values(
    label: str,
    values: list[str],
    *,
    ignore_empty: bool = False,
) -> None:
    seen: dict[str, int] = {}
    for index, value in enumerate(values, start=1):
        signature = normalize_batch_signature(value)
        if ignore_empty and not signature:
            continue
        if signature in seen:
            raise ValueError(
                f"script batch must use distinct {label}; duplicate found at positions {seen[signature]} and {index}"
            )
        seen[signature] = index


def normalize_batch_signature(value: Any) -> str:
    import re

    text = str(value or "").lower()
    text = re.sub(r"\[[^\]]+\]", " ", text)
    return re.sub(r"[\s\W_]+", " ", text).strip()


def token_overlap_ratio(first_value: str, second_value: str) -> float:
    first_tokens = batch_similarity_tokens(first_value)
    second_tokens = batch_similarity_tokens(second_value)
    if len(first_tokens) < 10 or len(second_tokens) < 10:
        return 0.0
    return len(first_tokens & second_tokens) / max(1, min(len(first_tokens), len(second_tokens)))


def batch_similarity_tokens(value: str) -> set[str]:
    import re

    return {
        token
        for token in re.findall(r"[a-z0-9]+|[\u3400-\u9fff]", str(value).lower())
        if len(token) > 1 or re.match(r"[\u3400-\u9fff]", token)
    }


def storyboard_duration_seconds(timestamp: str, duration: str) -> float | None:
    parsed_duration = parse_storyboard_seconds_value(duration)
    if parsed_duration is not None:
        return parsed_duration
    parsed_range = parse_storyboard_range_seconds(timestamp)
    if parsed_range is None:
        return None
    start_sec, end_sec = parsed_range
    return round(end_sec - start_sec, 2)


def parse_storyboard_seconds_value(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value or "").strip().lower()
    if not text:
        return None
    import re

    if "-" in text or "–" in text:
        parsed_range = parse_storyboard_range_seconds(text)
        if parsed_range:
            return round(parsed_range[1] - parsed_range[0], 2)
    match = re.search(r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds|秒)?", text)
    if not match:
        return None
    return float(match.group(1))


def parse_storyboard_range_seconds(value: Any) -> tuple[float, float] | None:
    text = str(value or "").strip().lower()
    if not text:
        return None
    import re

    match = re.search(
        r"(?:(\d{1,2}):)?(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds|秒)?\s*[-\u2013]\s*"
        r"(?:(\d{1,2}):)?(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds|秒)?",
        text,
    )
    if not match:
        return None
    start_min = float(match.group(1) or 0)
    start_value = float(match.group(2))
    end_min = float(match.group(3) or 0)
    end_value = float(match.group(4))
    start_sec = start_min * 60 + start_value
    end_sec = end_min * 60 + end_value
    if end_sec <= start_sec:
        return None
    return start_sec, end_sec


def normalize_storyboard_text(value: str) -> str:
    import re

    return re.sub(r"[\s\W_]+", " ", value.lower()).strip()


def has_enough_visual_detail(value: str, *, minimum_words: int, minimum_cjk_chars: int) -> bool:
    import re

    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", value)
    cjk_chars = re.findall(r"[\u3400-\u9fff]", value)
    return len(words) >= minimum_words or len(cjk_chars) >= minimum_cjk_chars


def english_word_count(value: str) -> int:
    import re

    return len(re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", str(value or "")))


def cjk_char_count(value: str) -> int:
    import re

    return len(re.findall(r"[\u3400-\u9fff]", str(value or "")))


def storyboard_voiceover_min_duration_sec(value: str) -> float:
    import math

    words = english_word_count(value)
    cjk_chars = cjk_char_count(value)
    english_seconds = words / 3.4 + 0.35 if words else 0.0
    cjk_seconds = cjk_chars / 2.8 + 0.6 if cjk_chars else 0.0
    required = max(english_seconds, cjk_seconds, MIN_STORYBOARD_VOICEOVER_DURATION_SEC)
    return float(math.ceil(required * 2) / 2)


def script_spoken_lines_for_length(voiceover_lines: list[str], cta: str) -> list[str]:
    spoken_lines = [str(line or "").strip() for line in voiceover_lines if str(line or "").strip()]
    normalized_existing = {normalize_storyboard_text(line) for line in spoken_lines}
    cta_text = str(cta or "").strip()
    if cta_text and normalize_storyboard_text(cta_text) not in normalized_existing:
        spoken_lines.append(cta_text)
    return spoken_lines


def script_voiceover_estimated_duration_sec(spoken_lines: list[str]) -> float:
    return round(sum(storyboard_voiceover_min_duration_sec(line) for line in spoken_lines), 2)


def storyboard_voiceover_natural_max_duration_sec(value: str) -> float:
    return min(
        MAX_STORYBOARD_ROW_DURATION_SEC,
        storyboard_voiceover_min_duration_sec(value) + STORYBOARD_VOICEOVER_HOLD_ALLOWANCE_SEC,
    )


def storyboard_has_explicit_visual_hold(*values: str) -> bool:
    text = " ".join(str(value or "") for value in values).lower()
    hold_terms = (
        "hold",
        "holds",
        "pause",
        "pauses",
        "silent",
        "silence",
        "reaction",
        "reacts",
        "linger",
        "lingers",
        "caption hold",
        "subtitle hold",
        "look into camera",
        "looks into camera",
        "stare",
        "stares",
        "停留",
        "停顿",
        "定格",
        "反应",
        "沉默",
        "无口播",
        "字幕停留",
        "镜头停留",
    )
    return any(term in text for term in hold_terms)


def sentence_chunk_count(value: str) -> int:
    import re

    return len([chunk for chunk in re.split(r"[.!?\u3002\uff01\uff1f]+", str(value or "")) if chunk.strip()])


def visual_element_signature(value: Any) -> str:
    if isinstance(value, str):
        items = [value]
    elif isinstance(value, list):
        items = [str(item) for item in value if str(item or "").strip()]
    else:
        items = []
    normalized = sorted({normalize_storyboard_text(item) for item in items if normalize_storyboard_text(item)})
    return " / ".join(normalized)


def repeated_storyboard_visual_element_signatures(
    rows: list[tuple[str, Any]],
) -> tuple[str, list[str]] | None:
    signatures: dict[str, list[str]] = {}
    for shot_id, visual_elements in rows:
        signature = visual_element_signature(visual_elements)
        if not signature:
            continue
        signatures.setdefault(signature, []).append(shot_id)
    for signature, shot_ids in signatures.items():
        if len(shot_ids) >= 3:
            return signature, shot_ids[:4]
    return None


def validate_overlay_highlight_text(value: str, field_path: str) -> None:
    text = str(value or "").strip()
    if not text:
        return
    import re

    normalized = re.sub(r"\s+", " ", text).strip().lower()
    if normalized in GENERIC_CAPTION_HIGHLIGHTS:
        raise ValueError(f"{field_path} must name a concrete caption highlight, not a generic attention cue")

    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text)
    cjk_chars = re.findall(r"[\u3400-\u9fff]", text)
    if (
        len(text) > MAX_OVERLAY_HIGHLIGHT_CHARS
        or len(words) > MAX_OVERLAY_HIGHLIGHT_ENGLISH_WORDS
        or len(cjk_chars) > MAX_OVERLAY_HIGHLIGHT_CJK_CHARS
    ):
        raise ValueError(f"{field_path} must stay short as a caption highlight, not a full subtitle transcript")


def validate_storyboard_visual_detail(
    field_name: str,
    value: str,
    shot_id: str,
    *,
    minimum_words: int = 8,
    minimum_cjk_chars: int = 12,
) -> None:
    normalized = normalize_storyboard_text(value)
    if normalized in GENERIC_STORYBOARD_TERMS:
        raise ValueError(f"storyboard {shot_id}.{field_name} is too generic for editor use")
    if not has_enough_visual_detail(value, minimum_words=minimum_words, minimum_cjk_chars=minimum_cjk_chars):
        raise ValueError(f"storyboard {shot_id}.{field_name} is too brief for editor use")


def validate_storyboard_before_now_alignment(
    voiceover: str,
    character_action: str,
    background: str,
    camera: str,
    shot_id: str,
) -> None:
    voiceover_text = voiceover.lower()
    has_english_contrast = "before" in voiceover_text and ("now" in voiceover_text or "after" in voiceover_text)
    has_chinese_contrast = "以前" in voiceover and ("现在" in voiceover or "之后" in voiceover or "如今" in voiceover)
    if not has_english_contrast and not has_chinese_contrast:
        return
    visual_text = f"{character_action} {background} {camera}".lower()
    transition_terms = [
        "now",
        "after",
        "then",
        "switch",
        "cut",
        "split",
        "comparison",
        "clean",
        "moras",
        "dashboard",
        "before-and-after",
        "现在",
        "之后",
        "如今",
        "切到",
        "切换",
        "转到",
        "对比",
        "变成",
        "干净",
        "仪表板",
    ]
    if not any(term in visual_text for term in transition_terms):
        raise ValueError(
            f"storyboard {shot_id} voiceover contrasts before/now, but visual action does not show that transition"
        )


def validate_veo_prompt_ready(value: str, field_name: str) -> None:
    if not has_enough_visual_detail(value, minimum_words=MIN_VEO_PROMPT_ENGLISH_WORDS, minimum_cjk_chars=MIN_VEO_PROMPT_CJK_CHARS):
        raise ValueError(f"{field_name} is too brief for a copyable Veo 3.1 prompt")
    lowered = value.lower()
    missing_components = [
        component
        for component, keywords in VEO_PROMPT_COMPONENT_KEYWORDS.items()
        if not any(keyword in lowered or keyword in value for keyword in keywords)
    ]
    if missing_components:
        raise ValueError(f"{field_name} is missing Veo prompt components: {', '.join(missing_components)}")


def validate_reference_image_prompt_ready(value: str, field_name: str) -> None:
    if not has_enough_visual_detail(value, minimum_words=MIN_VEO_PROMPT_ENGLISH_WORDS, minimum_cjk_chars=MIN_VEO_PROMPT_CJK_CHARS):
        raise ValueError(f"{field_name} is too brief for a copyable character reference image prompt")
    lowered = value.lower()
    required_groups = {
        "appearance": ["face", "hair", "skin", "eyes", "facial", "脸", "头发", "肤色", "眼睛", "五官"],
        "wardrobe": ["wearing", "wardrobe", "outfit", "jacket", "shirt", "服饰", "穿着", "外套", "上衣", "妆造"],
        "composition": ["portrait", "full-body", "three-quarter", "reference", "studio", "neutral background", "设定图", "参考图", "全身", "半身", "中性背景"],
        "style": ["realistic", "high fidelity", "natural light", "cinematic", "真实", "高清", "自然光", "电影感"],
    }
    missing = [
        group
        for group, keywords in required_groups.items()
        if not any(keyword in lowered or keyword in value for keyword in keywords)
    ]
    if missing:
        raise ValueError(f"{field_name} is missing character reference components: {', '.join(missing)}")


def validate_non_overlapping_intervals(intervals: list[tuple[float, float, str]], label: str) -> None:
    sorted_intervals = sorted(intervals, key=lambda item: (item[0], item[1]))
    previous_end: float | None = None
    previous_id = ""
    for start, end, item_id in sorted_intervals:
        if previous_end is not None and start < previous_end - 0.05:
            raise ValueError(f"{label} clips overlap: {previous_id} and {item_id}")
        previous_end = end
        previous_id = item_id


def validate_base_track_continuity(video_tracks: list[DirectorVideoTrack], total_duration: float) -> None:
    base_clips = [
        clip
        for track in video_tracks
        if track.layer == "base_track"
        for clip in track.clips
    ]
    if not base_clips:
        raise ValueError("director plan requires at least one base_track clip")
    sorted_clips = sorted(base_clips, key=lambda clip: (clip.timeline_start_sec, clip.timeline_end_sec))
    expected_start = 0.0
    for clip in sorted_clips:
        if abs(clip.timeline_start_sec - expected_start) > 0.1:
            raise ValueError("base_track clips must cover the full timeline without gaps")
        expected_start = clip.timeline_end_sec
    if abs(expected_start - total_duration) > 0.1:
        raise ValueError("base_track clips must end at metadata.total_duration_sec")


def validate_sequential_orders(values: list[int]) -> None:
    expected = list(range(1, len(values) + 1))
    if sorted(values) != expected:
        raise ValueError("tool_dispatches.sequence_order must be sequential starting at 1")


def find_forbidden_keys(value: Any) -> set[str]:
    found: set[str] = set()
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_RESULT_KEYS:
                found.add(key)
            found.update(find_forbidden_keys(child))
    elif isinstance(value, list):
        for child in value:
            found.update(find_forbidden_keys(child))
    return found
