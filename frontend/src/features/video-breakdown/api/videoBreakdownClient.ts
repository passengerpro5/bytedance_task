import {
  ApiBreakdownRecord,
  ApiCreatorPersonaRecord,
  ApiDirectorGenerationJobRecord,
  ApiDirectorPlanRecord,
  ApiDirectorPlanAssetBindingRecord,
  ApiDirectorPublishRecord,
  ApiDirectorRenderArtifactRecord,
  ApiDirectorRenderJobRecord,
  ApiDirectorRenderUsageRecord,
  ApiManualFactoryAssetRecord,
  ApiMorasAssetLibraryRecord,
  ApiPersonaGenerationJobRecord,
  ApiScriptGenerationJobRecord,
  ApiScriptRecord,
  Classification,
  CreatorPersonaRecord,
  DirectorGenerationJobRecord,
  DirectorPlanAssetBindingRecord,
  DirectorPlanRecord,
  DirectorPublishRecord,
  DirectorRenderArtifactRecord,
  DirectorRenderJobRecord,
  DirectorRenderUsageRecord,
  Decomposition,
  JsonObject,
  JsonValue,
  ManualFactoryAssetRecord,
  MorasAssetLibraryRecord,
  PersonaGenerationJobRecord,
  ScriptAgentBridge,
  ScriptGenerationJobRecord,
  ScriptRecord,
  SocialVideoAnalysis,
  SourceVideo,
} from "../types";

export const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

const TERMINAL_STATUSES = new Set(["succeeded", "failed"]);
const POLL_INTERVAL_MS = 2000;
const MAX_POLL_ATTEMPTS = 180;

