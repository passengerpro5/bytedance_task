export type JsonPrimitive = string | number | boolean | null;
export type JsonObject = { [key: string]: JsonValue | undefined };
export type JsonValue = JsonPrimitive | JsonValue[] | JsonObject;

export type SocialVideoStatus = "pending" | "importing" | "running" | "succeeded" | "failed" | string;

export type SourceVideo = JsonObject & {
  originalUrl?: string;
  importedVideoUrl?: string;
  sourceUrl?: string;
  title?: string | null;
  platform?: string | null;
  creatorHandle?: string | null;
  durationSeconds?: number | null;
  observedMetrics?: JsonObject;
  visibleMetrics?: JsonObject;
  sourceNotes?: string;
  contentSummary?: string;
};

export type Classification = JsonObject & {
  taxonomyVersion?: string;
  hookType?: string | null;
  emotionFactors?: JsonValue[];
  personaFactors?: JsonValue[];
  sceneFactors?: JsonValue[];
  conflictFactors?: JsonValue[];
  painFactors?: JsonValue[];
  itchFactors?: JsonValue[];
  valueFactors?: JsonValue[];
  proofFactors?: JsonValue[];
  ctaFactors?: JsonValue[];
  structureFactors?: JsonValue[];
  visualRhythmFactors?: JsonValue[];
  audienceSegments?: JsonValue[];
  generalTemplates?: JsonValue[];
  verticalTemplates?: JsonValue[];
  secondaryCandidates?: JsonValue[];
  confidence?: number;
  evidence?: JsonValue[];
  standardId?: string;
  factorReasoning?: string;
  missingInputs?: JsonValue[];
};

export type OpeningHook = JsonObject & {
  timeRange?: string;
  observedContent?: string;
  performanceFunction?: string;
};

export type DecompositionSegment = JsonObject & {
  segmentNo?: number;
  stepNo?: number;
  startSecond?: number | null;
  endSecond?: number | null;
  timeRange?: string;
  role?: string;
  content?: string;
  technique?: string;
  observedContent?: string;
  viewerJob?: string;
  executionNotes?: string;
};

export type Decomposition = JsonObject & {
  oneSentenceSummary?: string;
  hook?: string;
  openingHook?: OpeningHook;
  narrativeStructure?: JsonValue[];
  contentStructure?: JsonValue[];
  segments?: JsonValue[];
  keyTakeaways?: JsonValue[];
  visualLanguage?: string;
  audioLanguage?: string;
  interactionOrCta?: string;
  performanceLogic?: string;
};

export type ScriptAgentBridge = JsonObject & {
  reusablePattern?: string;
  scriptAgentInstructions?: JsonValue[];
  variablesToCollect?: JsonValue[];
  doNotCopy?: JsonValue[];
  adaptationNotes?: JsonValue[];
  usableInsights?: JsonValue[];
  doNotGenerate?: JsonValue[];
  reservedStandardIds?: JsonValue[];
  missingInputs?: JsonValue[];
};

export type SocialVideoAnalysis = {
  id: string;
  status: SocialVideoStatus;
  provider?: string;
  reusedExisting?: boolean;
  errorMessage: string | null;
  sourceVideo: SourceVideo | null;
  classification: Classification | null;
  decomposition: Decomposition | null;
  structureProtocol: JsonValue | null;
  scriptAgentBridge: ScriptAgentBridge | null;
  referenceStoryboard: ScriptStoryboardShot[];
  createdAt: string;
  updatedAt: string;
};

export type ScriptTopicPlan = JsonObject & {
  title?: string;
  targetAudience?: string;
  contentAngle?: string;
  trendSource?: string;
  template?: string;
  persona?: string;
  hookCandidates?: JsonValue[];
  ctaCandidates?: JsonValue[];
  recommendedPlatform?: string;
  morasRelevanceScore?: number;
  riskScore?: number;
};

export type StructuredScript = JsonObject & {
  scriptTitle?: string;
  targetAudience?: string;
  persona?: string;
  template?: string;
  corePain?: string;
  emotionalAngle?: string;
  hook?: string;
  voiceover?: JsonValue[];
  visual?: string;
  overlay?: JsonValue[];
  soundEffect?: string;
  proofInsert?: string;
  cta?: string;
  complianceNote?: string;
  version?: string;
};

export type ScriptStoryboardShot = JsonObject & {
  shotId?: string;
  timestamp?: string;
  duration?: string;
  camera?: string;
  characterAction?: string;
  facialExpression?: string;
  background?: string;
  props?: JsonValue[];
  voiceover?: string;
  overlay?: string;
  sound?: string;
  bgm?: string;
  soundEffects?: JsonValue[];
  subtitleLogic?: string;
  visualElements?: JsonValue[];
  visualElementLogic?: string;
  transition?: string;
  purpose?: string;
};

