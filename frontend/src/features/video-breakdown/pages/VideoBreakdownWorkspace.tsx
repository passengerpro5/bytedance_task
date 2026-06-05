import { ChangeEvent, FormEvent, ReactNode, useEffect, useMemo, useRef, useState } from "react";
import {
  AlertCircle,
  BadgeCheck,
  Blocks,
  Camera,
  CheckCircle2,
  Clapperboard,
  Clock3,
  Copy,
  Download,
  ExternalLink,
  FileText,
  Film,
  Link as LinkIcon,
  Library,
  Loader2,
  PlayCircle,
  RefreshCw,
  Send,
  Sparkles,
  Tags,
  Trash2,
  UploadCloud,
  X,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { API_BASE, videoBreakdownClient } from "../api/videoBreakdownClient";
import { CreativeLibraryPage } from "./CreativeLibraryPage";
import type { CreativeAssetScriptGenerationIntent } from "./CreativeLibraryPage";
import { ScriptEditorialPage } from "./ScriptEditorialPage";
import type { ScriptGenerationIntent, ScriptGenerationPayload } from "./ScriptEditorialPage";
import {
  Classification,
  Decomposition,
  DirectorGenerationJobRecord,
  DirectorPlanAssetBindingRecord,
  DirectorPlanRecord,
  DirectorPublishRecord,
  DirectorRenderArtifactRecord,
  DirectorRenderJobRecord,
  DirectorRenderUsageRecord,
  JsonObject,
  JsonValue,
  ManualFactoryAssetRecord,
  MorasAssetLibraryRecord,
  ScriptRecord,
  ScriptStoryboardShot,
  SocialVideoAnalysis,
  SourceVideo,
} from "../types";

type SubmitState = "idle" | "running" | "done" | "failed";
type HistoryState = "idle" | "loading" | "failed";
type WorkspaceTab = "teardown" | "scripts" | "factory";
type TeardownView = "intake" | "creative-library";

type TimelineItem = {
  id: string;
  title: string;
  time: string;
  role: string;
  content: string;
  technique: string;
};

const statusCopy: Record<string, string> = {
  pending: "排队中",
  importing: "导入视频",
  running: "模型拆解中",
  succeeded: "已完成",
  failed: "失败",
};

const fieldLabels: Record<string, string> = {
  originalUrl: "原始链接",
  importedVideoUrl: "导入后视频",
  sourceUrl: "来源地址",
  title: "标题",
  platform: "平台",
  creatorHandle: "创作者",
  durationSeconds: "时长",
  observedMetrics: "可见指标",
  visibleMetrics: "可见指标",
  sourceNotes: "来源备注",
  contentSummary: "内容摘要",
  taxonomyVersion: "分类版本",
  hookType: "Hook 因子",
  emotionFactors: "情绪因子",
  personaFactors: "人设因子",
  sceneFactors: "场景因子",
  conflictFactors: "冲突因子",
  painFactors: "痛点因子",
  itchFactors: "痒点因子",
  valueFactors: "Value 因子",
  proofFactors: "Proof 因子",
  ctaFactors: "CTA 因子",
  structureFactors: "视频结构因子",
  visualRhythmFactors: "视觉节奏因子",
  audienceSegments: "人群洞察",
  generalTemplates: "General 模板",
  verticalTemplates: "Vertical 模板",
  confidence: "置信度",
  evidence: "判断证据",
  standardId: "标准编号",
  factorReasoning: "判断依据",
  missingInputs: "缺失输入",
  version: "版本",
  source: "来源",
  corePattern: "核心结构",
  timelineSlots: "时间线槽位",
  reuseRules: "复用规则",
  riskFlags: "风险标记",
  slotId: "槽位编号",
  name: "槽位名称",
  startSecond: "开始秒",
  endSecond: "结束秒",
  role: "结构作用",
  observableEvidence: "观察证据",
  requiredAssets: "所需素材",
  transferRule: "迁移规则",
  oneSentenceSummary: "一句话拆解",
  hook: "开头钩子",
  openingHook: "开头钩子",
  narrativeStructure: "叙事结构",
  contentStructure: "内容结构",
  segments: "片段",
  keyTakeaways: "关键结论",
  keyShots: "关键镜头",
  visualLanguage: "画面语言",
  audioLanguage: "声音语言",
  interactionOrCta: "互动 / 行动引导",
  performanceLogic: "有效机制",
  reusablePattern: "可复用模式",
  scriptAgentInstructions: "脚本智能体指令",
  variablesToCollect: "需要补齐的变量",
  doNotCopy: "不可照搬",
  adaptationNotes: "迁移备注",
  usableInsights: "可用洞察",
  doNotGenerate: "禁止生成",
  reservedStandardIds: "保留标准编号",
};

const hiddenSourceKeys = new Set([
  "originalUrl",
  "importedVideoUrl",
  "sourceUrl",
  "title",
  "platform",
  "creatorHandle",
  "durationSeconds",
  "contentSummary",
  "observedMetrics",
  "visibleMetrics",
]);
const hiddenClassificationKeys = new Set([
  "taxonomyVersion",
  "hookType",
  "emotionFactors",
  "personaFactors",
  "sceneFactors",
  "conflictFactors",
  "painFactors",
  "itchFactors",
  "valueFactors",
  "proofFactors",
  "ctaFactors",
  "structureFactors",
  "visualRhythmFactors",
  "audienceSegments",
  "generalTemplates",
  "verticalTemplates",
  "confidence",
  "evidence",
  "standardId",
  "factorReasoning",
  "missingInputs",
]);
const hiddenDecompositionKeys = new Set([
  "oneSentenceSummary",
  "hook",
  "openingHook",
  "narrativeStructure",
  "contentStructure",
  "segments",
  "keyTakeaways",
  "visualLanguage",
  "audioLanguage",
  "interactionOrCta",
  "performanceLogic",
]);
const hiddenBridgeKeys = new Set([
  "reusablePattern",
  "scriptAgentInstructions",
  "variablesToCollect",
  "doNotCopy",
  "adaptationNotes",
  "usableInsights",
  "doNotGenerate",
  "reservedStandardIds",
  "missingInputs",
]);

const workspaceTabs: Array<{ id: WorkspaceTab; label: string; icon: LucideIcon }> = [
  { id: "teardown", label: "视频拆解", icon: Film },
  { id: "scripts", label: "脚本编辑部", icon: FileText },
  { id: "factory", label: "视频工厂", icon: Camera },
];
const appDisplayName = "社媒视频生产 Agent";

const realMorasAssetTypeOptions = [
  { value: "real_moras_screen_recording", label: "Moras 录屏" },
  { value: "real_moras_screenshot", label: "Moras 截图" },
  { value: "moras_product_workflow", label: "Moras 工作流" },
];

const realMorasAssetCategoryOptions = [
  { value: "workflow_screen_recording", label: "工作流录屏" },
  { value: "product_card_to_video_draft_before_after", label: "商品卡到视频草稿对比" },
  { value: "product_to_script_before_after", label: "商品到脚本对比（旧）" },
  { value: "time_saved_comparison", label: "省时对比" },
  { value: "product_selection_logic", label: "选品逻辑" },
  { value: "published_content_feedback", label: "发布反馈" },
  { value: "approved_feature_screenshot", label: "功能截图" },
];

const workspaceActiveTabStorageKey = "moras.workspace.activeTab";
const factoryActiveScriptStorageKey = "moras.videoFactory.activeScriptId";

export function VideoBreakdownWorkspace() {
  const [videoUrl, setVideoUrl] = useState("");
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [analysis, setAnalysis] = useState<SocialVideoAnalysis | null>(null);
  const [submitState, setSubmitState] = useState<SubmitState>("idle");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [history, setHistory] = useState<SocialVideoAnalysis[]>([]);
  const [historyState, setHistoryState] = useState<HistoryState>("idle");
  const [historyError, setHistoryError] = useState("");
  const [isLibraryOpen, setIsLibraryOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<WorkspaceTab>(() => readWorkspaceActiveTab());
  const [teardownView, setTeardownView] = useState<TeardownView>("intake");
  const [factoryScript, setFactoryScript] = useState<ScriptGenerationPayload | null>(null);
  const [scriptGenerationIntent, setScriptGenerationIntent] = useState<ScriptGenerationIntent | null>(null);
  const uploadInputRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    document.title = appDisplayName;
  }, []);

  useEffect(() => {
    void loadHistory();
  }, []);

  const trimmedUrl = videoUrl.trim();
  const canSubmit = (selectedFile !== null || isSupportedVideoUrl(trimmedUrl)) && submitState !== "running";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!canSubmit) return;

    setSubmitState("running");
    setError("");
    setNotice("");
    setAnalysis(null);

    try {
      const result = selectedFile
        ? await videoBreakdownClient.uploadSocialVideoAnalysis(selectedFile)
        : await videoBreakdownClient.createSocialVideoAnalysis(trimmedUrl);
      setAnalysis(result);
      setSelectedFile(null);
      upsertHistory(result);
      if (result.status === "failed") {
        setSubmitState("failed");
        setError(result.errorMessage || "视频拆解失败，请稍后重试。");
      } else {
        setSubmitState("done");
        setNotice(result.reusedExisting ? "检测到该视频已拆解过，已打开历史拆解结果，未重复消耗模型分析。" : "");
      }
    } catch (err) {
      setSubmitState("failed");
      setError(err instanceof Error ? err.message : "视频拆解失败，请稍后重试。");
    }
  }

  function handleVideoUrlChange(event: ChangeEvent<HTMLInputElement>) {
    setVideoUrl(event.target.value);
    setSelectedFile(null);
    setAnalysis(null);
    setError("");
    setNotice("");
    if (submitState !== "running") {
      setSubmitState("idle");
    }
  }

  function handleUploadChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    event.target.value = "";
    if (!file || submitState === "running") return;

    setSelectedFile(file);
    setVideoUrl("");
    setSubmitState("idle");
    setError("");
    setNotice("");
    setAnalysis(null);
  }

  async function loadHistory() {
    setHistoryState("loading");
    setHistoryError("");
    try {
      const records = await videoBreakdownClient.listSocialVideoAnalyses();
      setHistory(records);
      setHistoryState("idle");
    } catch (err) {
      setHistoryState("failed");
      setHistoryError(err instanceof Error ? err.message : "历史记录加载失败。");
    }
  }

  function upsertHistory(record: SocialVideoAnalysis) {
    setHistory(current => {
      const next = current.filter(item => item.id !== record.id);
      return [record, ...next];
    });
  }

  function handleOpenLibrary() {
    setIsLibraryOpen(true);
    void loadHistory();
  }

  function handleOpenCreativeLibrary() {
    setTeardownView("creative-library");
    setIsLibraryOpen(false);
    void loadHistory();
  }

  function handleSelectHistory(record: SocialVideoAnalysis) {
    setAnalysis(record);
    setError(record.status === "failed" ? record.errorMessage || "该视频拆解失败。" : "");
    setSubmitState(record.status === "failed" ? "failed" : record.status === "succeeded" ? "done" : "idle");
    const sourceUrl = firstString(record.sourceVideo?.originalUrl, record.sourceVideo?.sourceUrl);
    setVideoUrl(sourceUrl.startsWith("/uploads/") ? "" : sourceUrl);
    setSelectedFile(null);
    setIsLibraryOpen(false);
  }

  async function handleDeleteHistory(record: SocialVideoAnalysis) {
    await videoBreakdownClient.deleteSocialVideoAnalysis(record.id);
    setHistory(current => current.filter(item => item.id !== record.id));
    if (analysis?.id === record.id) {
      setAnalysis(null);
      setVideoUrl("");
      setSelectedFile(null);
      setSubmitState("idle");
      setError("");
    }
  }

  function handleGenerateScriptFromCreativeAsset(intent: CreativeAssetScriptGenerationIntent) {
    setScriptGenerationIntent(intent);
    storeWorkspaceActiveTab("scripts");
    setActiveTab("scripts");
    setIsLibraryOpen(false);
    setTeardownView("intake");
  }

  return (
    <main className={`dashboard-shell${activeTab === "scripts" ? " dashboard-shell--script-editorial" : ""}`}>
      <section className="dashboard-header" aria-labelledby="page-title">
        <div className="workspace-header-main">
          <h1 id="page-title" className="visually-hidden">{appDisplayName}</h1>
          <nav className={`workspace-tabs workspace-tabs--${activeTab}`} aria-label={`${appDisplayName}模块`} role="tablist">
            <span className="workspace-tabs__indicator" aria-hidden="true" />
            {workspaceTabs.map(tab => {
              const TabIcon = tab.icon;
              const isActive = activeTab === tab.id;

              return (
                <button
                  key={tab.id}
                  type="button"
                  className={`workspace-tab${isActive ? " workspace-tab--active" : ""}`}
                  role="tab"
                  aria-selected={isActive}
                  onClick={() => {
                    storeWorkspaceActiveTab(tab.id);
                    setActiveTab(tab.id);
                    setIsLibraryOpen(false);
                    setTeardownView("intake");
                  }}
                >
                  <span className="workspace-tab__content">
                    <TabIcon className="workspace-tab__icon" size={20} strokeWidth={2.5} aria-hidden="true" />
                    <span className="workspace-tab__label">{tab.label}</span>
                  </span>
                </button>
              );
            })}
          </nav>
        </div>
      </section>

      <LibraryDrawer
        open={activeTab === "teardown" && isLibraryOpen}
        items={history}
        selectedId={analysis?.id}
        state={historyState}
        error={historyError}
        onClose={() => setIsLibraryOpen(false)}
        onRefresh={loadHistory}
        onSelect={handleSelectHistory}
        onDelete={handleDeleteHistory}
      />

      {activeTab === "teardown" ? (
        teardownView === "creative-library" ? (
          <CreativeLibraryPage
            analyses={history}
            onBack={() => setTeardownView("intake")}
            onGenerateScript={handleGenerateScriptFromCreativeAsset}
          />
        ) : (
          <>
            <section className="teardown-intro">
              <p>输入一个社媒视频链接，自动完成来源导入、爆款因子分类和内容拆解。</p>
              <div className="teardown-actions">
                <nav className="teardown-secondary-tabs" aria-label="视频拆解二级导航" role="tablist">
                  <button
                    className="teardown-secondary-tab"
                    type="button"
                    role="tab"
                    aria-selected={false}
                    onClick={handleOpenCreativeLibrary}
                  >
                    <Library size={18} aria-hidden="true" />
                    <span>创意仓库</span>
                  </button>
                </nav>
                <button className="library-button" type="button" onClick={handleOpenLibrary} aria-haspopup="dialog">
                  <Library size={18} aria-hidden="true" />
                  <span>历史</span>
                  {history.length > 0 && <strong>{history.length}</strong>}
                </button>
              </div>
            </section>
            <form className="analysis-form" onSubmit={handleSubmit} noValidate>
              <label className="video-url-field">
                <span>视频链接</span>
                <div className="video-url-control">
                  <LinkIcon size={18} aria-hidden="true" />
                  <input
                    type="text"
                    value={videoUrl}
                    onChange={handleVideoUrlChange}
                    placeholder="https://www.tiktok.com/... 或 https://www.douyin.com/..."
                    disabled={submitState === "running"}
                    aria-describedby="video-url-help"
                  />
                </div>
              </label>
              <input
                ref={uploadInputRef}
                className="visually-hidden"
                type="file"
                accept="video/mp4,video/quicktime,.mp4,.mov"
                aria-label="上传本地视频"
                onChange={handleUploadChange}
              />
              <button
                className="upload-button"
                type="button"
                disabled={submitState === "running"}
                onClick={() => uploadInputRef.current?.click()}
              >
                <UploadCloud size={18} aria-hidden="true" />
                上传本地视频
              </button>
              <button className="submit-button" type="submit" disabled={!canSubmit}>
                {submitState === "running" ? <Loader2 className="spin" size={18} aria-hidden="true" /> : <Send size={18} aria-hidden="true" />}
                {submitState === "running" ? "正在拆解" : "开始拆解"}
              </button>
              <p id="video-url-help" className="form-help">
                {selectedFile
                  ? `已选择本地视频：${selectedFile.name}。点击“开始拆解”后上传并分析。`
                  : "支持公开视频链接或本地 mp4 / mov；后端会负责导入视频并返回完整拆解结果。"}
              </p>
            </form>

            {submitState === "running" && <RunningPanel />}
            {notice && <StatusBanner message={notice} />}
            {error && <ErrorBanner message={error} />}

            {analysis ? (
              <AnalysisDashboard analysis={analysis} />
            ) : (
              submitState !== "running" && (
                <section className="empty-dashboard">
                  <Sparkles size={28} aria-hidden="true" />
                  <div>
                    <h2>等待输入视频链接</h2>
                    <p>结果会按来源状态、爆款因子分类、开头钩子、结构时间线和关键镜头分区展示。</p>
                  </div>
                </section>
              )
            )}
          </>
        )
      ) : activeTab === "scripts" ? (
          <ScriptEditorialPage
            generationIntent={scriptGenerationIntent}
            onGenerationIntentHandled={intentId => {
              setScriptGenerationIntent(current => (current?.id === intentId ? null : current));
            }}
            onStartVideoGeneration={payload => {
              setFactoryScript(payload);
              storeWorkspaceActiveTab("factory");
              setActiveTab("factory");
              setIsLibraryOpen(false);
              setTeardownView("intake");
            }}
        />
      ) : (
        <VideoFactory script={factoryScript} />
      )}
    </main>
  );
}

