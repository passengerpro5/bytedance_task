import { EMPTY_ANALYSIS_SETTINGS, EMPTY_SETTINGS_FORM, EMPTY_TASK3_SETTINGS } from './defaults'
import type {
  AnalysisMethodName,
  AnalysisSettingsState,
  AnalysisStepSetting,
  DecompositionInputMode,
  SettingsApiItem,
  SettingsFormState,
  StepModelType,
  Task3SettingsState,
  VideoStatus,
} from './types'

export function mapSettingsItemsToForm(items: SettingsApiItem[]): SettingsFormState {
  const nextForm = { ...EMPTY_SETTINGS_FORM }

  for (const item of items) {
    nextForm[item.key] = item.value ?? ''
  }

  return nextForm
}

export function normalizeAnalysisMethodName(methodName?: string | null): AnalysisMethodName {
  if (methodName === 'fast' || methodName === 'deep') {
    return methodName
  }

  return 'fast'
}

export function formatAnalysisMethodLabel(methodName: string): string {
  switch (methodName) {
    case 'fast':
      return '快速拆解'
    case 'deep':
      return '深度拆解'
    case 'upload_auto_shot_detection':
      return '上传自动解析'
    default:
      return '快速拆解'
  }
}

export function readSavedAnalysisSettings(): AnalysisSettingsState {
  const savedSettings = window.localStorage.getItem('hot-engine-analysis-settings')

  if (!savedSettings) {
    return EMPTY_ANALYSIS_SETTINGS
  }

  try {
    const parsed = JSON.parse(savedSettings) as Partial<AnalysisSettingsState>

    return {
      ...EMPTY_ANALYSIS_SETTINGS,
      ...parsed,
      methodName: normalizeAnalysisMethodName(parsed.methodName),
      frameInterval: parsed.frameInterval || EMPTY_ANALYSIS_SETTINGS.frameInterval,
      fastSteps: parsed.fastSteps?.length ? parsed.fastSteps : EMPTY_ANALYSIS_SETTINGS.fastSteps,
      directVideoDeepSteps: parsed.directVideoDeepSteps?.length
        ? parsed.directVideoDeepSteps
        : parsed.deepSteps?.length
          ? parsed.deepSteps
          : EMPTY_ANALYSIS_SETTINGS.directVideoDeepSteps,
      structuredDeepSteps: parsed.structuredDeepSteps?.length
        ? parsed.structuredDeepSteps
        : EMPTY_ANALYSIS_SETTINGS.structuredDeepSteps,
    }
  } catch {
    return EMPTY_ANALYSIS_SETTINGS
  }
}

export function saveAnalysisSettings(settings: AnalysisSettingsState): void {
  window.localStorage.setItem('hot-engine-analysis-settings', JSON.stringify(settings))
}

export function readSavedTask3Settings(): Task3SettingsState {
  const savedSettings = window.localStorage.getItem('hot-engine-task3-analysis-settings')

  if (!savedSettings) {
    return EMPTY_TASK3_SETTINGS
  }

  try {
    const parsed = JSON.parse(savedSettings) as Partial<Task3SettingsState>
    return {
      ...EMPTY_TASK3_SETTINGS,
      ...parsed,
      steps: parsed.steps?.length ? parsed.steps : EMPTY_TASK3_SETTINGS.steps,
    }
  } catch {
    return EMPTY_TASK3_SETTINGS
  }
}

export function saveTask3Settings(settings: Task3SettingsState): void {
  window.localStorage.setItem('hot-engine-task3-analysis-settings', JSON.stringify(settings))
}

export function normalizeStepSetting(step: Partial<AnalysisStepSetting>, fallbackId: string): AnalysisStepSetting {
  const skillKey = step.skillKey || step.skill || ''
  const modelType =
    step.modelType === 'speech-recognition' ||
    step.modelType === 'image-recognition' ||
    step.modelType === 'video-recognition'
      ? step.modelType
      : 'image-recognition'

  return {
    id: step.id || fallbackId,
    name: step.name || '未命名步骤',
    description: step.description || '从 JSON 导入的拆解步骤。',
    prompt: step.prompt || '',
    promptKey: step.promptKey,
    skill: step.skill || skillKey,
    skillKey,
    modelType,
  }
}