export type CreatorPersona = JsonObject & {
  personaId?: string;
  displayName?: string;
  personaType?: string;
  roleTask?: string;
  audienceCallout?: string;
  targetProblemProfile?: JsonObject;
  trustBasis?: JsonObject;
  proofPolicy?: string;
  personaScenePair?: JsonObject;
  recurringScenes?: JsonValue[];
  memorySymbols?: JsonObject;
  contentPillars?: JsonValue[];
  hookPreferences?: JsonValue[];
  ctaStyle?: string;
  endorsementBoundary?: JsonObject;
  personaQualityScore?: JsonObject;
  scriptAgentHandoff?: JsonObject;
  role?: string;
  demographic?: string;
  creatorBackground?: string;
  personality?: string;
  trustStance?: string;
  speechStyle?: string;
  hobbiesInterests?: JsonValue[];
  appearance?: string;
  faceHairMakeup?: string;
  wardrobe?: string;
  stylingDetails?: string;
  distinctiveMarksOrTattoos?: string;
  props?: JsonValue[];
  consistencyRules?: JsonValue[];
  veoIdentityString?: string;
  referenceImagePrompt?: string;
  digitalHumanPromptAssets?: JsonObject;
};

export type ProductionAssetPlanEntry = JsonObject & {
  planId?: string;
  timeRange?: string;
  shotIds?: JsonValue[];
  narrativePhase?: string;
  assetType?: string;
  morasAssetCategory?: string;
  layer?: string;
  usageReason?: string;
  editorNote?: string;
};

export type VideoPromptPackage = JsonObject & {
  promptTitle?: string;
  aspectRatio?: string;
  targetModel?: string;
  veoModelId?: string;
  veoGenerationMode?: string;
  veoBaseDurationSec?: number;
  characterLock?: string;
  sceneLock?: string;
  generationPrompt?: string;
  overlayExclusionNote?: string;
  consistencyNotes?: JsonValue[];
  targetDurationSec?: number;
  veoGenerationDurationSec?: number;
  seedanceGenerationDurationSec?: number;
  segments?: JsonValue[];
};

export type ScriptRiskCheck = JsonObject & {
  riskLevel?: string;
  forbiddenClaimsChecked?: JsonValue[];
  complianceNotes?: JsonValue[];
  allowedForVideoFactory?: boolean;
};

