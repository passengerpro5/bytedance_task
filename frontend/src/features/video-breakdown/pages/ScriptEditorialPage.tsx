import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import {
  AlertCircle,
  Bot,
  ChevronDown,
  Check,
  Clock3,
  Copy,
  FileText,
  Film,
  Layers3,
  Loader2,
  RotateCcw,
  Send,
  Trash2,
  UserRound,
  Video,
  WandSparkles,
  X,
} from "lucide-react";
import { videoBreakdownClient } from "../api/videoBreakdownClient";
import { CreatorPersona, CreatorPersonaRecord, JsonObject, JsonValue, PersonaGenerationJobRecord, ProductionAssetPlanEntry, ScriptGenerationJobRecord, ScriptRecord, ScriptStoryboardShot } from "../types";
import "./ScriptEditorialPage.css";

export type ScriptGenerationPayload = {
  id: string;
  title: string;
  persona: string;
  creativeTypes: string[];
  tags: string[];
};

export type ScriptGenerationIntent = {
  id: string;
  assetTitle: string;
  scriptType: string;
  sourceBreakdownIds: string[];
};

type ScriptEditorialPageProps = {
  generationIntent?: ScriptGenerationIntent | null;
  onGenerationIntentHandled?: (intentId: string) => void;
  onStartVideoGeneration?: (payload: ScriptGenerationPayload) => void;
};

type ScriptLanguage = "en" | "zh";
type SidebarTab = "scripts" | "personas";
type PendingGenerationStatus = "queued" | "generating" | "failed";
type PendingGenerationCard = {
  id: string;
  jobId: string;
  kind: "script" | "persona";
  title: string;
  index: number;
  total: number;
  status: PendingGenerationStatus;
  progress: number;
  scriptType: string;
  errorMessage?: string;
};
type PersonaCard = {
  id: string;
  recordId: string;
  personaId: string;
  label: string;
  personaType: string;
  role: string;
  summary: string;
  tags: string[];
  qualityScore: number | null;
  audienceCallout: string;
  roleTask: string;
  creatorPersona: CreatorPersona;
};

const scriptCountOptions = [1, 2, 3, 5, 8, 10];
const personaCountOptions = [1, 2, 3, 5, 8, 10];
const scriptTypeOptions = [
  "全部",
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
];