export function normalizeImportedAnalysisSettings(payload: unknown): AnalysisSettingsState {
  if (!payload || typeof payload !== 'object') {
    throw new Error('JSON 内容不是有效对象。')
  }

  const data = payload as Partial<AnalysisSettingsState> & {
    steps?: {
      fast?: Partial<AnalysisStepSetting>[]
      deep?: Partial<AnalysisStepSetting>[]
      directVideoDeep?: Partial<AnalysisStepSetting>[]
      structuredDeep?: Partial<AnalysisStepSetting>[]
    }
  }
  const fastStepsSource = data.steps?.fast ?? data.fastSteps ?? []
  const directVideoDeepStepsSource = data.steps?.directVideoDeep ?? data.directVideoDeepSteps ?? data.steps?.deep ?? data.deepSteps ?? []
  const structuredDeepStepsSource = data.steps?.structuredDeep ?? data.structuredDeepSteps ?? []
  const fastSteps = fastStepsSource.map((step, index) =>
    normalizeStepSetting(step, `fast-imported-${index + 1}`),
  )
  const directVideoDeepSteps = directVideoDeepStepsSource.map((step, index) =>
    normalizeStepSetting(step, `direct-video-deep-imported-${index + 1}`),
  )
  const structuredDeepSteps = structuredDeepStepsSource.map((step, index) =>
    normalizeStepSetting(step, `structured-deep-imported-${index + 1}`),
  )

  if (fastSteps.length === 0 && directVideoDeepSteps.length === 0 && structuredDeepSteps.length === 0) {
    throw new Error('JSON 中没有可用的 fast/deep 拆解步骤。')
  }

  return {
    ...EMPTY_ANALYSIS_SETTINGS,
    inputMode: data.inputMode === 'structured' ? 'structured' : 'direct-video',
    methodName: normalizeAnalysisMethodName(data.methodName),
    frameInterval: String(data.frameInterval || EMPTY_ANALYSIS_SETTINGS.frameInterval),
    templateHashes: data.templateHashes,
    fastSteps: fastSteps.length > 0 ? fastSteps : EMPTY_ANALYSIS_SETTINGS.fastSteps,
    directVideoDeepSteps: directVideoDeepSteps.length > 0
      ? directVideoDeepSteps
      : EMPTY_ANALYSIS_SETTINGS.directVideoDeepSteps,
    structuredDeepSteps: structuredDeepSteps.length > 0
      ? structuredDeepSteps
      : EMPTY_ANALYSIS_SETTINGS.structuredDeepSteps,
  }
}

export function buildPortableAnalysisSettings(settings: AnalysisSettingsState) {
  const normalizeStep = (step: AnalysisStepSetting) => ({
    id: step.id,
    name: step.name,
    description: step.description,
    modelType: step.modelType || 'image-recognition',
    promptKey: step.promptKey,
    skillKey: step.skillKey || step.skill,
    prompt: step.prompt,
  })

  return {
    version: 1,
    inputMode: settings.inputMode,
    methodName: settings.methodName,
    frameInterval: Number.parseInt(settings.frameInterval, 10) || 5,
    templateHashes: settings.templateHashes,
    steps: {
      fast: settings.fastSteps.map(normalizeStep),
      directVideoDeep: settings.directVideoDeepSteps.map(normalizeStep),
      structuredDeep: settings.structuredDeepSteps.map(normalizeStep),
    },
  }
}

export function buildExportableAnalysisSettings(settings: AnalysisSettingsState) {
  return {
    ...buildPortableAnalysisSettings(settings),
    savedAt: new Date().toISOString(),
  }
}

export function normalizeStepModelForMode(
  inputMode: DecompositionInputMode,
  modelType?: StepModelType,
): StepModelType {
  if (inputMode === 'direct-video') {
    return 'video-recognition'
  }

  return modelType === 'speech-recognition' ? 'speech-recognition' : 'image-recognition'
}

export function formatDuration(durationMs: number): string {
  const totalSeconds = Math.max(Math.floor(durationMs / 1000), 0)
  const seconds = totalSeconds % 60
  const minutes = Math.floor(totalSeconds / 60) % 60
  const hours = Math.floor(totalSeconds / 3600)

  if (hours > 0) {
    return [hours, minutes, seconds]
      .map((value) => String(value).padStart(2, '0'))
      .join(':')
  }

  return [minutes, seconds].map((value) => String(value).padStart(2, '0')).join(':')
}

export function formatBytes(sizeBytes?: number): string {
  if (!sizeBytes) {
    return '-'
  }

  const sizeMb = sizeBytes / 1024 / 1024
  return `${sizeMb.toFixed(2)} MB`
}

export function formatFps(fps?: number | null): string {
  if (!fps) {
    return '-'
  }

  return `${fps.toFixed(2)} fps`
}

export function statusLabel(status: VideoStatus): string {
  switch (status) {
    case 'uploaded':
      return '已上传'
    case 'analyzing':
      return '解析中'
    case 'ready':
      return '可查看'
    case 'failed':
      return '失败'
    default:
      return status
  }
}

export async function readJsonOrThrow<T>(response: Response): Promise<T> {
  const payload = await response.json().catch(() => null)

  if (!response.ok) {
    const detail =
      payload && typeof payload === 'object' && 'detail' in payload
        ? String(payload.detail)
        : '请求失败。'
    throw new Error(detail)
  }

  return payload as T
}