export type ScriptRecord = {
  id: string;
  status: string;
  provider: string;
  modelName: string;
  scriptType: string;
  sourceBreakdownIds: JsonValue[];
  topicPlan: ScriptTopicPlan;
  script: StructuredScript;
  storyboard: ScriptStoryboardShot[];
  creatorPersona: CreatorPersona;
  videoPrompt: VideoPromptPackage;
  productionAssetPlan: ProductionAssetPlanEntry[];
  riskCheck: ScriptRiskCheck;
  sourceComponentSummary: JsonValue[];
  revisionHistory: JsonObject[];
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ScriptGenerationJobStatus = "queued" | "generating" | "succeeded" | "failed" | string;

export type ScriptGenerationJobRecord = {
  id: string;
  status: ScriptGenerationJobStatus;
  scriptCount: number;
  scriptType: string;
  sourceBreakdownIds: JsonValue[];
  personaId?: string | null;
  personaHint?: JsonObject;
  completedCount: number;
  scriptIds: JsonValue[];
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type PersonaGenerationJobStatus = "queued" | "generating" | "succeeded" | "failed" | string;

export type PersonaGenerationJobRecord = {
  id: string;
  status: PersonaGenerationJobStatus;
  personaCount: number;
  topicOrBrandContext: string;
  targetAudience: string;
  requiredDemographic: string | null;
  completedCount: number;
  personaIds: JsonValue[];
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type CreatorPersonaRecord = {
  id: string;
  status: string;
  provider: string;
  modelName: string;
  creatorPersona: CreatorPersona;
  sourceScriptIds: JsonValue[];
  createdAt: string;
  updatedAt: string;
};

export type DirectorPlanRecord = {
  id: string;
  scriptId: string;
  status: string;
  provider: string;
  modelName: string;
  promptVersion: string;
  metadata: JsonObject;
  timeline: JsonObject;
  assetResolution: JsonObject[];
  toolDispatches: JsonObject[];
  validationSummary: JsonObject;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type DirectorGenerationJobStatus = "queued" | "generating" | "succeeded" | "failed" | "canceled" | string;

export type DirectorGenerationJobRecord = {
  id: string;
  status: DirectorGenerationJobStatus;
  scriptId: string;
  directorPlanId: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type ManualFactoryAssetRecord = {
  id: string;
  directorPlanId: string;
  scriptId: string;
  clipId: string;
  sourceReferenceId: string;
  assetRole: string;
  originalFilename: string;
  storedAssetUrl: string;
  mimeType: string;
  fileSizeBytes: number;
  durationSec: number;
  width: number;
  height: number;
  validationStatus: string;
  reviewStatus: string;
  reviewNotes: string;
  reviewedAt: string | null;
  semanticReviewStatus: string;
  semanticReviewNotes: string;
  semanticReviewMethod: string;
  semanticReviewReviewer: string;
  semanticReviewedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type MorasAssetLibraryRecord = {
  id: string;
  assetType: string;
  morasAssetCategory: string;
  title: string;
  originalFilename: string;
  storedAssetUrl: string;
  mimeType: string;
  fileSizeBytes: number;
  durationSec: number;
  width: number;
  height: number;
  validationStatus: string;
  reviewStatus: string;
  reviewNotes: string;
  reviewedAt: string | null;
  semanticReviewStatus: string;
  semanticReviewNotes: string;
  semanticReviewMethod: string;
  semanticReviewReviewer: string;
  semanticReviewedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type DirectorPlanAssetBindingRecord = {
  id: string;
  directorPlanId: string;
  scriptId: string;
  assetRef: string;
  sourcePlanId: string;
  libraryAssetId: string;
  createdAt: string;
  updatedAt: string;
};

export type DirectorRenderJobStatus =
  | "queued"
  | "rendering"
  | "blocked"
  | "succeeded"
  | "failed"
  | string;

export type DirectorRenderJobRecord = {
  id: string;
  directorPlanId: string;
  scriptId: string;
  status: DirectorRenderJobStatus;
  outputAssetUrl: string | null;
  outputFilename: string | null;
  outputAudioUrl: string | null;
  outputSubtitleUrl: string | null;
  fileSizeBytes: number;
  durationSec: number;
  width: number;
  height: number;
  readinessSummary: JsonObject;
  qaSummary: JsonObject;
  qaReviewStatus: string;
  qaReviewNotes: string;
  qaReviewedAt: string | null;
  errorMessage: string | null;
  createdAt: string;
  updatedAt: string;
};

export type DirectorRenderArtifactRecord = {
  id: string;
  renderJobId: string;
  directorPlanId: string;
  scriptId: string;
  artifactType: "video" | "audio" | "subtitle" | "metadata" | "caption_composition" | "caption_overlay" | string;
  assetUrl: string;
  filename: string;
  mimeType: string;
  fileSizeBytes: number;
  durationSec: number;
  width: number;
  height: number;
  storageStatus: "active" | "retention_expired" | "deleted" | string;
  retentionExpiresAt: string | null;
  deletedAt: string | null;
  createdAt: string;
  updatedAt: string;
};

export type DirectorRenderUsageRecord = {
  id: string;
  renderJobId: string;
  directorPlanId: string;
  scriptId: string;
  inputClipCount: number;
  outputDurationSec: number;
  outputBytes: number;
  subtitleCueCount: number;
  ttsCharacterCount: number;
  renderEngine: string;
  audioEngine: string;
  captionEngine: string;
  createdAt: string;
  updatedAt: string;
};

export type DirectorPublishRecord = {
  id: string;
  directorPlanId: string;
  scriptId: string;
  renderJobId: string;
  channel: string;
  publishStatus: string;
  caption: string;
  scheduledAt: string | null;
  publishedUrl: string | null;
  notes: string;
  createdAt: string;
  updatedAt: string;
};

export type ApiBreakdownRecord = {
  id: string;
  status: SocialVideoStatus;
  provider?: string;
  reused_existing?: boolean;
  error_message?: string | null;
  source_video?: JsonValue | null;
  classification?: JsonValue | null;
  decomposition?: JsonValue | null;
  structure_protocol?: JsonValue | null;
  script_agent_bridge?: JsonValue | null;
  reference_storyboard?: JsonValue[] | null;
  created_at: string;
  updated_at: string;
};

export type ApiScriptRecord = {
  id: string;
  status: string;
  provider: string;
  model_name: string;
  script_type: string;
  source_breakdown_ids?: JsonValue[];
  topic_plan?: JsonValue;
  script?: JsonValue;
  storyboard?: JsonValue;
  creator_persona?: JsonValue;
  video_prompt?: JsonValue;
  production_asset_plan?: JsonValue[];
  risk_check?: JsonValue;
  source_component_summary?: JsonValue[];
  revision_history?: JsonValue[];
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiScriptGenerationJobRecord = {
  id: string;
  status: ScriptGenerationJobStatus;
  script_count: number;
  script_type: string;
  source_breakdown_ids?: JsonValue[];
  persona_id?: string | null;
  persona_hint?: JsonValue;
  completed_count?: number;
  script_ids?: JsonValue[];
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiPersonaGenerationJobRecord = {
  id: string;
  status: PersonaGenerationJobStatus;
  persona_count: number;
  topic_or_brand_context: string;
  target_audience: string;
  required_demographic?: string | null;
  completed_count: number;
  persona_ids?: JsonValue[];
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiCreatorPersonaRecord = {
  id: string;
  status: string;
  provider: string;
  model_name: string;
  creator_persona?: JsonValue;
  source_script_ids?: JsonValue[];
  created_at: string;
  updated_at: string;
};

export type ApiDirectorPlanRecord = {
  id: string;
  script_id: string;
  status: string;
  provider: string;
  model_name: string;
  prompt_version: string;
  metadata?: JsonValue;
  timeline?: JsonValue;
  asset_resolution?: JsonValue[];
  tool_dispatches?: JsonValue[];
  validation_summary?: JsonValue;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiDirectorGenerationJobRecord = {
  id: string;
  status: DirectorGenerationJobStatus;
  script_id: string;
  director_plan_id?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiManualFactoryAssetRecord = {
  id: string;
  director_plan_id: string;
  script_id: string;
  clip_id: string;
  source_reference_id: string;
  asset_role: string;
  original_filename: string;
  stored_asset_url: string;
  mime_type: string;
  file_size_bytes: number;
  duration_sec: number;
  width: number;
  height: number;
  validation_status: string;
  review_status: string;
  review_notes: string;
  reviewed_at?: string | null;
  semantic_review_status?: string;
  semantic_review_notes?: string;
  semantic_review_method?: string;
  semantic_review_reviewer?: string;
  semantic_reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiMorasAssetLibraryRecord = {
  id: string;
  asset_type: string;
  moras_asset_category: string;
  title: string;
  original_filename: string;
  stored_asset_url: string;
  mime_type: string;
  file_size_bytes: number;
  duration_sec: number;
  width: number;
  height: number;
  validation_status: string;
  review_status: string;
  review_notes: string;
  reviewed_at?: string | null;
  semantic_review_status?: string;
  semantic_review_notes?: string;
  semantic_review_method?: string;
  semantic_review_reviewer?: string;
  semantic_reviewed_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiDirectorPlanAssetBindingRecord = {
  id: string;
  director_plan_id: string;
  script_id: string;
  asset_ref: string;
  source_plan_id: string;
  library_asset_id: string;
  created_at: string;
  updated_at: string;
};

export type ApiDirectorRenderJobRecord = {
  id: string;
  director_plan_id: string;
  script_id: string;
  status: DirectorRenderJobStatus;
  output_asset_url?: string | null;
  output_filename?: string | null;
  output_audio_url?: string | null;
  output_subtitle_url?: string | null;
  file_size_bytes: number;
  duration_sec: number;
  width: number;
  height: number;
  readiness_summary?: JsonValue;
  qa_summary?: JsonValue;
  qa_review_status?: string;
  qa_review_notes?: string;
  qa_reviewed_at?: string | null;
  error_message?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiDirectorRenderArtifactRecord = {
  id: string;
  render_job_id: string;
  director_plan_id: string;
  script_id: string;
  artifact_type: string;
  asset_url: string;
  filename: string;
  mime_type: string;
  file_size_bytes: number;
  duration_sec: number;
  width: number;
  height: number;
  storage_status: string;
  retention_expires_at?: string | null;
  deleted_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type ApiDirectorRenderUsageRecord = {
  id: string;
  render_job_id: string;
  director_plan_id: string;
  script_id: string;
  input_clip_count: number;
  output_duration_sec: number;
  output_bytes: number;
  subtitle_cue_count: number;
  tts_character_count: number;
  render_engine: string;
  audio_engine: string;
  caption_engine: string;
  created_at: string;
  updated_at: string;
};

export type ApiDirectorPublishRecord = {
  id: string;
  director_plan_id: string;
  script_id: string;
  render_job_id: string;
  channel: string;
  publish_status: string;
  caption?: string;
  scheduled_at?: string | null;
  published_url?: string | null;
  notes?: string;
  created_at: string;
  updated_at: string;
};