export function ScriptEditorialPage({
  generationIntent = null,
  onGenerationIntentHandled,
  onStartVideoGeneration,
}: ScriptEditorialPageProps = {}) {
  const [scripts, setScripts] = useState<ScriptRecord[]>([]);
  const [creatorPersonaRecords, setCreatorPersonaRecords] = useState<CreatorPersonaRecord[]>([]);
  const [sidebarTab, setSidebarTab] = useState<SidebarTab>("scripts");
  const [selectedScriptId, setSelectedScriptId] = useState("");
  const [selectedPersonaCardId, setSelectedPersonaCardId] = useState("");
  const [generationPersonaCardId, setGenerationPersonaCardId] = useState("");
  const [scriptCount, setScriptCount] = useState(3);
  const [personaCount, setPersonaCount] = useState(3);
  const [scriptType, setScriptType] = useState("全部");
  const [isLoading, setIsLoading] = useState(true);
  const [isCreatingGenerationJob, setIsCreatingGenerationJob] = useState(false);
  const [isCreatingPersonaGenerationJob, setIsCreatingPersonaGenerationJob] = useState(false);
  const [editingPersonaCardId, setEditingPersonaCardId] = useState<string | null>(null);
  const [personaEditInstruction, setPersonaEditInstruction] = useState("");
  const [generationJobs, setGenerationJobs] = useState<ScriptGenerationJobRecord[]>([]);
  const [personaGenerationJobs, setPersonaGenerationJobs] = useState<PersonaGenerationJobRecord[]>([]);
  const [deletingGenerationJobIds, setDeletingGenerationJobIds] = useState<Set<string>>(() => new Set());
  const [deletingPersonaGenerationJobIds, setDeletingPersonaGenerationJobIds] = useState<Set<string>>(() => new Set());
  const [retryingGenerationJobIds, setRetryingGenerationJobIds] = useState<Set<string>>(() => new Set());
  const [retryingPersonaGenerationJobIds, setRetryingPersonaGenerationJobIds] = useState<Set<string>>(() => new Set());
  const [error, setError] = useState("");
  const [unreadScriptIds, setUnreadScriptIds] = useState<Set<string>>(() => new Set());
  const [editingProgress, setEditingProgress] = useState<Record<string, number>>({});
  const [videoConfirmScriptId, setVideoConfirmScriptId] = useState<string | null>(null);
  const [deleteConfirmScriptId, setDeleteConfirmScriptId] = useState<string | null>(null);
  const [editingScriptId, setEditingScriptId] = useState<string | null>(null);
  const [editInstruction, setEditInstruction] = useState("");
  const [scriptLanguage, setScriptLanguage] = useState<ScriptLanguage>("en");
  const [copiedPromptKey, setCopiedPromptKey] = useState("");
  const handledGenerationIntentIds = useRef<Set<string>>(new Set());

  useEffect(() => {
    void loadScripts();
  }, []);

  const visibleScripts = useMemo(() => collapseDuplicateScripts(scripts), [scripts]);
  const selectedScript = useMemo(
    () => visibleScripts.find(script => script.id === selectedScriptId) ?? visibleScripts[0] ?? null,
    [visibleScripts, selectedScriptId],
  );
  const personaCards = useMemo(
    () => buildPersonaCards(creatorPersonaRecords, scriptLanguage),
    [creatorPersonaRecords, scriptLanguage],
  );
  const selectedPersonaCard = useMemo(
    () => personaCards.find(persona => persona.id === selectedPersonaCardId) ?? personaCards[0] ?? null,
    [personaCards, selectedPersonaCardId],
  );
  const selectedGenerationPersona = useMemo(
    () => personaCards.find(persona => persona.id === generationPersonaCardId) ?? null,
    [personaCards, generationPersonaCardId],
  );

  const activeGenerationJobIds = useMemo(
    () => generationJobs.filter(isActiveGenerationJob).map(job => job.id),
    [generationJobs],
  );
  const activeGenerationJobKey = activeGenerationJobIds.join("|");
  const isGenerationLocked = isCreatingGenerationJob || activeGenerationJobIds.length > 0;
  const generationCards = useMemo(
    () => generationJobs.flatMap(buildPendingGenerationCards),
    [generationJobs],
  );
  const activePersonaGenerationJobIds = useMemo(
    () => personaGenerationJobs.filter(isActivePersonaGenerationJob).map(job => job.id),
    [personaGenerationJobs],
  );
  const activePersonaGenerationJobKey = activePersonaGenerationJobIds.join("|");
  const isPersonaGenerationLocked = isCreatingPersonaGenerationJob || activePersonaGenerationJobIds.length > 0;
  const personaGenerationCards = useMemo(
    () => personaGenerationJobs.flatMap(buildPendingPersonaGenerationCards),
    [personaGenerationJobs],
  );

  useEffect(() => {
    if (!generationIntent || isLoading || handledGenerationIntentIds.current.has(generationIntent.id)) return;
    handledGenerationIntentIds.current.add(generationIntent.id);
    void handleGenerateScriptsFromIntent(generationIntent);
  }, [generationIntent, isLoading]);

  useEffect(() => {
    if (!selectedPersonaCardId) {
      if (personaCards[0]) setSelectedPersonaCardId(personaCards[0].id);
      return;
    }
    if (personaCards.some(persona => persona.id === selectedPersonaCardId)) return;
    setSelectedPersonaCardId(personaCards[0]?.id ?? "");
  }, [personaCards, selectedPersonaCardId]);

  useEffect(() => {
    if (!generationPersonaCardId) {
      if (personaCards[0]) setGenerationPersonaCardId(personaCards[0].id);
      return;
    }
    if (!generationPersonaCardId || personaCards.some(persona => persona.id === generationPersonaCardId)) return;
    setGenerationPersonaCardId("");
  }, [generationPersonaCardId, personaCards]);

  useEffect(() => {
    if (!activeGenerationJobKey) return undefined;

    let isDisposed = false;
    const refreshActiveJobs = async () => {
      try {
        const updatedJobs = await Promise.all(
          activeGenerationJobIds.map(jobId => videoBreakdownClient.getScriptGenerationJob(jobId)),
        );
        if (isDisposed) return;
        const hasScriptProgress = updatedJobs.some(job => job.status === "succeeded" || scriptGenerationCompletedCount(job) > 0);
        setGenerationJobs(previous => mergeGenerationJobs(previous, updatedJobs).filter(job => job.status !== "succeeded"));
        if (hasScriptProgress) {
          await refreshScriptsOnly();
        }
      } catch (err) {
        if (!isDisposed) {
          setError(err instanceof Error ? err.message : "脚本生成状态刷新失败。");
        }
      }
    };

    void refreshActiveJobs();
    const timer = window.setInterval(() => void refreshActiveJobs(), 2000);
    return () => {
      isDisposed = true;
      window.clearInterval(timer);
    };
  }, [activeGenerationJobKey]);

  useEffect(() => {
    if (!activePersonaGenerationJobKey) return undefined;

    let isDisposed = false;
    const refreshActivePersonaJobs = async () => {
      try {
        const updatedJobs = await Promise.all(
          activePersonaGenerationJobIds.map(jobId => videoBreakdownClient.getPersonaGenerationJob(jobId)),
        );
        if (isDisposed) return;
        const hasProgress = updatedJobs.some(job => job.completedCount > 0 || job.status === "succeeded");
        setPersonaGenerationJobs(previous => mergePersonaGenerationJobs(previous, updatedJobs).filter(job => job.status !== "succeeded"));
        if (hasProgress) {
          await refreshCreatorPersonasOnly();
        }
      } catch (err) {
        if (!isDisposed) {
          setError(err instanceof Error ? err.message : "人设生成状态刷新失败。");
        }
      }
    };

    void refreshActivePersonaJobs();
    const timer = window.setInterval(() => void refreshActivePersonaJobs(), 2000);
    return () => {
      isDisposed = true;
      window.clearInterval(timer);
    };
  }, [activePersonaGenerationJobKey]);

  async function loadScripts() {
    setIsLoading(true);
    setError("");
    try {
      const [records, jobs, personas, personaJobs] = await Promise.all([
        videoBreakdownClient.listScripts(),
        videoBreakdownClient.listScriptGenerationJobs(),
        videoBreakdownClient.listCreatorPersonas(),
        videoBreakdownClient.listPersonaGenerationJobs(),
      ]);
      setScripts(records);
      setGenerationJobs(jobs.filter(job => job.status !== "succeeded"));
      setCreatorPersonaRecords(personas);
      setPersonaGenerationJobs(personaJobs.filter(job => job.status !== "succeeded"));
      setSelectedScriptId(current => current || records[0]?.id || "");
    } catch (err) {
      setError(err instanceof Error ? err.message : "脚本加载失败。");
    } finally {
      setIsLoading(false);
    }
  }

  async function refreshScriptsOnly() {
    const records = await videoBreakdownClient.listScripts();
    setScripts(records);
    setSelectedScriptId(current => current || records[0]?.id || "");
  }

  async function refreshCreatorPersonasOnly() {
    const personas = await videoBreakdownClient.listCreatorPersonas();
    setCreatorPersonaRecords(personas);
  }

  const handleSelectScript = (scriptId: string) => {
    setSelectedScriptId(scriptId);
    setUnreadScriptIds(previous => {
      const next = new Set(previous);
      next.delete(scriptId);
      return next;
    });
  };

  const handleGenerateScripts = async () => {
    if (isGenerationLocked) return;
    const requestedCount = scriptCount;
    const requestedType = normalizeScriptType(scriptType);
    const selectedPersona = selectedGenerationPersona;
    if (!selectedPersona) {
      setSidebarTab("personas");
      setError("请先生成 Persona 资产并选择一个，再生成脚本。");
      return;
    }
    const payload: {
      scriptCount: number;
      scriptType: string;
      personaId?: string;
      personaHint?: JsonObject;
    } = {
      scriptCount: requestedCount,
      scriptType: requestedType,
      personaId: selectedPersona.recordId,
      personaHint: creatorPersonaHint(selectedPersona.creatorPersona),
    };
    setIsCreatingGenerationJob(true);
    setError("");
    try {
      const job = await videoBreakdownClient.createScriptGenerationJob(payload);
      setGenerationJobs(previous => mergeGenerationJobs(previous, [job]).filter(item => item.status !== "succeeded"));
    } catch (err) {
      const message = err instanceof Error ? err.message : "脚本生成失败。";
      setError(message);
    } finally {
      setIsCreatingGenerationJob(false);
    }
  };

  const handleGenerateScriptsFromPersona = async (persona: PersonaCard) => {
    if (isGenerationLocked) return;
    setSelectedPersonaCardId(persona.id);
    setGenerationPersonaCardId(persona.id);
    setSidebarTab("scripts");
    const payload = {
      scriptCount,
      scriptType: normalizeScriptType(scriptType),
      personaId: persona.recordId,
      personaHint: creatorPersonaHint(persona.creatorPersona),
    };
    setIsCreatingGenerationJob(true);
    setError("");
    try {
      const job = await videoBreakdownClient.createScriptGenerationJob(payload);
      setGenerationJobs(previous => mergeGenerationJobs(previous, [job]).filter(item => item.status !== "succeeded"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "脚本生成失败。");
    } finally {
      setIsCreatingGenerationJob(false);
    }
  };

  const handleGenerateScriptsFromIntent = async (intent: ScriptGenerationIntent) => {
    if (isGenerationLocked) {
      setError("已有脚本生成任务正在运行，完成后再从创意仓库生成。");
      onGenerationIntentHandled?.(intent.id);
      return;
    }
    const persona = selectedGenerationPersona ?? personaCards[0] ?? null;
    if (!persona) {
      setSidebarTab("personas");
      setError(`请先生成 Persona 资产并选择一个，再用「${intent.assetTitle}」生成脚本。`);
      onGenerationIntentHandled?.(intent.id);
      return;
    }

    setSidebarTab("scripts");
    setSelectedPersonaCardId(persona.id);
    setGenerationPersonaCardId(persona.id);
    setScriptType(intent.scriptType);
    const payload = {
      scriptCount,
      scriptType: normalizeScriptType(intent.scriptType),
      sourceBreakdownIds: intent.sourceBreakdownIds,
      personaId: persona.recordId,
      personaHint: creatorPersonaHint(persona.creatorPersona),
    };
    setIsCreatingGenerationJob(true);
    setError("");
    try {
      const job = await videoBreakdownClient.createScriptGenerationJob(payload);
      setGenerationJobs(previous => mergeGenerationJobs(previous, [job]).filter(item => item.status !== "succeeded"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "脚本生成失败。");
    } finally {
      setIsCreatingGenerationJob(false);
      onGenerationIntentHandled?.(intent.id);
    }
  };

  const handleGeneratePersonas = async () => {
    if (isPersonaGenerationLocked) return;
    setIsCreatingPersonaGenerationJob(true);
    setError("");
    try {
      const job = await videoBreakdownClient.createPersonaGenerationJob({ personaCount });
      setPersonaGenerationJobs(previous => mergePersonaGenerationJobs(previous, [job]).filter(item => item.status !== "succeeded"));
      setSidebarTab("personas");
    } catch (err) {
      setError(err instanceof Error ? err.message : "人设生成失败。");
    } finally {
      setIsCreatingPersonaGenerationJob(false);
    }
  };

  const requestDeleteScript = (scriptId: string) => {
    setDeleteConfirmScriptId(scriptId);
  };

  const copyPrompt = async (key: string, text: string) => {
    const value = text.trim();
    if (!value) return;
    try {
      await copyTextToClipboard(value);
      setCopiedPromptKey(key);
      window.setTimeout(() => {
        setCopiedPromptKey(previous => (previous === key ? "" : previous));
      }, 1400);
    } catch (err) {
      setError(err instanceof Error ? err.message : "复制提示词失败。");
    }
  };

  const handleDeleteGenerationJob = async (jobId: string) => {
    setDeletingGenerationJobIds(previous => new Set(previous).add(jobId));
    setError("");
    try {
      await videoBreakdownClient.deleteScriptGenerationJob(jobId);
      setGenerationJobs(previous => previous.filter(job => job.id !== jobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "失败任务删除失败。");
    } finally {
      setDeletingGenerationJobIds(previous => {
        const next = new Set(previous);
        next.delete(jobId);
        return next;
      });
    }
  };

  const handleRetryGenerationJob = async (jobId: string) => {
    if (isGenerationLocked) return;
    setRetryingGenerationJobIds(previous => new Set(previous).add(jobId));
    setError("");
    try {
      const retryJob = await videoBreakdownClient.retryScriptGenerationJob(jobId);
      setGenerationJobs(previous => mergeGenerationJobs(previous.filter(job => job.id !== jobId), [retryJob]).filter(job => job.status !== "succeeded"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "脚本任务重试失败。");
    } finally {
      setRetryingGenerationJobIds(previous => {
        const next = new Set(previous);
        next.delete(jobId);
        return next;
      });
    }
  };

  const handleDeletePersonaGenerationJob = async (jobId: string) => {
    setDeletingPersonaGenerationJobIds(previous => new Set(previous).add(jobId));
    setError("");
    try {
      await videoBreakdownClient.deletePersonaGenerationJob(jobId);
      setPersonaGenerationJobs(previous => previous.filter(job => job.id !== jobId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "失败人设任务删除失败。");
    } finally {
      setDeletingPersonaGenerationJobIds(previous => {
        const next = new Set(previous);
        next.delete(jobId);
        return next;
      });
    }
  };

  const handleRetryPersonaGenerationJob = async (jobId: string) => {
    if (isPersonaGenerationLocked) return;
    setRetryingPersonaGenerationJobIds(previous => new Set(previous).add(jobId));
    setError("");
    try {
      const retryJob = await videoBreakdownClient.retryPersonaGenerationJob(jobId);
      setPersonaGenerationJobs(previous => mergePersonaGenerationJobs(previous.filter(job => job.id !== jobId), [retryJob]).filter(job => job.status !== "succeeded"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "人设任务重试失败。");
    } finally {
      setRetryingPersonaGenerationJobIds(previous => {
        const next = new Set(previous);
        next.delete(jobId);
        return next;
      });
    }
  };

  const handleDeletePersona = async (persona: PersonaCard) => {
    setError("");
    try {
      await videoBreakdownClient.deleteCreatorPersona(persona.recordId);
      setCreatorPersonaRecords(previous => previous.filter(record => record.id !== persona.recordId));
      setSelectedPersonaCardId(current => (current === persona.id ? "" : current));
      setGenerationPersonaCardId(current => (current === persona.id ? "" : current));
    } catch (err) {
      setError(err instanceof Error ? err.message : "人设删除失败。");
    }
  };

  const handleSubmitPersonaEdit = async () => {
    const target = personaCards.find(persona => persona.id === editingPersonaCardId);
    const instruction = personaEditInstruction.trim();
    if (!target || !instruction) return;
    setEditingPersonaCardId(null);
    setPersonaEditInstruction("");
    setError("");
    try {
      const updated = await videoBreakdownClient.editCreatorPersona(target.recordId, instruction);
      setCreatorPersonaRecords(previous => previous.map(record => (record.id === updated.id ? updated : record)));
      setSelectedPersonaCardId(updated.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "人设编辑失败。");
    }
  };

  const performDeleteScript = async (scriptId: string) => {
    try {
      await videoBreakdownClient.deleteScript(scriptId);
      setScripts(previous => {
        const next = previous.filter(script => script.id !== scriptId);
        if (selectedScriptId === scriptId) {
          setSelectedScriptId(next[0]?.id ?? "");
        }
        return next;
      });
      setUnreadScriptIds(previous => {
        const next = new Set(previous);
        next.delete(scriptId);
        return next;
      });
    } catch (err) {
      setError(err instanceof Error ? err.message : "脚本删除失败。");
    } finally {
      setDeleteConfirmScriptId(null);
    }
  };

  const handleConfirmVideoGeneration = () => {
    const script = scripts.find(item => item.id === videoConfirmScriptId);
    if (!script) return;
    setVideoConfirmScriptId(null);
    onStartVideoGeneration?.({
      id: script.id,
      title: scriptTitle(script, "en"),
      persona: scriptPersona(script, "en"),
      creativeTypes: scriptCreativeTypes(script, "en"),
      tags: scriptTags(script, "en"),
    });
  };

  const handleSubmitAiEdit = async () => {
    const targetId = editingScriptId;
    const instruction = editInstruction.trim();
    if (!targetId || !instruction) return;

    setEditingScriptId(null);
    setEditInstruction("");
    setEditingProgress(previous => ({ ...previous, [targetId]: 28 }));
    setScripts(previous => previous.map(script => (
      script.id === targetId ? { ...script, status: "editing" } : script
    )));

    const progressTimer = window.setInterval(() => {
      setEditingProgress(previous => {
        const current = previous[targetId] ?? 28;
        return { ...previous, [targetId]: Math.min(88, current + 16) };
      });
    }, 700);

    try {
      const updated = await videoBreakdownClient.editScript(targetId, instruction);
      window.clearInterval(progressTimer);
      setScripts(previous => previous.map(script => (script.id === targetId ? updated : script)));
      setEditingProgress(previous => {
        const next = { ...previous };
        delete next[targetId];
        return next;
      });
      if (targetId !== selectedScriptId) {
        setUnreadScriptIds(previous => new Set(previous).add(targetId));
      }
    } catch (err) {
      window.clearInterval(progressTimer);
      setError(err instanceof Error ? err.message : "脚本修改失败。");
      setScripts(previous => previous.map(script => (
        script.id === targetId ? { ...script, status: "failed", errorMessage: "脚本修改失败。" } : script
      )));
      setEditingProgress(previous => {
        const next = { ...previous };
        delete next[targetId];
        return next;
      });
    }
  };

  const videoConfirmScript = scripts.find(script => script.id === videoConfirmScriptId) ?? null;
  const deleteConfirmScript = scripts.find(script => script.id === deleteConfirmScriptId) ?? null;
  const editingScript = scripts.find(script => script.id === editingScriptId) ?? null;
  const editingPersona = personaCards.find(persona => persona.id === editingPersonaCardId) ?? null;

  return (
    <section className="script-editorial-page" aria-label="脚本编辑部">
      <aside className="script-editorial-sidebar" aria-label="脚本列表">
        <div className="script-editorial-sidebar-tabs" role="tablist" aria-label="脚本编辑部内容">
          <button
            type="button"
            role="tab"
            aria-selected={sidebarTab === "scripts"}
            className={sidebarTab === "scripts" ? "script-editorial-sidebar-tab script-editorial-sidebar-tab--active" : "script-editorial-sidebar-tab"}
            onClick={() => setSidebarTab("scripts")}
          >
            <FileText size={17} aria-hidden="true" />
            脚本
          </button>
          <button
            type="button"
            role="tab"
            aria-selected={sidebarTab === "personas"}
            className={sidebarTab === "personas" ? "script-editorial-sidebar-tab script-editorial-sidebar-tab--active" : "script-editorial-sidebar-tab"}
            onClick={() => setSidebarTab("personas")}
          >
            <UserRound size={17} aria-hidden="true" />
            人设
          </button>
        </div>

        <div className={`script-editorial-sidebar-content script-editorial-sidebar-content--${sidebarTab}`}>
          {sidebarTab === "scripts" ? (
            <>
              <div className="script-generation-panel" aria-label="脚本生成配置">
                <button
                  type="button"
                  className="script-generation-button"
                  onClick={handleGenerateScripts}
                  disabled={isGenerationLocked || !selectedGenerationPersona}
                >
                  {isGenerationLocked ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Bot size={16} aria-hidden="true" />}
                  {isGenerationLocked ? "生成中" : selectedGenerationPersona ? "生成脚本" : "先选择人设"}
                </button>
                <label className="script-generation-select">
                  <span>数量</span>
                  <select aria-label="数量" value={scriptCount} onChange={event => setScriptCount(Number(event.target.value))} disabled={isGenerationLocked}>
                    {scriptCountOptions.map(value => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                  <ChevronDown size={15} aria-hidden="true" />
                </label>
                <label className="script-generation-select script-generation-select--wide">
                  <span>类型</span>
                  <select aria-label="类型" value={scriptType} onChange={event => setScriptType(event.target.value)} disabled={isGenerationLocked}>
                    {scriptTypeOptions.map(value => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                  <ChevronDown size={15} aria-hidden="true" />
                </label>
                <label className="script-generation-select script-generation-select--wide">
                  <span>人设</span>
                  <select
                    aria-label="人设"
                    value={generationPersonaCardId || ""}
                    onChange={event => setGenerationPersonaCardId(event.target.value)}
                    disabled={isGenerationLocked || personaCards.length === 0}
                  >
                    <option value="">先选择人设</option>
                    {personaCards.map(persona => (
                      <option key={persona.id} value={persona.id}>{persona.label}</option>
                    ))}
                  </select>
                  <ChevronDown size={15} aria-hidden="true" />
                </label>
              </div>

              <div className="script-editorial-list" aria-label="脚本卡片列表">
                {error && <div className="script-editorial-empty" role="alert">{error}</div>}
                {isLoading && <div className="script-editorial-empty">脚本加载中...</div>}
                {!isLoading && visibleScripts.length === 0 && generationCards.length === 0 && (
                  <div className="script-editorial-empty">暂无脚本，先在人设页生成并选择人设。</div>
                )}

                {generationCards.map(card => (
                  <PendingGenerationCardView
                    key={card.id}
                    card={card}
                    isDeleting={deletingGenerationJobIds.has(card.jobId)}
                    isRetrying={retryingGenerationJobIds.has(card.jobId)}
                    onDelete={card.status === "failed" ? () => void handleDeleteGenerationJob(card.jobId) : undefined}
                    onRetry={card.status === "failed" ? () => void handleRetryGenerationJob(card.jobId) : undefined}
                  />
                ))}

                {visibleScripts.map(script => {
                  const progress = editingProgress[script.id];
                  const isEditing = script.status === "editing" || typeof progress === "number";
                  return (
                    <article
                      key={script.id}
                      className={[
                        "script-editorial-card",
                        selectedScript && script.id === selectedScript.id ? "script-editorial-card--active" : "",
                        unreadScriptIds.has(script.id) ? "script-editorial-card--unread" : "",
                        isEditing ? "script-editorial-card--editing" : "",
                      ].filter(Boolean).join(" ")}
                    >
                      <button
                        type="button"
                        className="script-editorial-card__select"
                        onClick={() => handleSelectScript(script.id)}
                        aria-pressed={selectedScript ? script.id === selectedScript.id : false}
                        aria-label={`${scriptTitle(script, scriptLanguage)}${unreadScriptIds.has(script.id) ? "，未读" : ""}`}
                      >
                        <div className="script-editorial-card__title-row">
                          <h3>{scriptTitle(script, scriptLanguage)}</h3>
                        </div>
                        <TagRow values={scriptCreativeTypes(script, scriptLanguage)} />
                        {isEditing ? (
                          <ProgressInline label="等待修改" progress={progress ?? 36} />
                        ) : (
                          <p>{scriptPersona(script, scriptLanguage)}</p>
                        )}
                      </button>
                      <button
                        type="button"
                        className="script-editorial-card__delete"
                        aria-label={`删除脚本：${scriptTitle(script, scriptLanguage)}`}
                        onClick={() => requestDeleteScript(script.id)}
                      >
                        <Trash2 size={17} aria-hidden="true" />
                      </button>
                    </article>
                  );
                })}
              </div>
            </>
          ) : (
            <>
              <div className="script-generation-panel script-generation-panel--persona" aria-label="人设生成配置">
                <button
                  type="button"
                  className="script-generation-button"
                  onClick={handleGeneratePersonas}
                  disabled={isPersonaGenerationLocked}
                >
                  {isPersonaGenerationLocked ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <UserRound size={16} aria-hidden="true" />}
                  {isPersonaGenerationLocked ? "生成中" : "生成 Persona 资产"}
                </button>
                <label className="script-generation-select">
                  <span>数量</span>
                  <select aria-label="人设数量" value={personaCount} onChange={event => setPersonaCount(Number(event.target.value))} disabled={isPersonaGenerationLocked}>
                    {personaCountOptions.map(value => (
                      <option key={value} value={value}>{value}</option>
                    ))}
                  </select>
                  <ChevronDown size={15} aria-hidden="true" />
                </label>
              </div>

              <div className="script-editorial-persona-list" aria-label="人设卡片列表">
                {error && <div className="script-editorial-empty" role="alert">{error}</div>}
                {isLoading && <div className="script-editorial-empty">人设加载中...</div>}
                {!isLoading && personaCards.length === 0 && personaGenerationCards.length === 0 && (
                  <div className="script-editorial-empty">暂无 Persona 资产，先点击生成。</div>
                )}
                {personaGenerationCards.map(card => (
                  <PendingGenerationCardView
                    key={card.id}
                    card={card}
                    isDeleting={deletingPersonaGenerationJobIds.has(card.jobId)}
                    isRetrying={retryingPersonaGenerationJobIds.has(card.jobId)}
                    onDelete={card.status === "failed" ? () => void handleDeletePersonaGenerationJob(card.jobId) : undefined}
                    onRetry={card.status === "failed" ? () => void handleRetryPersonaGenerationJob(card.jobId) : undefined}
                  />
                ))}
                {personaCards.map(persona => (
                  <PersonaCardView
                    key={persona.id}
                    persona={persona}
                    isActive={selectedPersonaCard?.id === persona.id}
                    onSelect={() => setSelectedPersonaCardId(persona.id)}
                  />
                ))}
              </div>
            </>
          )}
        </div>
      </aside>

      {sidebarTab === "personas" ? (
        selectedPersonaCard ? (
          <article className="script-editorial-detail">
            <header className="script-editorial-detail__header">
              <div className="script-editorial-title-row">
                <div className="script-editorial-title-with-toggle">
                  <h2>{selectedPersonaCard.label}</h2>
                  <LanguageToggle value={scriptLanguage} onChange={setScriptLanguage} ariaLabel="人设详情语言" />
                </div>
                <div className="script-editorial-actions" aria-label="人设操作">
                  <button
                    type="button"
                    className="script-editorial-action script-editorial-action--primary"
                    onClick={() => void handleGenerateScriptsFromPersona(selectedPersonaCard)}
                    disabled={isGenerationLocked}
                  >
                    {isGenerationLocked ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <Bot size={16} aria-hidden="true" />}
                    生成脚本
                  </button>
                  <button
                    type="button"
                    className="script-editorial-action"
                    onClick={() => {
                      setEditingPersonaCardId(selectedPersonaCard.id);
                      setPersonaEditInstruction("");
                    }}
                  >
                    <WandSparkles size={16} aria-hidden="true" />
                    AI 编辑
                  </button>
                  <button
                    type="button"
                    className="script-editorial-action script-editorial-action--danger"
                    onClick={() => void handleDeletePersona(selectedPersonaCard)}
                  >
                    <Trash2 size={16} aria-hidden="true" />
                    删除
                  </button>
                </div>
              </div>
              <div className="script-editorial-metric-row">
                <span className="script-editorial-persona">
                  <UserRound size={15} aria-hidden="true" />
                  <span className="script-editorial-persona__text">{selectedPersonaCard.role || "Reusable creator persona"}</span>
                </span>
              </div>
              <TagRow values={selectedPersonaCard.tags} />
            </header>

            <section className="script-editorial-section" aria-labelledby="script-editorial-persona-library-title">
              <h3 id="script-editorial-persona-library-title">
                <UserRound size={18} aria-hidden="true" />
                {uiText(scriptLanguage, "Creator Persona", "创作者人设")}
              </h3>
              <CreatorPersonaPanel
                persona={selectedPersonaCard.creatorPersona}
                fallbackPersona={selectedPersonaCard.role}
                language={scriptLanguage}
                copyKey={`persona-${selectedPersonaCard.id}-reference-image-prompt`}
                copiedPromptKey={copiedPromptKey}
                onCopyPrompt={copyPrompt}
              />
            </section>
          </article>
        ) : (
          <div className="script-editorial-empty">暂无选中的人设。</div>
        )
      ) : selectedScript ? (
        <article className="script-editorial-detail">
          <header className="script-editorial-detail__header">
            <div className="script-editorial-title-row">
              <div>
                <h2>{scriptTitle(selectedScript, scriptLanguage)}</h2>
              </div>
              <div className="script-editorial-actions" aria-label="脚本操作">
                <button
                  type="button"
                  className="script-editorial-action script-editorial-action--primary"
                  onClick={() => setVideoConfirmScriptId(selectedScript.id)}
                  disabled={selectedScript.status === "editing"}
                >
                  <Video size={16} aria-hidden="true" />
                  生成视频
                </button>
                <button
                  type="button"
                  className="script-editorial-action"
                  onClick={() => {
                    setEditingScriptId(selectedScript.id);
                    setEditInstruction("");
                  }}
                  disabled={selectedScript.status === "editing"}
                >
                  <WandSparkles size={16} aria-hidden="true" />
                  AI 编辑
                </button>
                <button
                  type="button"
                  className="script-editorial-action script-editorial-action--danger"
                  onClick={() => requestDeleteScript(selectedScript.id)}
                >
                  <Trash2 size={16} aria-hidden="true" />
                  删除
                </button>
              </div>
            </div>
            <div className="script-editorial-metric-row">
              <span className="script-editorial-persona">
                <UserRound size={15} aria-hidden="true" />
                <span className="script-editorial-persona__text">{scriptPersona(selectedScript, scriptLanguage)}</span>
              </span>
            </div>
            <TagRow values={scriptTags(selectedScript, scriptLanguage)} />
            {(selectedScript.status === "editing" || editingProgress[selectedScript.id]) && (
              <div className="script-editorial-editing-banner">
                <Loader2 className="spin" size={16} aria-hidden="true" />
                <ProgressInline label="脚本智能体正在修改" progress={editingProgress[selectedScript.id] ?? 36} />
              </div>
            )}
          </header>

          <section className="script-editorial-section" aria-labelledby="script-editorial-storyboard-title">
            <div className="script-editorial-section-heading">
              <h3 id="script-editorial-storyboard-title">
                <Film size={18} aria-hidden="true" />
                {uiText(scriptLanguage, "Storyboard", "分镜头脚本")}
              </h3>
              <LanguageToggle value={scriptLanguage} onChange={setScriptLanguage} />
            </div>
            <StoryboardTable shots={selectedScript.storyboard} language={scriptLanguage} />
          </section>

          <section className="script-editorial-section" aria-labelledby="script-editorial-persona-title">
            <h3 id="script-editorial-persona-title">
              <UserRound size={18} aria-hidden="true" />
              {uiText(scriptLanguage, "Creator Persona", "创作者人设")}
            </h3>
            <CreatorPersonaPanel
              persona={selectedScript.creatorPersona}
              fallbackPersona={selectedScript.script.persona || selectedScript.topicPlan.persona}
              language={scriptLanguage}
              copyKey={`script-${selectedScript.id}-reference-image-prompt`}
              copiedPromptKey={copiedPromptKey}
              onCopyPrompt={copyPrompt}
            />
          </section>

          <section className="script-editorial-section" aria-labelledby="script-editorial-video-prompt-title">
            <h3 id="script-editorial-video-prompt-title">
              <Video size={18} aria-hidden="true" />
              {uiText(scriptLanguage, "Video Prompts", "视频提示词")}
            </h3>
            <h4>{uiText(scriptLanguage, "Veo 3.1 Dynamic Segment Prompts", "Veo 3.1 动态分段提示词")}</h4>
            <p className="script-editorial-body-text">{veoDurationSummary(selectedScript.videoPrompt, scriptLanguage)}</p>
            <ol className="script-editorial-video-segments">
              {veoSegments(selectedScript.videoPrompt, scriptLanguage).map(segment => (
                <li key={`${selectedScript.id}-veo-${segment.segmentIndex}`} className="script-editorial-prompt-card">
                  <PromptCopyButton
                    label={uiText(scriptLanguage, `Copy video prompt segment ${segment.segmentIndex}`, `复制视频提示词分段 ${segment.segmentIndex}`)}
                    copiedLabel={uiText(scriptLanguage, `Copied video prompt segment ${segment.segmentIndex}`, `已复制视频提示词分段 ${segment.segmentIndex}`)}
                    copied={copiedPromptKey === `${selectedScript.id}-veo-${segment.segmentIndex}`}
                    onCopy={() => void copyPrompt(`${selectedScript.id}-veo-${segment.segmentIndex}`, segment.fullPrompt)}
                  />
                  <div className="script-editorial-video-segments__top">
                    <strong>{uiText(scriptLanguage, `Segment ${segment.segmentIndex}`, `分段 ${segment.segmentIndex}`)}</strong>
                    <time>{segment.durationLabel ? `${segment.timeRange} / ${segment.durationLabel}` : segment.timeRange}</time>
                  </div>
                  <p>{segment.fullPrompt}</p>
                </li>
              ))}
            </ol>
            <h4>{uiText(scriptLanguage, "Overall Generation Summary", "整体生成摘要")}</h4>
            <p className="script-editorial-body-text">{localizedField(selectedScript.videoPrompt, "generationPrompt", selectedScript.videoPrompt.generationPrompt, scriptLanguage)}</p>
            <h4>{uiText(scriptLanguage, "Character Lock", "角色锁定")}</h4>
            <p className="script-editorial-body-text">{localizedField(selectedScript.videoPrompt, "characterLock", selectedScript.videoPrompt.characterLock, scriptLanguage)}</p>
            <h4>{uiText(scriptLanguage, "Scene Lock", "场景锁定")}</h4>
            <p className="script-editorial-body-text">{localizedField(selectedScript.videoPrompt, "sceneLock", selectedScript.videoPrompt.sceneLock, scriptLanguage)}</p>
            <h4>{uiText(scriptLanguage, "Prompt Boundary", "提示词边界")}</h4>
            <p className="script-editorial-body-text">{localizedField(selectedScript.videoPrompt, "overlayExclusionNote", selectedScript.videoPrompt.overlayExclusionNote, scriptLanguage)}</p>
          </section>

          <section className="script-editorial-section" aria-labelledby="script-editorial-asset-plan-title">
            <h3 id="script-editorial-asset-plan-title">
              <Layers3 size={18} aria-hidden="true" />
              {uiText(scriptLanguage, "Asset Usage Plan", "素材应用计划")}
            </h3>
            <p className="script-editorial-body-text">
              {uiText(
                scriptLanguage,
                "Shows where real Moras assets, AI footage, avatar or live creator footage, post-production captions, and sound design are used in the final edit.",
                "标明真实 Moras 素材、AI 生成、数字人 / 真人、后期字幕与音效在最终剪辑里的使用位置。",
              )}
            </p>
            <ol className="script-editorial-asset-plan">
              {scriptProductionAssetPlan(selectedScript).map(entry => (
                <ProductionAssetPlanView key={entry.planId ?? JSON.stringify(entry)} entry={entry} language={scriptLanguage} />
              ))}
            </ol>
          </section>
        </article>
      ) : (
        <div className="script-editorial-empty">暂无选中的脚本。</div>
      )}

      {videoConfirmScript && (
        <ConfirmDialog
          title="确认生成视频"
          message={`确认把《${scriptTitle(videoConfirmScript, scriptLanguage)}》送入视频工厂吗？当前视频生成链路还未接入，会先进入占位流程。`}
          confirmText="进入视频工厂"
          onConfirm={handleConfirmVideoGeneration}
          onCancel={() => setVideoConfirmScriptId(null)}
        />
      )}

      {deleteConfirmScript && (
        <ConfirmDialog
          title="确认删除脚本"
          message={`确认删除《${scriptTitle(deleteConfirmScript, scriptLanguage)}》吗？删除后会从脚本库移除。`}
          confirmText="删除"
          confirmTone="danger"
          onConfirm={() => void performDeleteScript(deleteConfirmScript.id)}
          onCancel={() => setDeleteConfirmScriptId(null)}
        />
      )}

      {editingScript && (
        <AiEditDialog
          script={editingScript}
          instruction={editInstruction}
          onInstructionChange={setEditInstruction}
          onSubmit={() => void handleSubmitAiEdit()}
          language={scriptLanguage}
          onClose={() => {
            setEditingScriptId(null);
            setEditInstruction("");
          }}
        />
      )}

      {editingPersona && (
        <PersonaEditDialog
          persona={editingPersona}
          instruction={personaEditInstruction}
          onInstructionChange={setPersonaEditInstruction}
          onSubmit={() => void handleSubmitPersonaEdit()}
          onClose={() => {
            setEditingPersonaCardId(null);
            setPersonaEditInstruction("");
          }}
        />
      )}
    </section>
  );
}

function buildPendingGenerationCards(job: ScriptGenerationJobRecord): PendingGenerationCard[] {
  if (job.status === "succeeded") return [];
  const count = Math.max(1, job.scriptCount);
  const completedCount = scriptGenerationCompletedCount(job);
  if (job.status === "failed") {
    const failedIndex = Math.max(1, Math.min(count, completedCount + 1));
    return [{
      id: `script-generation-${job.id}-${failedIndex}-failed`,
      jobId: job.id,
      kind: "script",
      title: `脚本任务 ${failedIndex} / ${count}`,
      index: failedIndex,
      total: count,
      status: "failed",
      progress: 100,
      scriptType: `已完成 ${completedCount} / ${count}`,
      errorMessage: job.errorMessage ?? undefined,
    }];
  }
  return Array.from({ length: count }).flatMap((_, index) => {
    const status = pendingGenerationCardStatus(job, index);
    if (status === "succeeded") return [];
    return [{
      id: `script-generation-${job.id}-${index + 1}`,
      jobId: job.id,
      kind: "script" as const,
      title: `脚本任务 ${index + 1} / ${count}`,
      index: index + 1,
      total: count,
      status,
      progress: pendingGenerationProgress(job, index),
      scriptType: `已完成 ${completedCount} / ${count}`,
      errorMessage: job.errorMessage ?? undefined,
    }];
  });
}

function buildPendingPersonaGenerationCards(job: PersonaGenerationJobRecord): PendingGenerationCard[] {
  if (job.status === "succeeded") return [];
  const count = Math.max(1, job.personaCount);
  if (job.status === "failed") {
    return [{
      id: `persona-generation-${job.id}-failed`,
      jobId: job.id,
      kind: "persona",
      title: `人设任务 ${job.completedCount} / ${count}`,
      index: Math.max(1, Math.min(count, job.completedCount + 1)),
      total: count,
      status: "failed",
      progress: 100,
      scriptType: `已完成 ${job.completedCount} / ${count}`,
      errorMessage: job.errorMessage ?? undefined,
    }];
  }
  return Array.from({ length: count }).flatMap((_, index) => {
    const status = pendingPersonaGenerationCardStatus(job, index);
    if (status === "succeeded") return [];
    return [{
      id: `persona-generation-${job.id}-${index + 1}`,
      jobId: job.id,
      kind: "persona" as const,
      title: `人设任务 ${index + 1} / ${count}`,
      index: index + 1,
      total: count,
      status,
      progress: pendingPersonaGenerationProgress(job, index),
      scriptType: `已完成 ${Math.min(job.completedCount, count)} / ${count}`,
      errorMessage: job.errorMessage ?? undefined,
    }];
  });
}

function isActiveGenerationJob(job: ScriptGenerationJobRecord): boolean {
  return job.status === "queued" || job.status === "generating";
}

function isActivePersonaGenerationJob(job: PersonaGenerationJobRecord): boolean {
  return job.status === "queued" || job.status === "generating";
}

function mergeGenerationJobs(
  currentJobs: ScriptGenerationJobRecord[],
  updatedJobs: ScriptGenerationJobRecord[],
): ScriptGenerationJobRecord[] {
  const byId = new Map(currentJobs.map(job => [job.id, job]));
  updatedJobs.forEach(job => byId.set(job.id, job));
  return Array.from(byId.values()).sort((first, second) => second.createdAt.localeCompare(first.createdAt));
}

function mergePersonaGenerationJobs(
  currentJobs: PersonaGenerationJobRecord[],
  updatedJobs: PersonaGenerationJobRecord[],
): PersonaGenerationJobRecord[] {
  const byId = new Map(currentJobs.map(job => [job.id, job]));
  updatedJobs.forEach(job => byId.set(job.id, job));
  return Array.from(byId.values()).sort((first, second) => second.createdAt.localeCompare(first.createdAt));
}

function scriptGenerationCompletedCount(job: ScriptGenerationJobRecord): number {
  return Math.max(0, Math.min(job.scriptCount, job.completedCount ?? job.scriptIds.length));
}

function pendingGenerationCardStatus(job: ScriptGenerationJobRecord, index: number): PendingGenerationStatus | "succeeded" {
  const completedCount = scriptGenerationCompletedCount(job);
  if (index < completedCount) return "succeeded";
  if (job.status === "failed") return "failed";
  if (job.status === "generating" && index === completedCount) return "generating";
  return "queued";
}

function pendingPersonaGenerationCardStatus(job: PersonaGenerationJobRecord, index: number): PendingGenerationStatus | "succeeded" {
  if (index < job.completedCount) return "succeeded";
  if (job.status === "generating" && index === job.completedCount) return "generating";
  return "queued";
}

function pendingGenerationProgress(job: ScriptGenerationJobRecord, index: number): number {
  const completedCount = scriptGenerationCompletedCount(job);
  if (index < completedCount || job.status === "failed") return 100;
  if (job.status === "generating" && index === completedCount) return 48;
  return 8;
}

function pendingPersonaGenerationProgress(job: PersonaGenerationJobRecord, index: number): number {
  if (index < job.completedCount) return 100;
  if (job.status === "generating" && index === job.completedCount) return 48;
  return 8;
}

function PendingGenerationCardView({
  card,
  isDeleting,
  isRetrying,
  onDelete,
  onRetry,
}: {
  card: PendingGenerationCard;
  isDeleting?: boolean;
  isRetrying?: boolean;
  onDelete?: () => void;
  onRetry?: () => void;
}) {
  const label = pendingGenerationLabel(card.status);
  const message = pendingGenerationMessage(card);
  const taskLabel = card.kind === "persona" ? "人设任务" : "脚本任务";
  const icon = card.status === "failed"
    ? <AlertCircle size={17} aria-hidden="true" />
    : card.status === "queued"
      ? <Clock3 size={17} aria-hidden="true" />
      : <Loader2 className="spin" size={17} aria-hidden="true" />;
  return (
    <article
      className={[
        "script-editorial-card",
        "script-editorial-card--pending",
        `script-editorial-card--${card.status}`,
      ].join(" ")}
      aria-label={`${taskLabel} ${card.index} / ${card.total}，${label}`}
      aria-live="polite"
    >
      <div className="script-editorial-card__select script-editorial-card__select--static">
        <div className="script-editorial-card__title-row">
          <h3>{card.title}</h3>
        </div>
        <div className="script-editorial-card__status-row">
          <span className={`script-editorial-status-pill script-editorial-status-pill--${card.status}`}>
            {icon}
            {label}
          </span>
          <span className="script-editorial-status-meta">{card.scriptType}</span>
        </div>
        <ProgressInline label={label} progress={card.progress} />
        <p className={card.status === "failed" ? "script-editorial-card__error" : undefined} title={card.errorMessage}>
          {message}
        </p>
      </div>
      {(onRetry || onDelete) && (
        <div className="script-editorial-card__actions">
          {onRetry && (
            <button
              type="button"
              className="script-editorial-card__retry"
              aria-label={`重试失败${taskLabel}：${card.title}`}
              disabled={isRetrying || isDeleting}
              onClick={onRetry}
            >
              {isRetrying ? <Loader2 className="spin" size={16} aria-hidden="true" /> : <RotateCcw size={16} aria-hidden="true" />}
              <span>重试任务</span>
            </button>
          )}
          {onDelete && (
            <button
              type="button"
              className="script-editorial-card__delete"
              aria-label={`删除失败${taskLabel}：${card.title}`}
              disabled={isDeleting || isRetrying}
              onClick={onDelete}
            >
              {isDeleting ? <Loader2 className="spin" size={17} aria-hidden="true" /> : <Trash2 size={17} aria-hidden="true" />}
            </button>
          )}
        </div>
      )}
    </article>
  );
}

function PersonaCardView({
  persona,
  isActive,
  onSelect,
}: {
  persona: PersonaCard;
  isActive: boolean;
  onSelect: () => void;
}) {
  return (
    <article
      className={[
        "script-persona-card",
        isActive ? "script-persona-card--active" : "",
      ].filter(Boolean).join(" ")}
    >
      <button
        type="button"
        className="script-persona-card__select"
        onClick={onSelect}
        aria-pressed={isActive}
        aria-label={`选择人设：${persona.label}`}
      >
        <div className="script-persona-card__top">
          <span className="script-persona-card__icon">
            <UserRound size={17} aria-hidden="true" />
          </span>
          <div>
            <h3>{persona.label}</h3>
            {persona.personaType || persona.role ? <p>{compactStrings([persona.personaType, persona.role]).join(" / ")}</p> : null}
          </div>
          {persona.qualityScore !== null ? (
            <span className="script-persona-card__score" aria-label={`Persona quality score ${persona.qualityScore}`}>
              {persona.qualityScore}
            </span>
          ) : null}
        </div>
        <TagRow values={persona.tags} />
        {persona.roleTask ? <p className="script-persona-card__mission">{persona.roleTask}</p> : null}
        <p className="script-persona-card__summary">{persona.summary || "可复用的 Moras 创作者人设。"}</p>
      </button>
    </article>
  );
}

function pendingGenerationLabel(status: PendingGenerationStatus): string {
  if (status === "queued") return "排队中";
  if (status === "failed") return "生成失败";
  return "生成中";
}

function pendingGenerationMessage(card: PendingGenerationCard): string {
  if (card.status === "failed") {
    return compactGenerationError(
      card.errorMessage,
      card.kind === "persona" ? "人设智能体生成失败，请调整输入后重试。" : undefined,
    );
  }
  if (card.kind === "persona") {
    if (card.status === "queued") return `第 ${card.index} 个人设在队列中，Persona Agent 会逐个生成。`;
    return `正在生成第 ${card.index} 个人设，完成后会自动进入人设库。`;
  }
  if (card.status === "queued") return `第 ${card.index} 个脚本在队列中，当前批次会按顺序返回。`;
  return `正在生成第 ${card.index} 个脚本，后端 Script Agent 正在运行。`;
}

function compactGenerationError(message?: string, fallback = "脚本智能体生成失败，请调整输入后重试。"): string {
  if (!message?.trim()) return fallback;
  if (/server disconnected|transport failed|request disconnected|remote protocol|timeout/i.test(message)) {
    return "模型服务连接中断，系统已自动重试但仍失败。请点击重试任务。";
  }
  const lines = message
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line && !line.startsWith("https://errors.pydantic.dev") && !line.startsWith("For further information"));
  const validationSummary = lines.find(line => /validation errors? for/i.test(line));
  const valueErrors = lines
    .filter(line => /Value error|should have|too generic|too brief|before\/now/i.test(line))
    .slice(0, 2);
  const summary = [validationSummary, ...valueErrors]
    .filter((line, index, all) => line && all.indexOf(line) === index)
    .join("；");
  const compact = summary || lines[0] || fallback;
  return compact.length > 220 ? `${compact.slice(0, 217)}...` : compact;
}

function LanguageToggle({
  value,
  onChange,
  ariaLabel = "脚本文本语言",
}: {
  value: ScriptLanguage;
  onChange: (value: ScriptLanguage) => void;
  ariaLabel?: string;
}) {
  return (
    <div className="script-language-toggle" role="group" aria-label={ariaLabel}>
      <button
        type="button"
        className={value === "en" ? "script-language-toggle__button script-language-toggle__button--active" : "script-language-toggle__button"}
        aria-pressed={value === "en"}
        onClick={() => onChange("en")}
      >
        EN
      </button>
      <button
        type="button"
        className={value === "zh" ? "script-language-toggle__button script-language-toggle__button--active" : "script-language-toggle__button"}
        aria-pressed={value === "zh"}
        onClick={() => onChange("zh")}
      >
        中文
      </button>
    </div>
  );
}

function uiText(language: ScriptLanguage, en: string, zh: string): string {
  return language === "zh" ? zh : en;
}

async function copyTextToClipboard(text: string): Promise<void> {
  if (navigator.clipboard?.writeText) {
    await navigator.clipboard.writeText(text);
    return;
  }
  const textArea = document.createElement("textarea");
  textArea.value = text;
  textArea.setAttribute("readonly", "");
  textArea.style.position = "fixed";
  textArea.style.left = "-9999px";
  document.body.appendChild(textArea);
  textArea.select();
  const didCopy = document.execCommand("copy");
  document.body.removeChild(textArea);
  if (!didCopy) throw new Error("复制提示词失败。");
}

function PromptCopyButton({
  label,
  copiedLabel,
  copied,
  onCopy,
}: {
  label: string;
  copiedLabel: string;
  copied: boolean;
  onCopy: () => void;
}) {
  return (
    <button
      type="button"
      className="script-editorial-prompt-copy"
      aria-label={copied ? copiedLabel : label}
      title={copied ? copiedLabel : label}
      onClick={onCopy}
    >
      {copied ? <Check size={15} aria-hidden="true" /> : <Copy size={15} aria-hidden="true" />}
    </button>
  );
}

function StoryboardTable({ shots, language }: { shots: ScriptStoryboardShot[]; language: ScriptLanguage }) {
  if (!shots.length) return <p className="script-editorial-body-text">{uiText(language, "No storyboard yet.", "暂无分镜。")}</p>;

  return (
    <div className="script-editorial-storyboard-scroll">
      <table className="script-editorial-storyboard-table">
        <caption className="visually-hidden">{uiText(language, "Storyboard", "分镜头脚本")}</caption>
        <thead>
          <tr>
            <th scope="col">{uiText(language, "Shot / Time", "镜号 / 时间")}</th>
            <th scope="col">{uiText(language, "Visual Action", "画面动作")}</th>
            <th scope="col">{uiText(language, "Shot / Camera", "景别 / 运镜")}</th>
            <th scope="col">{uiText(language, "Scene / Props", "场景 / 道具")}</th>
            <th scope="col">{uiText(language, "Voiceover / Caption Highlight / Sound", "口播 / 重点字幕 / 声音")}</th>
            <th scope="col">{uiText(language, "Transition / Purpose", "转场 / 作用")}</th>
          </tr>
        </thead>
        <tbody>
          {shots.map((shot, index) => (
            <StoryboardTableRow
              key={shot.shotId ?? shot.timestamp ?? JSON.stringify(shot)}
              shot={shot}
              index={index}
              language={language}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}

function StoryboardTableRow({
  shot,
  index,
  language,
}: {
  shot: ScriptStoryboardShot;
  index: number;
  language: ScriptLanguage;
}) {
  const action = localizedField(shot, "characterAction", shot.characterAction, language)
    || localizedField(shot, "purpose", shot.purpose, language)
    || "-";
  const duration = localizedField(shot, "duration", shot.duration, language);
  const timestamp = localizedField(shot, "timestamp", shot.timestamp, language) || "-";
  return (
    <tr>
      <th scope="row" className="script-editorial-storyboard-table__shot">
        <span>{formatShotNumber(shot.shotId, index, language)}</span>
        <time>{timestamp}</time>
        {duration ? <small>{duration}</small> : null}
      </th>
      <td>
        <p>{action}</p>
        <StoryboardTableField label={uiText(language, "Expression", "表情")} value={localizedField(shot, "facialExpression", shot.facialExpression, language)} />
      </td>
      <td>
        <StoryboardTableField label={uiText(language, "Camera", "镜头")} value={localizedField(shot, "camera", shot.camera, language)} />
      </td>
      <td>
        <StoryboardTableField label={uiText(language, "Background", "背景")} value={localizedField(shot, "background", shot.background, language)} />
        <StoryboardTableField label={uiText(language, "Props", "道具")} value={localizedArray(shot, "props", shot.props, language).join(" / ")} />
        <StoryboardTableField label={uiText(language, "Visual elements", "画面要素")} value={localizedArray(shot, "visualElements", shot.visualElements, language).join(" / ")} />
      </td>
      <td>
        <StoryboardTableField
          label={uiText(language, "Voiceover", "口播")}
          value={localizedField(shot, "voiceover", shot.voiceover, language)}
          variant="voiceover"
        />
        <StoryboardTableField label={uiText(language, "Caption highlight", "重点字幕")} value={localizedField(shot, "overlay", shot.overlay, language)} />
        <StoryboardTableField label={uiText(language, "Sound", "音效")} value={localizedField(shot, "sound", shot.sound, language)} />
        <StoryboardTableField label={uiText(language, "BGM", "BGM")} value={localizedField(shot, "bgm", shot.bgm, language)} />
        <StoryboardTableField label={uiText(language, "Sound FX", "音效元素")} value={localizedArray(shot, "soundEffects", shot.soundEffects, language).join(" / ")} />
        <StoryboardTableField label={uiText(language, "Caption logic", "字幕逻辑")} value={localizedField(shot, "subtitleLogic", shot.subtitleLogic, language)} />
      </td>
      <td>
        <StoryboardTableField label={uiText(language, "Transition", "转场")} value={localizedField(shot, "transition", shot.transition, language)} />
        <StoryboardTableField label={uiText(language, "Purpose", "作用")} value={localizedField(shot, "purpose", shot.purpose, language)} />
        <StoryboardTableField label={uiText(language, "Visual logic", "要素逻辑")} value={localizedField(shot, "visualElementLogic", shot.visualElementLogic, language)} />
      </td>
    </tr>
  );
}

function StoryboardTableField({ label, value, variant }: { label: string; value?: string; variant?: "voiceover" }) {
  if (!value) return null;
  return (
    <span className={`script-editorial-storyboard-table__field${variant ? ` script-editorial-storyboard-table__field--${variant}` : ""}`}>
      <strong>{label}</strong>
      <span className="script-editorial-storyboard-table__value">{value}</span>
    </span>
  );
}

function formatShotNumber(shotId: string | undefined, index: number, language: ScriptLanguage): string {
  const numberMatch = shotId?.match(/\d+/);
  const shotNumber = numberMatch ? Number.parseInt(numberMatch[0], 10) : index + 1;
  const label = uiText(language, "Shot", "镜头");
  if (Number.isFinite(shotNumber)) return `${label} ${String(shotNumber).padStart(2, "0")}`;
  return shotId || `${label} ${String(index + 1).padStart(2, "0")}`;
}

function CreatorPersonaPanel({
  persona,
  fallbackPersona,
  language,
  copyKey,
  copiedPromptKey,
  onCopyPrompt,
}: {
  persona: CreatorPersona;
  fallbackPersona?: JsonValue;
  language: ScriptLanguage;
  copyKey: string;
  copiedPromptKey: string;
  onCopyPrompt: (key: string, text: string) => void;
}) {
  const personaName = localizedField(persona, "displayName", persona.displayName, language) || "Creator persona";
  const personaType = localizedField(persona, "personaType", persona.personaType, language);
  const roleTask = localizedField(persona, "roleTask", persona.roleTask, language);
  const audienceCallout = localizedField(persona, "audienceCallout", persona.audienceCallout, language);
  const role = localizedField(persona, "role", persona.role || fallbackPersona, language);
  const problemProfile = localizedObject(persona, "targetProblemProfile", persona.targetProblemProfile, language);
  const trustBasis = localizedObject(persona, "trustBasis", persona.trustBasis, language);
  const scenePair = localizedObject(persona, "personaScenePair", persona.personaScenePair, language);
  const memorySymbols = localizedObject(persona, "memorySymbols", persona.memorySymbols, language);
  const endorsement = localizedObject(persona, "endorsementBoundary", persona.endorsementBoundary, language);
  const handoff = localizedObject(persona, "scriptAgentHandoff", persona.scriptAgentHandoff, language);
  const promptAssets = localizedObject(persona, "digitalHumanPromptAssets", persona.digitalHumanPromptAssets, language);
  const quality = personaQualityScore(persona);
  const qualityNotes = qualityReviewNotes(persona, language);
  const pillars = localizedArray(persona, "contentPillars", persona.contentPillars, language);
  const scenes = localizedArray(persona, "recurringScenes", persona.recurringScenes, language);
  const proofAssets = toStringArray(firstDefined(trustBasis.usableProofAssets, trustBasis.usable_proof_assets));
  const bannedClaims = toStringArray(firstDefined(endorsement.bannedClaims, endorsement.banned_claims));
  const allowedClaims = toStringArray(firstDefined(endorsement.allowedClaims, endorsement.allowed_claims));
  const openingRules = toStringArray(firstDefined(handoff.openingSceneRules, handoff.opening_scene_rules));
  const proofRules = toStringArray(firstDefined(handoff.proofAssetRules, handoff.proof_asset_rules));
  const appearance = compactStrings([
    localizedField(persona, "appearance", persona.appearance, language),
    localizedField(persona, "faceHairMakeup", persona.faceHairMakeup, language),
    localizedField(persona, "wardrobe", persona.wardrobe, language),
    localizedField(persona, "stylingDetails", persona.stylingDetails, language),
  ]).join("\n");
  const veoIdentity = localizedField(persona, "veoIdentityString", persona.veoIdentityString, language);
  const referencePrompt = localizedField(persona, "referenceImagePrompt", persona.referenceImagePrompt, language);
  const avatarMotionPrompt = jsonText(firstDefined(promptAssets.avatarMotionPrompt, promptAssets.avatar_motion_prompt));
  const voiceStylePrompt = jsonText(firstDefined(promptAssets.voiceStylePrompt, promptAssets.voice_style_prompt));
  const sampleRequirement = jsonText(firstDefined(promptAssets.sampleRequirement, promptAssets.sample_requirement));
  const syntheticDisclosure = jsonText(firstDefined(promptAssets.syntheticDisclosureNote, promptAssets.synthetic_disclosure_note));
  const deliveryRules = toStringArray(firstDefined(promptAssets.scriptDeliveryRules, promptAssets.script_delivery_rules));

  if (!Object.keys(persona || {}).length && !role) {
    return <p className="script-editorial-body-text">{uiText(language, "No Persona asset information yet.", "暂无 Persona 资产信息。")}</p>;
  }

  return (
    <div className="script-editorial-persona-panel">
      <div className="script-editorial-persona__summary">
        <div>
          <strong>{personaName}</strong>
          {compactStrings([personaType, role]).length ? <span>{compactStrings([personaType, role]).join(" / ")}</span> : null}
        </div>
        <p>{localizedField(persona, "demographic", persona.demographic, language)}</p>
        {quality !== null ? <span className="script-editorial-persona__score">{quality}</span> : null}
      </div>

      <PersonaDetailSection title={uiText(language, "Operating Brief", "运营简报")}>
        <dl className="script-editorial-persona__grid">
          <ShotField label={uiText(language, "Role task", "人设任务")} value={roleTask} />
          <ShotField label={uiText(language, "Audience signal", "目标受众信号")} value={audienceCallout} />
          <ShotField label={uiText(language, "CTA style", "CTA 风格")} value={localizedField(persona, "ctaStyle", persona.ctaStyle, language)} />
        </dl>
      </PersonaDetailSection>

      <PersonaDetailSection title={uiText(language, "Tension Map", "痛点地图")}>
        <dl className="script-editorial-persona__grid">
          <ShotField label={uiText(language, "Explicit pains", "明确痛点")} value={toStringArray(firstDefined(problemProfile.explicitPains, problemProfile.explicit_pains)).join(" / ")} />
          <ShotField label={uiText(language, "Inner conflict", "内心冲突")} value={jsonText(firstDefined(problemProfile.innerConflict, problemProfile.inner_conflict))} />
          <ShotField label={uiText(language, "Desired state", "渴望状态")} value={jsonText(firstDefined(problemProfile.desiredState, problemProfile.desired_state))} />
        </dl>
      </PersonaDetailSection>

      <PersonaDetailSection title={uiText(language, "Production Kit", "生产套件")}>
        <TagRow values={pillars} />
        <dl className="script-editorial-persona__grid">
          <ShotField label={uiText(language, "Primary scene", "主场景")} value={jsonText(firstDefined(scenePair.primaryScene, scenePair.primary_scene))} />
          <ShotField label={uiText(language, "Recurring scenes", "复用场景")} value={scenes.join(" / ")} />
          <ShotField label={uiText(language, "Scene logic", "场景逻辑")} value={jsonText(firstDefined(scenePair.sceneLogic, scenePair.scene_logic))} />
          <ShotField label={uiText(language, "Format cue", "形式记忆点")} value={jsonText(firstDefined(memorySymbols.fixedOpeningPattern, memorySymbols.fixed_opening_pattern))} />
          <ShotField label={uiText(language, "Visual anchor", "视觉记忆点")} value={jsonText(firstDefined(memorySymbols.visualAnchor, memorySymbols.visual_anchor))} />
          <ShotField label={uiText(language, "Recurring prop", "固定道具")} value={jsonText(firstDefined(memorySymbols.recurringProp, memorySymbols.recurring_prop))} />
          <ShotField label={uiText(language, "Column name", "栏目名")} value={jsonText(firstDefined(memorySymbols.columnName, memorySymbols.column_name))} />
          <ShotField label={uiText(language, "Opening rules", "开场规则")} value={openingRules.join("\n")} />
        </dl>
      </PersonaDetailSection>

      <PersonaDetailSection title={uiText(language, "Trust & Compliance", "信任与合规")}>
        <dl className="script-editorial-persona__grid">
          <ShotField label={uiText(language, "Trust angle", "可信角度")} value={jsonText(firstDefined(trustBasis.primaryTrustAngle, trustBasis.primary_trust_angle))} />
          <ShotField label={uiText(language, "Proof assets", "证明素材")} value={proofAssets.join(" / ")} />
          <ShotField label={uiText(language, "Proof policy", "证明策略")} value={localizedField(persona, "proofPolicy", persona.proofPolicy, language) || jsonText(firstDefined(trustBasis.proofInsertionRule, trustBasis.proof_insertion_rule))} />
          <ShotField label={uiText(language, "Allowed claims", "可说内容")} value={allowedClaims.join(" / ")} />
          <ShotField label={uiText(language, "Red lines", "禁线")} value={bannedClaims.join(" / ")} />
          <ShotField label={uiText(language, "Experience rule", "体验表达规则")} value={jsonText(firstDefined(endorsement.experienceRule, endorsement.experience_rule))} />
          <ShotField label={uiText(language, "Proof handoff", "证明交接")} value={proofRules.join("\n")} />
          <ShotField label={uiText(language, "Quality notes", "质量备注")} value={qualityNotes.join("\n")} />
        </dl>
      </PersonaDetailSection>

      <PersonaDetailSection title={uiText(language, "Digital Human Prompt Asset", "数字人提示词资产")}>
        <dl className="script-editorial-persona__grid">
          <ShotField label={uiText(language, "Visual motion prompt", "视觉动作提示词")} value={avatarMotionPrompt} />
          <ShotField label={uiText(language, "Voice / delivery prompt", "声音 / 表达提示词")} value={voiceStylePrompt} />
          <ShotField label={uiText(language, "Script delivery rules", "口播规则")} value={deliveryRules.join("\n")} />
          <ShotField label={uiText(language, "Reference requirement", "参考要求")} value={sampleRequirement} />
          <ShotField label={uiText(language, "Disclosure", "说明")} value={syntheticDisclosure} />
        </dl>
      </PersonaDetailSection>

      <PersonaDetailSection title={uiText(language, "Digital Human Visual Identity", "数字人视觉身份")}>
      <dl className="script-editorial-persona__grid">
        <ShotField label={uiText(language, "Background", "背景")} value={localizedField(persona, "creatorBackground", persona.creatorBackground, language)} />
        <ShotField label={uiText(language, "Personality", "性格")} value={localizedField(persona, "personality", persona.personality, language)} />
        <ShotField label={uiText(language, "Trust stance", "可信立场")} value={localizedField(persona, "trustStance", persona.trustStance, language)} />
        <ShotField label={uiText(language, "Speech style", "说话方式")} value={localizedField(persona, "speechStyle", persona.speechStyle, language)} />
        <ShotField label={uiText(language, "Interests", "爱好")} value={localizedArray(persona, "hobbiesInterests", persona.hobbiesInterests, language).join(" / ")} />
        <ShotField label={uiText(language, "Appearance / Makeup / Wardrobe", "外貌 / 妆造 / 服饰")} value={appearance} />
        <ShotField label={uiText(language, "Marks / Tattoos", "纹身 / 特征")} value={localizedField(persona, "distinctiveMarksOrTattoos", persona.distinctiveMarksOrTattoos, language)} />
        <ShotField label={uiText(language, "Props", "道具")} value={localizedArray(persona, "props", persona.props, language).join(" / ")} />
        <ShotField label={uiText(language, "Consistency rules", "一致性规则")} value={localizedArray(persona, "consistencyRules", persona.consistencyRules, language).join("\n")} />
      </dl>
      {veoIdentity ? (
        <div className="script-editorial-persona__prompt script-editorial-prompt-card">
          <PromptCopyButton
            label={uiText(language, "Copy Veo identity string", "复制 Veo 身份锚点")}
            copiedLabel={uiText(language, "Copied Veo identity string", "已复制 Veo 身份锚点")}
            copied={copiedPromptKey === `${copyKey}-veo`}
            onCopy={() => onCopyPrompt(`${copyKey}-veo`, veoIdentity)}
          />
          <h4>{uiText(language, "Veo Identity String", "Veo 身份锚点")}</h4>
          <p>{veoIdentity}</p>
        </div>
      ) : null}
      {referencePrompt ? (
        <div className="script-editorial-persona__prompt script-editorial-prompt-card">
          <PromptCopyButton
            label={uiText(language, "Copy character reference image prompt", "复制人设参考图提示词")}
            copiedLabel={uiText(language, "Copied character reference image prompt", "已复制人设参考图提示词")}
            copied={copiedPromptKey === copyKey}
            onCopy={() => onCopyPrompt(copyKey, referencePrompt)}
          />
          <h4>{uiText(language, "Character Reference Image Prompt", "人设参考图生图提示词")}</h4>
          <p>{referencePrompt}</p>
        </div>
      ) : null}
      </PersonaDetailSection>
    </div>
  );
}

function PersonaDetailSection({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="script-editorial-persona__section">
      <h4>{title}</h4>
      {children}
    </section>
  );
}

function ProductionAssetPlanView({ entry, language }: { entry: ProductionAssetPlanEntry; language: ScriptLanguage }) {
  const phase = localizedField(entry, "narrativePhase", entry.narrativePhase, language) || uiText(language, "Asset phase", "素材段落");
  const assetType = jsonText(entry.assetType);
  const category = jsonText(entry.morasAssetCategory);
  const layer = jsonText(entry.layer);
  return (
    <li className="script-editorial-asset-plan__item">
      <div className="script-editorial-asset-plan__top">
        <h4>{phase}</h4>
        <time>{entry.timeRange}</time>
      </div>
      <div className="script-editorial-asset-plan__badges" aria-label={uiText(language, "Asset type", "素材类型")}>
        <span>{assetModeLabel(assetType, language)}</span>
        {category && category !== "none" ? <span>{assetCategoryLabel(category, language)}</span> : null}
        {layer ? <span>{assetLayerLabel(layer, language)}</span> : null}
      </div>
      <dl>
        <ShotField label={uiText(language, "Related shots", "关联镜头")} value={toStringArray(entry.shotIds).join(" / ")} />
        <ShotField label={uiText(language, "Usage reason", "使用原因")} value={localizedField(entry, "usageReason", entry.usageReason, language)} />
        <ShotField label={uiText(language, "Editing note", "剪辑备注")} value={localizedField(entry, "editorNote", entry.editorNote, language)} />
      </dl>
    </li>
  );
}

function ShotField({ label, value }: { label: string; value?: string }) {
  if (!value) return null;
  return (
    <div className="script-editorial-shot__field">
      <dt>{label}</dt>
      <dd>{value}</dd>
    </div>
  );
}

function assetModeLabel(value: string, language: ScriptLanguage): string {
  if (language === "en") return value;
  return assetModeChineseLabels.get(value) || value;
}

function assetCategoryLabel(value: string, language: ScriptLanguage): string {
  if (language === "en") return value;
  return assetCategoryChineseLabels.get(value) || value;
}

function assetLayerLabel(value: string, language: ScriptLanguage): string {
  if (language === "en") return value;
  return assetLayerChineseLabels.get(value) || value;
}

function veoDurationSummary(videoPrompt: JsonObject, language: ScriptLanguage): string {
  const rawSegments = Array.isArray(videoPrompt.segments) ? videoPrompt.segments.filter(isJsonObject).slice(0, 7) : [];
  const targetDuration = numericJson(firstDefined(videoPrompt.targetDurationSec, videoPrompt.target_duration_sec));
  const veoDuration = numericJson(firstDefined(videoPrompt.veoGenerationDurationSec, videoPrompt.veo_generation_duration_sec, videoPrompt.seedanceGenerationDurationSec, videoPrompt.seedance_generation_duration_sec));
  const baseDuration = numericJson(firstDefined(videoPrompt.veoBaseDurationSec, videoPrompt.veo_base_duration_sec)) || 8;
  const targetText = targetDuration ? `${formatDurationValue(targetDuration)}s` : "25-50s";
  const veoText = veoDuration ? `${formatDurationValue(veoDuration)}s` : "按素材计划动态计算";
  if (language === "en") {
    const segmentText = rawSegments.length > 0 ? `${rawSegments.length} Veo 3.1 source clips` : "Dynamic Veo 3.1 source clips";
    const timelineText = veoDuration ? `${formatDurationValue(veoDuration)}s` : "calculated from the asset plan";
    return `${segmentText}; target final cut ${targetText}; Veo timeline coverage ${timelineText}; each edit slot is no longer than ${formatDurationValue(baseDuration)}s, with Moras screenshots or screen recordings inserted from the asset usage plan.`;
  }
  const segmentText = rawSegments.length > 0 ? `${rawSegments.length} 段` : "动态段数";
  return `${segmentText} Veo 3.1 原始素材；目标成片 ${targetText}，Veo 时间线覆盖 ${veoText}；单段剪辑位不超过 ${formatDurationValue(baseDuration)}s，Moras 截图 / 录屏由素材应用计划插入。`;
}

function veoSegments(videoPrompt: JsonObject, language: ScriptLanguage) {
  const rawSegments = Array.isArray(videoPrompt.segments) ? videoPrompt.segments.filter(isJsonObject).slice(0, 7) : [];
  const basePromptParts = compactStrings([
    localizedField(videoPrompt, "characterLock", videoPrompt.characterLock, language),
    localizedField(videoPrompt, "sceneLock", videoPrompt.sceneLock, language),
  ]);
  return rawSegments.map((segment, index) => {
    const segmentIndex = Number(segment.segmentIndex ?? index + 1);
    const segmentGenerationPrompt = localizedField(
      segment,
      "veoPrompt",
      firstDefined(segment.veoPrompt, segment.veo_prompt),
      language,
    ) || localizedField(
      segment,
      "visualPrompt",
      firstDefined(segment.visualPrompt, segment.visual_prompt, segment.segmentGenerationPrompt, segment.generationPrompt, segment.prompt),
      language,
    );
    const startSec = numericJson(firstDefined(segment.timelineStartSec, segment.timeline_start_sec));
    const endSec = numericJson(firstDefined(segment.timelineEndSec, segment.timeline_end_sec));
    const durationSec = numericJson(firstDefined(segment.durationSec, segment.duration_sec));
    const fallbackTimeRange = typeof startSec === "number" && typeof endSec === "number"
      ? `${formatDurationValue(startSec)}s-${formatDurationValue(endSec)}s`
      : ["0s-8s", "8s-16s", "16s-24s", "24s-32s", "32s-40s", "40s-48s", "48s-50s"][index] ?? "";
    return {
      segmentIndex,
      timeRange: jsonText(firstDefined(segment.timeRange, segment.time_range)) || fallbackTimeRange,
      durationLabel: typeof durationSec === "number" ? `${formatDurationValue(durationSec)}s` : "",
      fullPrompt: compactStrings([...basePromptParts, segmentGenerationPrompt]).join("\n\n"),
    };
  });
}

function numericJson(value: JsonValue | undefined): number | undefined {
  if (typeof value === "number" && Number.isFinite(value)) return value;
  if (typeof value === "string" && value.trim()) {
    const parsed = Number(value.trim().replace(/s$/i, ""));
    return Number.isFinite(parsed) ? parsed : undefined;
  }
  return undefined;
}

function formatDurationValue(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1).replace(/\.0$/, "");
}

function ProgressInline({ label, progress }: { label: string; progress: number }) {
  const safeProgress = Math.max(0, Math.min(100, Math.round(progress)));
  return (
    <div className="script-editorial-progress" aria-label={`${label} ${safeProgress}%`}>
      <div className="script-editorial-progress__label">
        <span>{label}</span>
        <strong>{safeProgress}%</strong>
      </div>
      <div className="script-editorial-progress__track">
        <span style={{ width: `${safeProgress}%` }} />
      </div>
    </div>
  );
}

function ConfirmDialog({
  title,
  message,
  confirmText,
  confirmTone = "primary",
  onConfirm,
  onCancel,
}: {
  title: string;
  message: string;
  confirmText: string;
  confirmTone?: "primary" | "danger";
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <div className="script-editorial-modal-backdrop" role="presentation">
      <section className="script-editorial-modal" role="dialog" aria-modal="true" aria-labelledby="script-confirm-title">
        <button type="button" className="script-editorial-modal__close" aria-label="关闭弹窗" onClick={onCancel}>
          <X size={17} aria-hidden="true" />
        </button>
        <h3 id="script-confirm-title">{title}</h3>
        <p>{message}</p>
        <div className="script-editorial-modal__actions">
          <button type="button" className="script-editorial-action" onClick={onCancel}>取消</button>
          <button
            type="button"
            className={`script-editorial-action script-editorial-action--${confirmTone}`}
            onClick={onConfirm}
          >
            {confirmTone === "danger" ? <Trash2 size={16} aria-hidden="true" /> : <Video size={16} aria-hidden="true" />}
            {confirmText}
          </button>
        </div>
      </section>
    </div>
  );
}

function AiEditDialog({
  script,
  instruction,
  onInstructionChange,
  onSubmit,
  language,
  onClose,
}: {
  script: ScriptRecord;
  instruction: string;
  onInstructionChange: (value: string) => void;
  onSubmit: () => void;
  language: ScriptLanguage;
  onClose: () => void;
}) {
  return (
    <div className="script-editorial-modal-backdrop" role="presentation">
      <section className="script-editorial-modal script-editorial-modal--wide" role="dialog" aria-modal="true" aria-labelledby="ai-edit-title">
        <button type="button" className="script-editorial-modal__close" aria-label="关闭弹窗" onClick={onClose}>
          <X size={17} aria-hidden="true" />
        </button>
        <div className="script-editorial-modal__heading">
          <Bot size={18} aria-hidden="true" />
          <h3 id="ai-edit-title">AI 编辑脚本</h3>
        </div>
        <p>修改意见会和当前脚本、分镜、视频提示词一起提交给脚本智能体，并保留修改记录。</p>
        <div className="script-editorial-modal__context">
          <strong>{scriptTitle(script, language)}</strong>
          <span>{scriptPersona(script, language)}</span>
        </div>
        <label className="script-editorial-edit-field">
          <span>修改意见</span>
          <textarea
            value={instruction}
            onChange={event => onInstructionChange(event.target.value)}
            placeholder="例如：把开头改得更像真实创作者口吻，减少教程感，保留三步结构。"
            rows={5}
            autoFocus
          />
        </label>
        <div className="script-editorial-modal__actions">
          <button type="button" className="script-editorial-action" onClick={onClose}>取消</button>
          <button
            type="button"
            className="script-editorial-action script-editorial-action--primary"
            disabled={!instruction.trim()}
            onClick={onSubmit}
          >
            <Send size={16} aria-hidden="true" />
            提交修改
          </button>
        </div>
      </section>
    </div>
  );
}

function PersonaEditDialog({
  persona,
  instruction,
  onInstructionChange,
  onSubmit,
  onClose,
}: {
  persona: PersonaCard;
  instruction: string;
  onInstructionChange: (value: string) => void;
  onSubmit: () => void;
  onClose: () => void;
}) {
  return (
    <div className="script-editorial-modal-backdrop" role="presentation">
      <section className="script-editorial-modal script-editorial-modal--wide" role="dialog" aria-modal="true" aria-labelledby="persona-edit-title">
        <button type="button" className="script-editorial-modal__close" aria-label="关闭弹窗" onClick={onClose}>
          <X size={17} aria-hidden="true" />
        </button>
        <div className="script-editorial-modal__heading">
          <WandSparkles size={18} aria-hidden="true" />
          <h3 id="persona-edit-title">AI 编辑 Persona 资产</h3>
        </div>
        <p>修改意见会更新当前人设的一致性规则，后续生成脚本会带入这版人设。</p>
        <div className="script-editorial-modal__context">
          <strong>{persona.label}</strong>
          <span>{persona.role}</span>
        </div>
        <label className="script-editorial-edit-field">
          <span>修改意见</span>
          <textarea
            value={instruction}
            onChange={event => onInstructionChange(event.target.value)}
            placeholder="例如：更像冷静的运营专家，说话更短，保留同一套服装和桌面道具。"
            rows={5}
            autoFocus
          />
        </label>
        <div className="script-editorial-modal__actions">
          <button type="button" className="script-editorial-action" onClick={onClose}>取消</button>
          <button
            type="button"
            className="script-editorial-action script-editorial-action--primary"
            disabled={!instruction.trim()}
            onClick={onSubmit}
          >
            <Send size={16} aria-hidden="true" />
            提交修改
          </button>
        </div>
      </section>
    </div>
  );
}

function TagRow({ values }: { values: string[] }) {
  const compactValues = uniqueCompactStrings(values).slice(0, 6);
  return (
    <div className="script-editorial-tag-row" aria-label="创意标签">
      {compactValues.map((value, index) => (
        <span key={value} className={`script-editorial-tag script-editorial-tag--${tagTone(index)}`}>
          {value}
        </span>
      ))}
    </div>
  );
}

function buildPersonaCards(records: CreatorPersonaRecord[], language: ScriptLanguage): PersonaCard[] {
  return records.map(record => {
    const persona = record.creatorPersona;
    const label = localizedField(persona, "displayName", persona.displayName, language) || "Unnamed persona";
    const personaType = localizedField(persona, "personaType", persona.personaType, language);
    const roleTask = localizedField(persona, "roleTask", persona.roleTask, language);
    const audienceCallout = localizedField(persona, "audienceCallout", persona.audienceCallout, language);
    const role = localizedField(persona, "role", persona.role, language);
    const demographic = localizedField(persona, "demographic", persona.demographic, language);
    const background = localizedField(persona, "creatorBackground", persona.creatorBackground, language);
    const trustStance = localizedField(persona, "trustStance", persona.trustStance, language);
    const speechStyle = localizedField(persona, "speechStyle", persona.speechStyle, language);
    const pillars = localizedArray(persona, "contentPillars", persona.contentPillars, language);
    const scenes = localizedArray(persona, "recurringScenes", persona.recurringScenes, language);
    const memorySymbols = localizedObject(persona, "memorySymbols", persona.memorySymbols, language);
    const quality = personaQualityScore(persona);
    return {
      id: record.id,
      recordId: record.id,
      personaId: jsonText(persona.personaId) || record.id,
      label,
      personaType,
      role,
      summary: compactStrings([roleTask, audienceCallout, demographic, background, trustStance]).join(" "),
      tags: compactStrings([personaType, pillars[0], scenes[0], jsonText(memorySymbols.columnName), speechStyle]).slice(0, 5),
      qualityScore: quality,
      audienceCallout,
      roleTask,
      creatorPersona: persona,
    };
  });
}

function creatorPersonaHint(persona: CreatorPersona): JsonObject {
  return cleanJsonObject({
    persona_id: persona.personaId,
    display_name: persona.displayName,
    persona_type: persona.personaType,
    role_task: persona.roleTask,
    audience_callout: persona.audienceCallout,
    target_problem_profile: persona.targetProblemProfile,
    trust_basis: persona.trustBasis,
    proof_policy: persona.proofPolicy,
    persona_scene_pair: persona.personaScenePair,
    recurring_scenes: persona.recurringScenes,
    memory_symbols: persona.memorySymbols,
    content_pillars: persona.contentPillars,
    cta_style: persona.ctaStyle,
    endorsement_boundary: persona.endorsementBoundary,
    persona_quality_score: persona.personaQualityScore,
    script_agent_handoff: persona.scriptAgentHandoff,
    role: persona.role,
    demographic: persona.demographic,
    creator_background: persona.creatorBackground,
    personality: persona.personality,
    trust_stance: persona.trustStance,
    speech_style: persona.speechStyle,
    hobbies_interests: persona.hobbiesInterests,
    appearance: persona.appearance,
    face_hair_makeup: persona.faceHairMakeup,
    wardrobe: persona.wardrobe,
    styling_details: persona.stylingDetails,
    distinctive_marks_or_tattoos: persona.distinctiveMarksOrTattoos,
    props: persona.props,
    consistency_rules: persona.consistencyRules,
    veo_identity_string: persona.veoIdentityString,
    reference_image_prompt: persona.referenceImagePrompt,
    digital_human_prompt_assets: persona.digitalHumanPromptAssets,
    localized: persona.localized,
  });
}

function cleanJsonObject(value: JsonObject): JsonObject {
  return Object.fromEntries(
    Object.entries(value).filter(([, child]) => {
      if (child === undefined || child === null || child === "") return false;
      if (Array.isArray(child) && child.length === 0) return false;
      if (typeof child === "object" && !Array.isArray(child) && Object.keys(child).length === 0) return false;
      return true;
    }),
  ) as JsonObject;
}

function scriptTitle(script: ScriptRecord, language: ScriptLanguage = "en"): string {
  return localizedField(script.script, "scriptTitle", script.script.scriptTitle, language)
    || localizedField(script.topicPlan, "title", script.topicPlan.title, language)
    || "未命名脚本";
}

function scriptPersona(script: ScriptRecord, language: ScriptLanguage = "en"): string {
  const creatorPersonaName = localizedField(script.creatorPersona, "displayName", script.creatorPersona.displayName, language);
  const creatorPersonaRole = localizedField(script.creatorPersona, "role", script.creatorPersona.role, language);
  const roleAlreadyContainsName = Boolean(
    creatorPersonaName
    && creatorPersonaRole
    && creatorPersonaRole.toLowerCase().includes(creatorPersonaName.toLowerCase()),
  );
  const creatorPersonaLabel = roleAlreadyContainsName
    ? creatorPersonaRole
    : compactStrings([creatorPersonaName, creatorPersonaRole]).join(" / ");
  if (creatorPersonaLabel) return creatorPersonaLabel;
  return [
    localizedField(script.script, "targetAudience", script.script.targetAudience, language)
      || localizedField(script.topicPlan, "targetAudience", script.topicPlan.targetAudience, language),
    localizedField(script.script, "persona", script.script.persona, language)
      || localizedField(script.topicPlan, "persona", script.topicPlan.persona, language),
  ]
    .filter(Boolean)
    .join(" / ") || "未指定人设";
}

function scriptCreativeTypes(script: ScriptRecord, language: ScriptLanguage = "en"): string[] {
  return compactStrings([
    localizedField(script.topicPlan, "template", script.topicPlan.template, language)
      || localizedField(script.script, "template", script.script.template, language),
    ...toStringArray(script.sourceComponentSummary).map(value => localizeText(value, language)),
  ]).slice(0, 3);
}

function scriptProductionAssetPlan(script: ScriptRecord): ProductionAssetPlanEntry[] {
  if (script.productionAssetPlan?.length) return script.productionAssetPlan;
  const shotIds = script.storyboard.map((shot, index) => shot.shotId || `shot_${index + 1}`);
  const firstShot = shotIds[0] || "shot_1";
  const secondShot = shotIds[1] || firstShot;
  const thirdShot = shotIds[2] || secondShot;
  return [
    {
      planId: "fallback_asset_1",
      timeRange: "0s-9s",
      shotIds: [firstShot],
      narrativePhase: "Hook",
      assetType: "digital_human_avatar",
      morasAssetCategory: "none",
      layer: "base_track",
      usageReason: "Use a human explainer or creator-style base track to make the hook feel trustworthy.",
      editorNote: "Fallback plan for older scripts; regenerate or AI-edit the script to get model-authored asset choices.",
    },
    {
      planId: "fallback_asset_2",
      timeRange: "9s-25s",
      shotIds: [secondShot],
      narrativePhase: "Solution / Proof",
      assetType: "real_moras_screen_recording",
      morasAssetCategory: "workflow_screen_recording",
      layer: "cutaway",
      usageReason: "Use real Moras workflow footage when the script explains product-to-video posting efficiency.",
      editorNote: "Fallback plan for older scripts; bind an approved Moras workflow recording with product library, Generate, ready-with-cart video, and posting entry.",
    },
    {
      planId: "fallback_asset_3",
      timeRange: "25s-38s",
      shotIds: [thirdShot],
      narrativePhase: "CTA / Resolution",
      assetType: "post_production_overlay",
      morasAssetCategory: "none",
      layer: "overlay",
      usageReason: "Use editing overlays for CTA, arrows, highlights, and final reminders.",
      editorNote: "Fallback plan for older scripts; new Script Agent outputs should provide a specific plan.",
    },
  ];
}

function scriptTags(script: ScriptRecord, language: ScriptLanguage = "en"): string[] {
  return compactStrings([
    localizedField(script.script, "template", script.script.template, language)
      || localizedField(script.topicPlan, "template", script.topicPlan.template, language),
    localizedField(script.script, "emotionalAngle", script.script.emotionalAngle, language),
    localizedField(script.script, "corePain", script.script.corePain, language),
    localizedField(script.topicPlan, "recommendedPlatform", script.topicPlan.recommendedPlatform, language),
  ]);
}

function collapseDuplicateScripts(records: ScriptRecord[]): ScriptRecord[] {
  const hasRealProviderScripts = records.some(record => !isMockScript(record));
  const candidates = records.filter(record => !(hasRealProviderScripts && isMockScript(record)));
  const seen = new Set<string>();
  const output: ScriptRecord[] = [];
  for (const record of candidates) {
    const key = scriptDuplicateKey(record);
    if (key && seen.has(key)) continue;
    if (key) seen.add(key);
    output.push(record);
  }
  return output;
}

function isMockScript(script: ScriptRecord): boolean {
  return script.provider === "mock" || script.modelName.startsWith("mock-");
}

function scriptDuplicateKey(script: ScriptRecord): string {
  return normalizeDuplicateText(scriptTitle(script, "en") || scriptTitle(script, "zh"));
}

function normalizeDuplicateText(value: string): string {
  return value.trim().toLocaleLowerCase().replace(/\s+/g, " ");
}

function normalizeScriptType(value: string): string {
  return value === "全部" ? "all" : value;
}

function toStringArray(value: JsonValue[] | JsonValue | undefined): string[] {
  if (!value) return [];
  if (!Array.isArray(value)) return [String(value)];
  return value.map(item => String(item)).filter(Boolean);
}

function compactStrings(values: Array<string | undefined | null>): string[] {
  return uniqueCompactStrings(values);
}

function uniqueCompactStrings(values: Array<string | undefined | null>): string[] {
  const seen = new Set<string>();
  const output: string[] = [];
  for (const value of values) {
    const text = value?.trim();
    if (!text) continue;
    const key = text.toLocaleLowerCase();
    if (seen.has(key)) continue;
    seen.add(key);
    output.push(text);
  }
  return output;
}

function localizedField(
  source: JsonObject | null | undefined,
  fieldName: string,
  fallback: JsonValue | undefined,
  language: ScriptLanguage,
): string {
  const fallbackText = jsonText(fallback);
  if (language === "en") return fallbackText;
  const explicitText = jsonText(findLocalizedValue(source, fieldName));
  if (explicitText) return localizeText(explicitText, language);
  return localizeText(fallbackText, language);
}

function localizedArray(
  source: JsonObject | null | undefined,
  fieldName: string,
  fallback: JsonValue[] | JsonValue | undefined,
  language: ScriptLanguage,
): string[] {
  const fallbackItems = toStringArray(fallback);
  if (language === "en") return fallbackItems;
  const explicitItems = toStringArray(findLocalizedValue(source, fieldName));
  return explicitItems.length > 0
    ? explicitItems.map(value => localizeText(value, language))
    : fallbackItems.map(value => localizeText(value, language));
}

function localizedObject(
  source: JsonObject | null | undefined,
  fieldName: string,
  fallback: JsonObject | undefined,
  language: ScriptLanguage,
): JsonObject {
  if (language === "zh") {
    const explicit = findLocalizedValue(source, fieldName);
    if (isJsonObject(explicit)) return explicit;
  }
  return isJsonObject(fallback) ? fallback : {};
}

function personaQualityScore(persona: CreatorPersona): number | null {
  const value = persona.personaQualityScore;
  if (!isJsonObject(value)) return null;
  const score = Number(value.score);
  return Number.isFinite(score) ? score : null;
}

function qualityReviewNotes(persona: CreatorPersona, language: ScriptLanguage): string[] {
  const quality = localizedObject(persona, "personaQualityScore", persona.personaQualityScore, language);
  return toStringArray(quality.reviewNotes);
}

function findLocalizedValue(source: JsonObject | null | undefined, fieldName: string): JsonValue | undefined {
  if (!source) return undefined;
  const snakeFieldName = toSnakeCase(fieldName);
  const directKeys = [
    `${fieldName}Zh`,
    `${fieldName}Cn`,
    `${fieldName}Chinese`,
    `${fieldName}Translation`,
    `${fieldName}TranslationZh`,
    `${fieldName}TranslationCn`,
    `${snakeFieldName}_zh`,
    `${snakeFieldName}_cn`,
    `${snakeFieldName}_chinese`,
  ];

  for (const key of directKeys) {
    const value = source[key];
    if (value !== undefined && value !== null) return value;
  }

  for (const containerKey of ["translations", "translation", "i18n", "localized", "localizations"]) {
    const container = source[containerKey];
    if (!isJsonObject(container)) continue;
    const languageContainer = firstJsonObject(container.zh, container.zhCN, container.zhCn, container.cn, container.chinese);
    const nestedField = firstDefined(container[fieldName], container[snakeFieldName]);
    const nestedLanguage = isJsonObject(nestedField)
      ? firstDefined(nestedField.zh, nestedField.zhCN, nestedField.zhCn, nestedField.cn, nestedField.chinese)
      : undefined;
    const languageField = languageContainer
      ? firstDefined(languageContainer[fieldName], languageContainer[snakeFieldName])
      : undefined;
    return firstDefined(languageField, nestedLanguage);
  }

  return undefined;
}

function jsonText(value: JsonValue | undefined): string {
  if (value === undefined || value === null || Array.isArray(value) || typeof value === "object") return "";
  return String(value);
}

function firstDefined(...values: Array<JsonValue | undefined>): JsonValue | undefined {
  return values.find(value => value !== undefined && value !== null);
}

function firstJsonObject(...values: Array<JsonValue | undefined>): JsonObject | undefined {
  return values.find(isJsonObject);
}

function isJsonObject(value: JsonValue | undefined): value is JsonObject {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function toSnakeCase(value: string): string {
  return value.replace(/[A-Z]/g, letter => `_${letter.toLowerCase()}`);
}

function localizeText(value: string, language: ScriptLanguage): string {
  if (language === "en" || !value) return value;
  const exact = exactChineseTranslations.get(value.trim());
  if (exact) return exact;
  if (value.includes(" / ")) {
    const parts = value.split(" / ");
    const translated = parts.map(part => localizeText(part, language));
    if (translated.some((part, index) => part !== parts[index])) return translated.join(" / ");
  }
  let translated = value;
  for (const [english, chinese] of phraseChineseTranslations) {
    translated = translated.split(english).join(chinese);
  }
  const mixedExact = exactChineseTranslations.get(translated.trim());
  if (mixedExact) return mixedExact;
  return translated;
}

function hasCjk(value: string): boolean {
  return /[\u3400-\u9fff]/.test(value);
}

const exactChineseTranslations = new Map<string, string>([
  ["Scale Content Without Writing", "不用从零写稿，也能规模化内容"],
  ["Find Your Edge with Moras", "用 Moras 找到你的优势"],
  ["The Blank Page Solution", "空白页解决方案"],
  ["Workflow Efficiency & Trial-and-Error Reduction", "工作流提效与减少试错"],
  ["Secret / Exposed", "秘密 / 揭示"],
  ["3-step logic structure", "三步逻辑结构"],
  ["Competitive advantage hook", "竞争优势钩子"],
  ["Shoppable Video Workflow", "商品视频工作流"],
  ["Beginner Trap", "新手陷阱"],
  ["Before/After structure", "前后对比结构"],
  ["Contrarian hook", "反常识钩子"],
  ["Save CTA", "收藏 CTA"],
  ["Creator desk workflow scene", "创作者桌面工作流场景"],
  ["Absurd visual hook", "荒诞画面钩子"],
  ["Angle clarity plan", "卖点清晰计划"],
  ["Blank-page relief CTA", "空白页缓解 CTA"],
  ["Mini-drama hook", "小剧场钩子"],
  ["Blank-page script rescue", "空白页脚本救援"],
  ["Draft-before-filming CTA", "草稿复查 CTA"],
  ["Creator talking-head scene", "创作者口播场景"],
  ["POV hook", "POV 钩子"],
  ["Late-night product post", "深夜商品发布"],
  ["Product-note cleanup CTA", "商品笔记清理 CTA"],
  ["Desk-and-phone scene", "桌面和手机场景"],
  ["Product-to-video hook", "商品到视频钩子"],
  ["Creator proof filter", "达人证明筛选"],
  ["Proof placement hook", "证明位置钩子"],
  ["Screenshot timing plan", "截图时机计划"],
  ["Three-second hook", "三秒钩子"],
  ["Offer clarity check", "卖点清晰度检查"],
  ["Desk reset hook", "桌面重启钩子"],
  ["Complexity cleanup", "复杂度清理"],
  ["Angle split hook", "角度分叉钩子"],
  ["Two-angle posting", "双角度发布"],
  ["Rewrite-loop hook", "改稿循环钩子"],
  ["Opening variation plan", "开头变体计划"],
  ["First-shot hook", "第一镜钩子"],
  ["Opening visual confidence", "开场画面信心"],
  ["Posting-session CTA", "内容发布 CTA"],
  ["Moras draft workflow scene", "Moras 草稿工作流场景"],
  ["Reusable Moras creator persona", "可复用 Moras 创作者人设"],
  ["Practical creator friend", "实用型创作者朋友"],
  ["Efficiency Expert persona", "效率型创作者人设"],
  ["Skeptical Reviewer persona", "谨慎评测者人设"],
  ["Efficiency Expert", "效率型创作者"],
  ["Skeptical Reviewer", "谨慎评测者"],
  ["Pain point exemption hook", "痛点豁免钩子"],
  ["Simple workflow demonstration", "简单工作流演示"],
  ["Product Picking", "选品"],
  ["Workflow", "工作流"],
  ["Product Picking / Workflow", "选品 / 工作流"],
  ["Comment Reply / Objection Response", "评论回复 / 异议回应"],
  ["Pain point identification", "痛点识别"],
  ["Direct-to-camera coaching style", "直面镜头指导风格"],
  ["Beginner KOC", "新手 KOC"],
  ["Beginner KOCs", "新手 KOC"],
  ["Professional Operations", "专业运营"],
  ["Lazy-but-Ambitious Creators", "想偷懒但有野心的创作者"],
  ["Tech Reviewer", "科技评测博主"],
  ["Tutorial Learner", "教程学习者"],
  ["Empathetic Coach", "共情型教练"],
  ["Pain Point Exemption & Workflow Speed", "痛点消除与工作流提速"],
  ["Anxiety about competition, relief through a structured solution", "对竞争焦虑，通过结构化方案获得缓解"],
  ["Anxiety about competition, relief through a 结构化 solution", "对竞争焦虑，通过结构化方案获得缓解"],
  ["Don't know how to turn selected products into videos that can earn", "不知道怎么把选中的商品变成能赚钱的视频"],
  [
    "Why are 500 other affiliates selling the exact same product, but you're getting zero views? I'll give you your competitive advantage in 15 seconds.",
    "为什么还有 500 个达人在卖同款产品，而你却没有播放量？我用 15 秒给你一个竞争优势。",
  ],
  [
    "Creator sitting at a desk, looking directly at the camera. Fast cuts to a laptop screen showing the Moras workflow, then back to the creator holding a notebook.",
    "创作者坐在桌前直视镜头。快速切到笔记本电脑屏幕，展示 Moras 工作流，再切回创作者拿着笔记本的画面。",
  ],
  [
    "Step one: Stop writing scripts from zero. You are losing posting windows.",
    "第一步：停止从零写脚本。你正在错过发布时间。",
  ],
  [
    "Step two: Turn more selected products into videos you can post.",
    "第二步：把更多选中的商品变成可以发布的视频。",
  ],
  [
    "Step three: Pick the product in Moras, hit Generate, and review the video Moras made.",
    "第三步：在 Moras 选商品，点击 Generate，检查 Moras 做出的视频。",
  ],
  [
    "It gives you a video to review with the commerce path visible, not a fixed-result promise.",
    "它会给你一条可检查的视频，并展示带货路径，但不承诺固定结果。",
  ],
  [
    "Comment 'WORKFLOW' and I'll send you the tool to speed up your content creation.",
    "评论「WORKFLOW」，我把这个提升内容创作效率的工具发给你。",
  ],
  [
    "Your Competitive Advantage / Step 1: Stop writing from zero / Step 2: Post more product videos / Step 3: Moras AI Agent / Comment 'WORKFLOW'",
    "你的竞争优势 / 第一步：停止从零写稿 / 第二步：发布更多商品视频 / 第三步：Moras AI 智能体 / 评论「WORKFLOW」",
  ],
  [
    "Moras workflow screen recording showing product selection, Generate, the completed video, and the posting entry.",
    "展示 Moras 工作流录屏：选品、Generate、完成视频和发布入口。",
  ],
  ["Comment 'WORKFLOW' for access.", "评论「WORKFLOW」获取入口。"],
  [
    "Avoided any income guarantees. Focused on workflow speed, video output, and posting path.",
    "避免任何收入承诺，只聚焦工作流提速、出片和发布路径。",
  ],
  [
    "How to use Moras product selection and Generate to create a product video with a commerce path.",
    "如何用 Moras 选商品并点击 Generate，生成带带货路径的商品视频。",
  ],
  [
    "Creator wearing a bright hoodie, standing in front of a dual-monitor setup. Fast-paced cuts showing the screen recording of the Moras interface generating a script.",
    "创作者穿着亮色连帽衫，站在双显示器工作台前。快速剪辑展示 Moras 界面自动生成脚本的录屏。",
  ],
  [
    "If you want to make money with TikTok Shop, you need more product videos. But writing takes forever.",
    "如果你想用 TikTok Shop 赚钱，你需要更多商品视频。但写稿太耗时间。",
  ],
  ["Here is the product-to-video workflow.", "这就是商品到视频工作流。"],
  [
    "First, choose the product in Moras. Second, tap Create video or Custom Create.",
    "第一，在 Moras 选择商品。第二，点击 Create video 或 Custom Create。",
  ],
  [
    "Moras creates the product video, shows the commerce path, and gives you review controls if needed.",
    "Moras 会生成商品视频，展示带货路径，并在需要时提供检查控件。",
  ],
  [
    "It gives you visual cues, voiceover, and hooks to review before cleanup.",
    "它会给你可复查的画面提示、口播和开头钩子，再进入清理。",
  ],
  [
    "Follow me for more tools to speed up your content creation.",
    "关注我，获取更多提升内容创作效率的工具。",
  ],
  [
    "Stop staring at a blank page. If you want to make product videos but don't know what to say, watch this.",
    "别再盯着空白页发呆了。如果你想做商品视频但不知道说什么，看这个。",
  ],
  [
    "Starts with the creator looking frustrated with their head in their hands. Transitions to them smiling and holding up a smartphone showing the Moras dashboard.",
    "开头是创作者双手抱头、表情沮丧。随后转场到创作者微笑举起手机，展示 Moras 仪表盘。",
  ],
  ["The biggest mistake creators make is trying to be copywriters.", "创作者最大的误区，是把自己当成专业文案。"],
  [
    "You don't need to write from zero. You need a workflow that gets product videos posted.",
    "你不需要从零写稿。你需要的是一套能把商品视频发出去的流程。",
  ],
  [
    "Enter Moras. You choose a product, hit Generate, and review the video Moras made.",
    "进入 Moras。你选择商品，点击 Generate，检查 Moras 做出的视频。",
  ],
  [
    "It gives you the product video, commerce path, and posting path from the product workflow.",
    "它会从商品流程里给你商品视频、带货路径和发布路径。",
  ],
  ["Less trial and error, more drafts to review before chasing ten angles.", "少一点试错，多一点追十个角度前可检查的视频草稿。"],
  ["Save this video and try Moras for your next content day.", "收藏这条视频，下次内容日试试 Moras。"],
]);

const phraseChineseTranslations: Array<[string, string]> = [
  ["Beginner Trap", "新手陷阱"],
  ["Before/After structure", "前后对比结构"],
  ["Reusable Moras creator persona", "可复用 Moras 创作者人设"],
  ["Efficiency Expert", "效率型创作者"],
  ["Skeptical Reviewer", "谨慎评测者"],
  ["Relief and excitement about a faster, easier process", "更快、更轻松流程带来的松弛和兴奋"],
  ["Writing scripts takes too much time", "写脚本太耗时"],
  ["lack of copywriting skills", "缺少文案能力"],
  ["ready-to-post shoppable videos", "可检查商品视频"],
  ["shoppable video drafts", "商品视频草稿"],
  ["shoppable videos", "商品视频"],
  ["single script from zero", "从零写脚本"],
  ["Moras AI agent", "Moras AI 智能体"],
  ["reviewable shoppable video drafts", "可检查的商品视频草稿"],
  ["ready-to-post video with cart", "带带货路径的可检查视频"],
  ["structured", "结构化"],
  ["visual cues", "画面提示"],
  ["voiceover", "口播"],
  ["hooks", "开头钩子"],
  ["workflow", "工作流"],
  ["creator", "创作者"],
  ["content creation", "内容创作"],
  ["product data", "商品数据"],
  ["screen recording", "录屏"],
  ["dual-monitor setup", "双显示器工作台"],
];

const assetModeChineseLabels = new Map<string, string>([
  ["real_moras_screen_recording", "真实 Moras 录屏"],
  ["real_moras_screenshot", "真实 Moras 截图"],
  ["moras_product_workflow", "Moras 产品工作流"],
  ["ai_generated_broll", "AI 生成补充画面"],
  ["digital_human_avatar", "数字人提示词素材"],
  ["live_creator_footage", "实拍创作者素材（需人工上传）"],
  ["post_production_overlay", "后期叠加元素"],
  ["sound_design", "音效设计"],
]);

const assetCategoryChineseLabels = new Map<string, string>([
  ["workflow_screen_recording", "工作流录屏"],
  ["product_card_to_video_draft_before_after", "选中商品到视频草稿前后对比"],
  ["product_to_script_before_after", "商品到脚本前后对比（旧）"],
  ["time_saved_comparison", "节省时间对比"],
  ["product_selection_logic", "选品逻辑"],
  ["published_content_feedback", "已发布内容反馈"],
  ["approved_feature_screenshot", "已批准功能截图"],
]);

const assetLayerChineseLabels = new Map<string, string>([
  ["base_track", "底层画面"],
  ["cutaway", "切入素材"],
  ["overlay", "后期叠加"],
  ["audio", "音频层"],
]);

function tagTone(index: number): "blue" | "green" | "amber" | "rose" | "violet" | "slate" {
  const tones = ["blue", "green", "amber", "rose", "violet", "slate"] as const;
  return tones[index % tones.length];
}

export default ScriptEditorialPage;
