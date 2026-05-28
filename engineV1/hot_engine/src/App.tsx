import { useEffect, useRef, useState } from 'react'
import type { ChangeEvent, DragEvent } from 'react'
import './App.css'
import { EMPTY_SETTINGS_FORM, EMPTY_TASK3_DRAFT } from './defaults'
import type {
  AnalysisDefaultTemplateResponse,
  AnalysisApiResponse,
  AnalysisMethodName,
  AnalysisSettingsState,
  AnalysisStepSetting,
  ApiListResponse,
  DecompositionInputMode,
  PageName,
  SettingsApiResponse,
  SettingsFormState,
  StepModelType,
  Task3AnalysisResult,
  Task3Draft,
  Task3InputRecord,
  Task3Material,
  Task3SettingsState,
  Task3StepModelType,
  Task4Result,
  VideoRecord,
} from './types'
import {
  buildExportableAnalysisSettings,
  buildPortableAnalysisSettings,
  formatAnalysisMethodLabel,
  formatBytes,
  formatDuration,
  formatFps,
  mapSettingsItemsToForm,
  normalizeImportedAnalysisSettings,
  normalizeStepModelForMode,
  readJsonOrThrow,
  readSavedAnalysisSettings,
  readSavedTask3Settings,
  saveAnalysisSettings,
  saveTask3Settings,
  statusLabel,
} from './utils'
type AnalysisStepGroup = 'fastSteps' | 'directVideoDeepSteps' | 'structuredDeepSteps'

