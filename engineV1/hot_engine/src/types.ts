export type VideoStatus = 'uploaded' | 'analyzing' | 'ready' | 'failed'

export type VideoRecord = {
  id: string
  name: string
  durationMs: number
  width: number
  height: number
  fps?: number | null
  sizeBytes?: number
  coverUrl?: string | null
  videoUrl: string
  status: VideoStatus
  errorMessage?: string | null
  analysis?: {
    shotCount?: number | null
    shotDetection?: {
      method?: string
      label?: string
      error?: string | null
    } | null
    shots?: Array<{
      index: number
      startMs: number
      endMs: number
      durationMs: number
      thumbnailUrl?: string
    }>
    subtitleOverview?: {
      hasSubtitle: boolean
      language?: string
      density?: 'low' | 'medium' | 'high'
      sampleLines?: string[]
    } | null
    voiceOverview?: {
      hasSpeech: boolean
      summary?: string
      keywords?: string[]
      transcriptPreview?: string
    } | null
  }
  createdAt: string
}

export type ApiListResponse = {
  items: VideoRecord[]
}

export type PageName =
  | 'home'
  | 'settings'
  | 'analysis'
  | 'analysis-settings'
  | 'task3'
  | 'task3-reference'
  | 'task3-settings'
  | 'task3-result'
  | 'task3-fix'
  | 'task4'

export type DecompositionInputMode = 'direct-video' | 'structured'
export type AnalysisMethodName = 'fast' | 'deep'
export type StepModelType = 'speech-recognition' | 'image-recognition' | 'video-recognition'
export type Task3StepModelType = StepModelType | 'chat'

export type AnalysisStepSetting = {
  id: string
  name: string
  description: string
  prompt: string
  promptKey?: string
  skill: string
  skillKey?: string
  modelType?: StepModelType
}

export type AnalysisSettingsState = {
  inputMode: DecompositionInputMode
  methodName: AnalysisMethodName
  frameInterval: string
  templateHashes?: {
    promptPath?: string
    promptHash?: string
    skillPath?: string
    skillHash?: string
    stepHashes?: Record<
      string,
      {
        promptPath?: string
        promptHash?: string
        skillPath?: string
        skillHash?: string
      }
    >
  }
  fastSteps: AnalysisStepSetting[]
  directVideoDeepSteps: AnalysisStepSetting[]
  structuredDeepSteps: AnalysisStepSetting[]
  deepSteps?: AnalysisStepSetting[]
}

export type AnalysisDefaultTemplateResponse = {
  promptPath: string
  prompt: string
  promptHash: string
  skillPath: string
  skill: string
  skillHash: string
  steps?: Array<{
    stepId: string
    promptPath: string
    prompt: string
    promptHash: string
    skillPath: string
    skill: string
    skillHash: string
  }>
}

export type AnalysisShot = {
  index: number
  startMs: number
  endMs: number
  durationMs: number
  thumbnailUrl?: string | null
}

export type AnalysisResult = {
  shotCount: number
  shotDetection?: {
    method?: string
    label?: string
    error?: string | null
  } | null
  shots: AnalysisShot[]
  subtitleOverview: {
    hasSubtitle: boolean
    language?: string | null
    density?: 'low' | 'medium' | 'high' | null
    sampleLines?: string[]
  } | null
  voiceOverview: {
    hasSpeech: boolean
    summary?: string | null
    keywords?: string[]
    transcriptPreview?: string | null
  } | null
  summary?: string | null
}

export type AnalysisApiResponse = {
  cached: boolean
  cacheKey: string | null
  videoId: string
  videoName: string
  coverUrl?: string | null
  videoUrl?: string | null
  methodName: string
  frameInterval: number
  persistedToDb: boolean
  analysis: AnalysisResult
  decomposition?: {
    outputPath?: string
    methodName?: string
    inputMode?: string
    model?: string
    overview?: unknown
    rawOverview?: string
    startedAt?: string
    completedAt?: string
    steps?: Array<{
      index?: number
      id?: string
      name?: string
      modelType?: string
      model?: string
      provider?: string
      promptKey?: string
      skillKey?: string
      output?: unknown
      rawOutput?: string
      completedAt?: string
    }>
  }
  cachedAt: string
}