function VideoFactory({ script }: { script: ScriptGenerationPayload | null }) {
  const [localScript, setLocalScript] = useState<ScriptGenerationPayload | null>(null);
  const [factoryScripts, setFactoryScripts] = useState<ScriptRecord[]>([]);
  const [factoryScriptsState, setFactoryScriptsState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [factoryScriptsError, setFactoryScriptsError] = useState("");
  const [selectedFactoryScriptId, setSelectedFactoryScriptId] = useState("");
  const [directorPlan, setDirectorPlan] = useState<DirectorPlanRecord | null>(null);
  const [directorGenerationJob, setDirectorGenerationJob] = useState<DirectorGenerationJobRecord | null>(null);
  const [manualAssets, setManualAssets] = useState<ManualFactoryAssetRecord[]>([]);
  const [morasAssets, setMorasAssets] = useState<MorasAssetLibraryRecord[]>([]);
  const [assetBindings, setAssetBindings] = useState<DirectorPlanAssetBindingRecord[]>([]);
  const [renderJobs, setRenderJobs] = useState<DirectorRenderJobRecord[]>([]);
  const [renderArtifacts, setRenderArtifacts] = useState<DirectorRenderArtifactRecord[]>([]);
  const [renderUsage, setRenderUsage] = useState<DirectorRenderUsageRecord | null>(null);
  const [renderAccountingState, setRenderAccountingState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [renderAccountingError, setRenderAccountingError] = useState("");
  const [artifactCleanupState, setArtifactCleanupState] = useState<"idle" | "running">("idle");
  const [deletingArtifactId, setDeletingArtifactId] = useState("");
  const [artifactCleanupError, setArtifactCleanupError] = useState("");
  const [publishRecords, setPublishRecords] = useState<DirectorPublishRecord[]>([]);
  const [renderState, setRenderState] = useState<"idle" | "running" | "failed">("idle");
  const [renderError, setRenderError] = useState("");
  const [qaReviewingRenderJobId, setQaReviewingRenderJobId] = useState("");
  const [publishState, setPublishState] = useState<"idle" | "running">("idle");
  const [publishError, setPublishError] = useState("");
  const [publishChannel, setPublishChannel] = useState("manual_upload");
  const [state, setState] = useState<"idle" | "loading" | "ready" | "failed">("idle");
  const [error, setError] = useState("");
  const [manualAssetError, setManualAssetError] = useState("");
  const [assetBindingError, setAssetBindingError] = useState("");
  const [uploadingClipId, setUploadingClipId] = useState("");
  const [uploadingAssetRef, setUploadingAssetRef] = useState("");
  const [bindingAssetRef, setBindingAssetRef] = useState("");
  const [reviewingAssetId, setReviewingAssetId] = useState("");
  const [selectedLibraryAssetIds, setSelectedLibraryAssetIds] = useState<Record<string, string>>({});
  const [copiedClipId, setCopiedClipId] = useState("");
  const [libraryAssetType, setLibraryAssetType] = useState("real_moras_screen_recording");
  const [libraryAssetCategory, setLibraryAssetCategory] = useState("workflow_screen_recording");
  const [libraryAssetTitle, setLibraryAssetTitle] = useState("");
  const [isUploadingLibraryAsset, setIsUploadingLibraryAsset] = useState(false);
  const [libraryAssetError, setLibraryAssetError] = useState("");
  const effectiveScript = script ?? localScript;
  const generationScriptIdRef = useRef("");
  const latestPlanRequestIdRef = useRef(0);
  const isDirectorJobRunning = isRunningDirectorGenerationJob(directorGenerationJob);
  const canRetryDirectorJob = directorGenerationJob?.status === "failed" || directorGenerationJob?.status === "canceled";
  const latestRenderJob = renderJobs[0] ?? null;
  const isRenderJobRunning = isRunningDirectorRenderJob(latestRenderJob);
  const canRetryRenderJob = latestRenderJob?.status === "blocked" || latestRenderJob?.status === "failed";
  const hasExpiredRenderArtifacts = renderArtifacts.some(artifact => artifact.storageStatus === "retention_expired");

  async function loadRenderAccounting(renderJobId: string, isCancelled: () => boolean = () => false) {
    setRenderAccountingState("loading");
    setRenderAccountingError("");
    try {
      const [artifacts, usage] = await Promise.all([
        videoBreakdownClient.listDirectorRenderArtifacts(renderJobId),
        videoBreakdownClient.getDirectorRenderUsage(renderJobId),
      ]);
      if (isCancelled()) return;
      setRenderArtifacts(artifacts);
      setRenderUsage(usage);
      setRenderAccountingState("ready");
    } catch (err) {
      if (isCancelled()) return;
      setRenderArtifacts([]);
      setRenderUsage(null);
      setRenderAccountingState("failed");
      setRenderAccountingError(err instanceof Error ? err.message : "渲染产物账本加载失败。");
    }
  }

  useEffect(() => {
    if (!latestRenderJob || latestRenderJob.status !== "succeeded") {
      setRenderArtifacts([]);
      setRenderUsage(null);
      setRenderAccountingState("idle");
      setRenderAccountingError("");
      setArtifactCleanupError("");
      return;
    }
    let cancelled = false;
    void loadRenderAccounting(latestRenderJob.id, () => cancelled);
    return () => {
      cancelled = true;
    };
  }, [latestRenderJob?.id, latestRenderJob?.status]);

  useEffect(() => {
    let cancelled = false;
    videoBreakdownClient.listMorasAssets()
      .then(records => {
        if (!cancelled) setMorasAssets(records);
      })
      .catch(err => {
        if (!cancelled) setLibraryAssetError(err instanceof Error ? err.message : "真实 Moras 素材库加载失败。");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (script) {
      setLocalScript(null);
      return;
    }
    if (localScript) return;

    let cancelled = false;
    setFactoryScriptsState("loading");
    setFactoryScriptsError("");
    videoBreakdownClient.listScripts()
      .then(async records => {
        if (cancelled) return;
        const storedScriptId = readFactoryActiveScriptId();
        const storedRecord = records.find(record => record.id === storedScriptId);
        let recoveredStoredRecord: ScriptRecord | null = null;
        if (storedScriptId && !storedRecord) {
          try {
            recoveredStoredRecord = await videoBreakdownClient.getScript(storedScriptId);
          } catch {
            recoveredStoredRecord = null;
          }
        }
        if (cancelled) return;
        const recordsForFactory = recoveredStoredRecord
          ? [recoveredStoredRecord, ...records.filter(record => record.id !== recoveredStoredRecord?.id)]
          : records;
        const activeRecord = storedRecord ?? recoveredStoredRecord;
        setFactoryScripts(recordsForFactory);
        setSelectedFactoryScriptId(current => {
          if (recordsForFactory.some(record => record.id === current)) return current;
          return activeRecord?.id || recordsForFactory[0]?.id || "";
        });
        if (activeRecord) {
          setLocalScript(scriptRecordToFactoryPayload(activeRecord));
        }
        setFactoryScriptsState("ready");
      })
      .catch(err => {
        if (cancelled) return;
        setFactoryScriptsState("failed");
        setFactoryScriptsError(err instanceof Error ? err.message : "脚本列表加载失败。");
      });
    return () => {
      cancelled = true;
    };
  }, [script?.id, localScript?.id]);

  useEffect(() => {
    if (!script) return;
    storeFactoryActiveScriptId(script.id);
    setSelectedFactoryScriptId(script.id);
    void startDirectorPlanGeneration(script);
  }, [script?.id]);

  useEffect(() => {
    if (!effectiveScript) {
      setDirectorPlan(null);
      setDirectorGenerationJob(null);
      setManualAssets([]);
      setAssetBindings([]);
      setRenderJobs([]);
      setPublishRecords([]);
      setSelectedLibraryAssetIds({});
      setState("idle");
      setError("");
      setManualAssetError("");
      setAssetBindingError("");
      setRenderState("idle");
      setRenderError("");
      setPublishState("idle");
      setPublishError("");
      return;
    }

    let cancelled = false;
    storeFactoryActiveScriptId(effectiveScript.id);
    setSelectedFactoryScriptId(effectiveScript.id);
    if (generationScriptIdRef.current === effectiveScript.id) return () => {
      cancelled = true;
    };
    setDirectorPlan(null);
    setDirectorGenerationJob(null);
    setManualAssets([]);
    setAssetBindings([]);
    setRenderJobs([]);
    setPublishRecords([]);
    setSelectedLibraryAssetIds({});
    setRenderState("idle");
    setRenderError("");
    setPublishState("idle");
    setPublishError("");
    const requestId = latestPlanRequestIdRef.current + 1;
    latestPlanRequestIdRef.current = requestId;
    setState("loading");
    setError("");
    setManualAssetError("");
    setAssetBindingError("");
    Promise.all([
      videoBreakdownClient.listDirectorGenerationJobs(effectiveScript.id, true),
      videoBreakdownClient.listDirectorPlans(effectiveScript.id),
    ])
      .then(async ([jobs, plans]) => {
        if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
        const latestJob = jobs[0] ?? null;
        const plan = plans[0];
        setDirectorGenerationJob(latestJob);
        if (!plan) {
          setDirectorPlan(null);
          setManualAssets([]);
          setAssetBindings([]);
          setPublishRecords([]);
          setSelectedLibraryAssetIds({});
          if (isRunningDirectorGenerationJob(latestJob)) {
            setState("loading");
            setError("");
          } else if (latestJob?.status === "failed") {
            setState("failed");
            setError(latestJob.errorMessage || "导演计划生成失败。");
          } else if (latestJob?.status === "canceled") {
            setState("idle");
            setError(latestJob.errorMessage || "导演计划生成已取消。");
          } else {
            setState("idle");
          }
          return;
        }
        await loadDirectorPlanBundle(plan, requestId);
        if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
        if (isRunningDirectorGenerationJob(latestJob)) {
          setState("loading");
          setError("");
        } else if (latestJob?.status === "failed") {
          setState("failed");
          setError(latestJob.errorMessage || "导演计划生成失败。");
        } else {
          setState("ready");
        }
      })
      .catch(err => {
        if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
        setState("failed");
        setError(err instanceof Error ? err.message : "已有导演计划恢复失败。");
      });
    return () => {
      cancelled = true;
    };
  }, [effectiveScript?.id]);

  useEffect(() => {
    if (!effectiveScript || !directorGenerationJob) return;
    if (directorGenerationJob.scriptId !== effectiveScript.id) return;
    if (!isRunningDirectorGenerationJob(directorGenerationJob)) return;

    let cancelled = false;
    const requestId = latestPlanRequestIdRef.current;
    const jobId = directorGenerationJob.id;

    async function pollDirectorGenerationJob() {
      try {
        const currentJob = await videoBreakdownClient.getDirectorGenerationJob(jobId);
        if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
        if (currentJob.status === "succeeded") {
          let plan: DirectorPlanRecord | undefined;
          if (currentJob.directorPlanId) {
            try {
              plan = await videoBreakdownClient.getDirectorPlan(currentJob.directorPlanId);
            } catch {
              plan = (await videoBreakdownClient.listDirectorPlans(currentJob.scriptId))[0];
            }
          } else {
            plan = (await videoBreakdownClient.listDirectorPlans(currentJob.scriptId))[0];
          }
          if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
          if (!plan) {
            setDirectorGenerationJob(currentJob);
            setState("failed");
            setError("导演任务已完成，但没有找到可恢复的导演计划。请重试任务或重新生成导演计划。");
            return;
          }
          await loadDirectorPlanBundle(plan, requestId);
          if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
          setDirectorGenerationJob(currentJob);
          setState("ready");
          setError("");
        } else if (currentJob.status === "failed") {
          setDirectorGenerationJob(currentJob);
          setState("failed");
          setError(currentJob.errorMessage || "导演计划生成失败。");
        } else if (currentJob.status === "canceled") {
          setDirectorGenerationJob(currentJob);
          setState(directorPlan ? "ready" : "idle");
          setError(currentJob.errorMessage || "导演计划生成已取消。");
        } else {
          setDirectorGenerationJob(currentJob);
          setState("loading");
          setError("");
        }
      } catch (err) {
        if (cancelled || latestPlanRequestIdRef.current !== requestId) return;
        setState("failed");
        setError(err instanceof Error ? err.message : "导演计划任务恢复失败。");
      }
    }

    void pollDirectorGenerationJob();
    const timer = window.setInterval(() => {
      void pollDirectorGenerationJob();
    }, 1200);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [directorGenerationJob?.id, directorGenerationJob?.status, directorPlan?.id, effectiveScript?.id]);

  useEffect(() => {
    if (!directorPlan || !latestRenderJob) return;
    if (latestRenderJob.directorPlanId !== directorPlan.id) return;
    if (!isRunningDirectorRenderJob(latestRenderJob)) return;

    let cancelled = false;
    const jobId = latestRenderJob.id;

    async function pollDirectorRenderJob() {
      try {
        const currentJob = await videoBreakdownClient.getDirectorRenderJob(jobId);
        if (cancelled) return;
        setRenderJobs(previous => upsertRenderJob(previous, currentJob));
        if (isRunningDirectorRenderJob(currentJob)) {
          setRenderState("running");
          setRenderError("");
          return;
        }
        setRenderState("idle");
        setRenderError("");
      } catch (err) {
        if (cancelled) return;
        setRenderState("failed");
        setRenderError(err instanceof Error ? err.message : "渲染任务状态恢复失败。");
      }
    }

    void pollDirectorRenderJob();
    const timer = window.setInterval(() => {
      void pollDirectorRenderJob();
    }, 1500);

    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, [directorPlan?.id, latestRenderJob?.id, latestRenderJob?.status]);

  async function loadDirectorPlanBundle(plan: DirectorPlanRecord, requestId: number) {
    const [assets, libraryAssets, bindings, jobs, records] = await Promise.all([
      videoBreakdownClient.listManualFactoryAssets(plan.id),
      videoBreakdownClient.listMorasAssets(),
      videoBreakdownClient.listDirectorPlanAssetBindings(plan.id),
      videoBreakdownClient.listDirectorRenderJobs(plan.id),
      videoBreakdownClient.listDirectorPublishRecords(plan.id),
    ]);
    if (latestPlanRequestIdRef.current !== requestId) return;
    setDirectorPlan(plan);
    setManualAssets(assets);
    setMorasAssets(libraryAssets);
    setAssetBindings(bindings);
    setRenderJobs(jobs);
    setPublishRecords(records);
    setSelectedLibraryAssetIds(Object.fromEntries(bindings.map(binding => [binding.assetRef, binding.libraryAssetId])));
    const latestJob = jobs[0] ?? null;
    if (isRunningDirectorRenderJob(latestJob)) {
      setRenderState("running");
      setRenderError("");
    } else {
      setRenderState("idle");
      setRenderError("");
    }
  }

  function handleStartFactoryScript() {
    const selectedRecord = factoryScripts.find(item => item.id === selectedFactoryScriptId) ?? factoryScripts[0];
    if (!selectedRecord) return;
    const payload = scriptRecordToFactoryPayload(selectedRecord);
    storeFactoryActiveScriptId(payload.id);
    setLocalScript(payload);
    void startDirectorPlanGeneration(payload);
  }

  function handleGenerateSelectedFactoryScript() {
    const selectedRecord = factoryScripts.find(item => item.id === selectedFactoryScriptId);
    if (selectedRecord && selectedRecord.id !== effectiveScript?.id) {
      const payload = scriptRecordToFactoryPayload(selectedRecord);
      storeFactoryActiveScriptId(payload.id);
      setLocalScript(payload);
      void startDirectorPlanGeneration(payload);
      return;
    }
    void startDirectorPlanGeneration(effectiveScript);
  }

  async function startDirectorPlanGeneration(targetScript = effectiveScript) {
    if (!targetScript) return;
    const requestId = latestPlanRequestIdRef.current + 1;
    latestPlanRequestIdRef.current = requestId;
    generationScriptIdRef.current = targetScript.id;
    storeFactoryActiveScriptId(targetScript.id);
    setSelectedFactoryScriptId(targetScript.id);
    setState("loading");
    setError("");
    setManualAssetError("");
    setAssetBindingError("");
    try {
      const job = await videoBreakdownClient.createDirectorGenerationJob(targetScript.id);
      if (latestPlanRequestIdRef.current !== requestId) return;
      setDirectorGenerationJob(job);
      setState("loading");
    } catch (err) {
      if (latestPlanRequestIdRef.current !== requestId) return;
      setState("failed");
      setError(err instanceof Error ? err.message : "导演计划生成失败。");
    } finally {
      if (generationScriptIdRef.current === targetScript.id) generationScriptIdRef.current = "";
    }
  }

  async function handleCancelDirectorGenerationJob() {
    if (!directorGenerationJob || !isRunningDirectorGenerationJob(directorGenerationJob)) return;
    const requestId = latestPlanRequestIdRef.current + 1;
    latestPlanRequestIdRef.current = requestId;
    setError("");
    try {
      const currentJob = await videoBreakdownClient.cancelDirectorGenerationJob(directorGenerationJob.id);
      if (latestPlanRequestIdRef.current !== requestId) return;
      setDirectorGenerationJob(currentJob);
      setState(directorPlan ? "ready" : "idle");
      setError(currentJob.errorMessage || "导演计划生成已取消。");
    } catch (err) {
      if (latestPlanRequestIdRef.current !== requestId) return;
      setState(directorPlan ? "ready" : "failed");
      setError(err instanceof Error ? err.message : "导演计划取消失败。");
    }
  }

  async function handleRetryDirectorGenerationJob() {
    if (!directorGenerationJob || !canRetryDirectorJob) {
      void startDirectorPlanGeneration(effectiveScript);
      return;
    }
    const requestId = latestPlanRequestIdRef.current + 1;
    latestPlanRequestIdRef.current = requestId;
    setState("loading");
    setError("");
    try {
      const retryJob = await videoBreakdownClient.retryDirectorGenerationJob(directorGenerationJob.id);
      if (latestPlanRequestIdRef.current !== requestId) return;
      setDirectorGenerationJob(retryJob);
      setState("loading");
    } catch (err) {
      if (latestPlanRequestIdRef.current !== requestId) return;
      setState(directorPlan ? "ready" : "failed");
      setError(err instanceof Error ? err.message : "导演计划重试失败。");
    }
  }

  async function handleCopyPrompt(clip: JsonObject) {
    const clipId = textValue(clip.clipId, textValue(clip.clip_id, ""));
    const prompt = generatedPromptText(clip);
    try {
      if (navigator.clipboard && prompt) {
        await navigator.clipboard.writeText(prompt);
      }
      setCopiedClipId(clipId);
    } catch {
      setManualAssetError("提示词复制失败，请手动选中文本复制。");
    }
  }

  async function handleManualAssetChange(clipId: string, event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file || !directorPlan) return;
    setUploadingClipId(clipId);
    setManualAssetError("");
    try {
      const asset = await videoBreakdownClient.uploadManualFactoryAsset(directorPlan.id, clipId, file);
      setManualAssets(previous => [asset, ...previous.filter(item => item.clipId !== clipId)]);
    } catch (err) {
      setManualAssetError(err instanceof Error ? err.message : "素材上传失败，请重新选择文件。");
    } finally {
      setUploadingClipId("");
    }
  }

  async function handleManualAssetReview(asset: ManualFactoryAssetRecord, reviewStatus: "approved" | "rejected") {
    setReviewingAssetId(asset.id);
    setManualAssetError("");
    try {
      const reviewed = await videoBreakdownClient.reviewManualFactoryAsset(
        asset.id,
        reviewStatus,
        reviewStatus === "approved" ? "人工确认素材文件可用于视频工厂。" : "人工拒绝：素材需要重新生成或替换。",
      );
      setManualAssets(previous => [reviewed, ...previous.filter(item => item.id !== reviewed.id)]);
    } catch (err) {
      setManualAssetError(err instanceof Error ? err.message : "素材审核状态更新失败。");
    } finally {
      setReviewingAssetId("");
    }
  }

  async function handleManualAssetSemanticReview(asset: ManualFactoryAssetRecord, status: "passed" | "failed") {
    setReviewingAssetId(asset.id);
    setManualAssetError("");
    try {
      const reviewed = await videoBreakdownClient.reviewManualFactoryAssetSemanticMatch(
        asset.id,
        status,
        status === "passed" ? "人工确认素材语义匹配复制的提示词和时间线。" : "人工退回：素材语义不匹配提示词或时间线。",
      );
      setManualAssets(previous => [reviewed, ...previous.filter(item => item.id !== reviewed.id)]);
    } catch (err) {
      setManualAssetError(err instanceof Error ? err.message : "素材语义复核状态更新失败。");
    } finally {
      setReviewingAssetId("");
    }
  }

  async function handleMorasAssetUpload(asset: JsonObject, event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file || !directorPlan) return;
    const ref = assetReference(asset);
    const requiredAssetType = textValue(asset.requiredAssetType, "real_moras_asset");
    const category = textValue(asset.morasAssetCategory, "none");
    setUploadingAssetRef(ref);
    setAssetBindingError("");
    try {
      const uploaded = await videoBreakdownClient.uploadMorasAsset({
        assetType: requiredAssetType,
        morasAssetCategory: category,
        title: `${ref} · ${category}`,
        file,
      });
      const binding = await videoBreakdownClient.bindDirectorPlanAsset(directorPlan.id, ref, uploaded.id);
      setMorasAssets(previous => [uploaded, ...previous.filter(item => item.id !== uploaded.id)]);
      setAssetBindings(previous => upsertAssetBinding(previous, binding));
      setSelectedLibraryAssetIds(previous => ({ ...previous, [ref]: uploaded.id }));
    } catch (err) {
      setAssetBindingError(err instanceof Error ? err.message : "真实 Moras 素材上传或绑定失败。");
    } finally {
      setUploadingAssetRef("");
    }
  }

  async function handleMorasAssetReview(asset: MorasAssetLibraryRecord, reviewStatus: "approved" | "rejected") {
    setReviewingAssetId(asset.id);
    setLibraryAssetError("");
    setAssetBindingError("");
    try {
      const reviewed = await videoBreakdownClient.reviewMorasAsset(
        asset.id,
        reviewStatus,
        reviewStatus === "approved" ? "人工确认素材文件可用于 Moras 视频工厂。" : "人工拒绝：素材不可用于当前视频工厂。",
      );
      setMorasAssets(previous => [reviewed, ...previous.filter(item => item.id !== reviewed.id)]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "真实 Moras 素材审核状态更新失败。";
      setLibraryAssetError(message);
      setAssetBindingError(message);
    } finally {
      setReviewingAssetId("");
    }
  }

  async function handleMorasAssetSemanticReview(asset: MorasAssetLibraryRecord, status: "passed" | "failed") {
    setReviewingAssetId(asset.id);
    setLibraryAssetError("");
    setAssetBindingError("");
    try {
      const reviewed = await videoBreakdownClient.reviewMorasAssetSemanticMatch(
        asset.id,
        status,
        status === "passed" ? "人工确认真实 Moras 素材语义匹配导演计划需求。" : "人工退回：真实 Moras 素材与导演计划需求不匹配。",
      );
      setMorasAssets(previous => [reviewed, ...previous.filter(item => item.id !== reviewed.id)]);
    } catch (err) {
      const message = err instanceof Error ? err.message : "真实 Moras 素材语义复核状态更新失败。";
      setLibraryAssetError(message);
      setAssetBindingError(message);
    } finally {
      setReviewingAssetId("");
    }
  }

  async function handleBindExistingMorasAsset(asset: JsonObject) {
    if (!directorPlan) return;
    const ref = assetReference(asset);
    const libraryAssetId = selectedLibraryAssetIds[ref];
    if (!libraryAssetId) {
      setAssetBindingError("请选择一个素材库条目后再绑定。");
      return;
    }
    setBindingAssetRef(ref);
    setAssetBindingError("");
    try {
      const binding = await videoBreakdownClient.bindDirectorPlanAsset(directorPlan.id, ref, libraryAssetId);
      setAssetBindings(previous => upsertAssetBinding(previous, binding));
      const latestAssets = await videoBreakdownClient.listMorasAssets();
      setMorasAssets(latestAssets);
    } catch (err) {
      setAssetBindingError(err instanceof Error ? err.message : "真实 Moras 素材绑定失败。");
    } finally {
      setBindingAssetRef("");
    }
  }

  async function handleLibraryAssetUpload(event: ChangeEvent<HTMLInputElement>) {
    const file = event.currentTarget.files?.[0];
    event.currentTarget.value = "";
    if (!file) return;
    setIsUploadingLibraryAsset(true);
    setLibraryAssetError("");
    try {
      const uploaded = await videoBreakdownClient.uploadMorasAsset({
        assetType: libraryAssetType,
        morasAssetCategory: libraryAssetCategory,
        title: libraryAssetTitle.trim() || file.name,
        file,
      });
      setMorasAssets(previous => [uploaded, ...previous.filter(item => item.id !== uploaded.id)]);
      setLibraryAssetTitle("");
    } catch (err) {
      setLibraryAssetError(err instanceof Error ? err.message : "真实 Moras 素材上传失败。");
    } finally {
      setIsUploadingLibraryAsset(false);
    }
  }

  async function handleCreateRenderJob() {
    if (!directorPlan) return;
    setRenderState("running");
    setRenderError("");
    setPublishError("");
    try {
      const job = await videoBreakdownClient.createDirectorRenderJob(directorPlan.id);
      setRenderJobs(previous => upsertRenderJob(previous, job));
      if (isRunningDirectorRenderJob(job)) {
        setRenderState("running");
        return;
      }
      setRenderState("idle");
      setRenderError("");
    } catch (err) {
      setRenderState("failed");
      setRenderError(err instanceof Error ? err.message : "视频草稿渲染请求失败。");
    }
  }

  async function handleRetryRenderJob() {
    if (!latestRenderJob || !canRetryRenderJob) return;
    setRenderState("running");
    setRenderError("");
    setPublishError("");
    try {
      const job = await videoBreakdownClient.retryDirectorRenderJob(latestRenderJob.id);
      setRenderJobs(previous => upsertRenderJob(previous, job));
      if (isRunningDirectorRenderJob(job)) {
        setRenderState("running");
        return;
      }
      setRenderState("idle");
      setRenderError("");
    } catch (err) {
      setRenderState("failed");
      setRenderError(err instanceof Error ? err.message : "视频草稿重试失败。");
    }
  }

  async function handleCleanupExpiredRenderArtifacts() {
    if (!latestRenderJob) return;
    setArtifactCleanupState("running");
    setArtifactCleanupError("");
    try {
      const artifacts = await videoBreakdownClient.cleanupExpiredDirectorRenderArtifacts(latestRenderJob.id);
      setRenderArtifacts(artifacts);
      await loadRenderAccounting(latestRenderJob.id);
    } catch (err) {
      setArtifactCleanupError(err instanceof Error ? err.message : "过期渲染产物清理失败。");
    } finally {
      setArtifactCleanupState("idle");
    }
  }

  async function handleDeleteRenderArtifact(artifact: DirectorRenderArtifactRecord) {
    if (artifact.storageStatus === "deleted") return;
    setDeletingArtifactId(artifact.id);
    setArtifactCleanupError("");
    try {
      const deleted = await videoBreakdownClient.deleteDirectorRenderArtifact(artifact.id);
      setRenderArtifacts(previous => previous.map(item => item.id === deleted.id ? deleted : item));
      if (latestRenderJob) await loadRenderAccounting(latestRenderJob.id);
    } catch (err) {
      setArtifactCleanupError(err instanceof Error ? err.message : "渲染产物删除失败。");
    } finally {
      setDeletingArtifactId("");
    }
  }

  async function handleRenderJobQaReview(renderJob: DirectorRenderJobRecord, reviewStatus: "approved" | "rejected") {
    setQaReviewingRenderJobId(renderJob.id);
    setRenderError("");
    setPublishError("");
    try {
      const reviewed = await videoBreakdownClient.reviewDirectorRenderJobQa(
        renderJob.id,
        reviewStatus,
        reviewStatus === "approved" ? "人工 QA 通过，可进入手动发布/交付。" : "人工 QA 退回：需要重新渲染或替换素材。",
      );
      setRenderJobs(previous => [reviewed, ...previous.filter(item => item.id !== reviewed.id)]);
    } catch (err) {
      setRenderError(err instanceof Error ? err.message : "渲染 QA 状态更新失败。");
    } finally {
      setQaReviewingRenderJobId("");
    }
  }

  async function handleCreatePublishRecord() {
    if (!directorPlan || !latestRenderJob) return;
    setPublishState("running");
    setPublishError("");
    try {
      const record = await videoBreakdownClient.createDirectorPublishRecord(directorPlan.id, {
        renderJobId: latestRenderJob.id,
        channel: publishChannel,
        publishStatus: "ready_for_upload",
        caption: textValue(directorPlan.metadata.caption, ""),
        notes: "QA 通过后创建的手动上传/交付记录。",
      });
      setPublishRecords(previous => [record, ...previous.filter(item => item.id !== record.id)]);
    } catch (err) {
      setPublishError(err instanceof Error ? err.message : "发布/交付记录创建失败。");
    } finally {
      setPublishState("idle");
    }
  }

  const morasLibraryPanel = (
    <section className="video-factory-panel" aria-labelledby="factory-moras-library-title">
      <div className="video-factory-panel__heading">
        <h3 id="factory-moras-library-title">真实 Moras 素材库</h3>
        <p>视频工厂的常驻素材入口。先把真实录屏、截图、工作流素材上传到这里，再绑定到导演计划里的 asset_ref。</p>
      </div>
      {libraryAssetError && <p className="factory-error">{libraryAssetError}</p>}
      <div className="moras-library-controls" aria-label="上传真实 Moras 素材">
        <label>
          <span>类型</span>
          <select value={libraryAssetType} onChange={event => setLibraryAssetType(event.target.value)}>
            {realMorasAssetTypeOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label>
          <span>分类</span>
          <select value={libraryAssetCategory} onChange={event => setLibraryAssetCategory(event.target.value)}>
            {realMorasAssetCategoryOptions.map(option => (
              <option key={option.value} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="moras-library-title-field">
          <span>标题</span>
          <input
            type="text"
            value={libraryAssetTitle}
            placeholder="默认使用文件名"
            onChange={event => setLibraryAssetTitle(event.target.value)}
          />
        </label>
        <label className={`manual-upload-button${isUploadingLibraryAsset ? " manual-upload-button--busy" : ""}`}>
          <UploadCloud size={16} aria-hidden="true" />
          {isUploadingLibraryAsset ? "上传中" : "上传到素材库"}
          <input
            className="visually-hidden"
            type="file"
            accept="video/mp4,video/quicktime,video/webm,image/png,image/jpeg,image/webp,.mp4,.mov,.webm,.png,.jpg,.jpeg,.webp"
            aria-label="上传到真实 Moras 素材库"
            disabled={isUploadingLibraryAsset}
            onChange={event => void handleLibraryAssetUpload(event)}
          />
        </label>
      </div>
      {morasAssets.length > 0 ? (
        <ol className="moras-library-list" aria-label="真实 Moras 素材库条目">
          {morasAssets.map(asset => (
            <li key={asset.id}>
              <div>
                <strong>{asset.title}</strong>
                <span>{asset.assetType} · {asset.morasAssetCategory}</span>
                <em className={`factory-status factory-status--${asset.reviewStatus === "approved" ? "ok" : "warning"}`}>
                  {assetReviewStatusLabel(asset.reviewStatus)}
                </em>
                <em className={`factory-status factory-status--${asset.semanticReviewStatus === "passed" ? "ok" : "warning"}`}>
                  {semanticReviewStatusLabel(asset.semanticReviewStatus)}
                </em>
              </div>
              <div className="asset-review-actions">
                <a className="manual-asset-link" href={`${API_BASE}${asset.storedAssetUrl}`} target="_blank" rel="noreferrer">
                  <ExternalLink size={14} aria-hidden="true" />
                  {asset.originalFilename} · {formatFileSize(asset.fileSizeBytes)} · {asset.width}x{asset.height}
                </a>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={reviewingAssetId === asset.id || asset.reviewStatus === "approved"}
                  aria-label={`通过真实 Moras 素材审核：${asset.title}`}
                  onClick={() => void handleMorasAssetReview(asset, "approved")}
                >
                  {reviewingAssetId === asset.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                  通过
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={reviewingAssetId === asset.id || asset.reviewStatus === "rejected"}
                  aria-label={`拒绝真实 Moras 素材审核：${asset.title}`}
                  onClick={() => void handleMorasAssetReview(asset, "rejected")}
                >
                  <X size={16} aria-hidden="true" />
                  拒绝
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={reviewingAssetId === asset.id || asset.reviewStatus !== "approved" || asset.semanticReviewStatus === "passed"}
                  aria-label={`通过真实 Moras 素材语义复核：${asset.title}`}
                  onClick={() => void handleMorasAssetSemanticReview(asset, "passed")}
                >
                  {reviewingAssetId === asset.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                  语义通过
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={reviewingAssetId === asset.id || asset.reviewStatus !== "approved" || asset.semanticReviewStatus === "failed"}
                  aria-label={`退回真实 Moras 素材语义复核：${asset.title}`}
                  onClick={() => void handleMorasAssetSemanticReview(asset, "failed")}
                >
                  <X size={16} aria-hidden="true" />
                  语义退回
                </button>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <p className="real-asset-empty">素材库还没有真实 Moras 素材。</p>
      )}
    </section>
  );

  if (!effectiveScript) {
    if (factoryScriptsState === "loading") {
      return (
        <div className="video-factory-page">
          <section className="empty-dashboard empty-dashboard--tab">
            <Loader2 className="spin" size={28} aria-hidden="true" />
            <div>
              <h2>视频工厂正在读取脚本库</h2>
              <p>正在从后端恢复可进入导演 Agent 的脚本。</p>
            </div>
          </section>
          {morasLibraryPanel}
        </div>
      );
    }

    if (factoryScriptsState === "failed") {
      return (
        <div className="video-factory-page">
          <section className="empty-dashboard empty-dashboard--tab">
            <AlertCircle size={28} aria-hidden="true" />
            <div>
              <h2>视频工厂脚本加载失败</h2>
              <p>{factoryScriptsError}</p>
            </div>
          </section>
          {morasLibraryPanel}
        </div>
      );
    }

    if (factoryScripts.length > 0) {
      const selectedId = selectedFactoryScriptId || factoryScripts[0].id;
      return (
        <div className="video-factory-page">
          <section className="empty-dashboard empty-dashboard--tab video-factory-recovery">
            <Blocks size={28} aria-hidden="true" />
            <div>
              <h2>视频工厂</h2>
              <p>后端已有 {factoryScripts.length} 个脚本。选择一个脚本后生成导演计划，刷新或直接进入本页也不需要回到脚本编辑部。</p>
              <div className="factory-script-picker">
                <label>
                  <span>选择脚本</span>
                  <select
                    aria-label="选择待生成脚本"
                    value={selectedId}
                    onChange={event => setSelectedFactoryScriptId(event.target.value)}
                  >
                    {factoryScripts.map(item => (
                      <option key={item.id} value={item.id}>
                        {factoryScriptTitle(item)}
                      </option>
                    ))}
                  </select>
                </label>
                <button type="button" className="submit-button" onClick={handleStartFactoryScript}>
                  <Send size={16} aria-hidden="true" />
                  生成导演计划
                </button>
              </div>
            </div>
          </section>
          {morasLibraryPanel}
        </div>
      );
    }

    return (
      <div className="video-factory-page">
        <section className="empty-dashboard empty-dashboard--tab">
          <Blocks size={28} aria-hidden="true" />
          <div>
            <h2>视频工厂</h2>
            <p>还没有可进入视频工厂的脚本。请先在脚本编辑部生成脚本。</p>
          </div>
        </section>
        {morasLibraryPanel}
      </div>
    );
  }

  if (!directorPlan) {
    const isPlanLoading = state === "loading";
    const isPlanFailed = state === "failed";
    return (
      <section className="video-factory-page" aria-label="视频工厂导演计划">
        <header className="video-factory-header">
          <div>
            <p>Director Agent</p>
            <h2>{effectiveScript.title}</h2>
          </div>
          <div className="video-factory-header__meta" aria-label="导演计划状态">
            <span><Film size={16} aria-hidden="true" /> 9:16</span>
            <span><Clock3 size={16} aria-hidden="true" /> 待规划</span>
            <span><CheckCircle2 size={16} aria-hidden="true" /> Gemini 3.5 Flash / Vertex</span>
          </div>
        </header>

        <section className="video-factory-panel factory-plan-status-card video-factory-recovery">
          {isPlanLoading ? (
            <Loader2 className="spin" size={28} aria-hidden="true" />
          ) : isPlanFailed ? (
            <AlertCircle size={28} aria-hidden="true" />
          ) : (
            <Blocks size={28} aria-hidden="true" />
          )}
          <div>
            <h2>{isPlanLoading ? "导演 Agent 正在生成计划" : isPlanFailed ? "导演计划生成失败" : "已选择脚本，等待生成导演计划"}</h2>
            <p>
              《{effectiveScript.title}》已进入视频工厂。生成期间素材库和脚本入口会保持可见；刷新后会自动恢复这个脚本并读取已有计划。
            </p>
            {directorGenerationJob && (
              <p className="factory-job-note">
                导演任务 {directorGenerationJob.id.slice(0, 8)} · {directorGenerationJobStatusLabel(directorGenerationJob.status)}
              </p>
            )}
            {(isPlanFailed || directorGenerationJob?.status === "canceled") && error && <p className="factory-error">{error}</p>}
            <div className="factory-script-picker">
              {factoryScripts.length > 0 && (
                <label>
                  <span>选择脚本</span>
                  <select
                    aria-label="选择待生成脚本"
                    value={selectedFactoryScriptId || effectiveScript.id}
                    onChange={event => setSelectedFactoryScriptId(event.target.value)}
                    disabled={isPlanLoading}
                  >
                    {factoryScripts.map(item => (
                      <option key={item.id} value={item.id}>
                        {factoryScriptTitle(item)}
                      </option>
                    ))}
                  </select>
                </label>
              )}
              <button
                type="button"
                className="submit-button"
                disabled={isPlanLoading}
                onClick={handleGenerateSelectedFactoryScript}
              >
                {isPlanLoading ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}
                {isPlanLoading ? "生成中" : "生成导演计划"}
              </button>
              {isDirectorJobRunning && (
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => void handleCancelDirectorGenerationJob()}
                >
                  <X size={16} aria-hidden="true" />
                  取消任务
                </button>
              )}
              {canRetryDirectorJob && (
                <button
                  type="button"
                  className="ghost-button"
                  onClick={() => void handleRetryDirectorGenerationJob()}
                >
                  <RefreshCw size={16} aria-hidden="true" />
                  重试任务
                </button>
              )}
            </div>
          </div>
        </section>
        {morasLibraryPanel}

        <section className="video-factory-panel render-job-panel" aria-labelledby="factory-render-pending-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-render-pending-title">渲染执行 / 输出视频</h3>
            <p>导演计划生成后，这里会检查外部生成视频片段和真实 Moras 绑定，并输出本地 9:16 FFmpeg 草稿。</p>
          </div>
          <div className="render-job-panel__top">
            <div>
              <strong>等待导演计划</strong>
              <span>{isPlanLoading ? "正在生成剪辑时间线和工具调度。" : "先生成导演计划，再执行素材检查和视频草稿渲染。"}</span>
            </div>
            <button type="button" className="submit-button" disabled>
              <PlayCircle size={16} aria-hidden="true" />
              检查并生成视频草稿
            </button>
          </div>
        </section>

        <section className="video-factory-panel" aria-labelledby="factory-manual-pending-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-manual-pending-title">外部生成视频片段</h3>
            <p>计划生成后会列出每个需要外部生成的视频 clip_id、提示词、时长和上传入口。</p>
          </div>
          <p className="real-asset-empty">当前脚本还没有可绑定的手动视频片段。</p>
        </section>

        <section className="video-factory-panel" aria-labelledby="factory-real-pending-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-real-pending-title">真实素材绑定</h3>
            <p>计划生成后会把 Moras 录屏、截图、工作流素材要求映射到真实素材库。</p>
          </div>
          <p className="real-asset-empty">真实 Moras 素材库入口已保留在上方，可先上传素材。</p>
        </section>

        <section className="video-factory-panel" aria-labelledby="factory-timeline-pending-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-timeline-pending-title">剪辑时间线</h3>
            <p>等待导演 Agent 产出多轨 timeline。</p>
          </div>
          <p className="real-asset-empty">时间线生成后会在这里展示视频轨、音频轨、每个 clip 的开始时间和持续时长。</p>
        </section>

        <div className="video-factory-grid">
          <section className="video-factory-panel" aria-labelledby="factory-assets-pending-title">
            <div className="video-factory-panel__heading">
              <h3 id="factory-assets-pending-title">素材绑定</h3>
              <p>等待导演计划里的 asset_resolution。</p>
            </div>
            <p className="real-asset-empty">生成后会显示每个素材的 ready / blocked / bound 状态。</p>
          </section>

          <section className="video-factory-panel" aria-labelledby="factory-tools-pending-title">
            <div className="video-factory-panel__heading">
              <h3 id="factory-tools-pending-title">工具调度</h3>
              <p>等待导演 Agent 输出工具调用顺序。</p>
            </div>
            <p className="real-asset-empty">生成后会显示 FFmpeg、字幕、音频和手动素材上传等步骤。</p>
          </section>
        </div>
      </section>
    );
  }

  const metadata = directorPlan.metadata;
  const totalDuration = numberValue(metadata.totalDurationSec, 38);
  const videoTracks = arrayObjects(objectValue(directorPlan.timeline.tracks)?.videoTracks);
  const audioTracks = arrayObjects(objectValue(directorPlan.timeline.tracks)?.audioTracks);
  const dispatches = directorPlan.toolDispatches;
  const manualGenerationClips = videoTracks.flatMap(track => (
    arrayObjects(track.clips).filter(clip => isManualGenerationClip(clip))
  ));
  const manualAssetByClip = new Map(manualAssets.map(asset => [asset.clipId, asset]));
  const assetBindingByRef = new Map(assetBindings.map(binding => [binding.assetRef, binding]));
  const libraryAssetById = new Map(morasAssets.map(asset => [asset.id, asset]));
  const realMorasAssetNeeds = directorPlan.assetResolution.filter(isRealMorasAssetRequirement);
  const boundGeneratedCount = manualGenerationClips.filter(clip => manualAssetByClip.has(textValue(clip.clipId, ""))).length;
  const boundRealMorasCount = realMorasAssetNeeds.filter(asset => assetBindingByRef.has(assetReference(asset))).length;
  const generatedSemanticReadyCount = manualGenerationClips.filter(clip => {
    const asset = manualAssetByClip.get(textValue(clip.clipId, ""));
    return asset?.reviewStatus === "approved" && asset.semanticReviewStatus === "passed";
  }).length;
  const realMorasSemanticReadyCount = realMorasAssetNeeds.filter(asset => {
    const binding = assetBindingByRef.get(assetReference(asset));
    const libraryAsset = binding ? libraryAssetById.get(binding.libraryAssetId) : undefined;
    return libraryAsset?.reviewStatus === "approved" && libraryAsset.semanticReviewStatus === "passed";
  }).length;
  const semanticReviewNeededCount = manualGenerationClips.length + realMorasAssetNeeds.length;
  const semanticReviewReadyCount = generatedSemanticReadyCount + realMorasSemanticReadyCount;
  const unresolvedAssets = directorPlan.assetResolution.filter(item => {
    const ref = assetReference(item);
    const status = textValue(item.resolutionStatus, "");
    if (manualAssetByClip.has(ref) || assetBindingByRef.has(ref)) return false;
    return status === "missing_placeholder" || status === "blocked";
  }).length;
  const renderReadiness = objectValue(latestRenderJob?.readinessSummary ?? {}) ?? {};
  const renderBlockers = arrayObjects(renderReadiness.blockers);
  const renderQaSummary = objectValue(latestRenderJob?.qaSummary ?? {}) ?? {};
  const renderQaChecks = objectValue(renderQaSummary.checks ?? {}) ?? {};
  const renderCaptionSummary = objectValue(renderQaSummary.caption ?? {}) ?? {};
  const latestRenderJobQaApproved = latestRenderJob?.status === "succeeded" && latestRenderJob.qaReviewStatus === "approved";

  return (
    <section className="video-factory-page" aria-label="视频工厂导演计划">
      <header className="video-factory-header">
        <div>
          <p>Director Agent</p>
          <h2>{effectiveScript.title}</h2>
        </div>
        <div className="video-factory-header__meta" aria-label="导演计划状态">
          <span><Film size={16} aria-hidden="true" /> {textValue(metadata.targetAspectRatio, "9:16")}</span>
          <span><Clock3 size={16} aria-hidden="true" /> {totalDuration}s</span>
          <span><CheckCircle2 size={16} aria-hidden="true" /> {directorPlan.modelName}</span>
          <button
            type="button"
            className="ghost-button"
            disabled={state === "loading"}
            onClick={() => void startDirectorPlanGeneration(effectiveScript)}
          >
            {state === "loading" ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
            {state === "loading" ? "生成中" : "重新生成"}
          </button>
        </div>
      </header>

      <div className="video-factory-kpis" aria-label="视频工厂计划摘要">
        <FactoryMetric label="计划状态" value={directorPlan.status === "ready" ? "已生成" : directorPlan.status} />
        <FactoryMetric label="工具步骤" value={`${dispatches.length}`} />
        <FactoryMetric label="待绑定素材" value={`${unresolvedAssets}`} tone={unresolvedAssets > 0 ? "warning" : "ok"} />
        <FactoryMetric label="真实素材" value={`${boundRealMorasCount}/${realMorasAssetNeeds.length}`} tone={boundRealMorasCount === realMorasAssetNeeds.length ? "ok" : "warning"} />
        <FactoryMetric label="Veo 3.1 上传" value={`${boundGeneratedCount}/${manualGenerationClips.length}`} tone={boundGeneratedCount === manualGenerationClips.length ? "ok" : "warning"} />
        <FactoryMetric label="语义复核" value={`${semanticReviewReadyCount}/${semanticReviewNeededCount}`} tone={semanticReviewReadyCount === semanticReviewNeededCount ? "ok" : "warning"} />
        <FactoryMetric label="执行范围" value={textValue(metadata.renderIntent, "plan_only")} />
      </div>

      {state === "loading" && (
        <section className="video-factory-panel factory-inline-status" aria-live="polite">
          <Loader2 className="spin" size={18} aria-hidden="true" />
          <span>
            导演 Agent 正在生成新的剪辑计划。当前计划会保留在页面上，完成后自动替换。
            {directorGenerationJob ? ` 任务 ${directorGenerationJob.id.slice(0, 8)} · ${directorGenerationJobStatusLabel(directorGenerationJob.status)}` : ""}
          </span>
          {isDirectorJobRunning && (
            <button
              type="button"
              className="ghost-button"
              onClick={() => void handleCancelDirectorGenerationJob()}
            >
              <X size={16} aria-hidden="true" />
              取消任务
            </button>
          )}
        </section>
      )}

      {state === "failed" && error && (
        <div className="factory-job-actions">
          <p className="factory-error">{error}</p>
          {canRetryDirectorJob && (
            <button
              type="button"
              className="ghost-button"
              onClick={() => void handleRetryDirectorGenerationJob()}
            >
              <RefreshCw size={16} aria-hidden="true" />
              重试任务
            </button>
          )}
        </div>
      )}

      {morasLibraryPanel}

      <section className="video-factory-panel render-job-panel" aria-labelledby="factory-render-title">
        <div className="video-factory-panel__heading">
          <h3 id="factory-render-title">渲染执行 / 输出视频</h3>
          <p>检查外部生成视频片段和真实 Moras 绑定；素材齐后生成本地 9:16 FFmpeg 草稿。</p>
        </div>
        {renderError && <p className="factory-error">{renderError}</p>}
        <div className="render-job-panel__top">
          <div>
            <strong>{latestRenderJob ? renderJobStatusLabel(latestRenderJob.status) : "待执行"}</strong>
            <span>
              {latestRenderJob
                ? `最近任务 ${latestRenderJob.id.slice(0, 8)} · ${latestRenderJob.createdAt}`
                : "还没有渲染任务。先上传/绑定素材，再生成视频草稿。"}
            </span>
          </div>
          <button
            type="button"
            className="submit-button"
            disabled={renderState === "running" || isRenderJobRunning}
            onClick={() => void handleCreateRenderJob()}
          >
            {renderState === "running" || isRenderJobRunning ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <PlayCircle size={16} aria-hidden="true" />}
            {renderState === "running" || isRenderJobRunning ? "执行中" : "检查并生成视频草稿"}
          </button>
          {canRetryRenderJob && (
            <button
              type="button"
              className="ghost-button"
              disabled={renderState === "running" || isRenderJobRunning}
              onClick={() => void handleRetryRenderJob()}
            >
              {renderState === "running" || isRenderJobRunning ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <RefreshCw size={16} aria-hidden="true" />}
              重试渲染
            </button>
          )}
        </div>
        {latestRenderJob?.outputAssetUrl && (
          <div className="render-output-card">
            <a className="manual-asset-link" href={`${API_BASE}${latestRenderJob.outputAssetUrl}`} target="_blank" rel="noreferrer">
              <ExternalLink size={14} aria-hidden="true" />
              {latestRenderJob.outputFilename || "factory-render.mp4"} · {formatFileSize(latestRenderJob.fileSizeBytes)} · {latestRenderJob.durationSec.toFixed(1)}s · {latestRenderJob.width}x{latestRenderJob.height}
            </a>
            <video controls preload="metadata" src={`${API_BASE}${latestRenderJob.outputAssetUrl}`}>
              {latestRenderJob.outputSubtitleUrl && (
                <track
                  kind="subtitles"
                  src={`${API_BASE}${latestRenderJob.outputSubtitleUrl}`}
                  srcLang="en"
                  label="Draft captions"
                  default
                />
              )}
            </video>
            <div className="render-artifact-list" aria-label="渲染产物">
              {latestRenderJob.outputSubtitleUrl && (
                <a href={`${API_BASE}${latestRenderJob.outputSubtitleUrl}`} target="_blank" rel="noreferrer">
                  字幕 VTT
                </a>
              )}
              {latestRenderJob.outputAudioUrl && (
                <a href={`${API_BASE}${latestRenderJob.outputAudioUrl}`} target="_blank" rel="noreferrer">
                  合成旁白音频 / TTS
                </a>
              )}
              <span>QA：{textValue(renderQaSummary.status, "pending")}</span>
              <span>字幕：{captionStatusLabel(renderCaptionSummary, renderUsage?.captionEngine)}</span>
              <span>人审：{renderQaReviewStatusLabel(latestRenderJob.qaReviewStatus)}</span>
            </div>
            {renderAccountingState === "loading" && (
              <p className="factory-job-note">
                <Loader2 className="spin" size={14} aria-hidden="true" />
                正在加载渲染产物账本
              </p>
            )}
            {renderAccountingState === "failed" && renderAccountingError && (
              <p className="factory-error">{renderAccountingError}</p>
            )}
            {renderArtifacts.length > 0 && (
              <div className="render-accounting-block" aria-label="渲染产物账本">
                <div className="render-accounting-header">
                  <h4>渲染产物</h4>
                  {hasExpiredRenderArtifacts && (
                    <button
                      type="button"
                      className="ghost-button ghost-button--compact"
                      disabled={artifactCleanupState === "running"}
                      onClick={() => void handleCleanupExpiredRenderArtifacts()}
                    >
                      {artifactCleanupState === "running" ? <Loader2 className="spin" size={14} aria-hidden="true" /> : <Trash2 size={14} aria-hidden="true" />}
                      清理过期产物
                    </button>
                  )}
                </div>
                {artifactCleanupError && <p className="factory-error">{artifactCleanupError}</p>}
                <div className="render-artifact-list render-artifact-list--ledger">
                  {renderArtifacts.map(artifact => {
                    const isDeleted = artifact.storageStatus === "deleted";
                    const label = `${renderArtifactTypeLabel(artifact.artifactType)} · ${formatFileSize(artifact.fileSizeBytes)} · ${renderStorageStatusLabel(artifact.storageStatus)}`;
                    const retentionText = artifact.deletedAt
                      ? ` · 删除于 ${formatShortDateTime(artifact.deletedAt)}`
                      : artifact.retentionExpiresAt
                        ? ` · 保留至 ${formatShortDateTime(artifact.retentionExpiresAt)}`
                        : "";
                    return (
                      <div key={artifact.id} className={`render-artifact-chip${isDeleted ? " render-artifact-chip--deleted" : ""}`}>
                        {isDeleted ? (
                          <span>{label}{retentionText}</span>
                        ) : (
                          <a href={`${API_BASE}${artifact.assetUrl}`} target="_blank" rel="noreferrer">
                            {label}{retentionText}
                          </a>
                        )}
                        <button
                          type="button"
                          className="icon-button icon-button--small"
                          disabled={isDeleted || deletingArtifactId === artifact.id || artifactCleanupState === "running"}
                          title="删除这个本地渲染产物"
                          aria-label={`删除${renderArtifactTypeLabel(artifact.artifactType)}`}
                          onClick={() => void handleDeleteRenderArtifact(artifact)}
                        >
                          {deletingArtifactId === artifact.id ? <Loader2 className="spin" size={14} aria-hidden="true" /> : <Trash2 size={14} aria-hidden="true" />}
                        </button>
                      </div>
                    );
                  })}
                </div>
              </div>
            )}
            {renderUsage && (
              <div className="render-accounting-block" aria-label="渲染用量记账">
                <h4>用量记账</h4>
                <dl className="render-qa-list">
                  <div>
                    <dt>输入片段</dt>
                    <dd>{renderUsage.inputClipCount}</dd>
                  </div>
                  <div>
                    <dt>输出时长</dt>
                    <dd>{renderUsage.outputDurationSec.toFixed(1)}s</dd>
                  </div>
                  <div>
                    <dt>输出大小</dt>
                    <dd>{formatFileSize(renderUsage.outputBytes)}</dd>
                  </div>
                  <div>
                    <dt>字幕 cue</dt>
                    <dd>{renderUsage.subtitleCueCount}</dd>
                  </div>
                  <div>
                    <dt>TTS 字符</dt>
                    <dd>{renderUsage.ttsCharacterCount}</dd>
                  </div>
                  <div>
                    <dt>Render</dt>
                    <dd>{renderUsage.renderEngine}</dd>
                  </div>
                  <div>
                    <dt>Audio</dt>
                    <dd>{renderUsage.audioEngine}</dd>
                  </div>
                  <div>
                    <dt>Caption</dt>
                    <dd>{renderUsage.captionEngine}</dd>
                  </div>
                  <div>
                    <dt>HyperFrames</dt>
                    <dd>{captionStatusLabel(renderCaptionSummary, renderUsage.captionEngine)}</dd>
                  </div>
                </dl>
              </div>
            )}
            {Object.keys(renderQaChecks).length > 0 && (
              <dl className="render-qa-list" aria-label="渲染 QA 检查">
                {Object.entries(renderQaChecks).map(([key, value]) => (
                  <div key={key}>
                    <dt>{renderQaLabel(key)}</dt>
                    <dd className={value ? "qa-pass" : "qa-warning"}>{value ? "通过" : "待复查"}</dd>
                  </div>
                ))}
              </dl>
            )}
            <div className="render-human-qa" aria-label="渲染人审 QA">
              <p>
                {latestRenderJob.qaReviewStatus === "approved"
                  ? "人工 QA 已通过，可以创建手动发布/交付记录。"
                  : latestRenderJob.qaReviewStatus === "rejected"
                    ? "人工 QA 已退回，需要重新渲染或替换素材。"
                    : "等待人工 QA：确认画面、字幕、音频和素材匹配后再交付。"}
              </p>
              {latestRenderJob.qaReviewNotes && <span>{latestRenderJob.qaReviewNotes}</span>}
              <div className="factory-job-actions">
                <button
                  type="button"
                  className="ghost-button"
                  disabled={qaReviewingRenderJobId === latestRenderJob.id || latestRenderJob.qaReviewStatus === "approved"}
                  aria-label={`通过渲染 QA：${latestRenderJob.id}`}
                  onClick={() => void handleRenderJobQaReview(latestRenderJob, "approved")}
                >
                  {qaReviewingRenderJobId === latestRenderJob.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                  QA 通过
                </button>
                <button
                  type="button"
                  className="ghost-button"
                  disabled={qaReviewingRenderJobId === latestRenderJob.id || latestRenderJob.qaReviewStatus === "rejected"}
                  aria-label={`退回渲染 QA：${latestRenderJob.id}`}
                  onClick={() => void handleRenderJobQaReview(latestRenderJob, "rejected")}
                >
                  <X size={16} aria-hidden="true" />
                  退回修改
                </button>
              </div>
            </div>
          </div>
        )}
        {latestRenderJob?.errorMessage && latestRenderJob.status !== "succeeded" && (
          <p className="factory-error">{latestRenderJob.errorMessage}</p>
        )}
        {renderBlockers.length > 0 && (
          <ol className="render-blocker-list" aria-label="渲染阻塞项">
            {renderBlockers.map(blocker => (
              <li key={`${textValue(blocker.type, "blocker")}-${textValue(blocker.ref, "")}`}>
                <strong>{textValue(blocker.ref, "asset")}</strong>
                <span>{textValue(blocker.message, "素材未就绪")}</span>
              </li>
            ))}
          </ol>
        )}
      </section>

      <section className="video-factory-panel publish-record-panel" aria-labelledby="factory-publish-title">
        <div className="video-factory-panel__heading">
          <h3 id="factory-publish-title">发布 / 交付记录</h3>
          <p>当前版本先记录 QA 通过后的手动上传交付，不冒充平台自动发布。</p>
        </div>
        {publishError && <p className="factory-error">{publishError}</p>}
        <div className="publish-record-panel__top">
          <label>
            <span>交付渠道</span>
            <select
              aria-label="选择发布交付渠道"
              value={publishChannel}
              onChange={event => setPublishChannel(event.target.value)}
            >
              <option value="manual_upload">Manual upload</option>
              <option value="tiktok_manual">TikTok manual</option>
              <option value="drive_delivery">Drive delivery</option>
              <option value="growth_ops_review">Growth ops review</option>
            </select>
          </label>
          <button
            type="button"
            className="submit-button"
            disabled={!latestRenderJobQaApproved || publishState === "running"}
            onClick={() => void handleCreatePublishRecord()}
          >
            {publishState === "running" ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Send size={16} aria-hidden="true" />}
            {publishState === "running" ? "记录中" : "创建交付记录"}
          </button>
        </div>
        {!latestRenderJob ? (
          <p className="real-asset-empty">先生成视频草稿，再进入 QA 和交付。</p>
        ) : !latestRenderJobQaApproved ? (
          <p className="real-asset-empty">当前最新视频草稿还没有通过人工 QA，暂不能创建交付记录。</p>
        ) : null}
        {publishRecords.length > 0 ? (
          <ol className="factory-list publish-record-list" aria-label="发布交付记录">
            {publishRecords.map(record => (
              <li key={record.id}>
                <div>
                  <strong>{publishStatusLabel(record.publishStatus)}</strong>
                  <span>{record.channel} · render {record.renderJobId.slice(0, 8)}</span>
                </div>
                <em className={`factory-status factory-status--${record.publishStatus === "ready_for_upload" || record.publishStatus === "published" ? "ok" : "warning"}`}>
                  {record.createdAt}
                </em>
                <p>{record.notes || record.caption || "等待人工上传或交付给增长运营。"}</p>
              </li>
            ))}
          </ol>
        ) : (
          <p className="real-asset-empty">还没有发布/交付记录。</p>
        )}
      </section>

      {manualGenerationClips.length > 0 && (
        <section className="video-factory-panel" aria-labelledby="factory-manual-seedance-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-manual-seedance-title">外部生成视频片段</h3>
            <p>外部生成后上传，按 clip_id 绑定到导演时间线。</p>
          </div>
          {manualAssetError && <p className="factory-error">{manualAssetError}</p>}
          <ol className="manual-seedance-list">
            {manualGenerationClips.map(clip => {
              const clipId = textValue(clip.clipId, "");
              const start = numberValue(clip.timelineStartSec, 0);
              const end = numberValue(clip.timelineEndSec, start + numberValue(clip.durationSec, 0));
              const prompt = generatedPromptText(clip);
              const asset = manualAssetByClip.get(clipId);
              const isUploading = uploadingClipId === clipId;
              return (
                <li key={clipId}>
                  <div className="manual-seedance-list__main">
                    <div>
                      <strong>{clipId}</strong>
                      <span>{start}s-{end}s · {numberValue(clip.durationSec, end - start)}s</span>
                    </div>
                    <p>{prompt}</p>
                    {asset && (
                      <div className="asset-review-summary">
                        <a className="manual-asset-link" href={`${API_BASE}${asset.storedAssetUrl}`} target="_blank" rel="noreferrer">
                          <ExternalLink size={14} aria-hidden="true" />
                          {asset.originalFilename} · {formatFileSize(asset.fileSizeBytes)} · {asset.durationSec.toFixed(1)}s · {asset.width}x{asset.height}
                        </a>
                        <em className={`factory-status factory-status--${asset.reviewStatus === "approved" ? "ok" : "warning"}`}>
                          {assetReviewStatusLabel(asset.reviewStatus)}
                        </em>
                        <em className={`factory-status factory-status--${asset.semanticReviewStatus === "passed" ? "ok" : "warning"}`}>
                          {semanticReviewStatusLabel(asset.semanticReviewStatus)}
                        </em>
                      </div>
                    )}
                  </div>
                  <div className="manual-seedance-list__actions">
                    <button type="button" className="ghost-button" onClick={() => void handleCopyPrompt(clip)} aria-label={`复制视频提示词：${clipId}`}>
                      <Copy size={16} aria-hidden="true" />
                      {copiedClipId === clipId ? "已复制提示词" : "复制视频提示词"}
                    </button>
                    {asset && (
                      <>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === asset.id || asset.reviewStatus === "approved"}
                          aria-label={`通过 Veo 3.1 素材审核：${clipId}`}
                          onClick={() => void handleManualAssetReview(asset, "approved")}
                        >
                          {reviewingAssetId === asset.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                          通过
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === asset.id || asset.reviewStatus === "rejected"}
                          aria-label={`拒绝 Veo 3.1 素材审核：${clipId}`}
                          onClick={() => void handleManualAssetReview(asset, "rejected")}
                        >
                          <X size={16} aria-hidden="true" />
                          拒绝
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === asset.id || asset.reviewStatus !== "approved" || asset.semanticReviewStatus === "passed"}
                          aria-label={`通过 Veo 3.1 素材语义复核：${clipId}`}
                          onClick={() => void handleManualAssetSemanticReview(asset, "passed")}
                        >
                          {reviewingAssetId === asset.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                          语义通过
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === asset.id || asset.reviewStatus !== "approved" || asset.semanticReviewStatus === "failed"}
                          aria-label={`退回 Veo 3.1 素材语义复核：${clipId}`}
                          onClick={() => void handleManualAssetSemanticReview(asset, "failed")}
                        >
                          <X size={16} aria-hidden="true" />
                          语义退回
                        </button>
                      </>
                    )}
                    <label className={`manual-upload-button${isUploading ? " manual-upload-button--busy" : ""}`}>
                      <UploadCloud size={16} aria-hidden="true" />
                      {isUploading ? "上传中" : asset ? "替换素材" : "上传素材"}
                      <input
                        className="visually-hidden"
                        type="file"
                        accept="video/mp4,video/quicktime,video/webm,.mp4,.mov,.webm"
                        aria-label={`上传 Veo 3.1 素材：${clipId}`}
                        disabled={isUploading}
                        onChange={event => void handleManualAssetChange(clipId, event)}
                      />
                    </label>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      {realMorasAssetNeeds.length > 0 && (
        <section className="video-factory-panel" aria-labelledby="factory-real-bindings-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-real-bindings-title">真实素材绑定</h3>
            <p>从真实 Moras 素材库中选择素材，并绑定到导演计划里的 asset_ref。</p>
          </div>
          {assetBindingError && <p className="factory-error">{assetBindingError}</p>}
          <div className="real-asset-summary">
            <span>{morasAssets.length} 个素材库条目</span>
            <span>{boundRealMorasCount}/{realMorasAssetNeeds.length} 已绑定</span>
          </div>
          <ol className="real-asset-list">
            {realMorasAssetNeeds.map(asset => {
              const ref = assetReference(asset);
              const requiredAssetType = textValue(asset.requiredAssetType, "real_moras_asset");
              const category = textValue(asset.morasAssetCategory, "none");
              const binding = assetBindingByRef.get(ref);
              const boundAsset = binding ? libraryAssetById.get(binding.libraryAssetId) : undefined;
              const matchingAssets = morasAssets.filter(item => libraryAssetMatchesRequirement(item, asset));
              const selectedId = selectedLibraryAssetIds[ref] ?? binding?.libraryAssetId ?? "";
              const isUploading = uploadingAssetRef === ref;
              const isBinding = bindingAssetRef === ref;
              return (
                <li key={ref}>
                  <div className="real-asset-list__main">
                    <div>
                      <strong>{ref}</strong>
                      <span>{requiredAssetType} · {category}</span>
                    </div>
                    <p>{textValue(asset.resolverNote, "Needs approved Moras asset before rendering.")}</p>
                    {boundAsset ? (
                      <div className="asset-review-summary">
                        <a className="manual-asset-link" href={`${API_BASE}${boundAsset.storedAssetUrl}`} target="_blank" rel="noreferrer">
                          <ExternalLink size={14} aria-hidden="true" />
                          {boundAsset.title} · {boundAsset.originalFilename} · {formatFileSize(boundAsset.fileSizeBytes)} · {boundAsset.width}x{boundAsset.height}
                        </a>
                        <em className={`factory-status factory-status--${boundAsset.reviewStatus === "approved" ? "ok" : "warning"}`}>
                          {assetReviewStatusLabel(boundAsset.reviewStatus)}
                        </em>
                        <em className={`factory-status factory-status--${boundAsset.semanticReviewStatus === "passed" ? "ok" : "warning"}`}>
                          {semanticReviewStatusLabel(boundAsset.semanticReviewStatus)}
                        </em>
                      </div>
                    ) : (
                      <span className="real-asset-empty">未绑定真实素材</span>
                    )}
                  </div>
                  <div className="real-asset-list__actions">
                    <select
                      className="asset-library-select"
                      aria-label={`选择真实素材：${ref}`}
                      value={selectedId}
                      onChange={event => setSelectedLibraryAssetIds(previous => ({ ...previous, [ref]: event.target.value }))}
                    >
                      <option value="">选择已有素材</option>
                      {matchingAssets.map(item => (
                        <option key={item.id} value={item.id}>{item.title} · {item.originalFilename}</option>
                      ))}
                    </select>
                    <button
                      type="button"
                      className="ghost-button"
                      disabled={!selectedId || isBinding}
                      onClick={() => void handleBindExistingMorasAsset(asset)}
                    >
                      {isBinding ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                      {isBinding ? "绑定中" : "绑定"}
                    </button>
                    {boundAsset && (
                      <div className="asset-review-actions asset-review-actions--grid">
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === boundAsset.id || boundAsset.reviewStatus === "approved"}
                          aria-label={`通过绑定真实素材审核：${ref}`}
                          onClick={() => void handleMorasAssetReview(boundAsset, "approved")}
                        >
                          {reviewingAssetId === boundAsset.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                          审核通过
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === boundAsset.id || boundAsset.reviewStatus === "rejected"}
                          aria-label={`拒绝绑定真实素材审核：${ref}`}
                          onClick={() => void handleMorasAssetReview(boundAsset, "rejected")}
                        >
                          <X size={16} aria-hidden="true" />
                          拒绝
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === boundAsset.id || boundAsset.reviewStatus !== "approved" || boundAsset.semanticReviewStatus === "passed"}
                          aria-label={`通过绑定真实素材语义复核：${ref}`}
                          onClick={() => void handleMorasAssetSemanticReview(boundAsset, "passed")}
                        >
                          {reviewingAssetId === boundAsset.id ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <BadgeCheck size={16} aria-hidden="true" />}
                          语义通过
                        </button>
                        <button
                          type="button"
                          className="ghost-button"
                          disabled={reviewingAssetId === boundAsset.id || boundAsset.reviewStatus !== "approved" || boundAsset.semanticReviewStatus === "failed"}
                          aria-label={`退回绑定真实素材语义复核：${ref}`}
                          onClick={() => void handleMorasAssetSemanticReview(boundAsset, "failed")}
                        >
                          <X size={16} aria-hidden="true" />
                          语义退回
                        </button>
                      </div>
                    )}
                    <label className={`manual-upload-button${isUploading ? " manual-upload-button--busy" : ""}`}>
                      <UploadCloud size={16} aria-hidden="true" />
                      {isUploading ? "上传中" : boundAsset ? "上传并替换" : "上传真实素材"}
                      <input
                        className="visually-hidden"
                        type="file"
                        accept="video/mp4,video/quicktime,video/webm,image/png,image/jpeg,image/webp,.mp4,.mov,.webm,.png,.jpg,.jpeg,.webp"
                        aria-label={`上传真实素材：${ref}`}
                        disabled={isUploading}
                        onChange={event => void handleMorasAssetUpload(asset, event)}
                      />
                    </label>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      )}

      <section className="video-factory-panel" aria-labelledby="factory-timeline-title">
        <div className="video-factory-panel__heading">
          <h3 id="factory-timeline-title">剪辑时间线</h3>
          <p>{textValue(directorPlan.validationSummary.timelineContinuity, "base_track continuity checked")}</p>
        </div>
        <div className="factory-timeline" aria-label="导演 Agent 多轨时间线">
          {videoTracks.map(track => (
            <FactoryTimelineLane
              key={`video-${textValue(track.layer, "track")}`}
              track={track}
              totalDuration={totalDuration}
            />
          ))}
          {audioTracks.map(track => (
            <FactoryTimelineLane
              key={`audio-${textValue(track.layer, "audio")}`}
              track={track}
              totalDuration={totalDuration}
            />
          ))}
        </div>
      </section>

      <div className="video-factory-grid">
        <section className="video-factory-panel" aria-labelledby="factory-assets-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-assets-title">素材绑定</h3>
            <p>{textValue(directorPlan.validationSummary.assetReadiness, "asset readiness pending")}</p>
          </div>
          <ol className="factory-list">
            {directorPlan.assetResolution.map(asset => {
              const ref = assetReference(asset);
              const binding = assetBindingByRef.get(ref);
              const boundAsset = binding ? libraryAssetById.get(binding.libraryAssetId) : undefined;
              const status = boundAsset ? "bound" : textValue(asset.resolutionStatus, "pending");
              return (
                <li key={ref || textValue(asset.sourcePlanId, "asset")}>
                  <div>
                    <strong>{textValue(asset.requiredAssetType, "asset")}</strong>
                    <span>{textValue(asset.morasAssetCategory, "none")}</span>
                  </div>
                  <em className={`factory-status factory-status--${status === "ready" || status === "resolved" || status === "bound" ? "ok" : "warning"}`}>
                    {status}
                  </em>
                  <p>{boundAsset ? `已绑定：${boundAsset.title}` : textValue(asset.resolverNote, "")}</p>
                </li>
              );
            })}
          </ol>
        </section>

        <section className="video-factory-panel" aria-labelledby="factory-tools-title">
          <div className="video-factory-panel__heading">
            <h3 id="factory-tools-title">工具调度</h3>
            <p>{textValue(directorPlan.validationSummary.renderScope, "plan only")}</p>
          </div>
          <ol className="factory-list factory-list--dispatches">
            {dispatches.map(dispatch => {
              const status = textValue(dispatch.status, "planned");
              return (
                <li key={`${dispatch.sequenceOrder}-${dispatch.toolName}`}>
                  <div>
                    <strong>{textValue(dispatch.toolName, "tool")}</strong>
                    <span>Step {textValue(dispatch.sequenceOrder, "")}</span>
                  </div>
                  <em className={`factory-status factory-status--${dispatchStatusTone(status)}`}>
                    {dispatchStatusLabel(status)}
                  </em>
                  <p>{textValue(dispatch.expectedOutput, "")}</p>
                </li>
              );
            })}
          </ol>
        </section>
      </div>
    </section>
  );
}

function FactoryMetric({ label, value, tone = "neutral" }: { label: string; value: string; tone?: "neutral" | "ok" | "warning" }) {
  return (
    <div className={`factory-metric factory-metric--${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function FactoryTimelineLane({ track, totalDuration }: { track: JsonObject; totalDuration: number }) {
  const clips = arrayObjects(track.clips);
  return (
    <div className="factory-timeline-lane">
      <div className="factory-timeline-lane__label">{textValue(track.layer, "track")}</div>
      <div className="factory-timeline-lane__track">
        {clips.map(clip => {
          const start = numberValue(clip.timelineStartSec, 0);
          const duration = numberValue(clip.durationSec, 0);
          const left = totalDuration > 0 ? Math.max(0, Math.min(100, (start / totalDuration) * 100)) : 0;
          const width = totalDuration > 0 ? Math.max(2, Math.min(100 - left, (duration / totalDuration) * 100)) : 100;
          return (
            <div
              key={textValue(clip.clipId, `${track.layer}-${start}`)}
              className={`factory-timeline-clip factory-timeline-clip--${timelineClipTone(textValue(clip.sourceType, ""))}`}
              style={{ left: `${left}%`, width: `${width}%` }}
              title={textValue(clip.notes, "")}
            >
              <strong>{textValue(clip.sourceType, "clip")}</strong>
              <span>{start}s-{numberValue(clip.timelineEndSec, start + duration)}s</span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function timelineClipTone(sourceType: string): string {
  if (sourceType.includes("veo")) return "blue";
  if (sourceType.includes("seedance")) return "blue";
  if (sourceType.includes("library")) return "green";
  if (sourceType.includes("hyperframes")) return "amber";
  if (sourceType.includes("tts") || sourceType.includes("music") || sourceType.includes("sound")) return "rose";
  return "slate";
}

function generatedPromptText(clip: JsonObject): string {
  return textValue(
    clip.veoPrompt,
    textValue(clip.veo_prompt, textValue(clip.manualPromptText, textValue(clip.promptText, textValue(clip.notes, "")))),
  );
}

function isManualGenerationClip(clip: JsonObject): boolean {
  const sourceType = textValue(clip.sourceType, textValue(clip.source_type, ""));
  return sourceType.includes("veo") || sourceType.includes("seedance");
}

function assetReference(asset: JsonObject): string {
  return textValue(asset.assetRef, textValue(asset.asset_ref, textValue(asset.sourcePlanId, textValue(asset.source_plan_id, "asset"))));
}

function isRealMorasAssetRequirement(asset: JsonObject): boolean {
  const requiredAssetType = textValue(asset.requiredAssetType, textValue(asset.required_asset_type, ""));
  const category = textValue(asset.morasAssetCategory, textValue(asset.moras_asset_category, "none"));
  if (!requiredAssetType || requiredAssetType === "manual_veo_clip" || requiredAssetType === "manual_seedance_clip") return false;
  if (requiredAssetType.includes("veo") || requiredAssetType.includes("seedance")) return false;
  return requiredAssetType.includes("moras") || category !== "none";
}

function libraryAssetMatchesRequirement(libraryAsset: MorasAssetLibraryRecord, requirement: JsonObject): boolean {
  const requiredAssetType = textValue(requirement.requiredAssetType, textValue(requirement.required_asset_type, ""));
  const category = textValue(requirement.morasAssetCategory, textValue(requirement.moras_asset_category, "none"));
  const typeMatches = !requiredAssetType || libraryAsset.assetType === requiredAssetType;
  const categoryMatches = !category || category === "none" || libraryAsset.morasAssetCategory === category;
  return typeMatches && categoryMatches;
}

function upsertAssetBinding(
  bindings: DirectorPlanAssetBindingRecord[],
  binding: DirectorPlanAssetBindingRecord,
): DirectorPlanAssetBindingRecord[] {
  return [binding, ...bindings.filter(item => item.assetRef !== binding.assetRef)];
}

function upsertRenderJob(
  jobs: DirectorRenderJobRecord[],
  job: DirectorRenderJobRecord,
): DirectorRenderJobRecord[] {
  return [job, ...jobs.filter(item => item.id !== job.id)];
}

function formatFileSize(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}

function formatShortDateTime(value: string): string {
  const timestamp = Date.parse(value);
  if (Number.isNaN(timestamp)) return value;
  return new Date(timestamp).toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function renderArtifactTypeLabel(type: string): string {
  if (type === "video") return "视频 MP4";
  if (type === "audio") return "音频 M4A";
  if (type === "subtitle") return "字幕 VTT";
  if (type === "caption_composition") return "字幕 HTML sidecar";
  if (type === "caption_overlay") return "HyperFrames overlay WebM";
  if (type === "metadata") return "元数据";
  return type || "产物";
}

function captionStatusLabel(summary: JsonObject, usageEngine?: string | null): string {
  const engine = textValue(summary.engine, usageEngine || "");
  const status = textValue(summary.hyperframesStatus, textValue(summary.hyperframes_status, ""));
  if (engine === "hyperframes_cli_v1" || status === "composited") return "HyperFrames 已合成";
  if (status === "overlay_rendered" || status === "rendered") return "HyperFrames overlay 已生成";
  if (status === "package_missing" || status === "cli_unavailable") return "HyperFrames CLI 未安装";
  if (status === "render_timeout") return "HyperFrames 渲染超时";
  if (status === "render_failed" || status === "cli_failed") return "HyperFrames 渲染失败";
  if (status === "cli_disabled") return "WebVTT 预览";
  if (engine) return engine;
  return "待生成";
}

function renderStorageStatusLabel(status: string): string {
  if (status === "active") return "保留中";
  if (status === "retention_expired") return "保留已过期";
  if (status === "deleted") return "已删除";
  return status || "未知状态";
}

function renderJobStatusLabel(status: string): string {
  if (status === "queued") return "渲染排队中";
  if (status === "succeeded") return "已输出视频草稿";
  if (status === "blocked") return "素材未齐，暂不能出片";
  if (status === "failed") return "渲染失败";
  if (status === "rendering") return "渲染中";
  return status || "待执行";
}

function dispatchStatusLabel(status: string): string {
  if (status === "planned") return "计划 / 待执行";
  if (status === "blocked") return "阻塞 / 等素材";
  if (status === "running") return "执行中";
  if (status === "succeeded" || status === "completed") return "已完成";
  if (status === "failed") return "执行失败";
  return status || "待执行";
}

function dispatchStatusTone(status: string): "ok" | "warning" {
  return status === "succeeded" || status === "completed" ? "ok" : "warning";
}

function assetReviewStatusLabel(status: string): string {
  if (status === "approved") return "审核通过";
  if (status === "rejected") return "已拒绝";
  return "待审核";
}

function semanticReviewStatusLabel(status: string): string {
  if (status === "passed") return "语义匹配通过";
  if (status === "failed") return "语义已退回";
  return "待语义复核";
}

function renderQaReviewStatusLabel(status: string): string {
  if (status === "approved") return "人工 QA 通过";
  if (status === "rejected") return "人工 QA 退回";
  return "待人工 QA";
}

function publishStatusLabel(status: string): string {
  if (status === "published") return "已发布";
  if (status === "canceled") return "已取消";
  return "待手动上传";
}

function renderQaLabel(key: string): string {
  const labels: Record<string, string> = {
    timelineDurationMatch: "时长匹配",
    vertical1080x1920: "竖屏规格",
    audioStreamPresent: "音频轨",
    subtitleCuesPresent: "字幕 cues",
  };
  return labels[key] ?? key;
}

function LibraryDrawer({
  open,
  items,
  selectedId,
  state,
  error,
  onClose,
  onRefresh,
  onSelect,
  onDelete,
}: {
  open: boolean;
  items: SocialVideoAnalysis[];
  selectedId?: string;
  state: HistoryState;
  error: string;
  onClose: () => void;
  onRefresh: () => void;
  onSelect: (record: SocialVideoAnalysis) => void;
  onDelete: (record: SocialVideoAnalysis) => Promise<void>;
}) {
  const [deleteTarget, setDeleteTarget] = useState<SocialVideoAnalysis | null>(null);
  const [deleteError, setDeleteError] = useState("");
  const [isDeleting, setIsDeleting] = useState(false);

  if (!open) return null;

  async function handleConfirmDelete() {
    if (!deleteTarget) return;
    setIsDeleting(true);
    setDeleteError("");
    try {
      await onDelete(deleteTarget);
      setDeleteTarget(null);
    } catch (err) {
      setDeleteError(err instanceof Error ? err.message : "删除失败，请稍后重试。");
    } finally {
      setIsDeleting(false);
    }
  }

  return (
    <div className="library-drawer" role="presentation">
      <button className="library-backdrop" type="button" aria-label="关闭历史库" onClick={onClose} />
      <aside className="library-panel" role="dialog" aria-modal="true" aria-labelledby="library-title">
        <header className="library-panel__header">
          <div>
            <h2 id="library-title">视频拆解库</h2>
            <p>选择一个已拆解视频，主页面会切换到对应结果。</p>
          </div>
          <div className="library-panel__actions">
            <button type="button" className="icon-button" onClick={onRefresh} aria-label="刷新历史记录" disabled={state === "loading"}>
              <RefreshCw className={state === "loading" ? "spin" : undefined} size={18} aria-hidden="true" />
            </button>
            <button type="button" className="icon-button" onClick={onClose} aria-label="关闭历史库">
              <X size={18} aria-hidden="true" />
            </button>
          </div>
        </header>

        {error && <div className="library-alert">{error}</div>}
        {deleteError && <div className="library-alert">{deleteError}</div>}
        {state === "loading" && items.length === 0 && <EmptyBlock text="正在加载历史记录。" />}
        {state !== "loading" && items.length === 0 && <EmptyBlock text="暂无历史拆解记录。" />}

        <div className="library-list">
          {items.map(item => (
            <HistoryVideoCard
              key={item.id}
              record={item}
              selected={item.id === selectedId}
              onClick={() => onSelect(item)}
              onDelete={() => {
                setDeleteTarget(item);
                setDeleteError("");
              }}
            />
          ))}
        </div>

        {deleteTarget && (
          <div className="library-confirm" role="dialog" aria-modal="true" aria-labelledby="library-delete-title">
            <div className="library-confirm__box">
              <h3 id="library-delete-title">确认删除视频拆解</h3>
              <p>确认从视频拆解库删除《{historyTitle(deleteTarget)}》吗？删除后会同步从仓库中移除。</p>
              <div className="library-confirm__actions">
                <button type="button" className="library-confirm__button" onClick={() => setDeleteTarget(null)} disabled={isDeleting}>取消</button>
                <button type="button" className="library-confirm__button library-confirm__button--danger" onClick={handleConfirmDelete} disabled={isDeleting}>
                  {isDeleting ? "删除中" : "删除"}
                </button>
              </div>
            </div>
          </div>
        )}
      </aside>
    </div>
  );
}

function HistoryVideoCard({
  record,
  selected,
  onClick,
  onDelete,
}: {
  record: SocialVideoAnalysis;
  selected: boolean;
  onClick: () => void;
  onDelete: () => void;
}) {
  const sourceVideo = record.sourceVideo;
  const videoSrc = getPlayableVideoSrc(sourceVideo);
  const title = historyTitle(record);
  const summary = firstString(sourceVideo?.contentSummary, sourceVideo?.originalUrl, record.id);
  const category = firstString(record.classification?.hookType, ...asArray(record.classification?.structureFactors));

  return (
    <article className={`library-card${selected ? " library-card--selected" : ""}`}>
      <button className="library-card__select" type="button" onClick={onClick} aria-label={`查看视频拆解：${title}`}>
        <div className="library-card__cover">
          {videoSrc ? (
            <video src={videoSrc} muted playsInline preload="metadata" aria-label={`${title} 封面预览`} />
          ) : (
            <div className="library-card__placeholder">
              <Film size={24} aria-hidden="true" />
            </div>
          )}
        </div>
        <div className="library-card__body">
          <h3>{title}</h3>
          <p>{summary}</p>
          <div className="library-card__meta">
            <StatusPill status={record.status} />
            {category && <span className="library-category">{category}</span>}
          </div>
          <time>{formatDate(record.updatedAt)}</time>
        </div>
      </button>
      <button type="button" className="library-card__delete" aria-label={`删除视频拆解：${title}`} onClick={onDelete}>
        <Trash2 size={17} aria-hidden="true" />
      </button>
    </article>
  );
}

function historyTitle(record: SocialVideoAnalysis) {
  return firstString(record.sourceVideo?.title, record.sourceVideo?.contentSummary, record.sourceVideo?.originalUrl, "未命名视频");
}

function AnalysisDashboard({ analysis }: { analysis: SocialVideoAnalysis }) {
  const sourceVideo = analysis.sourceVideo;
  const classification = analysis.classification;
  const decomposition = analysis.decomposition;
  const timeline = useMemo(() => buildTimeline(decomposition), [decomposition]);
  const keyShots = useMemo(() => buildKeyShots(decomposition, timeline), [decomposition, timeline]);
  const referenceStoryboard = useMemo(() => referenceStoryboardFromAnalysis(analysis), [analysis]);

  return (
    <div className="result-grid">
      <SourceStatusCard analysis={analysis} sourceVideo={sourceVideo} />
      <ClassificationCard classification={classification} />
      <HookTextCard decomposition={decomposition} />
      <TimelineCard timeline={timeline} />
      <ReferenceStoryboardCard storyboard={referenceStoryboard} />
      <KeyShotsCard keyShots={keyShots} />
    </div>
  );
}

function SourceStatusCard({ analysis, sourceVideo }: { analysis: SocialVideoAnalysis; sourceVideo: SourceVideo | null }) {
  const videoSrc = getPlayableVideoSrc(sourceVideo);
  const sourceHref = firstString(sourceVideo?.originalUrl, sourceVideo?.sourceUrl);
  const metrics = toObject(sourceVideo?.observedMetrics) ?? toObject(sourceVideo?.visibleMetrics);
  const extraFields = omitKeys(sourceVideo, hiddenSourceKeys);
  const sourceTitle = firstString(sourceVideo?.title, sourceVideo?.contentSummary, "未命名视频");
  const sourceMeta = [
    ["平台", sourceVideo?.platform],
    ["创作者", sourceVideo?.creatorHandle],
    ["时长", formatDuration(sourceVideo?.durationSeconds)],
  ].filter(([, value]) => hasRenderableValue(value as JsonValue | undefined)) as Array<[string, JsonValue]>;

  return (
    <section className="dashboard-card dashboard-card--source">
      <div className="card-head">
        <SectionHeading icon={<PlayCircle size={20} />} title="视频 / 来源状态" />
        <div className="source-actions">
          <StatusPill status={analysis.status} />
          <a className="export-button" href={videoBreakdownClient.markdownExportUrl(analysis.id)} target="_blank" rel="noreferrer">
            <Download size={16} aria-hidden="true" />
            导出拆解文档
          </a>
        </div>
      </div>
      <div className="source-layout">
        <div className="video-frame">
          {videoSrc ? (
            <video controls src={videoSrc} aria-label="导入后视频预览" />
          ) : (
            <div className="video-frame__empty">后端完成导入后显示可播放视频</div>
          )}
        </div>
        <div className="source-details">
          <div className="source-summary">
            <span>视频来源</span>
            <h3>{sourceTitle}</h3>
            {sourceVideo?.contentSummary && <p>{sourceVideo.contentSummary}</p>}
          </div>
          {sourceMeta.length > 0 && (
            <div className="source-meta-grid">
              {sourceMeta.map(([label, value]) => (
                <div key={label}>
                  <span>{label}</span>
                  <strong>{renderPrimitive(value)}</strong>
                </div>
              ))}
            </div>
          )}
          {sourceHref && <LinkRow label="原始链接" href={sourceHref} />}
          {sourceVideo?.importedVideoUrl && <LinkRow label="导入后视频" href={assetUrl(sourceVideo.importedVideoUrl)} />}
          {metrics && <MetricGrid metrics={metrics} />}
          <div className="source-technical">
            <InfoRow label="分析编号" value={analysis.id} code />
            <InfoRow label="更新时间" value={formatDate(analysis.updatedAt)} />
          </div>
          {Object.keys(extraFields).length > 0 && <StructuredValue value={extraFields} compact />}
        </div>
      </div>
    </section>
  );
}

function ClassificationCard({ classification }: { classification: Classification | null }) {
  const evidence = asArray(classification?.evidence);
  const missingInputs = asArray(classification?.missingInputs);
  const extraFields = omitKeys(classification, hiddenClassificationKeys);
  const factorGroups = [
    ["Hook 因子", valueList(classification?.hookType)],
    ["情绪因子", asArray(classification?.emotionFactors)],
    ["人设因子", asArray(classification?.personaFactors)],
    ["场景因子", asArray(classification?.sceneFactors)],
    ["冲突因子", asArray(classification?.conflictFactors)],
    ["痛点因子", asArray(classification?.painFactors)],
    ["痒点因子", asArray(classification?.itchFactors)],
    ["Value 因子", asArray(classification?.valueFactors)],
    ["Proof 因子", asArray(classification?.proofFactors)],
    ["CTA 因子", asArray(classification?.ctaFactors)],
    ["视频结构因子", asArray(classification?.structureFactors)],
    ["视觉节奏因子", asArray(classification?.visualRhythmFactors)],
    ["人群洞察", asArray(classification?.audienceSegments)],
    ["General 模板", asArray(classification?.generalTemplates)],
    ["Vertical 模板", asArray(classification?.verticalTemplates)],
  ].filter(([, items]) => (items as JsonValue[]).length > 0) as Array<[string, JsonValue[]]>;

  return (
    <section className="dashboard-card dashboard-card--classification">
      <div className="card-head card-head--stacked">
        <SectionHeading icon={<Tags size={20} />} title="爆款因子分类" />
        <div className="classification-main">
          <span className="category-chip">{classification?.hookType || "未返回 Hook 因子"}</span>
          {typeof classification?.confidence === "number" && (
            <span className="confidence-chip">置信度 {Math.round(classification.confidence * 100)}%</span>
          )}
        </div>
      </div>
      {classification?.factorReasoning && (
        <div className="reason-callout">
          <span>判断依据</span>
          <p>{classification.factorReasoning}</p>
        </div>
      )}
      <InfoRow label="标准编号" value={classification?.standardId} code />
      <div className="factor-grid">
        {factorGroups.map(([title, items]) => (
          <TagList key={title} title={title} items={items} />
        ))}
      </div>
      <div className="classification-evidence-grid">
        <BulletList title="判断证据" items={evidence} />
        <BulletList title="缺失输入" items={missingInputs} muted />
      </div>
      {Object.keys(extraFields).length > 0 && <StructuredValue value={extraFields} compact />}
    </section>
  );
}

function HookTextCard({ decomposition }: { decomposition: Decomposition | null }) {
  const openingHook = toObject(decomposition?.openingHook);
  const narrative = asArray(decomposition?.narrativeStructure);
  const takeaways = asArray(decomposition?.keyTakeaways);
  const extraFields = omitKeys(decomposition, hiddenDecompositionKeys);

  return (
    <section className="dashboard-card dashboard-card--wide dashboard-card--hook">
      <SectionHeading icon={<FileText size={20} />} title="开头钩子 / 文本拆解" />
      <div className="summary-strip">
        <InfoRow label="一句话拆解" value={decomposition?.oneSentenceSummary} />
        <InfoRow label="开头钩子" value={decomposition?.hook || stringFrom(openingHook?.observedContent)} />
      </div>
      {openingHook && (
        <div className="hook-box">
          <InfoRow label="时间范围" value={stringFrom(openingHook.timeRange)} code />
          <InfoRow label="观察内容" value={stringFrom(openingHook.observedContent)} />
          <InfoRow label="表现功能" value={stringFrom(openingHook.performanceFunction)} />
        </div>
      )}
      <div className="two-column">
        <div>
          <BulletList title="叙事结构" items={narrative} ordered />
          <BulletList title="关键结论" items={takeaways} />
        </div>
        <div>
          <InfoRow label="画面语言" value={decomposition?.visualLanguage} />
          <InfoRow label="声音语言" value={decomposition?.audioLanguage} />
          <InfoRow label="互动 / 行动引导" value={decomposition?.interactionOrCta} />
          <InfoRow label="有效机制" value={decomposition?.performanceLogic} />
        </div>
      </div>
      {Object.keys(extraFields).length > 0 && <StructuredValue value={extraFields} compact />}
    </section>
  );
}

function TimelineCard({ timeline }: { timeline: TimelineItem[] }) {
  return (
    <section className="dashboard-card dashboard-card--timeline">
      <SectionHeading icon={<Clock3 size={20} />} title="结构时间线" />
      {timeline.length > 0 ? (
        <ol className="timeline-list">
          {timeline.map(item => (
            <li key={item.id} className="timeline-item">
              <span className="timeline-time">{item.time}</span>
              <div>
                <h3>{item.title}</h3>
                <p>{item.content}</p>
                <dl className="inline-definition">
                  <div><dt>作用</dt><dd>{item.role || "未提供"}</dd></div>
                  <div><dt>手法</dt><dd>{item.technique || "未提供"}</dd></div>
                </dl>
              </div>
            </li>
          ))}
        </ol>
      ) : (
        <EmptyBlock text="后端结果中没有结构时间线。" />
      )}
    </section>
  );
}

function ReferenceStoryboardCard({ storyboard }: { storyboard: ScriptStoryboardShot[] }) {
  return (
    <section className="dashboard-card dashboard-card--wide dashboard-card--reference-storyboard">
      <SectionHeading icon={<Clapperboard size={20} />} title="爆款参考分镜脚本" />
      {storyboard.length > 0 ? (
        <div className="reference-storyboard-table-scroll">
          <table className="reference-storyboard-table" aria-label="爆款参考分镜脚本">
            <thead>
              <tr>
                <th scope="col">Shot / Time</th>
                <th scope="col">Visual Action</th>
                <th scope="col">Shot / Camera</th>
                <th scope="col">Voiceover / Overlay / Audio</th>
                <th scope="col">Edit Logic / Purpose</th>
              </tr>
            </thead>
            <tbody>
              {storyboard.map((shot, index) => (
                <tr key={`${shot.shotId || index}-${shot.timestamp || ""}`}>
                  <th scope="row">
                    <span>Shot {String(index + 1).padStart(2, "0")}</span>
                    <time>{firstString(shot.timestamp, shot.duration, "未标注")}</time>
                  </th>
                  <td>
                    <strong>{firstString(shot.characterAction, "未提供动作")}</strong>
                    <p>{firstString(shot.background, shot.facialExpression, "")}</p>
                  </td>
                  <td>
                    <p>{firstString(shot.camera, "未提供镜头")}</p>
                    {shot.props && shot.props.length > 0 && <small>{asArray(shot.props).map(renderPrimitive).join(" / ")}</small>}
                  </td>
                  <td>
                    <p>{firstString(shot.voiceover, "未观察到明确口播")}</p>
                    {shot.overlay && <small>{shot.overlay}</small>}
                    {shot.sound && <small>{shot.sound}</small>}
                    {shot.bgm && <small>BGM：{shot.bgm}</small>}
                    {shot.soundEffects && shot.soundEffects.length > 0 && <small>音效：{asArray(shot.soundEffects).map(renderPrimitive).join(" / ")}</small>}
                  </td>
                  <td>
                    {shot.subtitleLogic && <p>字幕逻辑：{shot.subtitleLogic}</p>}
                    {shot.visualElements && shot.visualElements.length > 0 && <small>画面要素：{asArray(shot.visualElements).map(renderPrimitive).join(" / ")}</small>}
                    {shot.visualElementLogic && <small>要素逻辑：{shot.visualElementLogic}</small>}
                    {shot.transition && <small>转场：{shot.transition}</small>}
                    <p>{firstString(shot.purpose, "未提供作用")}</p>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <EmptyBlock text="后端未返回爆款参考分镜脚本；完成新版拆解后会在这里展示和生成脚本统一字段的分镜。" />
      )}
    </section>
  );
}

function KeyShotsCard({ keyShots }: { keyShots: TimelineItem[] }) {
  return (
    <section className="dashboard-card dashboard-card--shots">
      <SectionHeading icon={<Camera size={20} />} title="关键镜头" />
      {keyShots.length > 0 ? (
        <div className="shot-list">
          {keyShots.map(item => (
            <article key={item.id} className="shot-item">
              <div className="shot-time">{item.time}</div>
              <h3>{item.title}</h3>
              <p>{item.content}</p>
              <span>{item.technique || item.role || "未提供镜头说明"}</span>
            </article>
          ))}
        </div>
      ) : (
        <EmptyBlock text="后端未返回关键镜头；可由结构时间线继续补齐。" />
      )}
    </section>
  );
}

function RunningPanel() {
  return (
    <section className="running-panel" aria-live="polite">
      <Loader2 className="spin" size={22} aria-hidden="true" />
      <div>
        <h2>正在等待后端返回完整拆解结果</h2>
        <p>当前流程会提交到后端，后端完成导入、爆款因子分类和拆解后一次性展示结果。</p>
      </div>
    </section>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="error-banner" role="alert">
      <AlertCircle size={18} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function StatusBanner({ message }: { message: string }) {
  return (
    <div className="status-banner" role="status">
      <CheckCircle2 size={18} aria-hidden="true" />
      <span>{message}</span>
    </div>
  );
}

function SectionHeading({ icon, title }: { icon: ReactNode; title: string }) {
  return (
    <div className="section-heading">
      <span aria-hidden="true">{icon}</span>
      <h2>{title}</h2>
    </div>
  );
}

function StatusPill({ status, active = false }: { status: string; active?: boolean }) {
  const tone = status === "succeeded" ? "ok" : status === "failed" ? "bad" : active || status === "running" || status === "importing" ? "live" : "idle";
  const icon = status === "succeeded"
    ? <CheckCircle2 size={16} aria-hidden="true" />
    : status === "failed"
      ? <AlertCircle size={16} aria-hidden="true" />
      : active
        ? <Loader2 className="spin" size={16} aria-hidden="true" />
        : <BadgeCheck size={16} aria-hidden="true" />;

  return (
    <span className={`status-pill status-pill--${tone}`}>
      {icon}
      {statusCopy[status] || status}
    </span>
  );
}

function InfoRow({ label, value, code = false }: { label: string; value: JsonValue | undefined; code?: boolean }) {
  if (!hasRenderableValue(value)) return null;
  return (
    <div className="info-row">
      <dt>{label}</dt>
      <dd className={code ? "code-text" : undefined}>{renderPrimitive(value)}</dd>
    </div>
  );
}

function LinkRow({ label, href }: { label: string; href: string }) {
  return (
    <div className="info-row">
      <dt>{label}</dt>
      <dd>
        <a className="text-link" href={href} target="_blank" rel="noreferrer">
          打开链接 <ExternalLink size={14} aria-hidden="true" />
        </a>
      </dd>
    </div>
  );
}

function MetricGrid({ metrics }: { metrics: JsonObject }) {
  const entries = Object.entries(metrics).filter(([, value]) => hasRenderableValue(value));
  if (entries.length === 0) return null;
  return (
    <div className="metric-grid">
      {entries.map(([key, value]) => (
        <div key={key} className="metric-item">
          <span>{fieldLabel(key)}</span>
          <strong>{renderPrimitive(value)}</strong>
        </div>
      ))}
    </div>
  );
}

function TagList({ title, items }: { title: string; items: JsonValue[] }) {
  const values = items.filter(hasRenderableValue);
  if (values.length === 0) return null;
  return (
    <div className="tag-group">
      <span>{title}</span>
      <div>
        {values.map((item, index) => <span className="tag-chip" key={`${title}-${index}`}>{renderPrimitive(item)}</span>)}
      </div>
    </div>
  );
}

function BulletList({ title, items, muted = false, ordered = false }: { title: string; items: JsonValue[]; muted?: boolean; ordered?: boolean }) {
  const values = items.filter(hasRenderableValue);
  if (values.length === 0) return null;
  const ListTag = ordered ? "ol" : "ul";
  return (
    <div className={`bullet-block${muted ? " bullet-block--muted" : ""}`}>
      <h3>{title}</h3>
      <ListTag>
        {values.map((item, index) => <li key={`${title}-${index}`}>{renderStructuredInline(item)}</li>)}
      </ListTag>
    </div>
  );
}

function StructuredValue({ value, compact = false }: { value: JsonValue | undefined; compact?: boolean }) {
  if (!hasRenderableValue(value)) return <span className="muted-text">未提供</span>;
  if (Array.isArray(value)) {
    return (
      <div className={`structured-list${compact ? " structured-list--compact" : ""}`}>
        {value.filter(hasRenderableValue).map((item, index) => (
          <div key={index} className="structured-list__item">{renderStructuredInline(item)}</div>
        ))}
      </div>
    );
  }
  if (typeof value === "object" && value !== null) {
    return (
      <dl className={`structured-map${compact ? " structured-map--compact" : ""}`}>
        {Object.entries(value)
          .filter(([, child]) => hasRenderableValue(child))
          .map(([key, child]) => (
            <div key={key}>
              <dt>{fieldLabel(key)}</dt>
              <dd>{renderStructuredInline(child)}</dd>
            </div>
          ))}
      </dl>
    );
  }
  return <span>{renderPrimitive(value)}</span>;
}

function EmptyBlock({ text }: { text: string }) {
  return <div className="empty-block">{text}</div>;
}

function buildTimeline(decomposition: Decomposition | null): TimelineItem[] {
  const contentStructure = asArray(decomposition?.contentStructure).map((item, index) => {
    const value = toObject(item);
    return value ? timelineItemFromObject(value, index) : null;
  }).filter(Boolean) as TimelineItem[];
  if (contentStructure.length > 0) return contentStructure;

  return asArray(decomposition?.segments).map((item, index) => {
    const value = toObject(item);
    return value ? timelineItemFromObject(value, index) : null;
  }).filter(Boolean) as TimelineItem[];
}

function buildKeyShots(decomposition: Decomposition | null, timeline: TimelineItem[]): TimelineItem[] {
  const explicit = asArray(decomposition?.keyShots).map((item, index) => {
    const value = toObject(item);
    return value ? timelineItemFromObject(value, index) : null;
  }).filter(Boolean) as TimelineItem[];
  if (explicit.length > 0) return explicit;
  return timeline.filter(item => item.time !== "未标注").slice(0, 6);
}

function referenceStoryboardFromAnalysis(analysis: SocialVideoAnalysis): ScriptStoryboardShot[] {
  if (analysis.referenceStoryboard?.length) return analysis.referenceStoryboard;
  return asArray(analysis.decomposition?.segments).map((item, index) => {
    const value = toObject(item);
    if (!value) return null;
    const start = numberFrom(value.startSecond);
    const end = numberFrom(value.endSecond);
    const timestamp = start !== null && end !== null ? `${start}s-${end}s` : timeLabel(value, index);
    return {
      shotId: `shot_${index + 1}`,
      timestamp,
      duration: timestamp,
      camera: firstString(analysis.decomposition?.visualLanguage, "旧版拆解未单独返回镜头字段。"),
      characterAction: firstString(value.content, "旧版拆解未单独返回主体动作字段。"),
      facialExpression: "旧版拆解未单独返回表情字段。",
      background: firstString(value.role, "旧版拆解未单独返回背景字段。"),
      props: [],
      voiceover: "旧版拆解未单独返回口播字段。",
      overlay: "",
      sound: firstString(analysis.decomposition?.audioLanguage, "旧版拆解未单独返回声音字段。"),
      bgm: "",
      soundEffects: [],
      subtitleLogic: "旧版拆解未单独返回字幕逻辑。",
      visualElements: [],
      visualElementLogic: "旧版拆解未单独返回画面要素逻辑。",
      transition: firstString(value.technique, "旧版拆解未单独返回转场字段。"),
      purpose: firstString(value.role, "由旧版分段拆解映射。"),
    };
  }).filter(Boolean) as ScriptStoryboardShot[];
}

function timelineItemFromObject(value: JsonObject, index: number): TimelineItem {
  const title = firstString(value.role, value.viewerJob, value.title, value.stepNo ? `步骤 ${value.stepNo}` : "", `片段 ${index + 1}`);
  const content = firstString(value.observedContent, value.content, value.summary, "未提供内容说明");
  const technique = firstString(value.executionNotes, value.technique, value.reusableMove, "");
  const role = firstString(value.viewerJob, value.role, value.performanceFunction, "");
  return {
    id: `${index}-${title}-${content}`,
    title,
    time: timeLabel(value, index),
    role,
    content,
    technique,
  };
}

function timeLabel(value: JsonObject, index: number): string {
  const explicit = firstString(value.timeRange);
  if (explicit) return explicit;
  const start = numberFrom(value.startSecond);
  const end = numberFrom(value.endSecond);
  if (start !== null && end !== null) return `${start}s-${end}s`;
  if (start !== null) return `${start}s`;
  return value.segmentNo || value.stepNo ? `#${value.segmentNo || value.stepNo}` : `#${index + 1}`;
}

function renderStructuredInline(value: JsonValue | undefined): ReactNode {
  if (!hasRenderableValue(value)) return <span className="muted-text">未提供</span>;
  if (Array.isArray(value) || (typeof value === "object" && value !== null)) return <StructuredValue value={value} compact />;
  return renderPrimitive(value);
}

function renderPrimitive(value: JsonValue | undefined): string {
  if (typeof value === "boolean") return value ? "是" : "否";
  if (typeof value === "number") return Number.isInteger(value) ? String(value) : value.toFixed(2);
  if (typeof value === "string") return value;
  if (value === null || value === undefined) return "未提供";
  return "";
}

function scriptRecordToFactoryPayload(record: ScriptRecord): ScriptGenerationPayload {
  return {
    id: record.id,
    title: factoryScriptTitle(record),
    persona: [
      textValue(record.script.targetAudience, textValue(record.topicPlan.targetAudience, "")),
      textValue(record.script.persona, textValue(record.topicPlan.persona, "")),
    ].filter(Boolean).join(" / ") || "未指定人设",
    creativeTypes: [
      textValue(record.topicPlan.template, textValue(record.script.template, "")),
      ...record.sourceComponentSummary.map(value => stringFrom(value)).filter((value): value is string => Boolean(value)),
    ].filter(Boolean).slice(0, 3),
    tags: [
      textValue(record.script.corePain, ""),
      textValue(record.script.emotionalAngle, ""),
      textValue(record.topicPlan.recommendedPlatform, ""),
    ].filter(Boolean),
  };
}

function factoryScriptTitle(record: ScriptRecord): string {
  return textValue(record.script.scriptTitle, textValue(record.topicPlan.title, "未命名脚本"));
}

function isRunningDirectorGenerationJob(job: DirectorGenerationJobRecord | null | undefined): boolean {
  return job?.status === "queued" || job?.status === "generating";
}

function isRunningDirectorRenderJob(job: DirectorRenderJobRecord | null | undefined): boolean {
  return job?.status === "queued" || job?.status === "rendering";
}

function directorGenerationJobStatusLabel(status: string): string {
  if (status === "queued") return "排队中";
  if (status === "generating") return "生成中";
  if (status === "succeeded") return "已完成";
  if (status === "failed") return "失败";
  if (status === "canceled") return "已取消";
  return status;
}

function readWorkspaceActiveTab(): WorkspaceTab {
  try {
    const storedTab = window.localStorage.getItem(workspaceActiveTabStorageKey);
    if (storedTab === "teardown" || storedTab === "scripts" || storedTab === "factory") return storedTab;
    if (window.localStorage.getItem(factoryActiveScriptStorageKey)) return "factory";
  } catch {
    // Non-browser test environments can disable localStorage.
  }
  return "teardown";
}

function storeWorkspaceActiveTab(tab: WorkspaceTab) {
  try {
    window.localStorage.setItem(workspaceActiveTabStorageKey, tab);
  } catch {
    // Non-browser test environments can disable localStorage.
  }
}

function readFactoryActiveScriptId(): string {
  try {
    return window.localStorage.getItem(factoryActiveScriptStorageKey) || "";
  } catch {
    return "";
  }
}

function storeFactoryActiveScriptId(scriptId: string) {
  try {
    window.localStorage.setItem(factoryActiveScriptStorageKey, scriptId);
  } catch {
    // Non-browser test environments can disable localStorage.
  }
}

function firstString(...values: Array<JsonValue | undefined | null>): string {
  for (const value of values) {
    if (typeof value === "string" && value.trim()) return value;
    if (typeof value === "number") return String(value);
  }
  return "";
}

function textValue(value: JsonValue | undefined | null, fallback = ""): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number") return String(value);
  return fallback;
}

function numberValue(value: JsonValue | undefined | null, fallback = 0): number {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim() && Number.isFinite(Number(value))) return Number(value);
  return fallback;
}

function objectValue(value: JsonValue | undefined | null): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function arrayObjects(value: JsonValue | undefined | null): JsonObject[] {
  return Array.isArray(value) ? value.filter((item): item is JsonObject => Boolean(item && typeof item === "object" && !Array.isArray(item))) : [];
}

function stringFrom(value: JsonValue | undefined): string | undefined {
  return typeof value === "string" || typeof value === "number" ? String(value) : undefined;
}

function numberFrom(value: JsonValue | undefined): number | null {
  return typeof value === "number" ? value : null;
}

function toObject(value: JsonValue | undefined | null): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function asArray(value: JsonValue | undefined | null): JsonValue[] {
  return Array.isArray(value) ? value : [];
}

function valueList(value: JsonValue | undefined | null): JsonValue[] {
  return hasRenderableValue(value) ? [value] : [];
}

function omitKeys(value: JsonObject | null | undefined, keys: Set<string>): JsonObject {
  if (!value) return {};
  return Object.fromEntries(Object.entries(value).filter(([key, child]) => !keys.has(key) && hasRenderableValue(child))) as JsonObject;
}

function hasRenderableValue(value: JsonValue | undefined): value is JsonValue {
  if (value === undefined || value === null) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.some(hasRenderableValue);
  if (typeof value === "object") return Object.values(value).some(hasRenderableValue);
  return true;
}

function fieldLabel(key: string): string {
  return fieldLabels[key] || key;
}

function formatDate(value: string): string {
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : date.toLocaleString("zh-CN");
}

function formatDuration(value: number | null | undefined): string {
  if (typeof value !== "number" || Number.isNaN(value)) return "";
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return minutes > 0 ? `${minutes}分${seconds.toString().padStart(2, "0")}秒` : `${seconds}秒`;
}

function assetUrl(value: string): string {
  if (/^https?:\/\//i.test(value)) return value;
  if (value.startsWith("/")) return `${API_BASE}${value}`;
  return value;
}

function getPlayableVideoSrc(sourceVideo: SourceVideo | null): string {
  const candidate = firstString(sourceVideo?.importedVideoUrl, sourceVideo?.sourceUrl);
  if (!candidate) return "";
  const isLikelyVideo = candidate.startsWith("/uploads/") || /\.(mp4|mov|webm|m4v)(\?|#|$)/i.test(candidate);
  return isLikelyVideo ? assetUrl(candidate) : "";
}

function isSupportedVideoUrl(value: string): boolean {
  if (value.startsWith("/uploads/")) return true;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:";
  } catch {
    return false;
  }
}