function App() {
  const [videos, setVideos] = useState<VideoRecord[]>([])
  const [selectedId, setSelectedId] = useState<string | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [uploading, setUploading] = useState(false)
  const [uploadProgress, setUploadProgress] = useState<number>(0)
  const [pageError, setPageError] = useState<string | null>(null)
  const [isDragging, setIsDragging] = useState(false)
  const [currentPage, setCurrentPage] = useState<PageName>('home')
  const [settingsForm, setSettingsForm] = useState<SettingsFormState>(EMPTY_SETTINGS_FORM)
  const [settingsEnvPath, setSettingsEnvPath] = useState<string>('.env')
  const [settingsLoading, setSettingsLoading] = useState(false)
  const [settingsSaving, setSettingsSaving] = useState(false)
  const [settingsError, setSettingsError] = useState<string | null>(null)
  const [settingsNotice, setSettingsNotice] = useState<string | null>(null)
  const [settingsLoadedOnce, setSettingsLoadedOnce] = useState(false)
  const [analysisSettings, setAnalysisSettings] = useState<AnalysisSettingsState>(() =>
    readSavedAnalysisSettings(),
  )
  const [draftAnalysisSettings, setDraftAnalysisSettings] = useState<AnalysisSettingsState>(() =>
    readSavedAnalysisSettings(),
  )
  const [selectedDraftStepId, setSelectedDraftStepId] = useState<string>(
    () => readSavedAnalysisSettings().fastSteps[0]?.id ?? 'fast-summary',
  )
  const [draggedDraftStepId, setDraggedDraftStepId] = useState<string | null>(null)
  const [analysisSettingsError, setAnalysisSettingsError] = useState<string | null>(null)
  const [analysisSettingsNotice, setAnalysisSettingsNotice] = useState<string | null>(null)
  const [analysisPersistToDb, setAnalysisPersistToDb] = useState(false)
  const [analysisLoading, setAnalysisLoading] = useState(false)
  const [analysisRunning, setAnalysisRunning] = useState(false)
  const [analysisError, setAnalysisError] = useState<string | null>(null)
  const [analysisNotice, setAnalysisNotice] = useState<string | null>(null)
  const [analysisResult, setAnalysisResult] = useState<AnalysisApiResponse | null>(null)
  const [analysisTargetVideoId, setAnalysisTargetVideoId] = useState<string | null>(null)
  const [analysisPageVideos, setAnalysisPageVideos] = useState<VideoRecord[]>([])
  const [task3Draft, setTask3Draft] = useState<Task3Draft>(EMPTY_TASK3_DRAFT)
  const [task3Settings, setTask3Settings] = useState<Task3SettingsState>(() => readSavedTask3Settings())
  const [draftTask3Settings, setDraftTask3Settings] = useState<Task3SettingsState>(() => readSavedTask3Settings())
  const [task3InputRecord, setTask3InputRecord] = useState<Task3InputRecord | null>(null)
  const [task3AnalysisResult, setTask3AnalysisResult] = useState<Task3AnalysisResult | null>(null)
  const [task3Running, setTask3Running] = useState(false)
  const [task3Error, setTask3Error] = useState<string | null>(null)
  const [task3Notice, setTask3Notice] = useState<string | null>(null)
  const [task4Result, setTask4Result] = useState<Task4Result | null>(null)
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const task3MaterialInputRef = useRef<HTMLInputElement | null>(null)

  const selectedVideo =
    videos.find((video) => video.id === selectedId) ?? (videos.length > 0 ? videos[0] : null)
  const analysisVideo =
    analysisPageVideos.find((video) => video.id === analysisTargetVideoId) ??
    videos.find((video) => video.id === analysisTargetVideoId) ??
    selectedVideo ??
    null
  const analysisVideoItems = analysisPageVideos.length > 0 ? analysisPageVideos : videos
  const analysisVideoIndex = analysisVideo
    ? analysisVideoItems.findIndex((video) => video.id === analysisVideo.id)
    : -1
  const analysisVideoDisplayName =
    analysisVideoIndex >= 0 ? `待拆解视频${analysisVideoIndex + 1}` : '待拆解视频'
  const analysisSettingsSummary =
    analysisSettings.inputMode === 'structured'
      ? analysisSettings.structuredDeepSteps.map((step) => `${step.name}:${step.modelType === 'speech-recognition' ? '语音' : '图片'}`).join(' / ')
      : analysisSettings.methodName === 'deep'
      ? analysisSettings.directVideoDeepSteps.map((step) => step.name).join(' / ')
      : analysisSettings.fastSteps[0]?.name ?? '一次性概览'

  const cloneAnalysisSettings = (settings: AnalysisSettingsState): AnalysisSettingsState => ({
    ...settings,
    templateHashes: settings.templateHashes
      ? {
          ...settings.templateHashes,
          stepHashes: settings.templateHashes.stepHashes
            ? Object.fromEntries(
                Object.entries(settings.templateHashes.stepHashes).map(([key, value]) => [
                  key,
                  { ...value },
                ]),
              )
            : undefined,
        }
      : undefined,
    fastSteps: settings.fastSteps.map((step) => ({ ...step })),
    directVideoDeepSteps: settings.directVideoDeepSteps.map((step) => ({ ...step })),
    structuredDeepSteps: settings.structuredDeepSteps.map((step) => ({ ...step })),
  })

  const applyDefaultTemplate = (
    settings: AnalysisSettingsState,
    template: AnalysisDefaultTemplateResponse,
    options: { fillEmpty: boolean; clearIfChanged: boolean },
  ): { settings: AnalysisSettingsState; changed: boolean; cleared: boolean } => {
    const nextSettings = cloneAnalysisSettings(settings)
    const firstStep = nextSettings.fastSteps[0]

    if (!firstStep) {
      return { settings: nextSettings, changed: false, cleared: false }
    }

    const previousHashes = nextSettings.templateHashes
    const usesDefaultPaths =
      firstStep.promptKey === template.promptPath && firstStep.skillKey === template.skillPath
    const hashesChanged =
      usesDefaultPaths &&
      !!previousHashes &&
      previousHashes.promptPath === template.promptPath &&
      previousHashes.skillPath === template.skillPath &&
      ((previousHashes.promptHash ?? '') !== template.promptHash ||
        (previousHashes.skillHash ?? '') !== template.skillHash)

    const nextStep = { ...firstStep }
    let changed = false
    let cleared = false

    if (options.clearIfChanged && hashesChanged) {
      nextStep.prompt = ''
      nextStep.skill = ''
      changed = nextStep.prompt !== firstStep.prompt || nextStep.skill !== firstStep.skill
      cleared = changed
    } else if (options.fillEmpty) {
      if (!nextStep.prompt && template.prompt) {
        nextStep.prompt = template.prompt
        changed = true
      }
      if (!nextStep.skill && template.skill) {
        nextStep.skill = template.skill
        changed = true
      }
    }

    if (options.fillEmpty || !nextStep.promptKey) {
      nextStep.promptKey = template.promptPath
      changed = true
    }
    if (options.fillEmpty || !nextStep.skillKey) {
      nextStep.skillKey = template.skillPath
      changed = true
    }

    nextSettings.fastSteps = [nextStep, ...nextSettings.fastSteps.slice(1)]
    nextSettings.templateHashes = {
      promptPath: template.promptPath,
      promptHash: template.promptHash,
      skillPath: template.skillPath,
      skillHash: template.skillHash,
      stepHashes: nextSettings.templateHashes?.stepHashes,
    }

    const stepHashes = { ...(nextSettings.templateHashes.stepHashes ?? {}) }
    for (const templateStep of template.steps ?? []) {
      const groups: AnalysisStepGroup[] = ['fastSteps', 'directVideoDeepSteps', 'structuredDeepSteps']
      for (const group of groups) {
        nextSettings[group] = nextSettings[group].map((step) => {
          if (step.id !== templateStep.stepId) {
            return step
          }

          const previousStepHash = stepHashes[step.id]
          const usesDefaultStepPaths =
            step.promptKey === templateStep.promptPath && step.skillKey === templateStep.skillPath
          const stepTemplateChanged =
            options.clearIfChanged &&
            usesDefaultStepPaths &&
            !!previousStepHash &&
            previousStepHash.promptPath === templateStep.promptPath &&
            previousStepHash.skillPath === templateStep.skillPath &&
            ((previousStepHash.promptHash ?? '') !== templateStep.promptHash ||
              (previousStepHash.skillHash ?? '') !== templateStep.skillHash)
          const nextStep = { ...step }

          if (stepTemplateChanged) {
            nextStep.prompt = ''
            nextStep.skill = ''
            changed = true
            cleared = true
          } else if (options.fillEmpty) {
            if (!nextStep.prompt && templateStep.prompt) {
              nextStep.prompt = templateStep.prompt
              changed = true
            }
            if (!nextStep.skill && templateStep.skill) {
              nextStep.skill = templateStep.skill
              changed = true
            }
          }

          if (options.fillEmpty || !nextStep.promptKey) {
            nextStep.promptKey = templateStep.promptPath
            changed = true
          }
          if (options.fillEmpty || !nextStep.skillKey) {
            nextStep.skillKey = templateStep.skillPath
            changed = true
          }

          stepHashes[step.id] = {
            promptPath: templateStep.promptPath,
            promptHash: templateStep.promptHash,
            skillPath: templateStep.skillPath,
            skillHash: templateStep.skillHash,
          }
          return nextStep
        })
      }
    }
    nextSettings.templateHashes.stepHashes = stepHashes

    return {
      settings: nextSettings,
      changed:
        changed ||
        previousHashes?.promptHash !== template.promptHash ||
        previousHashes?.skillHash !== template.skillHash,
      cleared,
    }
  }

  const fetchDefaultAnalysisTemplate = async () => {
    const response = await fetch('/api/analysis/default-template')
    return readJsonOrThrow<AnalysisDefaultTemplateResponse>(response)
  }

  const getAnalysisStepGroup = (settings: AnalysisSettingsState): AnalysisStepGroup => {
    if (settings.inputMode === 'structured') {
      return 'structuredDeepSteps'
    }
    return settings.methodName === 'deep' ? 'directVideoDeepSteps' : 'fastSteps'
  }

  const initializeDefaultAnalysisTemplate = async () => {
    if (window.localStorage.getItem('hot-engine-analysis-settings')) {
      return
    }

    try {
      const template = await fetchDefaultAnalysisTemplate()
      const applied = applyDefaultTemplate(readSavedAnalysisSettings(), template, {
        fillEmpty: true,
        clearIfChanged: false,
      })
      setAnalysisSettings(applied.settings)
      setDraftAnalysisSettings(applied.settings)
      setSelectedDraftStepId(applied.settings.fastSteps[0]?.id ?? 'fast-summary')
      saveAnalysisSettings(applied.settings)
    } catch {
      // If the template files are unavailable, keep the empty defaults visible.
    }
  }

  const loadVideos = async () => {
    setPageError(null)

    try {
      const response = await fetch('/api/videos')
      const payload = await readJsonOrThrow<ApiListResponse>(response)
      setVideos(payload.items)
    } catch (error) {
      setPageError(error instanceof Error ? error.message : '视频列表加载失败。')
    } finally {
      setIsLoading(false)
    }
  }

  const loadSettings = async () => {
    setSettingsLoading(true)
    setSettingsError(null)

    try {
      const response = await fetch('/api/settings')
      const payload = await readJsonOrThrow<SettingsApiResponse>(response)
      setSettingsEnvPath(payload.envPath)
      setSettingsForm(mapSettingsItemsToForm(payload.items))
      setSettingsNotice(null)
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : '设置读取失败。')
    } finally {
      setSettingsLoading(false)
    }
  }

  const loadAnalysis = async (videoId: string) => {
    setAnalysisLoading(true)
    setAnalysisError(null)

    try {
      const response = await fetch(`/api/videos/${videoId}/analysis`)

      if (response.status === 404) {
        setAnalysisResult(null)
        setAnalysisNotice('当前视频还没有拆解记录。')
        return
      }

      const payload = await readJsonOrThrow<AnalysisApiResponse>(response)
      setAnalysisResult(payload)
      setAnalysisPersistToDb(payload.persistedToDb)
      setAnalysisNotice(payload.cached ? '已读取临时缓存的拆解结果。' : '已读取已保存的拆解结果。')
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : '拆解结果读取失败。')
    } finally {
      setAnalysisLoading(false)
    }
  }

  const runAnalysis = async (scope: 'single' | 'all') => {
    if (analysisRunning || !analysisVideo) {
      return
    }

    setAnalysisRunning(true)
    setAnalysisError(null)
    setAnalysisNotice(null)

    const frameInterval = Math.max(Number.parseInt(analysisSettings.frameInterval, 10) || 5, 1)
    const payload = {
      methodName: analysisSettings.methodName,
      frameInterval,
      persistToDb: analysisPersistToDb,
      force: false,
      settings: buildPortableAnalysisSettings(analysisSettings),
    }

    try {
      if (scope === 'single') {
        const response = await fetch(`/api/videos/${analysisVideo.id}/analysis`, {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify(payload),
        })
        const result = await readJsonOrThrow<AnalysisApiResponse>(response)
        setAnalysisResult(result)
        setAnalysisNotice(result.cached ? '命中临时缓存，未重复拆解。' : '拆解完成并已写入缓存。')
        if (analysisPersistToDb) {
          await loadVideos()
        }
        return
      }

      const response = await fetch('/api/videos/analysis/bulk', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          ...payload,
          videoIds: videos.map((video) => video.id),
        }),
      })

      const result = await readJsonOrThrow<{ count: number; items: AnalysisApiResponse[] }>(response)
      const currentResult = result.items.find((item) => item.videoId === analysisVideo.id) ?? null
      setAnalysisResult(currentResult)
      setAnalysisNotice(`已拆解 ${result.count} 个视频。`)
      if (analysisPersistToDb) {
        await loadVideos()
      }
    } catch (error) {
      setAnalysisError(error instanceof Error ? error.message : '拆解失败。')
    } finally {
      setAnalysisRunning(false)
    }
  }

  const saveSettings = async (nextForm: SettingsFormState = settingsForm) => {
    if (settingsSaving) {
      return
    }

    setSettingsSaving(true)
    setSettingsError(null)

    try {
      const response = await fetch('/api/settings', {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(nextForm),
      })
      const payload = await readJsonOrThrow<SettingsApiResponse>(response)
      setSettingsEnvPath(payload.envPath)
      setSettingsForm(mapSettingsItemsToForm(payload.items))
      setSettingsNotice('已同步写入 .env')
    } catch (error) {
      setSettingsError(error instanceof Error ? error.message : '设置保存失败。')
    } finally {
      setSettingsSaving(false)
    }
  }

  useEffect(() => {
    void loadVideos()
  }, [])

  useEffect(() => {
    void initializeDefaultAnalysisTemplate()
  }, [])

  useEffect(() => {
    if (currentPage === 'settings' && !settingsLoadedOnce) {
      void loadSettings()
      setSettingsLoadedOnce(true)
    }
  }, [currentPage, settingsLoadedOnce])

  useEffect(() => {
    if (currentPage === 'analysis' && analysisVideo) {
      void loadAnalysis(analysisVideo.id)
    }
  }, [currentPage, analysisVideo?.id])

  useEffect(() => {
    if (currentPage !== 'analysis-settings') {
      return
    }

    const steps = draftAnalysisSettings[getAnalysisStepGroup(draftAnalysisSettings)]

    if (!steps.some((step) => step.id === selectedDraftStepId)) {
      setSelectedDraftStepId(steps[0]?.id ?? '')
    }
  }, [currentPage, draftAnalysisSettings, selectedDraftStepId])

  useEffect(() => {
    if (videos.length === 0) {
      setSelectedId(null)
      return
    }

    if (!selectedId || !videos.some((video) => video.id === selectedId)) {
      setSelectedId(videos[0].id)
    }
  }, [selectedId, videos])

  const triggerFilePicker = () => {
    fileInputRef.current?.click()
  }

  const uploadFiles = async (files: File[]) => {
    if (files.length === 0 || uploading) {
      return
    }

    setUploading(true)
    setUploadProgress(0)
    setPageError(null)

    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))

    await new Promise<void>((resolve, reject) => {
      const xhr = new XMLHttpRequest()
      xhr.open('POST', '/api/videos/upload')
      xhr.responseType = 'json'

      xhr.upload.addEventListener('progress', (event) => {
        if (event.lengthComputable) {
          setUploadProgress(Math.round((event.loaded / event.total) * 100))
        }
      })

      xhr.addEventListener('load', () => {
        if (xhr.status >= 200 && xhr.status < 300) {
          resolve()
          return
        }

        const detail =
          xhr.response && typeof xhr.response === 'object' && 'detail' in xhr.response
            ? String(xhr.response.detail)
            : '上传失败。'
        reject(new Error(detail))
      })

      xhr.addEventListener('error', () => {
        reject(new Error('上传失败，无法连接后端服务。'))
      })

      xhr.send(formData)
    })

    await loadVideos()
    setUploadProgress(100)
    setUploading(false)
  }

  const handleFileChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])

    try {
      await uploadFiles(files)
    } catch (error) {
      setPageError(error instanceof Error ? error.message : '上传失败。')
      setUploading(false)
    } finally {
      event.target.value = ''
      setTimeout(() => setUploadProgress(0), 250)
    }
  }

  const handleDelete = async (videoId: string) => {
    try {
      const response = await fetch(`/api/videos/${videoId}`, { method: 'DELETE' })
      await readJsonOrThrow<{ status: string }>(response)
      await loadVideos()
    } catch (error) {
      setPageError(error instanceof Error ? error.message : '删除失败。')
    }
  }

  const handleDragEnter = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setIsDragging(true)
  }

  const handleDragOver = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setIsDragging(true)
  }

  const handleDragLeave = (event: DragEvent<HTMLElement>) => {
    event.preventDefault()

    if (event.currentTarget.contains(event.relatedTarget as Node | null)) {
      return
    }

    setIsDragging(false)
  }

  const handleDrop = async (event: DragEvent<HTMLElement>) => {
    event.preventDefault()
    setIsDragging(false)

    const files = Array.from(event.dataTransfer.files).filter((file) =>
      file.type.startsWith('video/'),
    )

    try {
      await uploadFiles(files)
    } catch (error) {
      setPageError(error instanceof Error ? error.message : '上传失败。')
      setUploading(false)
    } finally {
      setTimeout(() => setUploadProgress(0), 250)
    }
  }

  const handleSettingsChange = (field: keyof SettingsFormState, value: string) => {
    setSettingsForm((previous) => ({
      ...previous,
      [field]: value,
    }))
    setSettingsNotice(null)
  }

  const openAnalysisSettingsPage = async () => {
    let sourceSettings = cloneAnalysisSettings(analysisSettings)
    let templateChanged = false

    try {
      const template = await fetchDefaultAnalysisTemplate()
      const applied = applyDefaultTemplate(sourceSettings, template, {
        fillEmpty: false,
        clearIfChanged: true,
      })
      sourceSettings = applied.settings
      templateChanged = applied.cleared
      if (applied.changed) {
        setAnalysisSettings(sourceSettings)
        saveAnalysisSettings(sourceSettings)
      }
    } catch {
      templateChanged = false
    }

    const nextDraft = cloneAnalysisSettings(sourceSettings)
    const nextSteps = nextDraft[getAnalysisStepGroup(nextDraft)]
    setDraftAnalysisSettings(nextDraft)
    setSelectedDraftStepId(nextSteps[0]?.id ?? '')
    setAnalysisSettingsError(null)
    setAnalysisSettingsNotice(templateChanged ? '默认模板文件已变动，Prompt 和 Skill 已置空，请重新加载或填写。' : null)
    setCurrentPage('analysis-settings')
  }

  const saveDraftAnalysisSettings = () => {
    const inputMode = draftAnalysisSettings.inputMode
    const nextSettings = {
      ...draftAnalysisSettings,
      methodName: inputMode === 'structured' ? 'deep' : draftAnalysisSettings.methodName,
      frameInterval: String(Math.max(Number.parseInt(draftAnalysisSettings.frameInterval, 10) || 5, 1)),
      fastSteps: draftAnalysisSettings.fastSteps.map((step) => ({
        ...step,
        modelType: normalizeStepModelForMode(inputMode, step.modelType),
      })),
      directVideoDeepSteps: draftAnalysisSettings.directVideoDeepSteps.map((step) => ({
        ...step,
        modelType: 'video-recognition' as StepModelType,
      })),
      structuredDeepSteps: draftAnalysisSettings.structuredDeepSteps.map((step) => ({
        ...step,
        modelType: (step.modelType === 'speech-recognition' ? 'speech-recognition' : 'image-recognition') as StepModelType,
      })),
    }
    setAnalysisSettings(nextSettings)
    saveAnalysisSettings(nextSettings)
    setAnalysisSettingsNotice(null)
    setAnalysisSettingsError(null)
    setCurrentPage('analysis')
  }

  const updateDraftStep = (
    group: AnalysisStepGroup,
    stepId: string,
    field: 'prompt' | 'skill',
    value: string,
  ) => {
    setDraftAnalysisSettings((previous) => ({
      ...previous,
      [group]: previous[group].map((step) =>
        step.id === stepId
          ? {
              ...step,
              [field]: value,
            }
          : step,
      ),
    }))
  }

  const activeDraftSteps =
    draftAnalysisSettings[getAnalysisStepGroup(draftAnalysisSettings)]
  const activeDraftStepGroup = getAnalysisStepGroup(draftAnalysisSettings)
  const selectedDraftStep = activeDraftSteps.find((step) => step.id === selectedDraftStepId) ?? activeDraftSteps[0]

  const readTextFile = (file: File): Promise<string> =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.addEventListener('load', () => resolve(String(reader.result ?? '')))
      reader.addEventListener('error', () => reject(new Error('文件读取失败。')))
      reader.readAsText(file, 'utf-8')
    })

  const loadStepFile = async (
    event: ChangeEvent<HTMLInputElement>,
    stepId: string,
    field: 'prompt' | 'skill',
  ) => {
    const file = event.target.files?.[0]
    event.target.value = ''

    if (!file) {
      return
    }

    const expectedExtension = field === 'skill' ? '.md' : '.txt'

    if (!file.name.toLowerCase().endsWith(expectedExtension)) {
      setAnalysisSettingsError(`${field === 'skill' ? 'Skill' : 'Prompt'} 文件必须是 ${expectedExtension} 格式。`)
      setAnalysisSettingsNotice(null)
      return
    }

    try {
      const text = await readTextFile(file)
      if (field === 'skill') {
        setDraftAnalysisSettings((previous) => ({
          ...previous,
          [activeDraftStepGroup]: previous[activeDraftStepGroup].map((step) =>
            step.id === stepId
              ? {
                  ...step,
                  skill: text,
                  skillKey: file.name,
                }
              : step,
          ),
        }))
      } else {
        setDraftAnalysisSettings((previous) => ({
          ...previous,
          [activeDraftStepGroup]: previous[activeDraftStepGroup].map((step) =>
            step.id === stepId
              ? {
                  ...step,
                  prompt: text,
                  promptKey: file.name,
                }
              : step,
          ),
        }))
      }
      setAnalysisSettingsError(null)
      setAnalysisSettingsNotice(`已加载 ${file.name}`)
    } catch (error) {
      setAnalysisSettingsError(error instanceof Error ? error.message : '文件读取失败。')
      setAnalysisSettingsNotice(null)
    }
  }

  const savePromptModification = (stepId: string) => {
    const nextSettings = {
      ...analysisSettings,
      ...draftAnalysisSettings,
      [activeDraftStepGroup]: draftAnalysisSettings[activeDraftStepGroup].map((step) => ({ ...step })),
    }
    setAnalysisSettings(nextSettings)
    saveAnalysisSettings(nextSettings)
    setAnalysisSettingsError(null)
    setAnalysisSettingsNotice(`已保存 ${activeDraftSteps.find((step) => step.id === stepId)?.name ?? '当前步骤'} 的 Prompt 修改。`)
  }

  const saveSkillModification = (stepId: string) => {
    const nextSettings = {
      ...analysisSettings,
      ...draftAnalysisSettings,
      [activeDraftStepGroup]: draftAnalysisSettings[activeDraftStepGroup].map((step) => ({ ...step })),
    }
    setAnalysisSettings(nextSettings)
    saveAnalysisSettings(nextSettings)
    setAnalysisSettingsError(null)
    setAnalysisSettingsNotice(`已保存 ${activeDraftSteps.find((step) => step.id === stepId)?.name ?? '当前步骤'} 的 Skill 修改。`)
  }

  const exportDraftAnalysisSettings = () => {
    const portableSettings = buildExportableAnalysisSettings(draftAnalysisSettings)
    const blob = new Blob([JSON.stringify(portableSettings, null, 2)], {
      type: 'application/json',
    })
    const url = URL.createObjectURL(blob)
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'analysis-settings.json'
    anchor.click()
    URL.revokeObjectURL(url)
    setAnalysisSettingsError(null)
    setAnalysisSettingsNotice('已导出 JSON 配置。')
  }

  const importDraftAnalysisSettings = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''

    if (!file) {
      return
    }

    if (!file.name.toLowerCase().endsWith('.json')) {
      setAnalysisSettingsError('拆解设置文件必须是 .json 格式。')
      setAnalysisSettingsNotice(null)
      return
    }

    try {
      const text = await readTextFile(file)
      const importedSettings = normalizeImportedAnalysisSettings(JSON.parse(text))
      const nextSteps = importedSettings[getAnalysisStepGroup(importedSettings)]
      setDraftAnalysisSettings(importedSettings)
      setSelectedDraftStepId(nextSteps[0]?.id ?? '')
      setAnalysisSettingsError(null)
      setAnalysisSettingsNotice(`已导入 ${file.name}`)
    } catch (error) {
      setAnalysisSettingsError(error instanceof Error ? error.message : 'JSON 导入失败。')
      setAnalysisSettingsNotice(null)
    }
  }

  const addDraftStep = () => {
    const group = getAnalysisStepGroup(draftAnalysisSettings)
    const nextIndex = draftAnalysisSettings[group].length + 1
    const nextStep: AnalysisStepSetting = {
      id: `deep-custom-${Date.now()}`,
      name: `深度步骤 ${nextIndex}`,
      description: '自定义拆解步骤，可加载 skill 或 prompt 文件后继续编辑。',
      prompt: '请填写这个步骤的拆解 prompt。',
      skill: '自定义 skill',
      modelType: draftAnalysisSettings.inputMode === 'direct-video' ? 'video-recognition' : 'image-recognition',
    }

    setDraftAnalysisSettings((previous) => ({
      ...previous,
      [group]: [...previous[group], nextStep],
    }))
    setSelectedDraftStepId(nextStep.id)
  }

  const deleteDraftStep = (stepId: string) => {
    const group = getAnalysisStepGroup(draftAnalysisSettings)
    if (group === 'fastSteps' || draftAnalysisSettings[group].length <= 1) {
      return
    }

    setDraftAnalysisSettings((previous) => {
      const nextSteps = previous[group].filter((step) => step.id !== stepId)
      setSelectedDraftStepId(nextSteps[0]?.id ?? '')
      return {
        ...previous,
        [group]: nextSteps,
      }
    })
  }

  const moveDraftStep = (sourceId: string, targetId: string) => {
    const group = getAnalysisStepGroup(draftAnalysisSettings)
    if (sourceId === targetId || group === 'fastSteps') {
      return
    }

    setDraftAnalysisSettings((previous) => {
      const sourceIndex = previous[group].findIndex((step) => step.id === sourceId)
      const targetIndex = previous[group].findIndex((step) => step.id === targetId)

      if (sourceIndex < 0 || targetIndex < 0) {
        return previous
      }

      const nextSteps = [...previous[group]]
      const [sourceStep] = nextSteps.splice(sourceIndex, 1)
      nextSteps.splice(targetIndex, 0, sourceStep)

      return {
        ...previous,
        [group]: nextSteps,
      }
    })
  }

  const updateTask3Draft = (field: keyof Task3Draft, value: string) => {
    setTask3Draft((previous) => ({
      ...previous,
      [field]: value,
    }))
  }

  const createTask3InputPayload = () => ({
    topic: task3Draft.topic,
    sellingPoints: task3Draft.sellingPointsText
      .split('\n')
      .map((item) => item.trim())
      .filter(Boolean),
    copyText: task3Draft.copyText,
    targetAudience: task3Draft.targetAudience,
    platform: task3Draft.platform,
    stylePreference: task3Draft.stylePreference,
    materials: task3Draft.materials,
    sourceAnalysisVideoIds: analysisVideoItems.map((video) => video.id),
  })

  const createOrUpdateTask3Input = async (): Promise<Task3InputRecord> => {
    const payload = createTask3InputPayload()
    const response = await fetch(
      task3InputRecord ? `/api/task3/inputs/${task3InputRecord.id}` : '/api/task3/inputs',
      {
        method: task3InputRecord ? 'PUT' : 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(payload),
      },
    )
    const record = await readJsonOrThrow<Task3InputRecord>(response)
    setTask3InputRecord(record)
    return record
  }

  const uploadTask3Materials = async (files: File[]) => {
    if (files.length === 0) {
      return
    }

    setTask3Error(null)
    const record = await createOrUpdateTask3Input()
    const formData = new FormData()
    files.forEach((file) => formData.append('files', file))
    const response = await fetch(`/api/task3/inputs/${record.id}/materials`, {
      method: 'POST',
      body: formData,
    })
    const payload = await readJsonOrThrow<{ items: Task3Material[]; input: Task3InputRecord }>(response)
    setTask3InputRecord(payload.input)
    setTask3Draft((previous) => ({
      ...previous,
      materials: payload.input.materials,
    }))
    setTask3Notice(`已上传 ${payload.items.length} 个素材。`)
  }

  const handleTask3MaterialChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const files = Array.from(event.target.files ?? [])
    event.target.value = ''

    try {
      await uploadTask3Materials(files)
    } catch (error) {
      setTask3Error(error instanceof Error ? error.message : '素材上传失败。')
    }
  }

  const runTask3Analysis = async () => {
    if (task3Running) {
      return
    }

    setTask3Running(true)
    setTask3Error(null)
    setTask3Notice(null)

    try {
      const record = await createOrUpdateTask3Input()
      const response = await fetch(`/api/task3/inputs/${record.id}/analyze`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ settings: task3Settings }),
      })
      const result = await readJsonOrThrow<Task3AnalysisResult>(response)
      setTask3AnalysisResult(result)
      setCurrentPage('task3-result')
    } catch (error) {
      setTask3Error(error instanceof Error ? error.message : '素材分析失败。')
    } finally {
      setTask3Running(false)
    }
  }

  const saveDraftTask3Settings = () => {
    setTask3Settings(draftTask3Settings)
    saveTask3Settings(draftTask3Settings)
    setCurrentPage('task3')
  }

  const openTask3Settings = () => {
    setDraftTask3Settings({
      ...task3Settings,
      steps: task3Settings.steps.map((step) => ({ ...step })),
    })
    setCurrentPage('task3-settings')
  }

  const updateTask3GapResolution = (gapId: string, resolution: string) => {
    setTask3AnalysisResult((previous) =>
      previous
        ? {
            ...previous,
            gaps: previous.gaps.map((gap) =>
              gap.id === gapId
                ? {
                    ...gap,
                    resolution,
                  }
                : gap,
            ),
          }
        : previous,
    )
  }

  const createSupplementMaterial = () => {
    setTask3Notice('已记录生成补充素材请求，后续可接入 AIGC 素材生成。')
  }

  const startMigrationGeneration = () => {
    const unresolvedGaps = task3AnalysisResult?.gaps.filter((gap) => (gap.resolution ?? 'pending') === 'pending') ?? []
    setTask4Result({
      title: task3Draft.topic || '新视频方案',
      summary:
        unresolvedGaps.length > 0
          ? `已基于当前素材生成简易迁移结果，仍有 ${unresolvedGaps.length} 个缺口将通过文案或包装补全。`
          : '已基于当前素材生成简易迁移结果，素材状态完整。',
      videoStatus: 'demo 待生成',
      generatedAt: new Date().toISOString(),
    })
    setCurrentPage('task4')
  }

  if (currentPage === 'settings') {
    return (
      <main className="app-shell">
        {/* 页面0：设置页面 */}
        <section className="settings-panel">
          <div className="settings-header">
            <div>
              <p className="eyebrow">页面0 / 设置页面</p>
              <h1>设置</h1>
              <p className="hero-text">
                在这里编辑语音识别、OCR 识别、视频识别和文本交互（chat）的 API 链接。
                修改后会自动写回根目录的 .env 文件。
              </p>
              <p className="hint-text">当前配置文件：{settingsEnvPath}</p>
            </div>

            <button type="button" className="ghost-button" onClick={() => setCurrentPage('home')}>
              返回首页
            </button>
          </div>

          {settingsError ? <div className="settings-banner error">{settingsError}</div> : null}
          {settingsNotice ? <div className="settings-banner success">{settingsNotice}</div> : null}

          <div className="settings-grid">
            <article className="settings-model-card">
              <h2>语音识别</h2>
              <label className="settings-field">
                <span>API 链接</span>
                <small>SPEECH_RECOGNITION_API_URL</small>
                <input
                  type="url"
                  value={settingsForm.speechRecognitionApiUrl}
                  placeholder="https://..."
                  onChange={(event) => handleSettingsChange('speechRecognitionApiUrl', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>API Key</span>
                <small>SPEECH_RECOGNITION_APP_KEY</small>
                <input
                  type="password"
                  value={settingsForm.speechRecognitionAppKey}
                  placeholder="X-Api-App-Key"
                  onChange={(event) => handleSettingsChange('speechRecognitionAppKey', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>Access Key</span>
                <small>SPEECH_RECOGNITION_API_KEY</small>
                <input
                  type="password"
                  value={settingsForm.speechRecognitionApiKey}
                  placeholder="X-Api-Access-Key"
                  onChange={(event) => handleSettingsChange('speechRecognitionApiKey', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>模型</span>
                <small>SPEECH_RECOGNITION_MODEL</small>
                <input
                  type="text"
                  value={settingsForm.speechRecognitionModel}
                  placeholder="服务商真实模型 ID / 推理接入点 ID"
                  onChange={(event) => handleSettingsChange('speechRecognitionModel', event.target.value)}
                />
              </label>
            </article>

            <article className="settings-model-card">
              <h2>OCR / 视觉识别</h2>
              <label className="settings-field">
                <span>API 链接</span>
                <small>OCR_RECOGNITION_API_URL</small>
                <input
                  type="url"
                  value={settingsForm.ocrRecognitionApiUrl}
                  placeholder="https://..."
                  onChange={(event) => handleSettingsChange('ocrRecognitionApiUrl', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>API Key</span>
                <small>OCR_RECOGNITION_API_KEY</small>
                <input
                  type="password"
                  value={settingsForm.ocrRecognitionApiKey}
                  placeholder="sk-... / dashscope-... / ark-..."
                  onChange={(event) => handleSettingsChange('ocrRecognitionApiKey', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>模型</span>
                <small>OCR_RECOGNITION_MODEL</small>
                <input
                  type="text"
                  value={settingsForm.ocrRecognitionModel}
                  placeholder="服务商真实模型 ID / 推理接入点 ID"
                  onChange={(event) => handleSettingsChange('ocrRecognitionModel', event.target.value)}
                />
              </label>
            </article>

            <article className="settings-model-card">
              <h2>视频识别</h2>
              <label className="settings-field">
                <span>API 链接</span>
                <small>VIDEO_RECOGNITION_API_URL</small>
                <input
                  type="url"
                  value={settingsForm.videoRecognitionApiUrl}
                  placeholder="https://..."
                  onChange={(event) => handleSettingsChange('videoRecognitionApiUrl', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>API Key</span>
                <small>VIDEO_RECOGNITION_API_KEY</small>
                <input
                  type="password"
                  value={settingsForm.videoRecognitionApiKey}
                  placeholder="Gemini / OpenAI / Ark API Key"
                  onChange={(event) => handleSettingsChange('videoRecognitionApiKey', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>模型</span>
                <small>VIDEO_RECOGNITION_MODEL</small>
                <input
                  type="text"
                  value={settingsForm.videoRecognitionModel}
                  placeholder="例如 gemini-2.5-pro / Ark 推理接入点 ID"
                  onChange={(event) => handleSettingsChange('videoRecognitionModel', event.target.value)}
                />
              </label>
            </article>

            <article className="settings-model-card">
              <h2>文本交互</h2>
              <label className="settings-field">
                <span>API 链接</span>
                <small>CHAT_API_URL</small>
                <input
                  type="url"
                  value={settingsForm.chatApiUrl}
                  placeholder="https://..."
                  onChange={(event) => handleSettingsChange('chatApiUrl', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>API Key</span>
                <small>CHAT_API_KEY</small>
                <input
                  type="password"
                  value={settingsForm.chatApiKey}
                  placeholder="sk-... / dashscope-... / ark-..."
                  onChange={(event) => handleSettingsChange('chatApiKey', event.target.value)}
                />
              </label>
              <label className="settings-field">
                <span>模型</span>
                <small>CHAT_MODEL</small>
                <input
                  type="text"
                  value={settingsForm.chatModel}
                  placeholder="服务商真实模型 ID / 推理接入点 ID"
                  onChange={(event) => handleSettingsChange('chatModel', event.target.value)}
                />
              </label>
            </article>
          </div>

          <div className="settings-actions">
            <button
              type="button"
              className="primary-button"
              onClick={() => void saveSettings()}
              disabled={settingsSaving || settingsLoading}
            >
              {settingsSaving ? '保存中...' : '保存到 .env'}
            </button>
            <button
              type="button"
              className="secondary-button"
              onClick={() => void loadSettings()}
              disabled={settingsLoading || settingsSaving}
            >
              {settingsLoading ? '读取中...' : '重新读取 .env'}
            </button>
            <p className="hint-text">输入框失焦后会自动同步到 .env，也可以手动点击保存。</p>
          </div>
        </section>
      </main>
    )
  }

  if (currentPage === 'analysis-settings') {
    return (
      <main className="app-shell">
        {/* 页面2.1：拆解方法设置页面 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面2.1 / 拆解方法设置</p>
              <h1>拆解方法设置</h1>
              <p className="hero-text">
                设置会保存在本地浏览器中，页面2会读取当前方案执行拆解。
              </p>
            </div>

            <div className="analysis-header-actions">
              <label className="secondary-button file-button">
                导入 JSON
                <input
                  type="file"
                  accept=".json,application/json"
                  onChange={(event) => void importDraftAnalysisSettings(event)}
                />
              </label>
              <button type="button" className="secondary-button" onClick={exportDraftAnalysisSettings}>
                导出 JSON
              </button>
              <button type="button" className="ghost-button" onClick={() => setCurrentPage('analysis')}>
                取消
              </button>
              <button type="button" className="primary-button" onClick={saveDraftAnalysisSettings}>
                确认
              </button>
            </div>
          </div>

          <div className="analysis-settings-layout">
            {analysisSettingsError ? <div className="settings-banner error">{analysisSettingsError}</div> : null}
            {analysisSettingsNotice ? <div className="settings-banner success">{analysisSettingsNotice}</div> : null}

            <section className="analysis-control-card">
              <p className="section-kicker">方法</p>
              <div className="analysis-method-panel">
                <label className="analysis-method-field">
                  <span>拆解输入模式</span>
                  <select
                    value={draftAnalysisSettings.inputMode}
                    onChange={(event) =>
                      setDraftAnalysisSettings((previous) => {
                        const inputMode = event.target.value as DecompositionInputMode
                        const methodName = inputMode === 'structured' ? 'deep' : previous.methodName
                        const nextSettings = {
                          ...previous,
                          inputMode,
                          methodName,
                        }
                        const nextSteps = nextSettings[getAnalysisStepGroup(nextSettings)]
                        setSelectedDraftStepId(nextSteps[0]?.id ?? '')
                        return {
                          ...previous,
                          inputMode,
                          methodName,
                          fastSteps: previous.fastSteps.map((step) => ({
                            ...step,
                            modelType: inputMode === 'direct-video' ? 'video-recognition' : step.modelType,
                          })),
                          directVideoDeepSteps: previous.directVideoDeepSteps.map((step) => ({
                            ...step,
                            modelType: 'video-recognition' as StepModelType,
                          })),
                          structuredDeepSteps: previous.structuredDeepSteps.map((step) => ({
                            ...step,
                            modelType: (step.modelType === 'speech-recognition' ? 'speech-recognition' : 'image-recognition') as StepModelType,
                          })),
                        }
                      })
                    }
                  >
                    <option value="direct-video">直接视频理解</option>
                    <option value="structured">结构化拆解</option>
                  </select>
                </label>

                <label className="analysis-method-field">
                  <span>拆解方法</span>
                  <select
                    value={draftAnalysisSettings.methodName}
                    disabled={draftAnalysisSettings.inputMode === 'structured'}
                    onChange={(event) =>
                      setDraftAnalysisSettings((previous) => {
                        const methodName = event.target.value as AnalysisMethodName
                        const nextSettings = { ...previous, methodName }
                        const nextSteps = nextSettings[getAnalysisStepGroup(nextSettings)]
                        setSelectedDraftStepId(nextSteps[0]?.id ?? '')
                        return {
                          ...previous,
                          methodName,
                        }
                      })
                    }
                  >
                    <option value="fast">快速拆解（一次完成）</option>
                    <option value="deep">深度拆解（多角度拆解）</option>
                  </select>
                  {draftAnalysisSettings.inputMode === 'structured' ? (
                    <em>结构化拆解固定使用深度拆解。</em>
                  ) : null}
                </label>

                <label className="analysis-method-field">
                  <span>拆解间隔（秒）</span>
                  <input
                    type="number"
                    min={1}
                    step={1}
                    value={draftAnalysisSettings.frameInterval}
                    onChange={(event) =>
                      setDraftAnalysisSettings((previous) => ({
                        ...previous,
                        frameInterval: event.target.value,
                      }))
                    }
                  />
                </label>
              </div>
            </section>

            <section className="analysis-control-card">
              <div className="analysis-step-header">
                <p className="section-kicker">步骤</p>
                {draftAnalysisSettings.methodName === 'deep' ? (
                  <button type="button" className="secondary-button" onClick={addDraftStep}>
                    新增步骤
                  </button>
                ) : null}
              </div>

              <div className="analysis-step-editor-layout">
                <div className="analysis-step-list">
                  {activeDraftSteps.map((step, index) => (
                    <button
                      key={step.id}
                      type="button"
                      className={`analysis-step-tab ${selectedDraftStep?.id === step.id ? 'active' : ''}`.trim()}
                      draggable={draftAnalysisSettings.methodName === 'deep'}
                      onClick={() => setSelectedDraftStepId(step.id)}
                      onDragStart={() => setDraggedDraftStepId(step.id)}
                      onDragOver={(event) => event.preventDefault()}
                      onDrop={(event) => {
                        event.preventDefault()
                        if (draggedDraftStepId) {
                          moveDraftStep(draggedDraftStepId, step.id)
                        }
                        setDraggedDraftStepId(null)
                      }}
                      onDragEnd={() => setDraggedDraftStepId(null)}
                    >
                      <span>{index + 1}</span>
                      <strong>{step.name}</strong>
                    </button>
                  ))}
                </div>

                {selectedDraftStep ? (
                  <article className="analysis-step-card">
                    <div className="analysis-step-card-heading">
                      <div>
                        <h3>{selectedDraftStep.name}</h3>
                        <p>{selectedDraftStep.description}</p>
                      </div>
                      {draftAnalysisSettings.methodName === 'deep' ? (
                        <button
                          type="button"
                          className="ghost-button"
                          onClick={() => deleteDraftStep(selectedDraftStep.id)}
                          disabled={activeDraftSteps.length <= 1}
                        >
                          删除步骤
                        </button>
                      ) : null}
                    </div>

                    <div className="analysis-file-actions">
                      <label className="secondary-button file-button">
                        一键加载 Skill
                        <input
                          type="file"
                          accept=".md,text/markdown,text/plain"
                          onChange={(event) => void loadStepFile(event, selectedDraftStep.id, 'skill')}
                        />
                      </label>
                      <label className="secondary-button file-button">
                        一键加载 Prompt
                        <input
                          type="file"
                          accept=".txt,text/plain"
                          onChange={(event) => void loadStepFile(event, selectedDraftStep.id, 'prompt')}
                        />
                      </label>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => saveSkillModification(selectedDraftStep.id)}
                      >
                        保存 Skill 修改
                      </button>
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => savePromptModification(selectedDraftStep.id)}
                      >
                        保存 Prompt 修改
                      </button>
                    </div>

                    <label className="analysis-method-field">
                      <span>步骤使用模型</span>
                      <select
                        value={normalizeStepModelForMode(
                          draftAnalysisSettings.inputMode,
                          selectedDraftStep.modelType,
                        )}
                        disabled={draftAnalysisSettings.inputMode === 'direct-video'}
                        onChange={(event) =>
                          setDraftAnalysisSettings((previous) => ({
                            ...previous,
                            [activeDraftStepGroup]: previous[activeDraftStepGroup].map((step) =>
                              step.id === selectedDraftStep.id
                                ? {
                                    ...step,
                                    modelType: event.target.value as StepModelType,
                                  }
                                : step,
                            ),
                          }))
                        }
                      >
                        {draftAnalysisSettings.inputMode === 'direct-video' ? (
                          <option value="video-recognition">视频识别模型</option>
                        ) : null}
                        <option value="speech-recognition">语音识别模型</option>
                        <option value="image-recognition">图片识别模型</option>
                      </select>
                      {draftAnalysisSettings.inputMode === 'direct-video' ? (
                        <em>直接视频理解模式下固定使用页面0配置的视频识别模型。</em>
                      ) : null}
                    </label>

                    <label className="analysis-method-field">
                      <span>Skill</span>
                      <em>{selectedDraftStep.skillKey ? `文件：${selectedDraftStep.skillKey}` : '未绑定 Skill 文件'}</em>
                      <textarea
                        value={selectedDraftStep.skill}
                        onChange={(event) =>
                          updateDraftStep(activeDraftStepGroup, selectedDraftStep.id, 'skill', event.target.value)
                        }
                      />
                    </label>

                    <label className="analysis-method-field analysis-prompt-field">
                      <span>Prompt</span>
                      <em>{selectedDraftStep.promptKey ? `文件：${selectedDraftStep.promptKey}` : '未绑定 Prompt 文件'}</em>
                      <textarea
                        value={selectedDraftStep.prompt}
                        onChange={(event) =>
                          updateDraftStep(activeDraftStepGroup, selectedDraftStep.id, 'prompt', event.target.value)
                        }
                      />
                    </label>

                    <div className="analysis-prompt-preview">
                      <strong>Prompt 预览</strong>
                      <p>{selectedDraftStep.prompt}</p>
                    </div>
                  </article>
                ) : null}
              </div>
            </section>
          </div>
        </section>
      </main>
    )
  }

  if (currentPage === 'task3-settings') {
    return (
      <main className="app-shell">
        {/* 页面3设置：任务3分析设置 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面3设置 / 分析设置</p>
              <h1>新内容素材分析设置</h1>
              <p className="hero-text">配置任务3的识别目标、分析模式和素材适配步骤。</p>
            </div>
            <div className="analysis-header-actions">
              <button type="button" className="ghost-button" onClick={() => setCurrentPage('task3')}>
                取消
              </button>
              <button type="button" className="primary-button" onClick={saveDraftTask3Settings}>
                确认
              </button>
            </div>
          </div>

          <section className="analysis-control-card">
            <div className="analysis-method-panel">
              <label className="analysis-method-field">
                <span>识别目标</span>
                <select
                  value={draftTask3Settings.targetMode}
                  onChange={(event) =>
                    setDraftTask3Settings((previous) => ({
                      ...previous,
                      targetMode: event.target.value,
                    }))
                  }
                >
                  <option value="material-fit">素材槽位适配</option>
                  <option value="selling-point-fit">卖点覆盖识别</option>
                  <option value="gap-detection">素材缺口识别</option>
                </select>
              </label>
              <label className="analysis-method-field">
                <span>分析输入模式</span>
                <select
                  value={draftTask3Settings.inputMode}
                  onChange={(event) =>
                    setDraftTask3Settings((previous) => ({
                      ...previous,
                      inputMode: event.target.value as Task3SettingsState['inputMode'],
                    }))
                  }
                >
                  <option value="structured">结构化分析</option>
                  <option value="multimodal">直接多模态分析</option>
                </select>
              </label>
            </div>
          </section>

          <section className="analysis-control-card">
            <p className="section-kicker">分析步骤</p>
            <div className="analysis-step-grid">
              {draftTask3Settings.steps.map((step) => (
                <article key={step.id} className="analysis-step-card">
                  <label className="analysis-method-field">
                    <span>步骤名称</span>
                    <input
                      type="text"
                      value={step.name}
                      onChange={(event) =>
                        setDraftTask3Settings((previous) => ({
                          ...previous,
                          steps: previous.steps.map((item) =>
                            item.id === step.id ? { ...item, name: event.target.value } : item,
                          ),
                        }))
                      }
                    />
                  </label>
                  <label className="analysis-method-field">
                    <span>模型类型</span>
                    <select
                      value={step.modelType}
                      onChange={(event) =>
                        setDraftTask3Settings((previous) => ({
                          ...previous,
                          steps: previous.steps.map((item) =>
                            item.id === step.id
                              ? { ...item, modelType: event.target.value as Task3StepModelType }
                              : item,
                          ),
                        }))
                      }
                    >
                      <option value="chat">文本交互模型</option>
                      <option value="image-recognition">图片识别模型</option>
                      <option value="video-recognition">视频识别模型</option>
                    </select>
                  </label>
                  <label className="analysis-method-field">
                    <span>Skill Key</span>
                    <input
                      type="text"
                      value={step.skillKey}
                      onChange={(event) =>
                        setDraftTask3Settings((previous) => ({
                          ...previous,
                          steps: previous.steps.map((item) =>
                            item.id === step.id ? { ...item, skillKey: event.target.value } : item,
                          ),
                        }))
                      }
                    />
                  </label>
                  <label className="analysis-method-field analysis-prompt-field">
                    <span>Prompt</span>
                    <textarea
                      value={step.prompt}
                      onChange={(event) =>
                        setDraftTask3Settings((previous) => ({
                          ...previous,
                          steps: previous.steps.map((item) =>
                            item.id === step.id ? { ...item, prompt: event.target.value } : item,
                          ),
                        }))
                      }
                    />
                  </label>
                </article>
              ))}
            </div>
          </section>
        </section>
      </main>
    )
  }

  if (currentPage === 'task3') {
    return (
      <main className="app-shell">
        {/* 页面3：新内容与素材输入 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面3 / 新内容与素材输入</p>
              <h1>输入新内容与用户素材</h1>
              <p className="hero-text">输入新的主题、商品卖点或素材，判断它们是否足以支撑样例视频结构。</p>
            </div>
            <div className="analysis-header-actions">
              <button type="button" className="ghost-button" onClick={() => setCurrentPage('analysis')}>
                返回上一步
              </button>
              <button type="button" className="secondary-button" onClick={openTask3Settings}>
                分析设置
              </button>
              <button type="button" className="primary-button" onClick={() => void runTask3Analysis()} disabled={task3Running}>
                {task3Running ? '分析中...' : '开始分析'}
              </button>
            </div>
          </div>

          {task3Error ? <div className="settings-banner error">{task3Error}</div> : null}
          {task3Notice ? <div className="settings-banner success">{task3Notice}</div> : null}

          <div className="analysis-layout">
            <aside className="analysis-sidebar">
              <p className="section-kicker">样例结构摘要</p>
              <h2>来自页面2</h2>
              <p>视频数量：{analysisVideoItems.length}</p>
              <p>当前设置：{formatAnalysisMethodLabel(analysisSettings.methodName)}</p>
              <p>估算镜头段数：{analysisVideo?.analysis?.shotCount ?? analysisResult?.analysis.shotCount ?? '-'}</p>
            </aside>

            <section className="analysis-main">
              <div className="analysis-control-card">
                <div className="analysis-method-panel">
                  <label className="analysis-method-field">
                    <span>新主题</span>
                    <input value={task3Draft.topic} onChange={(event) => updateTask3Draft('topic', event.target.value)} />
                  </label>
                  <label className="analysis-method-field">
                    <span>目标人群</span>
                    <input value={task3Draft.targetAudience} onChange={(event) => updateTask3Draft('targetAudience', event.target.value)} />
                  </label>
                  <label className="analysis-method-field">
                    <span>平台</span>
                    <input value={task3Draft.platform} onChange={(event) => updateTask3Draft('platform', event.target.value)} />
                  </label>
                  <label className="analysis-method-field">
                    <span>风格偏好</span>
                    <input value={task3Draft.stylePreference} onChange={(event) => updateTask3Draft('stylePreference', event.target.value)} />
                  </label>
                </div>
                <label className="analysis-method-field analysis-prompt-field">
                  <span>商品卖点（一行一个）</span>
                  <textarea value={task3Draft.sellingPointsText} onChange={(event) => updateTask3Draft('sellingPointsText', event.target.value)} />
                </label>
                <label className="analysis-method-field analysis-prompt-field">
                  <span>用户文案</span>
                  <textarea value={task3Draft.copyText} onChange={(event) => updateTask3Draft('copyText', event.target.value)} />
                </label>
              </div>

              <div className="analysis-control-card">
                <div className="analysis-step-header">
                  <p className="section-kicker">用户素材</p>
                  <button type="button" className="secondary-button" onClick={() => task3MaterialInputRef.current?.click()}>
                    上传素材
                  </button>
                  <input
                    ref={task3MaterialInputRef}
                    className="hidden-input"
                    type="file"
                    multiple
                    accept=".mp4,.mov,.jpg,.jpeg,.png,.webp,.txt"
                    onChange={handleTask3MaterialChange}
                  />
                </div>
                <div className="analysis-step-list">
                  {task3Draft.materials.length ? (
                    task3Draft.materials.map((material) => (
                      <div key={material.id} className="analysis-shot-item">
                        <strong>{material.name}</strong>
                        <span>{material.type}</span>
                      </div>
                    ))
                  ) : (
                    <div className="empty-state">还没有上传素材。</div>
                  )}
                </div>
              </div>
            </section>
          </div>
        </section>
      </main>
    )
  }

  if (currentPage === 'task3-result') {
    return (
      <main className="app-shell">
        {/* 页面3.1：素材识别与缺口分析结果 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面3.1 / 素材识别结果</p>
              <h1>素材识别与缺口分析</h1>
              <p className="hero-text">{task3AnalysisResult?.summary ?? '等待分析结果。'}</p>
            </div>
            <div className="analysis-header-actions">
              <button type="button" className="ghost-button" onClick={() => setCurrentPage('task3')}>
                返回输入
              </button>
              <button type="button" className="primary-button" onClick={() => setCurrentPage('task3-fix')}>
                补全或修改素材
              </button>
            </div>
          </div>

          {task3AnalysisResult ? (
            <div className="analysis-results">
              <article className="analysis-result-card">
                <p className="section-kicker">输入摘要</p>
                <h3>{task3InputRecord?.topic || '未填写主题'}</h3>
                <p>卖点：{task3InputRecord?.sellingPoints?.join(' / ') || '-'}</p>
                <p>素材数量：{task3InputRecord?.materials?.length ?? 0}</p>
              </article>

              <article className="analysis-result-card">
                <p className="section-kicker">素材缺口</p>
                <h3>{task3AnalysisResult.gaps.length ? `${task3AnalysisResult.gaps.length} 个缺口` : '内容完整无缺口'}</h3>
                <p>{task3AnalysisResult.summary}</p>
              </article>

              <article className="analysis-result-card analysis-result-wide">
                <p className="section-kicker">已识别素材</p>
                <div className="analysis-shot-list">
                  {task3AnalysisResult.materialInventory.map((item) => (
                    <div key={item.materialId} className="analysis-shot-item">
                      <strong>{item.materialName ?? item.materialId}</strong>
                      <span>{item.usableForSlots?.join(' / ') || '待补充标签'}</span>
                    </div>
                  ))}
                </div>
              </article>

              <article className="analysis-result-card analysis-result-wide">
                <p className="section-kicker">结构槽位匹配</p>
                <div className="analysis-shot-list">
                  {task3AnalysisResult.slotMatches.map((slot) => (
                    <div key={slot.slotId} className="analysis-shot-item">
                      <strong>{slot.slotName}</strong>
                      <span>{slot.status}</span>
                    </div>
                  ))}
                </div>
              </article>
            </div>
          ) : (
            <div className="empty-state">暂无分析结果。</div>
          )}
        </section>
      </main>
    )
  }

  if (currentPage === 'task3-fix') {
    return (
      <main className="app-shell">
        {/* 页面3.2：素材补全与修改 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面3.2 / 素材补全与修改</p>
              <h1>补全或修改素材</h1>
              <p className="hero-text">即使没有缺口，也可以主动补充素材、修改文案或调整缺口处理方式。</p>
            </div>
            <div className="analysis-header-actions">
              <button type="button" className="ghost-button" onClick={() => setCurrentPage('task3-result')}>
                返回分析结果
              </button>
              <button type="button" className="secondary-button" onClick={createSupplementMaterial}>
                生成补充素材
              </button>
              <button type="button" className="primary-button" onClick={() => void runTask3Analysis()}>
                重新分析
              </button>
              <button type="button" className="primary-button" onClick={startMigrationGeneration}>
                开始迁移生成
              </button>
            </div>
          </div>

          <div className="analysis-layout">
            <aside className="analysis-sidebar">
              <p className="section-kicker">缺口列表</p>
              {task3AnalysisResult?.gaps.length ? (
                <div className="analysis-shot-list">
                  {task3AnalysisResult.gaps.map((gap) => (
                    <div key={gap.id} className="analysis-step-card">
                      <h3>{gap.name}</h3>
                      <p>{gap.reason}</p>
                      <label className="analysis-method-field">
                        <span>处理方式</span>
                        <select value={gap.resolution ?? 'pending'} onChange={(event) => updateTask3GapResolution(gap.id, event.target.value)}>
                          <option value="pending">待处理</option>
                          <option value="upload">上传补充素材</option>
                          <option value="copy">文案/字幕补全</option>
                          <option value="package">包装补全</option>
                          <option value="reorder">重排已有素材</option>
                          <option value="ignore">忽略</option>
                        </select>
                      </label>
                    </div>
                  ))}
                </div>
              ) : (
                <div className="empty-state">内容完整无缺口，也可以继续主动优化素材。</div>
              )}
            </aside>

            <section className="analysis-main">
              <div className="analysis-control-card">
                <label className="analysis-method-field analysis-prompt-field">
                  <span>修改用户文案</span>
                  <textarea value={task3Draft.copyText} onChange={(event) => updateTask3Draft('copyText', event.target.value)} />
                </label>
                <button type="button" className="secondary-button" onClick={() => task3MaterialInputRef.current?.click()}>
                  上传补充素材
                </button>
              </div>
            </section>
          </div>
        </section>
      </main>
    )
  }

  if (currentPage === 'task4') {
    return (
      <main className="app-shell">
        {/* 页面4：结构迁移与新视频展示 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面4 / 结构迁移结果</p>
              <h1>{task4Result?.title ?? '新视频方案'}</h1>
              <p className="hero-text">{task4Result?.summary ?? '等待生成结果。'}</p>
            </div>
            <div className="analysis-header-actions">
              <button type="button" className="ghost-button" onClick={() => setCurrentPage('task3-result')}>
                重新补全/分析
              </button>
            </div>
          </div>

          <div className="analysis-results">
            <article className="analysis-result-card">
              <p className="section-kicker">新视频</p>
              <h3>{task4Result?.videoStatus ?? 'demo 待生成'}</h3>
              <p>这里后续展示新视频 demo、预览图或播放器。</p>
            </article>
            <article className="analysis-result-card">
              <p className="section-kicker">生成信息</p>
              <h3>{task4Result ? new Date(task4Result.generatedAt).toLocaleString() : '-'}</h3>
              <p>首版先展示生成状态，后续接入任务4脚本、分镜、时间线和成片 demo。</p>
            </article>
            <article className="analysis-result-card analysis-result-wide">
              <p className="section-kicker">迁移说明</p>
              <h3>基于页面2样例结构与页面3素材分析结果生成</h3>
              <p>后续会在这里展示样例结构如何映射到新内容、哪些素材被复用、哪些缺口通过包装或文案补全。</p>
            </article>
          </div>
        </section>
      </main>
    )
  }

  if (currentPage === 'analysis') {
    return (
      <main className="app-shell">
        {/* 页面2：拆解页面 */}
        <section className="analysis-panel">
          <div className="analysis-header">
            <div>
              <p className="eyebrow">页面2 / 拆解页面</p>
              <h1>视频拆解</h1>
              <p className="hero-text">
                这里会带着页面1中加载的全部视频进入拆解页，并保留每个视频的封面。
                拆解结果默认进入临时缓存，勾选后才写入数据库。
              </p>
            </div>

            <div className="analysis-header-actions">
              <button type="button" className="secondary-button" onClick={() => setCurrentPage('home')}>
                重新选择视频
              </button>
              <button type="button" className="primary-button" onClick={() => setCurrentPage('task3')}>
                进入新内容输入
              </button>
            </div>
          </div>

          {analysisError ? <div className="settings-banner error">{analysisError}</div> : null}
          {analysisNotice ? <div className="settings-banner success">{analysisNotice}</div> : null}

          <div className="analysis-layout">
            <aside className="analysis-sidebar">
              <div className="panel-header">
                <div>
                  <p className="section-kicker">页面1带入的视频</p>
                  <h2>全部已加载视频</h2>
                </div>
                <span className="count-badge">{analysisVideoItems.length}</span>
              </div>

              {analysisVideoItems.length === 0 ? (
                <div className="empty-state">页面1还没有加载任何视频。</div>
              ) : (
                <div className="video-list analysis-video-list">
                  {analysisVideoItems.map((video) => (
                    <button
                      key={video.id}
                      type="button"
                      className={`video-list-item ${analysisVideo?.id === video.id ? 'active' : ''}`.trim()}
                      onClick={() => setAnalysisTargetVideoId(video.id)}
                    >
                      <div className="video-thumb">
                        {video.coverUrl ? (
                          <img src={video.coverUrl} alt={`${video.name} cover`} />
                        ) : (
                          <div className="thumb-fallback">无封面</div>
                        )}
                      </div>

                      <div className="video-summary">
                        <div className="summary-topline">
                          <strong title={video.name}>{video.name}</strong>
                          <span className={`status-pill status-${video.status}`}>{statusLabel(video.status)}</span>
                        </div>
                        <p>
                          {formatDuration(video.durationMs)} · {video.width} x {video.height}
                        </p>
                        <p>
                          {formatBytes(video.sizeBytes)}
                          {video.analysis?.shotCount ? ` · 估算镜头段数 ${video.analysis.shotCount}` : ''}
                        </p>
                      </div>
                    </button>
                  ))}
                </div>
              )}

              <div className="analysis-sidebar-actions">
                <button type="button" className="secondary-button" onClick={() => void openAnalysisSettingsPage()}>
                  拆解方法设置
                </button>
                <button
                  type="button"
                  className="secondary-button"
                  onClick={() => void runAnalysis('all')}
                  disabled={analysisRunning || analysisLoading || videos.length === 0}
                >
                  全部拆解
                </button>
              </div>
            </aside>

            {analysisVideo ? (
              <div className="analysis-main">
                <div className="analysis-hero">
                  <div className="analysis-cover-card">
                    <p className="section-kicker">当前封面</p>
                    <div className="analysis-cover-shell">
                      {analysisVideo.coverUrl ? (
                        <img src={analysisVideo.coverUrl} alt={`${analysisVideo.name} cover`} />
                      ) : (
                        <div className="thumb-fallback analysis-cover-fallback">无封面</div>
                      )}
                    </div>
                    <h2 title={analysisVideo.name}>{analysisVideoDisplayName}</h2>
                      <p>
                        {formatDuration(analysisVideo.durationMs)} · {analysisVideo.width} x {analysisVideo.height}
                      </p>
                    <p>
                      {formatBytes(analysisVideo.sizeBytes)}
                      {analysisVideo.analysis?.shotCount
                        ? ` · 估算镜头段数 ${analysisVideo.analysis.shotCount}`
                        : ''}
                    </p>
                  </div>

                  <div className="analysis-control-card">
                    <div className="analysis-toggle-row">
                      <div>
                        <p className="section-kicker">拆解控制</p>
                        <h2>拆解设置</h2>
                      </div>
                      <label className="analysis-checkbox">
                        <input
                          type="checkbox"
                          checked={analysisPersistToDb}
                          onChange={(event) => setAnalysisPersistToDb(event.target.checked)}
                        />
                        <span>将拆解结果纳入数据库</span>
                      </label>
                    </div>

                    <div className="analysis-button-row">
                      <button
                        type="button"
                        className="primary-button"
                        onClick={() => void runAnalysis('single')}
                        disabled={analysisRunning || analysisLoading}
                      >
                        {analysisRunning ? '拆解中...' : '拆解'}
                      </button>
                    </div>

                    {analysisResult ? (
                      <div className="analysis-result-meta">
                        <span>{analysisResult.cached ? '临时缓存命中' : '最新拆解结果'}</span>
                        <strong>
                          {formatAnalysisMethodLabel(analysisResult.methodName)} · 间隔 {analysisResult.frameInterval}s
                        </strong>
                      </div>
                    ) : null}

                    <div className="analysis-result-meta">
                      <span>当前拆解设置</span>
                      <strong>
                        {analysisSettings.inputMode === 'structured' ? '结构化拆解' : '直接视频理解'} ·
                        {formatAnalysisMethodLabel(analysisSettings.methodName)} · 间隔 {analysisSettings.frameInterval}s
                      </strong>
                      <span className="analysis-settings-summary" title={analysisSettingsSummary}>
                        {analysisSettingsSummary}
                      </span>
                    </div>
                  </div>
                </div>

                {analysisResult ? (
                  <div className="analysis-results">
                    <article className="analysis-result-card">
                      <p className="section-kicker">拆解概览</p>
                      <h3>{analysisResult.analysis.summary ?? '已复用页面1上传时自动生成的镜头段解析结果。'}</h3>
                      <p>
                        缓存时间：{new Date(analysisResult.cachedAt).toLocaleString()} ·
                        {analysisResult.persistedToDb ? ' 已写入数据库' : ' 仅缓存未入库'}
                      </p>
                    </article>

                    <article className="analysis-result-card">
                      <p className="section-kicker">镜头拆解</p>
                      <h3>估算镜头段数：{analysisResult.analysis.shotCount} 段</h3>
                      <p>
                        {analysisResult.analysis.shotDetection?.label ?? '估算镜头段数'} ·
                        {analysisResult.analysis.shotDetection?.method === 'interval_fallback'
                          ? ' 回退估算'
                          : ' PySceneDetect'}
                      </p>
                      <div className="analysis-shot-list">
                        {analysisResult.analysis.shots.map((shot) => (
                          <div key={shot.index} className="analysis-shot-item">
                            <strong>片段 {shot.index}</strong>
                            <span>
                              {Math.round(shot.startMs)}ms - {Math.round(shot.endMs)}ms
                            </span>
                          </div>
                        ))}
                      </div>
                    </article>

                    <article className="analysis-result-card">
                      <p className="section-kicker">字幕概览</p>
                      <h3>{analysisResult.analysis.subtitleOverview?.hasSubtitle ? '检测到字幕' : '未检测到字幕'}</h3>
                      <p>
                        语言：{analysisResult.analysis.subtitleOverview?.language ?? '-'} · 密度：
                        {analysisResult.analysis.subtitleOverview?.density ?? '-'}
                      </p>
                      <p>
                        {analysisResult.analysis.subtitleOverview?.sampleLines?.length
                          ? analysisResult.analysis.subtitleOverview.sampleLines.join(' / ')
                          : '暂无字幕样本。'}
                      </p>
                    </article>

                    <article className="analysis-result-card">
                      <p className="section-kicker">语音概览</p>
                      <h3>{analysisResult.analysis.voiceOverview?.hasSpeech ? '检测到语音' : '未检测到语音'}</h3>
                      <p>{analysisResult.analysis.voiceOverview?.summary ?? '暂无语音摘要。'}</p>
                      <p>
                        {analysisResult.analysis.voiceOverview?.keywords?.length
                          ? analysisResult.analysis.voiceOverview.keywords.join(' / ')
                          : '暂无关键词。'}
                      </p>
                    </article>

                    <article className="analysis-result-card analysis-result-wide">
                      <p className="section-kicker">临时缓存说明</p>
                      <h3>避免重复拆解的方式</h3>
                      <p>
                        当前后端会把视频 ID + 拆解方法 + 间隔组成缓存键，命中后会直接返回临时缓存结果，
                        不会重复执行拆解；只有勾选“将拆解结果纳入数据库”时，才会把结果写进视频记录。
                      </p>
                    </article>
                  </div>
                ) : (
                  <div className="analysis-ready-state">
                    <p className="section-kicker">准备就绪</p>
                    <h3>点击上方"拆解"按钮开始分析视频</h3>
                    <p>选择拆解方法和间隔后，点击拆解即可查看结果。</p>
                  </div>
                )}
              </div>
            ) : (
              <div className="empty-state">没有可拆解的视频，请先回到页面1上传视频。</div>
            )}
          </div>
        </section>
      </main>
    )
  }

  return (
    <main className="app-shell">
      {/* 页面1：基础解析页面 */}
      <section
        className={`hero-panel ${isDragging ? 'dragging' : ''}`.trim()}
        onDragEnter={handleDragEnter}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        <div className="hero-copy">
          <p className="eyebrow">Task 1 / Step 1, 2, 7</p>
          <h1>样例视频输入与基础解析</h1>
          <p className="hero-text">
            上传一个或多个本地视频后，后端会立刻保存文件、抽取时长、分辨率、帧率、文件大小和封面，
            前端按卡片列表和详情面板展示结果。
          </p>
        </div>

        <div className="upload-panel">
          <button type="button" className="primary-button" onClick={triggerFilePicker}>
            选择视频
          </button>
          <button type="button" className="secondary-button" onClick={() => setCurrentPage('settings')}>
            设置
          </button>
          <p className="hint-text">当前支持 MP4 / MOV，多文件上传会并行进入列表。</p>

          <input
            ref={fileInputRef}
            className="hidden-input"
            type="file"
            accept=".mp4,.mov,video/mp4,video/quicktime"
            multiple
            onChange={handleFileChange}
          />

          <div className="upload-progress">
            <div className="progress-meta">
              <span>上传状态</span>
              <strong>{uploading ? `${uploadProgress}%` : '待上传'}</strong>
            </div>
            <div className="progress-track" aria-hidden="true">
              <div className="progress-bar" style={{ width: `${uploadProgress}%` }} />
            </div>
          </div>
        </div>
      </section>

      {pageError ? <div className="error-banner">{pageError}</div> : null}

      <section className="workspace-panel">
        <aside className="list-panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">样例列表</p>
              <h2>已上传视频</h2>
            </div>
            <span className="count-badge">{videos.length}</span>
          </div>

          {isLoading ? (
            <div className="empty-state">正在读取已上传的视频列表...</div>
          ) : videos.length === 0 ? (
            <div className="empty-state">还没有视频。先上传一个 MP4 或 MOV 文件。</div>
          ) : (
            <div className="video-list-scroll">
              <div className="video-list">
                {videos.map((video) => (
                  <button
                    key={video.id}
                    type="button"
                    className={`video-list-item ${selectedVideo?.id === video.id ? 'active' : ''}`.trim()}
                    onClick={() => setSelectedId(video.id)}
                  >
                    <div className="video-thumb">
                      {video.coverUrl ? (
                        <img src={video.coverUrl} alt={`${video.name} cover`} />
                      ) : (
                        <div className="thumb-fallback">无封面</div>
                      )}
                    </div>

                    <div className="video-summary">
                      <div className="summary-topline">
                        <strong title={video.name}>{video.name}</strong>
                        <span className={`status-pill status-${video.status}`}>{statusLabel(video.status)}</span>
                      </div>
                      <p>
                        {formatDuration(video.durationMs)} · {video.width} x {video.height}
                      </p>
                      <p>{formatBytes(video.sizeBytes)}</p>
                    </div>
                  </button>
                ))}
              </div>
            </div>
          )}

          <div className="list-panel-footer">
            <button
              type="button"
              className="primary-button"
              disabled={videos.length === 0}
              onClick={() => {
                if (selectedVideo) {
                  setAnalysisPageVideos(videos.map((video) => ({ ...video })))
                  setAnalysisTargetVideoId(selectedVideo.id)
                }
                setAnalysisResult(null)
                setAnalysisNotice(null)
                setAnalysisError(null)
                setCurrentPage('analysis')
              }}
            >
              开始拆解
            </button>
          </div>
        </aside>

        <section className="detail-panel">
          {selectedVideo ? (
            <>
              <div className="panel-header">
                <div>
                  <p className="section-kicker">视频详情</p>
                  <h2 title={selectedVideo.name}>{selectedVideo.name}</h2>
                </div>
                <div className="detail-actions">
                  <span className={`status-pill status-${selectedVideo.status}`}>
                    {statusLabel(selectedVideo.status)}
                  </span>
                  <button
                    type="button"
                    className="ghost-button"
                    onClick={() => handleDelete(selectedVideo.id)}
                  >
                    删除视频
                  </button>
                </div>
              </div>

              <div className="preview-shell">
                <video
                  key={selectedVideo.id}
                  src={selectedVideo.videoUrl}
                  controls
                  preload="auto"
                  poster={selectedVideo.coverUrl ?? undefined}
                  playsInline
                />
              </div>

              <div className="meta-grid">
                <article className="meta-card">
                  <span>时长</span>
                  <strong>{formatDuration(selectedVideo.durationMs)}</strong>
                </article>
                <article className="meta-card">
                  <span>分辨率</span>
                  <strong>
                    {selectedVideo.width} x {selectedVideo.height}
                  </strong>
                </article>
                <article className="meta-card">
                  <span>帧率</span>
                  <strong>{formatFps(selectedVideo.fps)}</strong>
                </article>
                <article className="meta-card">
                  <span>大小</span>
                  <strong>{formatBytes(selectedVideo.sizeBytes)}</strong>
                </article>
              </div>

              <div className="analysis-grid">
                <article className="analysis-card">
                  <p className="section-kicker">镜头分析</p>
                  <h3>
                    {selectedVideo.analysis?.shotCount
                      ? `估算镜头段数：${selectedVideo.analysis.shotCount} 段`
                      : '待拆解'}
                  </h3>
                  <p>
                    {selectedVideo.analysis?.shotCount
                      ? '已基于拆解结果展示画面切换形成的镜头段数量。'
                      : '进入拆解页运行分析后，这里会展示估算镜头段数。'}
                  </p>
                </article>
                <article className="analysis-card">
                  <p className="section-kicker">字幕概览</p>
                  <h3>待接入 Step 5</h3>
                  <p>建议在此处展示是否检测到字幕、语言、密度和代表性字幕样本。</p>
                </article>
                <article className="analysis-card">
                  <p className="section-kicker">语音概览</p>
                  <h3>待接入 Step 6</h3>
                  <p>后续可补语音摘要、关键词和转写预览，当前界面位置已经预留。</p>
                </article>
              </div>

              {selectedVideo.status === 'failed' && selectedVideo.errorMessage ? (
                <div className="error-banner">{selectedVideo.errorMessage}</div>
              ) : null}
            </>
          ) : (
            <div className="detail-empty">
              选择左侧卡片后，这里会显示视频预览和解析详情。
            </div>
          )}
        </section>
      </section>
    </main>
  )
}

export default App
