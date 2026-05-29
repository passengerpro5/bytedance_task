import type { AnalysisSettingsState, SettingsFormState, Task3Draft, Task3SettingsState } from './types'

export const DEFAULT_FAST_PROMPT_PATH = 'prompts/fast-video-structure.txt'
export const DEFAULT_FAST_SKILL_PATH = 'skills/fast-video-structure.md'
export const DEFAULT_DEEP_SHOT_PROMPT_PATH = 'prompts/deep-shot-rhythm-structure.txt'
export const DEFAULT_DEEP_SHOT_SKILL_PATH = 'skills/deep-shot-rhythm-structure.md'
export const DEFAULT_DEEP_SCRIPT_PROMPT_PATH = 'prompts/deep-script-paragraph-structure.txt'
export const DEFAULT_DEEP_SCRIPT_SKILL_PATH = 'skills/deep-script-paragraph-structure.md'
export const DEFAULT_DEEP_PACKAGE_PROMPT_PATH = 'prompts/deep-packaging-structure.txt'
export const DEFAULT_DEEP_PACKAGE_SKILL_PATH = 'skills/deep-packaging-structure.md'
export const DEFAULT_STRUCTURED_VISUAL_PROMPT_PATH = 'prompts/structured-visual-structure.txt'
export const DEFAULT_STRUCTURED_VISUAL_SKILL_PATH = 'skills/structured-visual-structure.md'
export const DEFAULT_STRUCTURED_SPEECH_PROMPT_PATH = 'prompts/structured-speech-script-structure.txt'
export const DEFAULT_STRUCTURED_SPEECH_SKILL_PATH = 'skills/structured-speech-script-structure.md'
export const DEFAULT_STRUCTURED_PACKAGE_PROMPT_PATH = 'prompts/structured-packaging-structure.txt'
export const DEFAULT_STRUCTURED_PACKAGE_SKILL_PATH = 'skills/structured-packaging-structure.md'

export const EMPTY_TASK3_DRAFT: Task3Draft = {
  topic: '',
  sellingPointsText: '',
  copyText: '',
  targetAudience: '',
  platform: '',
  stylePreference: '',
  materials: [],
}

export const EMPTY_TASK3_SETTINGS: Task3SettingsState = {
  targetMode: 'material-fit',
  inputMode: 'structured',
  materialUnderstanding: {
    mode: 'standard',
    enabledAnalyzers: {
      metadata: true,
      sceneDetect: true,
      ocr: true,
      asr: true,
      vision: true,
      audioMood: false,
    },
    slotMatchingStrategy: 'hybrid',
    confidenceThreshold: 0.65,
    defaultGapFixes: ['text_fill', 'packaging_fill', 'reuse_crop', 'structure_reorder'],
  },
  steps: [
    {
      id: 'material-inventory',
      name: '素材盘点',
      modelType: 'image-recognition',
      skillKey: 'material-inventory.md',
      prompt: '识别用户素材中包含的商品、人物、场景、文字和可用片段。',
    },
    {
      id: 'slot-matching',
      name: '结构槽位匹配',
      modelType: 'chat',
      skillKey: 'slot-matching.md',
      prompt: '根据样例视频结构，判断当前素材可以覆盖哪些结构槽位。',
    },
    {
      id: 'gap-detection',
      name: '素材缺口识别',
      modelType: 'chat',
      skillKey: 'gap-detection.md',
      prompt: '识别缺失的开头吸引镜头、商品特写、使用过程、对比镜头和 CTA 镜头。',
    },
  ],
}

export const EMPTY_ANALYSIS_SETTINGS: AnalysisSettingsState = {
  inputMode: 'direct-video',
  methodName: 'fast',
  frameInterval: '5',
  fastSteps: [
    {
      id: 'fast-summary',
      name: '一次性概览',
      description: '使用视频理解模型一次性拆解脚本段落、节奏结构、包装结构和可迁移槽位。',
      prompt: '',
      promptKey: DEFAULT_FAST_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_FAST_SKILL_PATH,
      modelType: 'video-recognition',
    },
  ],
  directVideoDeepSteps: [
    {
      id: 'deep-shot',
      name: '镜头/节奏结构拆解',
      description: '先建立镜头时间线、节奏曲线、高潮位置和可迁移镜头槽位。',
      prompt: '',
      promptKey: DEFAULT_DEEP_SHOT_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_DEEP_SHOT_SKILL_PATH,
      modelType: 'image-recognition',
    },
    {
      id: 'deep-copy',
      name: '脚本/段落结构拆解',
      description: '结合前序时间锚点分析 hook、中段展开、高潮和 CTA。',
      prompt: '',
      promptKey: DEFAULT_DEEP_SCRIPT_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_DEEP_SCRIPT_SKILL_PATH,
      modelType: 'speech-recognition',
    },
    {
      id: 'deep-package',
      name: '包装结构拆解',
      description: '分析标题条、字幕密度、转场和强调元素。',
      prompt: '',
      promptKey: DEFAULT_DEEP_PACKAGE_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_DEEP_PACKAGE_SKILL_PATH,
      modelType: 'image-recognition',
    },
  ],
  structuredDeepSteps: [
    {
      id: 'structured-visual',
      name: '视觉/镜头结构拆解',
      description: '基于镜头段、关键帧和 OCR 信息拆解画面结构与节奏。',
      prompt: '',
      promptKey: DEFAULT_STRUCTURED_VISUAL_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_STRUCTURED_VISUAL_SKILL_PATH,
      modelType: 'image-recognition',
    },
    {
      id: 'structured-speech',
      name: '语音/脚本结构拆解',
      description: '基于 ASR、字幕和文案文本拆解 hook、中段展开和 CTA。',
      prompt: '',
      promptKey: DEFAULT_STRUCTURED_SPEECH_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_STRUCTURED_SPEECH_SKILL_PATH,
      modelType: 'speech-recognition',
    },
    {
      id: 'structured-package',
      name: '结构化包装拆解',
      description: '基于 OCR、关键帧和视觉检测结果拆解字幕、标题条、贴纸和转场。',
      prompt: '',
      promptKey: DEFAULT_STRUCTURED_PACKAGE_PROMPT_PATH,
      skill: '',
      skillKey: DEFAULT_STRUCTURED_PACKAGE_SKILL_PATH,
      modelType: 'image-recognition',
    },
  ],
}

export const EMPTY_SETTINGS_FORM: SettingsFormState = {
  speechRecognitionApiUrl: '',
  speechRecognitionAppKey: '',
  speechRecognitionApiKey: '',
  speechRecognitionModel: '',
  ocrRecognitionApiUrl: '',
  ocrRecognitionApiKey: '',
  ocrRecognitionModel: '',
  videoRecognitionApiUrl: '',
  videoRecognitionApiKey: '',
  videoRecognitionModel: '',
  chatApiUrl: '',
  chatApiKey: '',
  chatModel: '',
}