export const videoBreakdownClient = {
  async createSocialVideoAnalysis(videoUrl: string): Promise<SocialVideoAnalysis> {
    const created = fromApiBreakdownRecord(
      await request<ApiBreakdownRecord>("/api/breakdowns", {
        method: "POST",
        body: JSON.stringify({ video_url: videoUrl }),
      }),
    );

    if (TERMINAL_STATUSES.has(created.status)) return created;
    return pollSocialVideoAnalysis(created.id);
  },

  async uploadSocialVideoAnalysis(file: File): Promise<SocialVideoAnalysis> {
    const body = new FormData();
    body.append("file", file);
    const created = fromApiBreakdownRecord(
      await request<ApiBreakdownRecord>("/api/breakdowns/upload", {
        method: "POST",
        body,
      }),
    );

    if (TERMINAL_STATUSES.has(created.status)) return created;
    return pollSocialVideoAnalysis(created.id);
  },

  async getSocialVideoAnalysis(id: string): Promise<SocialVideoAnalysis> {
    return fromApiBreakdownRecord(
      await request<ApiBreakdownRecord>(`/api/breakdowns/${encodeURIComponent(id)}`),
    );
  },

  async listSocialVideoAnalyses(): Promise<SocialVideoAnalysis[]> {
    const records = await request<ApiBreakdownRecord[]>("/api/breakdowns");
    return records.map(fromApiBreakdownRecord);
  },

  async deleteSocialVideoAnalysis(id: string): Promise<void> {
    await request<null>(`/api/breakdowns/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  async listScripts(): Promise<ScriptRecord[]> {
    const records = await request<ApiScriptRecord[]>("/api/scripts");
    return records.map(fromApiScriptRecord);
  },

  async getScript(scriptId: string): Promise<ScriptRecord> {
    const record = await request<ApiScriptRecord>(`/api/scripts/${encodeURIComponent(scriptId)}`);
    return fromApiScriptRecord(record);
  },

  async createScriptGenerationJob(payload: {
    scriptCount: number;
    scriptType: string;
    sourceBreakdownIds?: string[];
    personaId?: string;
    personaHint?: JsonObject;
  }): Promise<ScriptGenerationJobRecord> {
    const record = await request<ApiScriptGenerationJobRecord>("/api/script-generation-jobs", {
      method: "POST",
      body: JSON.stringify({
        script_count: payload.scriptCount,
        script_type: payload.scriptType,
        source_breakdown_ids: payload.sourceBreakdownIds ?? [],
        persona_id: payload.personaId,
        persona_hint: payload.personaHint ?? {},
      }),
    });
    return fromApiScriptGenerationJobRecord(record);
  },

  async listCreatorPersonas(): Promise<CreatorPersonaRecord[]> {
    const records = await request<ApiCreatorPersonaRecord[]>("/api/creator-personas");
    return records.map(fromApiCreatorPersonaRecord);
  },

  async generateCreatorPersonas(payload: {
    personaCount: number;
  }): Promise<CreatorPersonaRecord[]> {
    const records = await request<ApiCreatorPersonaRecord[]>("/api/creator-personas/generate", {
      method: "POST",
      body: JSON.stringify({ persona_count: payload.personaCount }),
    });
    return records.map(fromApiCreatorPersonaRecord);
  },

  async createPersonaGenerationJob(payload: {
    personaCount: number;
    topicOrBrandContext?: string;
    targetAudience?: string;
    requiredDemographic?: string | null;
  }): Promise<PersonaGenerationJobRecord> {
    const record = await request<ApiPersonaGenerationJobRecord>("/api/persona-generation-jobs", {
      method: "POST",
      body: JSON.stringify({
        persona_count: payload.personaCount,
        topic_or_brand_context: payload.topicOrBrandContext,
        target_audience: payload.targetAudience,
        required_demographic: payload.requiredDemographic,
      }),
    });
    return fromApiPersonaGenerationJobRecord(record);
  },

  async listPersonaGenerationJobs(): Promise<PersonaGenerationJobRecord[]> {
    const records = await request<ApiPersonaGenerationJobRecord[]>("/api/persona-generation-jobs");
    return records.map(fromApiPersonaGenerationJobRecord);
  },

  async getPersonaGenerationJob(id: string): Promise<PersonaGenerationJobRecord> {
    const record = await request<ApiPersonaGenerationJobRecord>(`/api/persona-generation-jobs/${encodeURIComponent(id)}`);
    return fromApiPersonaGenerationJobRecord(record);
  },

  async deletePersonaGenerationJob(id: string): Promise<void> {
    await request<null>(`/api/persona-generation-jobs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  async retryPersonaGenerationJob(id: string): Promise<PersonaGenerationJobRecord> {
    return fromApiPersonaGenerationJobRecord(
      await request<ApiPersonaGenerationJobRecord>(`/api/persona-generation-jobs/${encodeURIComponent(id)}/retry`, {
        method: "POST",
      }),
    );
  },

  async editCreatorPersona(id: string, instruction: string): Promise<CreatorPersonaRecord> {
    const record = await request<ApiCreatorPersonaRecord>(`/api/creator-personas/${encodeURIComponent(id)}/edit`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    });
    return fromApiCreatorPersonaRecord(record);
  },

  async deleteCreatorPersona(id: string): Promise<void> {
    await request<null>(`/api/creator-personas/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  async listScriptGenerationJobs(): Promise<ScriptGenerationJobRecord[]> {
    const records = await request<ApiScriptGenerationJobRecord[]>("/api/script-generation-jobs");
    return records.map(fromApiScriptGenerationJobRecord);
  },

  async getScriptGenerationJob(id: string): Promise<ScriptGenerationJobRecord> {
    return fromApiScriptGenerationJobRecord(
      await request<ApiScriptGenerationJobRecord>(`/api/script-generation-jobs/${encodeURIComponent(id)}`),
    );
  },

  async deleteScriptGenerationJob(id: string): Promise<void> {
    await request<null>(`/api/script-generation-jobs/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  async retryScriptGenerationJob(id: string): Promise<ScriptGenerationJobRecord> {
    return fromApiScriptGenerationJobRecord(
      await request<ApiScriptGenerationJobRecord>(`/api/script-generation-jobs/${encodeURIComponent(id)}/retry`, {
        method: "POST",
      }),
    );
  },

  async generateScripts(payload: {
    scriptCount: number;
    scriptType: string;
    sourceBreakdownIds?: string[];
    personaId?: string;
    personaHint?: JsonObject;
  }): Promise<ScriptRecord[]> {
    const job = await videoBreakdownClient.createScriptGenerationJob(payload);
    const completedJob = await pollScriptGenerationJob(job.id);
    if (completedJob.status === "failed") {
      throw new Error(completedJob.errorMessage || "脚本生成失败。");
    }
    const scriptIds = new Set(completedJob.scriptIds.map(String));
    const scripts = await videoBreakdownClient.listScripts();
    return scripts.filter(script => scriptIds.has(script.id));
  },

  async editScript(id: string, instruction: string): Promise<ScriptRecord> {
    const record = await request<ApiScriptRecord>(`/api/scripts/${encodeURIComponent(id)}/edit`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    });
    return fromApiScriptRecord(record);
  },

  async deleteScript(id: string): Promise<void> {
    await request<null>(`/api/scripts/${encodeURIComponent(id)}`, {
      method: "DELETE",
    });
  },

  async generateDirectorPlan(scriptId: string): Promise<DirectorPlanRecord> {
    const record = await request<ApiDirectorPlanRecord>("/api/video-factory/director-plans", {
      method: "POST",
      body: JSON.stringify({ script_id: scriptId }),
    });
    return fromApiDirectorPlanRecord(record);
  },

  async createDirectorGenerationJob(scriptId: string): Promise<DirectorGenerationJobRecord> {
    const record = await request<ApiDirectorGenerationJobRecord>("/api/video-factory/director-generation-jobs", {
      method: "POST",
      body: JSON.stringify({ script_id: scriptId }),
    });
    return fromApiDirectorGenerationJobRecord(record);
  },

  async listDirectorGenerationJobs(
    scriptId?: string,
    includeSucceeded = false,
  ): Promise<DirectorGenerationJobRecord[]> {
    const params = new URLSearchParams();
    if (scriptId) params.set("script_id", scriptId);
    if (includeSucceeded) params.set("include_succeeded", "true");
    const query = params.toString();
    const records = await request<ApiDirectorGenerationJobRecord[]>(
      `/api/video-factory/director-generation-jobs${query ? `?${query}` : ""}`,
    );
    return records.map(fromApiDirectorGenerationJobRecord);
  },

  async getDirectorGenerationJob(jobId: string): Promise<DirectorGenerationJobRecord> {
    const record = await request<ApiDirectorGenerationJobRecord>(
      `/api/video-factory/director-generation-jobs/${encodeURIComponent(jobId)}`,
    );
    return fromApiDirectorGenerationJobRecord(record);
  },

  async cancelDirectorGenerationJob(jobId: string): Promise<DirectorGenerationJobRecord> {
    const record = await request<ApiDirectorGenerationJobRecord>(
      `/api/video-factory/director-generation-jobs/${encodeURIComponent(jobId)}/cancel`,
      { method: "POST" },
    );
    return fromApiDirectorGenerationJobRecord(record);
  },

  async retryDirectorGenerationJob(jobId: string): Promise<DirectorGenerationJobRecord> {
    const record = await request<ApiDirectorGenerationJobRecord>(
      `/api/video-factory/director-generation-jobs/${encodeURIComponent(jobId)}/retry`,
      { method: "POST" },
    );
    return fromApiDirectorGenerationJobRecord(record);
  },

  async listDirectorPlans(scriptId?: string): Promise<DirectorPlanRecord[]> {
    const params = new URLSearchParams();
    if (scriptId) params.set("script_id", scriptId);
    const query = params.toString();
    const records = await request<ApiDirectorPlanRecord[]>(
      `/api/video-factory/director-plans${query ? `?${query}` : ""}`,
    );
    return records.map(fromApiDirectorPlanRecord);
  },

  async getDirectorPlan(planId: string): Promise<DirectorPlanRecord> {
    const record = await request<ApiDirectorPlanRecord>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}`,
    );
    return fromApiDirectorPlanRecord(record);
  },

  async listManualFactoryAssets(planId: string): Promise<ManualFactoryAssetRecord[]> {
    const records = await request<ApiManualFactoryAssetRecord[]>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/manual-assets`,
    );
    return records.map(fromApiManualFactoryAssetRecord);
  },

  async uploadManualFactoryAsset(planId: string, clipId: string, file: File): Promise<ManualFactoryAssetRecord> {
    const body = new FormData();
    body.append("clip_id", clipId);
    body.append("file", file);
    const record = await request<ApiManualFactoryAssetRecord>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/manual-assets`,
      {
        method: "POST",
        body,
      },
    );
    return fromApiManualFactoryAssetRecord(record);
  },

  async reviewManualFactoryAsset(
    assetId: string,
    reviewStatus: "pending_review" | "approved" | "rejected",
    reviewNotes = "",
  ): Promise<ManualFactoryAssetRecord> {
    const record = await request<ApiManualFactoryAssetRecord>(
      `/api/video-factory/manual-assets/${encodeURIComponent(assetId)}/review`,
      {
        method: "POST",
        body: JSON.stringify({ review_status: reviewStatus, review_notes: reviewNotes }),
      },
    );
    return fromApiManualFactoryAssetRecord(record);
  },

  async reviewManualFactoryAssetSemanticMatch(
    assetId: string,
    status: "pending_review" | "passed" | "failed",
    notes = "",
    reviewer = "factory-operator",
    method = "human_prompt_match_v1",
  ): Promise<ManualFactoryAssetRecord> {
    const record = await request<ApiManualFactoryAssetRecord>(
      `/api/video-factory/manual-assets/${encodeURIComponent(assetId)}/semantic-review`,
      {
        method: "POST",
        body: JSON.stringify({ status, notes, reviewer, method }),
      },
    );
    return fromApiManualFactoryAssetRecord(record);
  },

  async listMorasAssets(filters: {
    assetType?: string;
    morasAssetCategory?: string;
  } = {}): Promise<MorasAssetLibraryRecord[]> {
    const params = new URLSearchParams();
    if (filters.assetType) params.set("asset_type", filters.assetType);
    if (filters.morasAssetCategory) params.set("moras_asset_category", filters.morasAssetCategory);
    const query = params.toString();
    const records = await request<ApiMorasAssetLibraryRecord[]>(
      `/api/video-factory/moras-assets${query ? `?${query}` : ""}`,
    );
    return records.map(fromApiMorasAssetLibraryRecord);
  },

  async uploadMorasAsset(payload: {
    assetType: string;
    morasAssetCategory: string;
    title?: string;
    file: File;
  }): Promise<MorasAssetLibraryRecord> {
    const body = new FormData();
    body.append("asset_type", payload.assetType);
    body.append("moras_asset_category", payload.morasAssetCategory);
    if (payload.title) body.append("title", payload.title);
    body.append("file", payload.file);
    const record = await request<ApiMorasAssetLibraryRecord>("/api/video-factory/moras-assets", {
      method: "POST",
      body,
    });
    return fromApiMorasAssetLibraryRecord(record);
  },

  async reviewMorasAsset(
    assetId: string,
    reviewStatus: "pending_review" | "approved" | "rejected",
    reviewNotes = "",
  ): Promise<MorasAssetLibraryRecord> {
    const record = await request<ApiMorasAssetLibraryRecord>(
      `/api/video-factory/moras-assets/${encodeURIComponent(assetId)}/review`,
      {
        method: "POST",
        body: JSON.stringify({ review_status: reviewStatus, review_notes: reviewNotes }),
      },
    );
    return fromApiMorasAssetLibraryRecord(record);
  },

  async reviewMorasAssetSemanticMatch(
    assetId: string,
    status: "pending_review" | "passed" | "failed",
    notes = "",
    reviewer = "factory-operator",
    method = "human_prompt_match_v1",
  ): Promise<MorasAssetLibraryRecord> {
    const record = await request<ApiMorasAssetLibraryRecord>(
      `/api/video-factory/moras-assets/${encodeURIComponent(assetId)}/semantic-review`,
      {
        method: "POST",
        body: JSON.stringify({ status, notes, reviewer, method }),
      },
    );
    return fromApiMorasAssetLibraryRecord(record);
  },

  async listDirectorPlanAssetBindings(planId: string): Promise<DirectorPlanAssetBindingRecord[]> {
    const records = await request<ApiDirectorPlanAssetBindingRecord[]>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/asset-bindings`,
    );
    return records.map(fromApiDirectorPlanAssetBindingRecord);
  },

  async bindDirectorPlanAsset(
    planId: string,
    assetRef: string,
    libraryAssetId: string,
  ): Promise<DirectorPlanAssetBindingRecord> {
    const record = await request<ApiDirectorPlanAssetBindingRecord>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/asset-bindings`,
      {
        method: "POST",
        body: JSON.stringify({
          asset_ref: assetRef,
          library_asset_id: libraryAssetId,
        }),
      },
    );
    return fromApiDirectorPlanAssetBindingRecord(record);
  },

  async listDirectorRenderJobs(planId: string): Promise<DirectorRenderJobRecord[]> {
    const records = await request<ApiDirectorRenderJobRecord[]>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/render-jobs`,
    );
    return records.map(fromApiDirectorRenderJobRecord);
  },

  async getDirectorRenderJob(renderJobId: string): Promise<DirectorRenderJobRecord> {
    const record = await request<ApiDirectorRenderJobRecord>(
      `/api/video-factory/render-jobs/${encodeURIComponent(renderJobId)}`,
    );
    return fromApiDirectorRenderJobRecord(record);
  },

  async listDirectorRenderArtifacts(renderJobId: string): Promise<DirectorRenderArtifactRecord[]> {
    const records = await request<ApiDirectorRenderArtifactRecord[]>(
      `/api/video-factory/render-jobs/${encodeURIComponent(renderJobId)}/artifacts`,
    );
    return records.map(fromApiDirectorRenderArtifactRecord);
  },

  async cleanupExpiredDirectorRenderArtifacts(renderJobId: string): Promise<DirectorRenderArtifactRecord[]> {
    const records = await request<ApiDirectorRenderArtifactRecord[]>(
      `/api/video-factory/render-jobs/${encodeURIComponent(renderJobId)}/artifacts/cleanup-expired`,
      { method: "POST" },
    );
    return records.map(fromApiDirectorRenderArtifactRecord);
  },

  async deleteDirectorRenderArtifact(artifactId: string): Promise<DirectorRenderArtifactRecord> {
    const record = await request<ApiDirectorRenderArtifactRecord>(
      `/api/video-factory/render-artifacts/${encodeURIComponent(artifactId)}`,
      { method: "DELETE" },
    );
    return fromApiDirectorRenderArtifactRecord(record);
  },

  async getDirectorRenderUsage(renderJobId: string): Promise<DirectorRenderUsageRecord | null> {
    const record = await request<ApiDirectorRenderUsageRecord | null>(
      `/api/video-factory/render-jobs/${encodeURIComponent(renderJobId)}/usage`,
    );
    return record ? fromApiDirectorRenderUsageRecord(record) : null;
  },

  async createDirectorRenderJob(planId: string): Promise<DirectorRenderJobRecord> {
    const record = await request<ApiDirectorRenderJobRecord>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/render-jobs`,
      { method: "POST" },
    );
    return fromApiDirectorRenderJobRecord(record);
  },

  async retryDirectorRenderJob(renderJobId: string): Promise<DirectorRenderJobRecord> {
    const record = await request<ApiDirectorRenderJobRecord>(
      `/api/video-factory/render-jobs/${encodeURIComponent(renderJobId)}/retry`,
      { method: "POST" },
    );
    return fromApiDirectorRenderJobRecord(record);
  },

  async reviewDirectorRenderJobQa(
    renderJobId: string,
    qaReviewStatus: "pending_review" | "approved" | "rejected",
    qaReviewNotes = "",
  ): Promise<DirectorRenderJobRecord> {
    const record = await request<ApiDirectorRenderJobRecord>(
      `/api/video-factory/render-jobs/${encodeURIComponent(renderJobId)}/qa-review`,
      {
        method: "POST",
        body: JSON.stringify({
          qa_review_status: qaReviewStatus,
          qa_review_notes: qaReviewNotes,
        }),
      },
    );
    return fromApiDirectorRenderJobRecord(record);
  },

  async listDirectorPublishRecords(planId: string): Promise<DirectorPublishRecord[]> {
    const records = await request<ApiDirectorPublishRecord[]>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/publish-records`,
    );
    return records.map(fromApiDirectorPublishRecord);
  },

  async createDirectorPublishRecord(planId: string, payload: {
    renderJobId: string;
    channel?: string;
    publishStatus?: string;
    caption?: string;
    scheduledAt?: string | null;
    publishedUrl?: string | null;
    notes?: string;
  }): Promise<DirectorPublishRecord> {
    const record = await request<ApiDirectorPublishRecord>(
      `/api/video-factory/director-plans/${encodeURIComponent(planId)}/publish-records`,
      {
        method: "POST",
        body: JSON.stringify({
          render_job_id: payload.renderJobId,
          channel: payload.channel ?? "manual_upload",
          publish_status: payload.publishStatus ?? "ready_for_upload",
          caption: payload.caption ?? "",
          scheduled_at: payload.scheduledAt ?? null,
          published_url: payload.publishedUrl ?? null,
          notes: payload.notes ?? "",
        }),
      },
    );
    return fromApiDirectorPublishRecord(record);
  },

  markdownExportUrl(id: string): string {
    return `${API_BASE}/api/breakdowns/${encodeURIComponent(id)}/export/markdown`;
  },
};