export type Task3Material = {
  id: string
  type: 'image' | 'video' | 'text' | 'audio'
  name: string
  url?: string
  text?: string | null
  tags?: string[]
  usageHint?: string
  notes?: string
}

export type Task3Draft = {
  topic: string
  sellingPointsText: string
  copyText: string
  targetAudience: string
  platform: string
  stylePreference: string
  materials: Task3Material[]
}

export type Task3InputRecord = {
  id: string
  topic: string
  sellingPoints: string[]
  copyText?: string | null
  targetAudience?: string | null
  platform?: string | null
  stylePreference?: string | null
  materials: Task3Material[]
  sourceAnalysisVideoIds: string[]
  createdAt: string
  updatedAt: string
}

export type Task3AnalysisResult = {
  id: string
  inputId: string
  status: 'pending' | 'analyzing' | 'ready' | 'failed'
  materialInventory: Array<{
    materialId: string
    materialName?: string
    materialType?: string
    summary?: string
    url?: string | null
    detectedObjects?: string[]
    detectedScenes?: string[]
    detectedText?: string[]
    audioSummary?: string
    usableSegments?: Array<{
      start: number
      end: number
      label: string
      recommendedSlots: string[]
      confidence?: number
    }>
    recommendedSlots?: Array<{
      slotId: string
      slotName: string
      reason: string
      confidence: number
    }>
    usableForSlots?: string[]
    confidence?: number
    quality?: Record<string, unknown>
    manualTags?: string[]
    usageHint?: string
    notes?: string
  }>
  slotMatches: Array<{
    slotId: string
    slotName: string
    requiredMaterial: string
    matchedMaterialIds: string[]
    status: 'covered' | 'partial' | 'missing'
    confidence?: number
    reason: string
  }>
  gaps: Array<{
    id: string
    slotId: string
    name: string
    severity: 'low' | 'medium' | 'high'
    reason: string
    suggestedFixes: string[]
    resolution?: string
  }>
  editingHints?: Array<{
    type: string
    materialId?: string | null
    operation: string
    targetSlot: string
    reason: string
  }>
  analysisMode?: string
  summary: string
  createdAt: string
}

export type Task3SettingStep = {
  id: string
  name: string
  modelType: Task3StepModelType
  skillKey: string
  prompt: string
}

export type Task3SettingsState = {
  targetMode: string
  inputMode: 'structured' | 'multimodal'
  materialUnderstanding: {
    mode: 'fast' | 'standard' | 'deep'
    enabledAnalyzers: {
      metadata: boolean
      sceneDetect: boolean
      ocr: boolean
      asr: boolean
      vision: boolean
      audioMood: boolean
    }
    slotMatchingStrategy: 'rule-first' | 'llm-first' | 'hybrid'
    confidenceThreshold: number
    defaultGapFixes: Array<'text_fill' | 'packaging_fill' | 'reuse_crop' | 'structure_reorder' | 'aigc_generate'>
  }
  steps: Task3SettingStep[]
}

export type Task4Result = {
  title: string
  summary: string
  videoStatus: string
  generatedAt: string
}

export type SettingsFormState = {
  speechRecognitionApiUrl: string
  speechRecognitionAppKey: string
  speechRecognitionApiKey: string
  speechRecognitionModel: string
  ocrRecognitionApiUrl: string
  ocrRecognitionApiKey: string
  ocrRecognitionModel: string
  videoRecognitionApiUrl: string
  videoRecognitionApiKey: string
  videoRecognitionModel: string
  chatApiUrl: string
  chatApiKey: string
  chatModel: string
}

export type SettingsApiItem = {
  key: keyof SettingsFormState
  label: string
  envName: string
  description: string
  value: string
}

export type SettingsApiResponse = {
  envPath: string
  items: SettingsApiItem[]
}