async function pollSocialVideoAnalysis(id: string): Promise<SocialVideoAnalysis> {
  let latest = await videoBreakdownClient.getSocialVideoAnalysis(id);
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    if (TERMINAL_STATUSES.has(latest.status)) return latest;
    await delay(POLL_INTERVAL_MS);
    latest = await videoBreakdownClient.getSocialVideoAnalysis(id);
  }
  return latest;
}

async function pollScriptGenerationJob(id: string): Promise<ScriptGenerationJobRecord> {
  let latest = await videoBreakdownClient.getScriptGenerationJob(id);
  for (let attempt = 0; attempt < MAX_POLL_ATTEMPTS; attempt += 1) {
    if (latest.status === "succeeded" || latest.status === "failed") return latest;
    await delay(POLL_INTERVAL_MS);
    latest = await videoBreakdownClient.getScriptGenerationJob(id);
  }
  return latest;
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = init.body instanceof FormData
    ? init.headers
    : { "Content-Type": "application/json", ...(init.headers ?? {}) };
  const response = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers,
  });
  const text = await response.text();
  if (!response.ok) {
    throw new Error(readErrorMessage(text) || `请求失败：${response.status}`);
  }
  return (text ? JSON.parse(text) : null) as T;
}

function fromApiBreakdownRecord(api: ApiBreakdownRecord): SocialVideoAnalysis {
  return {
    id: api.id,
    status: api.status,
    provider: api.provider,
    reusedExisting: Boolean(api.reused_existing),
    errorMessage: api.error_message ?? null,
    sourceVideo: toJsonObject(camelizeValue(api.source_video)) as SourceVideo | null,
    classification: toJsonObject(camelizeValue(api.classification)) as Classification | null,
    decomposition: toJsonObject(camelizeValue(api.decomposition)) as Decomposition | null,
    structureProtocol: camelizeValue(api.structure_protocol),
    scriptAgentBridge: toJsonObject(camelizeValue(api.script_agent_bridge)) as ScriptAgentBridge | null,
    referenceStoryboard: Array.isArray(api.reference_storyboard)
      ? (camelizeValue(api.reference_storyboard) as JsonValue[]).filter(item => item && typeof item === "object" && !Array.isArray(item)) as SocialVideoAnalysis["referenceStoryboard"]
      : [],
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiScriptRecord(api: ApiScriptRecord): ScriptRecord {
  return {
    id: api.id,
    status: api.status,
    provider: api.provider,
    modelName: api.model_name,
    scriptType: api.script_type,
    sourceBreakdownIds: camelizeValue(api.source_breakdown_ids ?? []) as JsonValue[],
    topicPlan: toJsonObject(camelizeValue(api.topic_plan)) ?? {},
    script: toJsonObject(camelizeValue(api.script)) ?? {},
    storyboard: (camelizeValue(api.storyboard) as JsonValue[] | null ?? []).filter(isJsonObject),
    creatorPersona: toJsonObject(camelizeValue(api.creator_persona)) ?? {},
    videoPrompt: toJsonObject(camelizeValue(api.video_prompt)) ?? {},
    productionAssetPlan: (camelizeValue(api.production_asset_plan ?? []) as JsonValue[] | null ?? []).filter(isJsonObject),
    riskCheck: toJsonObject(camelizeValue(api.risk_check)) ?? {},
    sourceComponentSummary: camelizeValue(api.source_component_summary ?? []) as JsonValue[],
    revisionHistory: (camelizeValue(api.revision_history ?? []) as JsonValue[] | null ?? []).filter(isJsonObject),
    errorMessage: api.error_message ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiScriptGenerationJobRecord(api: ApiScriptGenerationJobRecord): ScriptGenerationJobRecord {
  const scriptIds = camelizeValue(api.script_ids ?? []) as JsonValue[];
  return {
    id: api.id,
    status: api.status,
    scriptCount: api.script_count,
    scriptType: api.script_type,
    sourceBreakdownIds: camelizeValue(api.source_breakdown_ids ?? []) as JsonValue[],
    personaId: api.persona_id ?? null,
    personaHint: toJsonObject(camelizeValue(api.persona_hint)) ?? {},
    completedCount: api.completed_count ?? scriptIds.length,
    scriptIds,
    errorMessage: api.error_message ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiPersonaGenerationJobRecord(api: ApiPersonaGenerationJobRecord): PersonaGenerationJobRecord {
  return {
    id: api.id,
    status: api.status,
    personaCount: api.persona_count,
    topicOrBrandContext: api.topic_or_brand_context,
    targetAudience: api.target_audience,
    requiredDemographic: api.required_demographic ?? null,
    completedCount: api.completed_count,
    personaIds: camelizeValue(api.persona_ids ?? []) as JsonValue[],
    errorMessage: api.error_message ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiCreatorPersonaRecord(api: ApiCreatorPersonaRecord): CreatorPersonaRecord {
  return {
    id: api.id,
    status: api.status,
    provider: api.provider,
    modelName: api.model_name,
    creatorPersona: toJsonObject(camelizeValue(api.creator_persona)) ?? {},
    sourceScriptIds: camelizeValue(api.source_script_ids ?? []) as JsonValue[],
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorPlanRecord(api: ApiDirectorPlanRecord): DirectorPlanRecord {
  return {
    id: api.id,
    scriptId: api.script_id,
    status: api.status,
    provider: api.provider,
    modelName: api.model_name,
    promptVersion: api.prompt_version,
    metadata: toJsonObject(camelizeValue(api.metadata)) ?? {},
    timeline: toJsonObject(camelizeValue(api.timeline)) ?? {},
    assetResolution: (camelizeValue(api.asset_resolution ?? []) as JsonValue[] | null ?? []).filter(isJsonObject),
    toolDispatches: (camelizeValue(api.tool_dispatches ?? []) as JsonValue[] | null ?? []).filter(isJsonObject),
    validationSummary: toJsonObject(camelizeValue(api.validation_summary)) ?? {},
    errorMessage: api.error_message ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorGenerationJobRecord(api: ApiDirectorGenerationJobRecord): DirectorGenerationJobRecord {
  return {
    id: api.id,
    status: api.status,
    scriptId: api.script_id,
    directorPlanId: api.director_plan_id ?? null,
    errorMessage: api.error_message ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiManualFactoryAssetRecord(api: ApiManualFactoryAssetRecord): ManualFactoryAssetRecord {
  return {
    id: api.id,
    directorPlanId: api.director_plan_id,
    scriptId: api.script_id,
    clipId: api.clip_id,
    sourceReferenceId: api.source_reference_id,
    assetRole: api.asset_role,
    originalFilename: api.original_filename,
    storedAssetUrl: api.stored_asset_url,
    mimeType: api.mime_type,
    fileSizeBytes: api.file_size_bytes,
    durationSec: api.duration_sec,
    width: api.width,
    height: api.height,
    validationStatus: api.validation_status,
    reviewStatus: api.review_status,
    reviewNotes: api.review_notes,
    reviewedAt: api.reviewed_at ?? null,
    semanticReviewStatus: api.semantic_review_status ?? "pending_review",
    semanticReviewNotes: api.semantic_review_notes ?? "",
    semanticReviewMethod: api.semantic_review_method ?? "human_prompt_match_v1",
    semanticReviewReviewer: api.semantic_review_reviewer ?? "",
    semanticReviewedAt: api.semantic_reviewed_at ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiMorasAssetLibraryRecord(api: ApiMorasAssetLibraryRecord): MorasAssetLibraryRecord {
  return {
    id: api.id,
    assetType: api.asset_type,
    morasAssetCategory: api.moras_asset_category,
    title: api.title,
    originalFilename: api.original_filename,
    storedAssetUrl: api.stored_asset_url,
    mimeType: api.mime_type,
    fileSizeBytes: api.file_size_bytes,
    durationSec: api.duration_sec,
    width: api.width,
    height: api.height,
    validationStatus: api.validation_status,
    reviewStatus: api.review_status,
    reviewNotes: api.review_notes,
    reviewedAt: api.reviewed_at ?? null,
    semanticReviewStatus: api.semantic_review_status ?? "pending_review",
    semanticReviewNotes: api.semantic_review_notes ?? "",
    semanticReviewMethod: api.semantic_review_method ?? "human_prompt_match_v1",
    semanticReviewReviewer: api.semantic_review_reviewer ?? "",
    semanticReviewedAt: api.semantic_reviewed_at ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorPlanAssetBindingRecord(api: ApiDirectorPlanAssetBindingRecord): DirectorPlanAssetBindingRecord {
  return {
    id: api.id,
    directorPlanId: api.director_plan_id,
    scriptId: api.script_id,
    assetRef: api.asset_ref,
    sourcePlanId: api.source_plan_id,
    libraryAssetId: api.library_asset_id,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorRenderJobRecord(api: ApiDirectorRenderJobRecord): DirectorRenderJobRecord {
  return {
    id: api.id,
    directorPlanId: api.director_plan_id,
    scriptId: api.script_id,
    status: api.status,
    outputAssetUrl: api.output_asset_url ?? null,
    outputFilename: api.output_filename ?? null,
    outputAudioUrl: api.output_audio_url ?? null,
    outputSubtitleUrl: api.output_subtitle_url ?? null,
    fileSizeBytes: api.file_size_bytes,
    durationSec: api.duration_sec,
    width: api.width,
    height: api.height,
    readinessSummary: toJsonObject(camelizeValue(api.readiness_summary)) ?? {},
    qaSummary: toJsonObject(camelizeValue(api.qa_summary)) ?? {},
    qaReviewStatus: api.qa_review_status ?? "pending_review",
    qaReviewNotes: api.qa_review_notes ?? "",
    qaReviewedAt: api.qa_reviewed_at ?? null,
    errorMessage: api.error_message ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorRenderArtifactRecord(api: ApiDirectorRenderArtifactRecord): DirectorRenderArtifactRecord {
  return {
    id: api.id,
    renderJobId: api.render_job_id,
    directorPlanId: api.director_plan_id,
    scriptId: api.script_id,
    artifactType: api.artifact_type,
    assetUrl: api.asset_url,
    filename: api.filename,
    mimeType: api.mime_type,
    fileSizeBytes: api.file_size_bytes,
    durationSec: api.duration_sec,
    width: api.width,
    height: api.height,
    storageStatus: api.storage_status,
    retentionExpiresAt: api.retention_expires_at ?? null,
    deletedAt: api.deleted_at ?? null,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorRenderUsageRecord(api: ApiDirectorRenderUsageRecord): DirectorRenderUsageRecord {
  return {
    id: api.id,
    renderJobId: api.render_job_id,
    directorPlanId: api.director_plan_id,
    scriptId: api.script_id,
    inputClipCount: api.input_clip_count,
    outputDurationSec: api.output_duration_sec,
    outputBytes: api.output_bytes,
    subtitleCueCount: api.subtitle_cue_count,
    ttsCharacterCount: api.tts_character_count,
    renderEngine: api.render_engine,
    audioEngine: api.audio_engine,
    captionEngine: api.caption_engine,
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function fromApiDirectorPublishRecord(api: ApiDirectorPublishRecord): DirectorPublishRecord {
  return {
    id: api.id,
    directorPlanId: api.director_plan_id,
    scriptId: api.script_id,
    renderJobId: api.render_job_id,
    channel: api.channel,
    publishStatus: api.publish_status,
    caption: api.caption ?? "",
    scheduledAt: api.scheduled_at ?? null,
    publishedUrl: api.published_url ?? null,
    notes: api.notes ?? "",
    createdAt: api.created_at,
    updatedAt: api.updated_at,
  };
}

function camelizeValue(value: JsonValue | undefined | null): JsonValue | null {
  if (value === undefined || value === null) return null;
  if (Array.isArray(value)) return value.map(item => camelizeValue(item) as JsonValue);
  if (typeof value !== "object") return value;
  return Object.fromEntries(
    Object.entries(value).map(([key, child]) => [toCamelCase(key), camelizeValue(child)]),
  ) as JsonObject;
}

function toJsonObject(value: JsonValue | null): JsonObject | null {
  return value && typeof value === "object" && !Array.isArray(value) ? value : null;
}

function isJsonObject(value: JsonValue): value is JsonObject {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function toCamelCase(value: string): string {
  return value.replace(/_([a-z])/g, (_, letter: string) => letter.toUpperCase());
}

function readErrorMessage(text: string): string {
  if (!text) return "";
  try {
    const payload = JSON.parse(text) as { detail?: unknown; error?: unknown; message?: unknown };
    if (typeof payload.message === "string") return payload.message;
    if (typeof payload.error === "string") return payload.error;
    if (typeof payload.detail === "string") return payload.detail;
    if (payload.detail && typeof payload.detail === "object") {
      const detail = payload.detail as { message?: unknown; error?: { message?: unknown } };
      if (typeof detail.message === "string") return detail.message;
      if (typeof detail.error?.message === "string") return detail.error.message;
    }
  } catch {
    return text;
  }
  return text;
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => window.setTimeout(resolve, ms));
}
