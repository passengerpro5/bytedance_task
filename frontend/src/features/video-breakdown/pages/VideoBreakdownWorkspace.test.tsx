/** @vitest-environment jsdom */

import { act, cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { VideoBreakdownWorkspace } from "./VideoBreakdownWorkspace";
import { videoBreakdownClient } from "../api/videoBreakdownClient";

vi.mock("../api/videoBreakdownClient", () => ({
  API_BASE: "",
  videoBreakdownClient: {
    createSocialVideoAnalysis: vi.fn(),
    uploadSocialVideoAnalysis: vi.fn(),
    listSocialVideoAnalyses: vi.fn(),
    deleteSocialVideoAnalysis: vi.fn(),
    listScripts: vi.fn(),
    getScript: vi.fn(),
    listCreatorPersonas: vi.fn(),
    generateCreatorPersonas: vi.fn(),
    createPersonaGenerationJob: vi.fn(),
    listPersonaGenerationJobs: vi.fn(),
    getPersonaGenerationJob: vi.fn(),
    deletePersonaGenerationJob: vi.fn(),
    retryPersonaGenerationJob: vi.fn(),
    editCreatorPersona: vi.fn(),
    deleteCreatorPersona: vi.fn(),
    createScriptGenerationJob: vi.fn(),
    listScriptGenerationJobs: vi.fn(),
    getScriptGenerationJob: vi.fn(),
    deleteScriptGenerationJob: vi.fn(),
    retryScriptGenerationJob: vi.fn(),
    generateScripts: vi.fn(),
    editScript: vi.fn(),
    deleteScript: vi.fn(),
    generateDirectorPlan: vi.fn(),
    createDirectorGenerationJob: vi.fn(),
    listDirectorGenerationJobs: vi.fn(),
    getDirectorGenerationJob: vi.fn(),
    cancelDirectorGenerationJob: vi.fn(),
    retryDirectorGenerationJob: vi.fn(),
    getDirectorPlan: vi.fn(),
    listDirectorPlans: vi.fn(),
    listManualFactoryAssets: vi.fn(),
    uploadManualFactoryAsset: vi.fn(),
    reviewManualFactoryAsset: vi.fn(),
    reviewManualFactoryAssetSemanticMatch: vi.fn(),
    listMorasAssets: vi.fn(),
    uploadMorasAsset: vi.fn(),
    reviewMorasAsset: vi.fn(),
    reviewMorasAssetSemanticMatch: vi.fn(),
    listDirectorPlanAssetBindings: vi.fn(),
    bindDirectorPlanAsset: vi.fn(),
    listDirectorRenderJobs: vi.fn(),
    getDirectorRenderJob: vi.fn(),
    listDirectorRenderArtifacts: vi.fn(),
    cleanupExpiredDirectorRenderArtifacts: vi.fn(),
    deleteDirectorRenderArtifact: vi.fn(),
    getDirectorRenderUsage: vi.fn(),
    createDirectorRenderJob: vi.fn(),
    retryDirectorRenderJob: vi.fn(),
    reviewDirectorRenderJobQa: vi.fn(),
    listDirectorPublishRecords: vi.fn(),
    createDirectorPublishRecord: vi.fn(),
    markdownExportUrl: vi.fn((id: string) => `/api/breakdowns/${id}/export/markdown`),
  },
}));

const completedAnalysis = {
  id: "analysis-1",
  status: "succeeded",
  errorMessage: null,
  sourceVideo: {
    originalUrl: "https://www.tiktok.com/@demo/video/1",
    importedVideoUrl: "/uploads/social.mp4",
    title: "步骤清单演示视频",
    platform: "TikTok",
    creatorHandle: "@demo",
    durationSeconds: 38,
    observedMetrics: { likes: 1200 },
    contentSummary: "视频展示一组可保存的工具清单。",
  },
  classification: {
    taxonomyVersion: "moras_viral_factor_v1",
    hookType: "禁忌型",
    emotionFactors: ["焦虑", "好奇"],
    personaFactors: ["教程达人型"],
    sceneFactors: ["桌面工作流", "手机后台"],
    conflictFactors: ["她不是不努力，而是不知道正确方法。"],
    painFactors: ["每天都要想内容，太累", "不会写脚本"],
    itchFactors: ["想用更少时间发更多视频"],
    valueFactors: ["不用从零写脚本", "提高内容产出效率"],
    proofFactors: ["time saved proof"],
    ctaFactors: ["Save"],
    structureFactors: ["mistake list", "tutorial walkthrough"],
    visualRhythmFactors: ["0-3 秒能看懂主题", "有手机屏幕"],
    audienceSegments: ["Tutorial Learner"],
    generalTemplates: ["Mistake List"],
    verticalTemplates: ["Shoppable Video Workflow"],
    factorReasoning: "视频以禁忌式开头、编号步骤和屏幕演示作为主要表达机制。",
  },
  decomposition: {
    oneSentenceSummary: "用清单承诺留人。",
    hook: "别再一个个试工具了。",
    narrativeStructure: ["痛点提出", "步骤清单"],
    segments: [
      {
        segmentNo: 1,
        startSecond: 0,
        endSecond: 8,
        role: "开头留人",
        content: "展示问题场景。",
        technique: "大字幕快切。",
      },
    ],
    keyTakeaways: ["先承诺可保存结果。"],
  },
  structureProtocol: {
    corePattern: "[痛点] + [可保存结果承诺] + [编号步骤] + [收藏触发]",
    timelineSlots: [
      {
        slotId: "hook",
        name: "开头留人",
        role: "建立停留理由",
        observableEvidence: "首屏给出可保存承诺。",
        transferRule: "新主题前三秒必须给出明确收益。",
      },
    ],
    reuseRules: ["保留编号结构，不照搬原内容。"],
  },
  scriptAgentBridge: {
    reusablePattern: "先承诺可保存结果，再分步骤给出具体证据。",
    scriptAgentInstructions: ["只复用信息组织方式。"],
    variablesToCollect: ["目标主题"],
    doNotCopy: ["原口播句子"],
    adaptationNotes: ["先确认是否有足够可保存信息。"],
  },
  referenceStoryboard: [
    {
      shotId: "shot_1",
      timestamp: "0-4s",
      duration: "4s",
      camera: "Vertical close-up on the phone and creator's hand.",
      characterAction: "The creator pushes the phone into frame and points at the saveable checklist promise.",
      facialExpression: "Focused warning look.",
      background: "Desk workflow with phone, notes, and checklist overlay.",
      props: ["phone", "checklist"],
      voiceover: "Save this before you pick the next product.",
      overlay: "Save this checklist",
      sound: "Short tap sound.",
      bgm: "Low-volume upbeat loop starts under the hook.",
      soundEffects: ["tap", "hard cut hit"],
      subtitleLogic: "Hook caption appears immediately and stays short enough for silent viewers.",
      visualElements: ["checklist overlay", "pointing finger", "save cue"],
      visualElementLogic: "The checklist overlay and pointing gesture make the save promise visually obvious.",
      transition: "Hard cut into numbered steps.",
      purpose: "Turn the first seconds into a save-worthy promise.",
      localized: {
        zh: {
          duration: "4 秒",
          camera: "竖屏近景，聚焦手机和创作者手部。",
          characterAction: "创作者把手机推入画面，并指向可保存清单承诺。",
          facialExpression: "专注提醒的表情。",
          background: "桌面工作流，包含手机、笔记和清单字幕。",
          props: ["手机", "清单"],
          voiceover: "选下一个产品前先保存这条。",
          overlay: "先保存这张清单",
          sound: "短促点击音。",
          bgm: "低音量轻快循环音乐从开头进入。",
          soundEffects: ["点击声", "硬切提示音"],
          subtitleLogic: "钩子字幕立刻出现，并保持短句，方便静音观看。",
          visualElements: ["清单字幕", "指向手势", "保存提示"],
          visualElementLogic: "清单字幕和指向手势把保存承诺做成可见动作。",
          transition: "硬切进入编号步骤。",
          purpose: "把前三秒变成值得保存的承诺。",
        },
      },
    },
    {
      shotId: "shot_2",
      timestamp: "4-9s",
      duration: "5s",
      camera: "Over-the-shoulder screen view with the phone angled toward the lens.",
      characterAction: "The creator scrolls through the checklist and taps the proof line.",
      facialExpression: "Quick skeptical eyebrow raise.",
      background: "Same desk setup with product notes visible beside the phone.",
      props: ["phone", "product notes"],
      voiceover: "This is where most new creators skip the proof.",
      overlay: "Proof before pitch",
      sound: "Soft swipe and click.",
      bgm: "Background loop dips slightly during the proof tap.",
      soundEffects: ["swipe", "click"],
      subtitleLogic: "Caption lands on the proof tap to mark the rule, not as a decorative subtitle.",
      visualElements: ["proof-line highlight", "screen crop"],
      visualElementLogic: "The highlight appears exactly when the creator taps proof so the viewer knows where to look.",
      transition: "Swipe match cut into proof screen.",
      purpose: "Show the proof placement rule before the script asks for action.",
      localized: {
        zh: {
          duration: "5 秒",
          camera: "越肩屏幕视角，手机倾斜面向镜头。",
          characterAction: "创作者滑动清单，并点击证据行。",
          facialExpression: "快速挑眉，带一点怀疑感。",
          background: "同一张桌面，手机旁边能看到商品笔记。",
          props: ["手机", "商品笔记"],
          voiceover: "很多新手创作者就是在这里跳过证据。",
          overlay: "先证据，再推销",
          sound: "轻微滑动和点击声。",
          bgm: "点击证据时背景音乐略微压低。",
          soundEffects: ["滑动声", "点击声"],
          subtitleLogic: "字幕跟随点击证据的动作出现，用来标记规则，不做装饰。",
          visualElements: ["证据行高亮", "屏幕局部裁切"],
          visualElementLogic: "高亮在点击证据的瞬间出现，让观众知道要看哪里。",
          transition: "滑动匹配切到证据画面。",
          purpose: "在脚本要求行动前，展示证据应该放在哪里。",
        },
      },
    },
  ],
  createdAt: "2026-05-28T00:00:00Z",
  updatedAt: "2026-05-28T00:00:00Z",
};

const completedScript = {
  id: "script-1",
  status: "ready",
  provider: "mock",
  modelName: "mock-script-agent-v1",
  scriptType: "Beginner Trap",
  sourceBreakdownIds: ["analysis-1"],
  topicPlan: {
    title: "Stop Picking Products by Commission Alone",
    targetAudience: "Beginner KOC",
    contentAngle: "Use one concrete creator bottleneck to introduce the Moras product-to-video workflow.",
    trendSource: "Hook, structure, and visual pacing factors from the social video teardown library.",
    template: "Beginner Trap",
    persona: "Tutorial creator friend",
    hookCandidates: ["Stop choosing products just because the commission is high."],
    ctaCandidates: ["Save this before choosing your next product."],
    recommendedPlatform: "TikTok / Reels / Shorts",
    morasRelevanceScore: 86,
    riskScore: 18,
    localized: {
      zh: {
        title: "新手别再只看佣金选品",
        targetAudience: "新手 KOC",
        contentAngle: "用一个具体创作者阻塞点引出 Moras 的产品到视频工作流。",
        trendSource: "来自社媒视频拆解库的 Hook、结构和视觉节奏因子。",
        template: "新手误区",
        persona: "教程型创作者朋友",
        hookCandidates: ["别只因为佣金高就选这个产品。"],
        ctaCandidates: ["选下一个产品前先保存这条。"],
        recommendedPlatform: "TikTok / Reels / Shorts",
      },
    },
  },
  script: {
    scriptTitle: "Stop Picking Products by Commission Alone",
    targetAudience: "Beginner KOC",
    persona: "Tutorial creator friend",
    template: "Beginner Trap",
    corePain: "New creators mix product picking, script writing, and filming into one slow guessing loop.",
    emotionalAngle: "Relief after someone names the real bottleneck.",
    hook: "Stop choosing products just because the commission is high.",
    voiceover: [
      "Stop choosing products just because the commission is high.",
      "A high commission does not help if you cannot explain the product fast.",
    ],
    visual: "Phone product list, Moras workflow capture, and a before/after comparison from product info to script draft.",
    overlay: ["Don't chase commission", "Check explanation cost first"],
    soundEffect: "Light click sounds.",
    proofInsert: "Show the workflow comparison from product information to script draft.",
    cta: "Save these three checks.",
    complianceNote: "Only claims reduced guessing and improved content-production efficiency; no sales or income promises.",
    version: "v1",
    localized: {
      zh: {
        scriptTitle: "新手别再只看佣金选品",
        targetAudience: "新手 KOC",
        persona: "教程型创作者朋友",
        template: "新手误区",
        corePain: "新手把选品、脚本和视频制作混在一起。",
        emotionalAngle: "被理解 + 醒悟",
        hook: "别只因为佣金高就选这个产品。",
        voiceover: [
          "别只因为佣金高就选这个产品。",
          "如果你不能快速讲清楚产品，高佣金也帮不上忙。",
        ],
        visual: "手机产品列表、Moras 工作流录屏和脚本草稿前后对比。",
        overlay: ["别只看佣金", "先看解释成本"],
        soundEffect: "轻快点击声。",
        proofInsert: "展示从商品信息到脚本草稿的流程对比。",
        cta: "保存这三个判断点。",
        complianceNote: "只表达减少试错和提高内容产出效率，不承诺销量或收入。",
      },
    },
  },
  storyboard: [
    {
      shotId: "shot_1",
      timestamp: "0-3s",
      duration: "3s",
      camera: "Vertical phone close-up.",
      characterAction: "Aaliyah Brooks circles the high commission number on a product list.",
      facialExpression: "Brows knit with a concerned pause.",
      background: "Real creator desk workspace.",
      props: ["phone", "laptop"],
      voiceover: "Stop choosing products just because the commission is high.",
      overlay: "Don't chase commission",
      sound: "Short alert tone.",
      transition: "Quick cut to the desk capture.",
      purpose: "Create a reason to keep watching.",
      localized: {
        zh: {
          camera: "手机竖屏近景。",
          characterAction: "创作者用手圈出高佣金数字。",
          facialExpression: "皱眉、停顿。",
          background: "真实桌面工作区。",
          props: ["手机", "电脑"],
          voiceover: "别只因为佣金高就选这个产品。",
          overlay: "别只看佣金",
          sound: "短促提示音。",
          transition: "快速切到桌面录屏。",
          purpose: "建立停留理由。",
        },
      },
    },
  ],
  creatorPersona: {
    personaId: "creator_persona_aaliyah_brooks",
    displayName: "Aaliyah Brooks",
    role: "Creator educator",
    demographic: "26-year-old Black American social-commerce creator in a compact city apartment studio.",
    creatorBackground: "A practical creator who teaches beginner KOCs how to avoid product-picking traps.",
    personality: "Calm, direct, and helpful.",
    trustStance: "Explains workflow limits without promising sales or income.",
    speechStyle: "Short, clear tutorial language.",
    personaType: "Beginner KOC",
    roleTask: "Help TikTok Shop creators with followers turn product ideas into testable shoppable videos without pretending AI guarantees sales.",
    audienceCallout: "If you have TikTok Shop access but your videos still do not sell, check this before chasing ten angles.",
    targetProblemProfile: {
      explicitPains: ["does not know what to sell", "does not know how to write shoppable scripts", "posts but gets no sales"],
      innerConflict: "She has traffic, but she feels embarrassed that the account still is not earning.",
      desiredState: "She wants a repeatable testing system that makes her look professional without adding more filming work.",
    },
    trustBasis: {
      primaryTrustAngle: "Transparent workflow educator who shows Moras screens and TikTok Shop data before making a claim.",
      usableProofAssets: ["Moras product-to-video screen recording", "TikTok Shop dashboard screenshot", "before/after product-to-video comparison"],
      proofInsertionRule: "Insert a real Moras workflow or dashboard asset before claims about speed, testing, or conversion improvement.",
    },
    proofPolicy: "Use real Moras workflow footage or approved TikTok Shop data before any efficiency or conversion claim.",
    personaScenePair: {
      primaryScene: "desk workflow with phone backend",
      sceneLogic: "A repeatable desktop setup lets the creator show product selection, script, and shoppable-video creation in one frame.",
    },
    recurringScenes: ["desk workflow with phone backend", "late-night phone scroll", "comment screenshot reply"],
    memorySymbols: {
      fixedOpeningPattern: "Open on the product page and a visible scorecard before moving into the workflow.",
      visualAnchor: "green sticky-note scorecard beside the phone",
      recurringProp: "black gel pen",
      columnName: "Creator Checkout",
    },
    contentPillars: ["product selection traps", "Moras workflow tutorials", "no-sample testing"],
    hookPreferences: [],
    ctaStyle: "Ask the creator to draft one shoppable video in Moras and review the proof asset, not to expect guaranteed sales.",
    endorsementBoundary: {
      allowedClaims: ["Moras can reduce drafting steps", "Creators can review product angles before wasting effort"],
      bannedClaims: ["guaranteed income", "make $10K easily", "automatic money", "ai guarantees sales"],
      experienceRule: "Do not say the persona personally bought, used, earned, or recommends a product unless a real verified asset supports it.",
    },
    personaQualityScore: {
      score: 92,
      checks: {
        hasTargetAudience: true,
        hasReusableScenes: true,
        hasMemorySymbols: true,
        hasProofPolicy: true,
        avoidsFakeExperience: true,
        distinctFromExistingPersonas: true,
        fitsSmallMidCreator: true,
        scriptReady: true,
      },
      reviewNotes: ["Operational scene is reusable.", "Compliance boundaries are explicit."],
    },
    scriptAgentHandoff: {
      commonHooks: ["If you have TikTok Shop access but no sales yet...", "Stop choosing products by commission alone."],
      openingSceneRules: ["Start at the desk with the phone backend visible.", "Show the green sticky-note scorecard in the first second."],
      requiredProofAssets: ["Moras workflow screen recording", "TikTok Shop dashboard screenshot"],
      proofAssetRules: ["Use screen proof before workflow-speed claims.", "Do not invent GMV, commission, payout, or product-use evidence."],
      forbiddenClaims: ["guaranteed income", "make $10K easily", "automatic money", "ai guarantees sales"],
      preferredCtas: ["Create one shoppable video draft", "Check one product angle in Moras"],
    },
    hobbiesInterests: ["product notes", "desk setups"],
    appearance: "Oval face, deep brown skin tone, clear dark brown eyes, shoulder-length coily dark hair in a soft half-up style, relaxed posture, and expressive hands.",
    faceHairMakeup: "Natural brows, warm natural makeup, muted berry lip color, coily dark hair with a few loose curls.",
    wardrobe: "Ivory ribbed knit top and cropped sage utility jacket.",
    stylingDetails: "Minimal jewelry, simple black watch, short natural nails.",
    distinctiveMarksOrTattoos: "Optional tiny line-art star tattoo on the inner left wrist.",
    props: ["phone", "laptop", "notebook"],
    consistencyRules: ["Keep the same hair, wardrobe, and desk props across clips."],
    veoIdentityString: "Aaliyah Brooks, 26-year-old Black American social-commerce creator; oval face, deep brown skin tone, coily dark hair; ivory ribbed knit top and cropped sage utility jacket; phone, laptop, notebook.",
    referenceImagePrompt: "Create a high fidelity realistic character reference image for Veo video consistency. Subject: Aaliyah Brooks, a 26-year-old Black American social-commerce creator with an oval face, deep brown skin tone, clear dark brown eyes, shoulder-length coily dark hair in a soft half-up style, natural brows, warm natural makeup, and muted berry lip color. Wardrobe: ivory ribbed knit top, cropped sage utility jacket, small gold hoop earrings, simple black watch, optional tiny crescent line tattoo on the inner left wrist. Composition: clean three-quarter portrait plus visible hands at a creator desk, neutral studio-like home office background, smartphone, silver laptop, sticky notes, black gel pen, and small product sample box nearby. Style: realistic natural light, high fidelity, cinematic but practical, sharp facial detail, consistent wardrobe colors, plain non-branded background elements.",
    digitalHumanPromptAssets: {
      visualReferencePrompt: "Create a high fidelity realistic character reference image for Veo video consistency. Subject: Aaliyah Brooks with consistent face, hair, wardrobe, hands, and desk props.",
      avatarMotionPrompt: "Generate vertical 9:16 synthetic creator source footage featuring Aaliyah Brooks at the compact creator desk with natural face and hand movement.",
      voiceStylePrompt: "Synthetic TTS delivery for Aaliyah Brooks: short, clear tutorial language with calm pauses and grounded direct-to-phone rhythm.",
      scriptDeliveryRules: ["Use short spoken lines.", "Keep checklist pauses.", "Make Moras one mid-script rough first pass."],
      sampleRequirement: "no_real_sample_required",
      syntheticDisclosureNote: "Persona Agent defines visual identity and voice direction as text prompts without uploaded media.",
      keepConsistent: ["same face and hair", "same wardrobe and props", "same calm tutorial rhythm"],
      avoid: ["do not change age or face", "do not imitate a real person", "do not imply uploaded media was used"],
    },
    localized: {
      zh: {
        displayName: "Aaliyah Brooks",
        role: "创作者教育者",
        demographic: "26 岁美国黑人社交电商创作者，在紧凑城市公寓工作室拍摄。",
        creatorBackground: "实用型创作者，教新手 KOC 避开选品陷阱。",
        personality: "平静、直接、乐于帮助。",
        trustStance: "说明工作流边界，不承诺销量或收入。",
        speechStyle: "简短清楚的教程式表达。",
        personaType: "新手 KOC",
        roleTask: "帮已开通 TikTok Shop 的创作者把商品想法变成可测试的带货视频，不把 AI 说成销量保证。",
        audienceCallout: "如果你开通了 TikTok Shop 但视频还是不出单，先看这个。",
        targetProblemProfile: {
          explicitPains: ["不知道卖什么", "不会写带货脚本", "发了视频但没有销量"],
          innerConflict: "她有流量，却不好意思承认账号还没赚到钱。",
          desiredState: "她想要一套可复用的测试流程，看起来更专业，同时不增加拍摄负担。",
        },
        trustBasis: {
          primaryTrustAngle: "先展示 Moras 界面和 TikTok Shop 数据，再解释方法的透明工作流教育者。",
          usableProofAssets: ["Moras 商品转视频录屏", "TikTok Shop 后台截图", "商品到成品视频前后对比"],
          proofInsertionRule: "凡是涉及效率、测试或转化改善，都必须先插入真实 Moras 工作流或后台数据素材。",
        },
        proofPolicy: "涉及效率或转化的表达前，先使用真实 Moras 工作流画面或已批准的 TikTok Shop 数据。",
        personaScenePair: {
          primaryScene: "桌面工作流和手机后台",
          sceneLogic: "稳定桌面场景能在同一画面展示选品、脚本和带货视频创建流程。",
        },
        recurringScenes: ["桌面工作流和手机后台", "深夜刷手机", "评论截图回应"],
        memorySymbols: {
          fixedOpeningPattern: "先展示商品页和可见评分卡，再进入工作流。",
          visualAnchor: "手机旁的绿色便利贴评分卡",
          recurringProp: "黑色中性笔",
          columnName: "Creator Checkout",
        },
        contentPillars: ["选品避坑", "Moras 工作流教程", "零样品测试"],
        hookPreferences: [],
        ctaStyle: "引导创作者在 Moras 里先生成一个带货视频草稿并查看证明素材，不暗示必然出单。",
        endorsementBoundary: {
          allowedClaims: ["Moras 可以减少起稿步骤", "创作者可以先复查商品角度再浪费精力"],
          bannedClaims: ["guaranteed income", "make $10K easily", "automatic money", "ai guarantees sales"],
          experienceRule: "没有真实验证素材时，不得让人设说自己买过、用过、赚过或推荐某商品。",
        },
        personaQualityScore: {
          score: 92,
          checks: {
            hasTargetAudience: true,
            hasReusableScenes: true,
            hasMemorySymbols: true,
            hasProofPolicy: true,
            avoidsFakeExperience: true,
            distinctFromExistingPersonas: true,
            fitsSmallMidCreator: true,
            scriptReady: true,
          },
          reviewNotes: ["运营场景可复用。", "合规边界明确。"],
        },
        scriptAgentHandoff: {
          commonHooks: ["如果你开通了 TikTok Shop 但还没出单...", "别只因为佣金高就选这个产品。"],
          openingSceneRules: ["开头在桌面展示手机后台。", "第一秒露出绿色便利贴评分卡。"],
          requiredProofAssets: ["Moras 工作流录屏", "TikTok Shop 后台截图"],
          proofAssetRules: ["涉及流程提速前先插入录屏证明。", "不要虚构 GMV、佣金、到账或产品体验证据。"],
          forbiddenClaims: ["guaranteed income", "make $10K easily", "automatic money", "ai guarantees sales"],
          preferredCtas: ["生成一个带货视频草稿", "在 Moras 检查一个商品角度"],
        },
        hobbiesInterests: ["产品笔记", "桌面布置"],
        appearance: "鹅蛋脸、深棕肤色、深棕眼睛、及肩卷发半扎，姿态放松，手部表达丰富。",
        faceHairMakeup: "自然眉形、暖调自然妆、浆果色唇妆，卷发带少量碎卷。",
        wardrobe: "象牙色坑条针织上衣和鼠尾草绿短款工装外套。",
        stylingDetails: "少量首饰、简洁黑色腕表、短自然指甲。",
        distinctiveMarksOrTattoos: "左手腕内侧可有细小线条星星纹身。",
        props: ["手机", "笔记本电脑", "笔记本"],
        consistencyRules: ["每个片段保持相同发型、服装和桌面道具。"],
        veoIdentityString: "Aaliyah Brooks，26 岁美国黑人社交电商创作者；鹅蛋脸、深棕肤色、卷发；象牙色针织上衣和鼠尾草绿工装外套；手机、笔记本电脑、笔记本。",
        referenceImagePrompt: "为 Veo 视频一致性创建高保真人设参考图。主体：Aaliyah Brooks，26 岁美国黑人社交电商创作者，鹅蛋脸、深棕肤色、深棕眼睛、及肩卷发半扎、自然眉形、暖调自然妆和浆果色唇妆。服装：象牙色坑条针织上衣、鼠尾草绿短款工装外套、小金圈耳环、简洁黑色腕表，左手腕内侧可有细小新月线条纹身。构图：创作者桌前三分之四肖像并露出双手，中性家庭办公背景，附近有手机、银色笔记本电脑、便利贴、黑色中性笔和小产品样品盒。风格：真实自然光、高保真、实用电影感、面部细节清晰、服装颜色一致、无品牌背景元素。",
        digitalHumanPromptAssets: {
          visualReferencePrompt: "为 Veo 视频一致性创建高保真人设参考图，保持 Aaliyah Brooks 的脸、发型、服装、双手和桌面道具。",
          avatarMotionPrompt: "生成 9:16 竖屏合成创作者素材，Aaliyah Brooks 在紧凑桌面前自然面对手机口播，手部动作真实。",
          voiceStylePrompt: "Aaliyah Brooks 的合成旁白方向：简短清楚的教程式表达，语速平稳，清单点后留短暂停顿。",
          scriptDeliveryRules: ["使用短口播句。", "保留清单式停顿。", "Moras 只作为中段粗稿工具出现一次。"],
          sampleRequirement: "no_real_sample_required",
          syntheticDisclosureNote: "人设 Agent 用文本定义视觉身份和声音方向，不依赖上传媒体。",
          keepConsistent: ["脸和发型一致", "服装和道具一致", "教程式节奏一致"],
          avoid: ["不要改变年龄或脸", "不要模仿真实个人", "不要暗示使用了上传媒体"],
        },
      },
    },
  },
  videoPrompt: {
    promptTitle: "Stop Picking Products by Commission Alone Visual Prompt",
    aspectRatio: "vertical 9:16",
    targetModel: "Veo 3.1",
    veoModelId: "veo-3.1-generate-001",
    veoGenerationMode: "text_to_video_9x16",
    veoBaseDurationSec: 8,
    characterLock: "Use Aaliyah Brooks, a 26-year-old Black American social-commerce creator, as the only visible creator. Appearance continuity: oval face, deep brown skin tone, coily dark hair in a soft half-up style. Wardrobe continuity: ivory ribbed knit top and cropped sage utility jacket.",
    sceneLock: "Same compact creator desk.",
    generationPrompt: "Vertical smartphone video in a realistic creator desk setup.",
    overlayExclusionNote: "Overlay lines are stored separately.",
    consistencyNotes: ["Keep vertical 9:16 framing."],
    targetDurationSec: 38,
    veoGenerationDurationSec: 22,
    segments: [
      {
        segmentIndex: 1,
        timelineStartSec: 0,
        timelineEndSec: 8,
        durationSec: 8,
        timeRange: "0s-8s",
        veoPrompt: "Generate one 8-second vertical 9:16 Veo 3.1 source clip. Subject: Aaliyah Brooks, a 26-year-old Black American social-commerce creator with an oval face, deep brown skin tone, coily dark hair in a soft half-up style, ivory ribbed knit top, and cropped sage utility jacket. Action and expression: she pauses while comparing product options through phone and laptop actions. Camera: smartphone-style medium close-up with subtle handheld push-in. Lighting and style: realistic daylight, warm practical creator mood. Audio and ambiance: quiet room tone and soft desk sounds.",
      },
      {
        segmentIndex: 2,
        timelineStartSec: 8,
        timelineEndSec: 9,
        durationSec: 1,
        timeRange: "8s-9s",
        veoPrompt: "Generate one 8-second vertical 9:16 Veo 3.1 source clip to be trimmed to a 1-second timeline slot. Subject: Aaliyah Brooks, the same creator with coily dark hair, warm natural makeup, ivory ribbed knit top, cropped sage utility jacket, and simple black watch. Action and expression: her hand finishes circling the product note, then pauses. Camera: tight vertical desk close-up. Lighting and style: realistic soft daylight and shallow depth of field. Audio and ambiance: short paper movement and room tone.",
      },
      {
        segmentIndex: 3,
        timelineStartSec: 25,
        timelineEndSec: 33,
        durationSec: 8,
        timeRange: "25s-33s",
        veoPrompt: "Generate one 8-second vertical 9:16 Veo 3.1 source clip. Subject: Aaliyah Brooks, the same Black American social-commerce creator with deep brown skin tone, coily dark hair, ivory ribbed knit top, and cropped sage utility jacket. Action and expression: she organizes notes beside the laptop, nods with relief, and points to a saved checklist. Camera: vertical medium close-up with stable framing and gentle push-in. Lighting and style: high fidelity realistic creator video, soft side daylight. Audio and ambiance: gentle upbeat rhythm, pen and desk sounds.",
      },
      {
        segmentIndex: 4,
        timelineStartSec: 33,
        timelineEndSec: 38,
        durationSec: 5,
        timeRange: "33s-38s",
        veoPrompt: "Generate one 8-second vertical 9:16 Veo 3.1 source clip for a 5-second ending. Subject: Aaliyah Brooks, the same creator with warm natural makeup, coily dark hair, ivory ribbed knit top, cropped sage utility jacket, and consistent desk props. Action and expression: she smiles gently, places the note beside the laptop, and gestures toward the phone. Camera: vertical close-up, slight push-in, face and hands visible. Lighting and style: realistic warm daylight and practical social-video tone. Audio and ambiance: quiet room tone and soft save sound.",
      },
    ],
    localized: {
      zh: {
        promptTitle: "新手别再只看佣金选品 视觉生成提示",
        characterLock: "使用 Aaliyah Brooks 作为唯一出镜创作者，并保持相同外貌、发型和服装。",
        sceneLock: "保持同一个紧凑的创作者桌面。",
        generationPrompt: "真实创作者桌面环境中的竖屏手机视频。",
        overlayExclusionNote: "字幕和箭头只在剪辑阶段添加。",
      },
    },
  },
  productionAssetPlan: [
    {
      planId: "asset_1",
      timeRange: "0s-8s",
      shotIds: ["shot_1"],
      narrativePhase: "Hook",
      assetType: "digital_human_avatar",
      morasAssetCategory: "none",
      layer: "base_track",
      usageReason: "Use a human explainer to establish trust before the workflow proof.",
      editorNote: "Keep the avatar on the base track and add hook subtitles in editing.",
      localized: {
        zh: {
          narrativePhase: "开头",
          usageReason: "在工作流证据之前使用人物讲解建立信任。",
          editorNote: "保留人物在主轨，剪辑阶段再加开头字幕。",
        },
      },
    },
    {
      planId: "asset_2",
      timeRange: "9s-25s",
      shotIds: ["shot_1"],
      narrativePhase: "Solution / Proof",
      assetType: "real_moras_screen_recording",
      morasAssetCategory: "workflow_screen_recording",
      layer: "cutaway",
      usageReason: "Use real Moras workflow footage when the script explains product-to-script speed.",
      editorNote: "Cut to approved Moras recording and keep UI labels out of Veo prompts.",
      localized: {
        zh: {
          narrativePhase: "方案 / 证据",
          usageReason: "讲到商品到脚本速度时切入真实 Moras 工作流素材。",
          editorNote: "剪入已批准的 Moras 录屏，Veo 提示词里不写 UI 字幕。",
        },
      },
    },
  ],
  riskCheck: {
    riskLevel: "low",
    forbiddenClaimsChecked: ["guaranteed income"],
    complianceNotes: ["未承诺收入或销量。"],
    allowedForVideoFactory: true,
  },
  sourceComponentSummary: ["Contrarian hook", "Beginner Trap"],
  revisionHistory: [],
  errorMessage: null,
  createdAt: "2026-05-29T00:00:00Z",
  updatedAt: "2026-05-29T00:00:00Z",
};

const completedPersonaRecord = {
  id: "persona-record-aaliyah",
  status: "ready",
  provider: "local",
  modelName: "moras-persona-library-v1",
  creatorPersona: completedScript.creatorPersona,
  sourceScriptIds: [],
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedEnglishScript = {
  ...completedScript,
  id: "script-english",
  topicPlan: {
    ...completedScript.topicPlan,
    title: "Scale Content Without Writing",
    targetAudience: "Lazy-but-Ambitious Creators",
    contentAngle: "Pain Point Exemption & Workflow Speed",
    template: "Shoppable Video Workflow",
    persona: "Tech Reviewer",
    recommendedPlatform: "TikTok",
    morasRelevanceScore: 100,
    localized: {},
  },
  script: {
    ...completedScript.script,
    scriptTitle: "Scale Content Without Writing",
    targetAudience: "Lazy-but-Ambitious Creators",
    persona: "Tech Reviewer",
    template: "Shoppable Video Workflow",
    corePain: "Writing scripts takes too much time / lack of copywriting skills",
    emotionalAngle: "Relief and excitement about a faster, easier process",
    hook: "How to create shoppable video drafts in minutes without having to write a single script from zero.",
    visual: "Creator wearing a bright hoodie, standing in front of a dual-monitor setup. Fast-paced cuts showing the screen recording of the Moras interface generating a script.",
    voiceover: [
      "How to create shoppable video drafts in minutes without having to write a single script from zero.",
      "If you want to scale your TikTok Shop, you need to test more content. But writing takes forever.",
      "Here is the exact workflow.",
      "First, grab your product data. Second, drop it into the Moras AI agent.",
      "Moras instantly turns that product information into structured, production-ready short-video script drafts.",
      "It gives you the visual cues, the voiceover, and the hooks. You just hit record.",
      "Follow me for more tools to speed up your content creation.",
    ],
    overlay: ["No script from zero", "Moras drafts it"],
    proofInsert: "Show the Moras interface turning product information into structured script drafts.",
    cta: "Follow me for more tools to speed up your content creation.",
    complianceNote: "No income or sales guarantees.",
    localized: {},
  },
};

const completedCompetitiveScript = {
  ...completedScript,
  id: "script-competitive",
  topicPlan: {
    ...completedScript.topicPlan,
    title: "Find Your Edge with Moras",
    targetAudience: "Beginner KOC",
    contentAngle: "Workflow Efficiency & Trial-and-Error Reduction",
    template: "Product Picking / Workflow",
    persona: "Professional Operations",
    recommendedPlatform: "TikTok",
    morasRelevanceScore: 95,
    localized: {},
  },
  script: {
    ...completedScript.script,
    scriptTitle: "Find Your Edge with Moras",
    targetAudience: "Beginner KOC",
    persona: "Professional Operations",
    template: "Product Picking / Workflow",
    corePain: "Don't know how to write converting scripts, wasting time on trial and error",
    emotionalAngle: "Anxiety about competition, relief through a structured solution",
    hook: "Why are 500 other affiliates selling the exact same product, but you're getting zero views? I'll give you your competitive advantage in 15 seconds.",
    visual: "Creator sitting at a desk, looking directly at the camera. Fast cuts to a laptop screen showing the Moras workflow, then back to the creator holding a notebook.",
    voiceover: [
      "Why are 500 other affiliates selling the exact same product, but you're getting zero views? I'll give you your competitive advantage in 15 seconds.",
      "Step one: Stop writing scripts from zero. You are wasting time on trial and error.",
      "Step two: Realize that volume and testing are your only ways to win.",
      "Step three: Use the Moras AI agent. You just plug in your product data, and it instantly turns it into ready-to-test video scripts.",
      "It gives you a reviewable shoppable draft, not a promise that the final result needs no cleanup.",
      "Comment 'WORKFLOW' and I'll send you the tool to speed up your content creation.",
    ],
    overlay: ["Your Competitive Advantage", "Step 1: Stop writing from zero", "Step 2: Test more formats", "Step 3: Moras AI Agent", "Comment 'WORKFLOW'"],
    proofInsert: "Moras workflow screen recording showing product-to-script before/after.",
    cta: "Comment 'WORKFLOW' for access.",
    complianceNote: "Avoided any income guarantees. Focused strictly on workflow speed and reducing trial and error.",
    localized: {},
  },
};

const completedStoredChineseScript = {
  ...completedScript,
  id: "script-localized",
  topicPlan: {
    ...completedScript.topicPlan,
    title: "Shelf Test Narrative",
    targetAudience: "Cautious Shop Creator",
    contentAngle: "Show a careful creator using Moras to choose one product test.",
    template: "Proof-led Workflow",
    persona: "Measured Reviewer",
    localized: {
      zh: {
        title: "货架测试叙事",
        targetAudience: "谨慎型店铺创作者",
        contentAngle: "展示一位谨慎创作者如何用 Moras 选择一个商品测试。",
        template: "证据驱动工作流",
        persona: "克制评测者",
        recommendedPlatform: "TikTok",
      },
    },
  },
  script: {
    ...completedScript.script,
    scriptTitle: "Shelf Test Narrative",
    targetAudience: "Cautious Shop Creator",
    persona: "Measured Reviewer",
    template: "Proof-led Workflow",
    corePain: "Choosing products without a repeatable content test.",
    emotionalAngle: "Careful doubt turning into a practical next step.",
    hook: "I would not test this product until I checked one thing first.",
    visual: "A creator compares a product card with a short Moras workflow draft.",
    voiceover: [
      "I would not test this product until I checked one thing first.",
      "The question is not whether the product looks nice. It is whether I can explain it quickly.",
    ],
    overlay: ["Check explainability", "Then draft one test"],
    proofInsert: "Show the Moras draft next to the product information.",
    cta: "Save this before your next product test.",
    complianceNote: "No sales or income promise.",
    localized: {
      zh: {
        scriptTitle: "货架测试叙事",
        targetAudience: "谨慎型店铺创作者",
        persona: "克制评测者",
        template: "证据驱动工作流",
        corePain: "没有可复用的内容测试方法就直接选品。",
        emotionalAngle: "谨慎怀疑转成一个可执行的下一步。",
        hook: "我不会直接测试这个商品，除非先确认一件事。",
        visual: "创作者把商品卡片和 Moras 生成的工作流草稿放在一起对比。",
        voiceover: [
          "我不会直接测试这个商品，除非先确认一件事。",
          "问题不是商品看起来好不好，而是我能不能很快把它讲清楚。",
        ],
        overlay: ["先看解释成本", "再生成一个测试草稿"],
        proofInsert: "把 Moras 草稿和商品信息并排展示。",
        cta: "下次测品前先收藏这个判断方式。",
        complianceNote: "不承诺销量或收入。",
      },
    },
  },
  storyboard: [
    {
      ...completedScript.storyboard[0],
      camera: "Over-shoulder desk shot with product card and laptop.",
      localized: {
        zh: {
          camera: "桌面过肩镜头，同时看到商品卡片和电脑。",
          characterAction: "创作者暂停并圈出商品信息里的解释点。",
          purpose: "建立谨慎测试的可信理由。",
        },
      },
    },
  ],
  videoPrompt: {
    ...completedScript.videoPrompt,
    generationPrompt: "Vertical desk workflow scene with careful product comparison and calm decision-making.",
    localized: {
      zh: {
        generationPrompt: "竖屏桌面工作流画面，表现谨慎的商品对比和冷静决策。",
        characterLock: "保持同一位克制、谨慎的创作者。",
        sceneLock: "保持同一个自然光桌面工作区。",
        overlayExclusionNote: "字幕和箭头只在剪辑阶段添加。",
      },
    },
    segments: [
      {
        ...completedScript.videoPrompt.segments[0],
        visualPrompt: "Creator studies a product card, pauses, and compares notes on a laptop with careful body language.",
        localized: {
          zh: {
            visualPrompt: "创作者研究商品卡片，停顿后在电脑旁对比笔记，肢体语言谨慎。",
          },
        },
      },
    ],
  },
  productionAssetPlan: [
    {
      ...completedScript.productionAssetPlan[0],
      usageReason: "Use restrained creator footage to make the evaluation feel careful.",
      editorNote: "Keep the first seconds quiet and evidence-led.",
      localized: {
        zh: {
          narrativePhase: "谨慎开头",
          usageReason: "用克制的创作者素材，让评估显得更谨慎可信。",
          editorNote: "前几秒保持安静、证据导向。",
        },
      },
    },
  ],
};

const completedDirectorPlan = {
  id: "director-plan-1",
  scriptId: "script-1",
  status: "ready",
  provider: "mock",
  modelName: "mock-director-agent-v1",
  promptVersion: "moras_director_agent_v1",
  metadata: {
    targetAspectRatio: "9:16",
    totalDurationSec: 38,
    renderIntent: "plan_only",
    directorModel: "gemini-3.5-flash",
    providerRoute: "vertex-primary-aihubmix-fallback",
  },
  timeline: {
    tracks: {
      videoTracks: [
        {
          layer: "base_track",
          clips: [
            {
              clipId: "veo_clip_1",
              sourceType: "veo_generation",
              sourceReferenceId: "video_prompt.segments[1]",
              timelineStartSec: 0,
              timelineEndSec: 8,
              durationSec: 8,
              manualBindingStatus: "pending_upload",
              manualPromptText: "Opening generated Veo visual block.",
              notes: "Opening generated Veo visual block.",
            },
            {
              clipId: "asset_clip_asset_2",
              sourceType: "library_asset",
              sourceReferenceId: "asset_2",
              timelineStartSec: 9,
              timelineEndSec: 25,
              durationSec: 16,
              notes: "Approved Moras workflow recording placeholder.",
            },
          ],
        },
        {
          layer: "overlay",
          clips: [
            {
              clipId: "hyperframes_subtitle_overlay",
              sourceType: "hyperframes_overlay",
              sourceReferenceId: "script.voiceover+script.overlay",
              timelineStartSec: 0,
              timelineEndSec: 38,
              durationSec: 38,
              notes: "Subtitles and overlay lines.",
            },
          ],
        },
      ],
      audioTracks: [
        {
          layer: "audio",
          clips: [
            {
              clipId: "tts_voiceover_main",
              sourceType: "tts_voiceover",
              timelineStartSec: 0,
              timelineEndSec: 38,
              durationSec: 38,
              textContent: "Voiceover text.",
            },
          ],
        },
      ],
    },
  },
  assetResolution: [
    {
      assetRef: "veo_clip_1",
      sourcePlanId: "video_prompt.segments[1]",
      requiredAssetType: "manual_veo_clip",
      morasAssetCategory: "none",
      resolutionStatus: "missing_placeholder",
      resolverNote: "User must upload generated Veo 3.1 clip.",
    },
    {
      assetRef: "asset_2",
      sourcePlanId: "asset_2",
      requiredAssetType: "real_moras_screen_recording",
      morasAssetCategory: "workflow_screen_recording",
      resolutionStatus: "missing_placeholder",
      resolverNote: "Needs approved file id before rendering.",
    },
  ],
  toolDispatches: [
    {
      sequenceOrder: 1,
      toolName: "asset_resolver",
      status: "blocked",
      parameters: {},
      expectedOutput: "asset binding table",
    },
    {
      sequenceOrder: 2,
      toolName: "manual_veo_generation",
      status: "blocked",
      parameters: { clipId: "veo_clip_1" },
      expectedOutput: "manual external Veo 3.1 clip",
    },
    {
      sequenceOrder: 3,
      toolName: "manual_veo_upload",
      status: "blocked",
      parameters: { clipId: "veo_clip_1" },
      expectedOutput: "uploaded Veo 3.1 clip bound to director plan",
    },
    {
      sequenceOrder: 4,
      toolName: "render_hyperframes_subtitle",
      status: "planned",
      parameters: {},
      expectedOutput: "transparent subtitle layer",
    },
    {
      sequenceOrder: 5,
      toolName: "run_ffmpeg_mix",
      status: "blocked",
      parameters: {},
      expectedOutput: "draft MP4",
    },
  ],
  validationSummary: {
    timelineContinuity: "base_track covers 0s through target duration",
    layerCollisionCheck: "validated",
    veoLimitCheck: "all Veo 3.1 clips are <=8s",
    assetReadiness: "real Moras assets are placeholders until file ids are bound",
    renderScope: "V1 stores Director Plan only; render tools are not run",
  },
  errorMessage: null,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedDirectorGenerationJob = {
  id: "director-generation-job-1",
  status: "succeeded",
  scriptId: "script-1",
  directorPlanId: "director-plan-1",
  errorMessage: null,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedManualAsset = {
  id: "manual-asset-1",
  directorPlanId: "director-plan-1",
  scriptId: "script-1",
  clipId: "veo_clip_1",
  sourceReferenceId: "video_prompt.segments[1]",
  assetRole: "ai_generated_base_visual",
  originalFilename: "veo-1.mp4",
  storedAssetUrl: "/uploads/factory/veo-1.mp4",
  mimeType: "video/mp4",
  fileSizeBytes: 2048,
  durationSec: 8,
  width: 720,
  height: 1280,
  validationStatus: "validated",
  reviewStatus: "pending_review",
  reviewNotes: "",
  reviewedAt: null,
  semanticReviewStatus: "pending_review",
  semanticReviewNotes: "",
  semanticReviewMethod: "human_prompt_match_v1",
  semanticReviewReviewer: "",
  semanticReviewedAt: null,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedMorasAsset = {
  id: "moras-asset-1",
  assetType: "real_moras_screen_recording",
  morasAssetCategory: "workflow_screen_recording",
  title: "Moras workflow recording",
  originalFilename: "moras-workflow.mp4",
  storedAssetUrl: "/uploads/moras-assets/moras-workflow.mp4",
  mimeType: "video/mp4",
  fileSizeBytes: 4096,
  durationSec: 16,
  width: 1080,
  height: 1920,
  validationStatus: "uploaded",
  reviewStatus: "pending_review",
  reviewNotes: "",
  reviewedAt: null,
  semanticReviewStatus: "pending_review",
  semanticReviewNotes: "",
  semanticReviewMethod: "human_prompt_match_v1",
  semanticReviewReviewer: "",
  semanticReviewedAt: null,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedAssetBinding = {
  id: "binding-1",
  directorPlanId: "director-plan-1",
  scriptId: "script-1",
  assetRef: "asset_2",
  sourcePlanId: "asset_2",
  libraryAssetId: "moras-asset-1",
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedRenderJob = {
  id: "render-job-1",
  directorPlanId: "director-plan-1",
  scriptId: "script-1",
  status: "succeeded",
  outputAssetUrl: "/uploads/factory-renders/render-job-1.mp4",
  outputFilename: "render-job-1.mp4",
  outputAudioUrl: "/uploads/factory-renders/render-job-1.m4a",
  outputSubtitleUrl: "/uploads/factory-renders/render-job-1.vtt",
  fileSizeBytes: 8192,
  durationSec: 38,
  width: 1080,
  height: 1920,
  readinessSummary: {
    status: "ready",
    blockers: [],
    manualRequiredCount: 3,
    manualReadyCount: 3,
    realMorasRequiredCount: 2,
    realMorasReadyCount: 2,
  },
  qaSummary: {
    status: "passed",
    checks: {
      timelineDurationMatch: true,
      vertical1080x1920: true,
      audioStreamPresent: true,
      subtitleCuesPresent: true,
    },
    subtitleCueCount: 7,
    audio: {
      status: "succeeded",
      engine: "macos_say",
    },
    caption: {
      engine: "webvtt_track_v1",
      hyperframesStatus: "cli_disabled",
      compositionUrl: "/uploads/factory-renders/render-job-1-hyperframes/index.html",
      overlayUrl: null,
      note: "HyperFrames composition sidecar was generated; WebVTT remains the final caption track until CLI rendering is enabled.",
    },
  },
  qaReviewStatus: "pending_review",
  qaReviewNotes: "",
  qaReviewedAt: null,
  errorMessage: null,
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedRenderArtifacts = [
  {
    id: "artifact-video-1",
    renderJobId: "render-job-1",
    directorPlanId: "director-plan-1",
    scriptId: "script-1",
    artifactType: "video",
    assetUrl: "/uploads/factory-renders/render-job-1.mp4",
    filename: "render-job-1.mp4",
    mimeType: "video/mp4",
    fileSizeBytes: 8192,
    durationSec: 38,
    width: 1080,
    height: 1920,
    storageStatus: "active",
    retentionExpiresAt: "2026-06-15T00:00:00Z",
    deletedAt: null,
    createdAt: "2026-06-01T00:00:00Z",
    updatedAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "artifact-audio-1",
    renderJobId: "render-job-1",
    directorPlanId: "director-plan-1",
    scriptId: "script-1",
    artifactType: "audio",
    assetUrl: "/uploads/factory-renders/render-job-1.m4a",
    filename: "render-job-1.m4a",
    mimeType: "audio/mp4",
    fileSizeBytes: 4096,
    durationSec: 38,
    width: 0,
    height: 0,
    storageStatus: "active",
    retentionExpiresAt: "2026-06-15T00:00:00Z",
    deletedAt: null,
    createdAt: "2026-06-01T00:00:00Z",
    updatedAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "artifact-subtitle-1",
    renderJobId: "render-job-1",
    directorPlanId: "director-plan-1",
    scriptId: "script-1",
    artifactType: "subtitle",
    assetUrl: "/uploads/factory-renders/render-job-1.vtt",
    filename: "render-job-1.vtt",
    mimeType: "text/vtt",
    fileSizeBytes: 1024,
    durationSec: 38,
    width: 0,
    height: 0,
    storageStatus: "active",
    retentionExpiresAt: "2026-06-15T00:00:00Z",
    deletedAt: null,
    createdAt: "2026-06-01T00:00:00Z",
    updatedAt: "2026-06-01T00:00:00Z",
  },
  {
    id: "artifact-caption-composition-1",
    renderJobId: "render-job-1",
    directorPlanId: "director-plan-1",
    scriptId: "script-1",
    artifactType: "caption_composition",
    assetUrl: "/uploads/factory-renders/render-job-1-hyperframes/index.html",
    filename: "render-job-1-hyperframes/index.html",
    mimeType: "text/html",
    fileSizeBytes: 1536,
    durationSec: 38,
    width: 1080,
    height: 1920,
    storageStatus: "active",
    retentionExpiresAt: "2026-06-15T00:00:00Z",
    deletedAt: null,
    createdAt: "2026-06-01T00:00:00Z",
    updatedAt: "2026-06-01T00:00:00Z",
  },
];

const completedRenderUsage = {
  id: "usage-1",
  renderJobId: "render-job-1",
  directorPlanId: "director-plan-1",
  scriptId: "script-1",
  inputClipCount: 5,
  outputDurationSec: 38,
  outputBytes: 8192,
  subtitleCueCount: 7,
  ttsCharacterCount: 312,
  renderEngine: "local_ffmpeg_draft_v1",
  audioEngine: "macos_say",
  captionEngine: "webvtt_track_v1",
  createdAt: "2026-06-01T00:00:00Z",
  updatedAt: "2026-06-01T00:00:00Z",
};

const completedPublishRecord = {
  id: "publish-record-1",
  directorPlanId: "director-plan-1",
  scriptId: "script-1",
  renderJobId: "render-job-1",
  channel: "manual_upload",
  publishStatus: "ready_for_upload",
  caption: "",
  scheduledAt: null,
  publishedUrl: null,
  notes: "QA 通过后创建的手动上传/交付记录。",
  createdAt: "2026-06-01T00:02:00Z",
  updatedAt: "2026-06-01T00:02:00Z",
};

const clipboardWriteText = vi.fn(() => Promise.resolve());

describe("VideoBreakdownWorkspace", () => {
  beforeEach(() => {
    clipboardWriteText.mockClear();
    Object.defineProperty(navigator, "clipboard", {
      configurable: true,
      value: { writeText: clipboardWriteText },
    });
    vi.mocked(videoBreakdownClient.createSocialVideoAnalysis).mockReset();
    vi.mocked(videoBreakdownClient.uploadSocialVideoAnalysis).mockReset();
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockReset();
    vi.mocked(videoBreakdownClient.deleteSocialVideoAnalysis).mockReset();
    vi.mocked(videoBreakdownClient.listScripts).mockReset();
    vi.mocked(videoBreakdownClient.getScript).mockReset();
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockReset();
    vi.mocked(videoBreakdownClient.generateCreatorPersonas).mockReset();
    vi.mocked(videoBreakdownClient.createPersonaGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.listPersonaGenerationJobs).mockReset();
    vi.mocked(videoBreakdownClient.getPersonaGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.deletePersonaGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.retryPersonaGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.editCreatorPersona).mockReset();
    vi.mocked(videoBreakdownClient.deleteCreatorPersona).mockReset();
    vi.mocked(videoBreakdownClient.createScriptGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockReset();
    vi.mocked(videoBreakdownClient.getScriptGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.deleteScriptGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.retryScriptGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.generateScripts).mockReset();
    vi.mocked(videoBreakdownClient.editScript).mockReset();
    vi.mocked(videoBreakdownClient.deleteScript).mockReset();
    vi.mocked(videoBreakdownClient.generateDirectorPlan).mockReset();
    vi.mocked(videoBreakdownClient.createDirectorGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.listDirectorGenerationJobs).mockReset();
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.cancelDirectorGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.retryDirectorGenerationJob).mockReset();
    vi.mocked(videoBreakdownClient.getDirectorPlan).mockReset();
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockReset();
    vi.mocked(videoBreakdownClient.listManualFactoryAssets).mockReset();
    vi.mocked(videoBreakdownClient.uploadManualFactoryAsset).mockReset();
    vi.mocked(videoBreakdownClient.reviewManualFactoryAsset).mockReset();
    vi.mocked(videoBreakdownClient.reviewManualFactoryAssetSemanticMatch).mockReset();
    vi.mocked(videoBreakdownClient.listMorasAssets).mockReset();
    vi.mocked(videoBreakdownClient.uploadMorasAsset).mockReset();
    vi.mocked(videoBreakdownClient.reviewMorasAsset).mockReset();
    vi.mocked(videoBreakdownClient.reviewMorasAssetSemanticMatch).mockReset();
    vi.mocked(videoBreakdownClient.listDirectorPlanAssetBindings).mockReset();
    vi.mocked(videoBreakdownClient.bindDirectorPlanAsset).mockReset();
    vi.mocked(videoBreakdownClient.listDirectorRenderJobs).mockReset();
    vi.mocked(videoBreakdownClient.getDirectorRenderJob).mockReset();
    vi.mocked(videoBreakdownClient.listDirectorRenderArtifacts).mockReset();
    vi.mocked(videoBreakdownClient.cleanupExpiredDirectorRenderArtifacts).mockReset();
    vi.mocked(videoBreakdownClient.deleteDirectorRenderArtifact).mockReset();
    vi.mocked(videoBreakdownClient.getDirectorRenderUsage).mockReset();
    vi.mocked(videoBreakdownClient.createDirectorRenderJob).mockReset();
    vi.mocked(videoBreakdownClient.retryDirectorRenderJob).mockReset();
    vi.mocked(videoBreakdownClient.reviewDirectorRenderJobQa).mockReset();
    vi.mocked(videoBreakdownClient.listDirectorPublishRecords).mockReset();
    vi.mocked(videoBreakdownClient.createDirectorPublishRecord).mockReset();
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.deleteSocialVideoAnalysis).mockResolvedValue(undefined);
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([completedScript]);
    vi.mocked(videoBreakdownClient.getScript).mockResolvedValue(completedScript);
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.generateCreatorPersonas).mockResolvedValue([completedPersonaRecord]);
    vi.mocked(videoBreakdownClient.listPersonaGenerationJobs).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.createPersonaGenerationJob).mockResolvedValue({
      id: "persona-generation-job-1",
      status: "generating",
      personaCount: 3,
      topicOrBrandContext: "Moras social-commerce creator workflow",
      targetAudience: "TikTok Shop creators, sellers, and MCN operators",
      requiredDemographic: null,
      completedCount: 0,
      personaIds: [],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:00Z",
    });
    vi.mocked(videoBreakdownClient.getPersonaGenerationJob).mockResolvedValue({
      id: "persona-generation-job-1",
      status: "succeeded",
      personaCount: 3,
      topicOrBrandContext: "Moras social-commerce creator workflow",
      targetAudience: "TikTok Shop creators, sellers, and MCN operators",
      requiredDemographic: null,
      completedCount: 3,
      personaIds: ["persona-record-aaliyah"],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:02Z",
    });
    vi.mocked(videoBreakdownClient.deletePersonaGenerationJob).mockResolvedValue(undefined);
    vi.mocked(videoBreakdownClient.retryPersonaGenerationJob).mockResolvedValue({
      id: "persona-generation-job-retry",
      status: "queued",
      personaCount: 3,
      topicOrBrandContext: "Moras social-commerce creator workflow",
      targetAudience: "TikTok Shop creators, sellers, and MCN operators",
      requiredDemographic: null,
      completedCount: 0,
      personaIds: [],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:03Z",
      updatedAt: "2026-06-01T00:00:03Z",
    });
    vi.mocked(videoBreakdownClient.editCreatorPersona).mockResolvedValue(completedPersonaRecord);
    vi.mocked(videoBreakdownClient.deleteCreatorPersona).mockResolvedValue(undefined);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.createScriptGenerationJob).mockResolvedValue({
      id: "generation-job-1",
      status: "generating",
      scriptCount: 3,
      scriptType: "all",
      sourceBreakdownIds: [],
      completedCount: 0,
      scriptIds: [],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:00Z",
    });
    vi.mocked(videoBreakdownClient.getScriptGenerationJob).mockResolvedValue({
      id: "generation-job-1",
      status: "generating",
      scriptCount: 3,
      scriptType: "all",
      sourceBreakdownIds: [],
      completedCount: 0,
      scriptIds: [],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:00Z",
    });
    vi.mocked(videoBreakdownClient.deleteScriptGenerationJob).mockResolvedValue(undefined);
    vi.mocked(videoBreakdownClient.retryScriptGenerationJob).mockResolvedValue({
      id: "generation-job-retry",
      status: "queued",
      scriptCount: 3,
      scriptType: "all",
      sourceBreakdownIds: [],
      completedCount: 0,
      scriptIds: [],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:03Z",
      updatedAt: "2026-06-01T00:00:03Z",
    });
    vi.mocked(videoBreakdownClient.generateScripts).mockResolvedValue([{ ...completedScript, id: "script-generated", scriptType: "all" }]);
    vi.mocked(videoBreakdownClient.editScript).mockResolvedValue({
      ...completedScript,
      script: { ...completedScript.script, version: "v2", scriptTitle: "新手别再只看佣金选品（已修改）" },
      revisionHistory: [{ id: "revision-1", instruction: "开头更像真实创作者。" }],
    });
    vi.mocked(videoBreakdownClient.deleteScript).mockResolvedValue(undefined);
    vi.mocked(videoBreakdownClient.generateDirectorPlan).mockResolvedValue(completedDirectorPlan);
    vi.mocked(videoBreakdownClient.createDirectorGenerationJob).mockResolvedValue({
      ...completedDirectorGenerationJob,
      status: "generating",
      directorPlanId: null,
    });
    vi.mocked(videoBreakdownClient.listDirectorGenerationJobs).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockResolvedValue(completedDirectorGenerationJob);
    vi.mocked(videoBreakdownClient.cancelDirectorGenerationJob).mockResolvedValue({
      ...completedDirectorGenerationJob,
      status: "canceled",
      directorPlanId: null,
      errorMessage: "用户取消了导演计划生成任务。",
    });
    vi.mocked(videoBreakdownClient.retryDirectorGenerationJob).mockResolvedValue({
      ...completedDirectorGenerationJob,
      id: "director-generation-job-retry",
      status: "generating",
      directorPlanId: null,
      errorMessage: null,
    });
    vi.mocked(videoBreakdownClient.getDirectorPlan).mockResolvedValue(completedDirectorPlan);
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listManualFactoryAssets).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.uploadManualFactoryAsset).mockResolvedValue(completedManualAsset);
    vi.mocked(videoBreakdownClient.reviewManualFactoryAsset).mockResolvedValue({
      ...completedManualAsset,
      reviewStatus: "approved",
      reviewNotes: "人工确认素材文件可用于视频工厂。",
      reviewedAt: "2026-06-01T00:01:00Z",
    });
    vi.mocked(videoBreakdownClient.reviewManualFactoryAssetSemanticMatch).mockResolvedValue({
      ...completedManualAsset,
      reviewStatus: "approved",
      reviewNotes: "人工确认素材文件可用于视频工厂。",
      reviewedAt: "2026-06-01T00:01:00Z",
      semanticReviewStatus: "passed",
      semanticReviewNotes: "人工确认素材语义匹配复制的提示词和时间线。",
      semanticReviewReviewer: "factory-operator",
      semanticReviewedAt: "2026-06-01T00:02:00Z",
    });
    vi.mocked(videoBreakdownClient.listMorasAssets).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.uploadMorasAsset).mockResolvedValue(completedMorasAsset);
    vi.mocked(videoBreakdownClient.reviewMorasAsset).mockResolvedValue({
      ...completedMorasAsset,
      reviewStatus: "approved",
      reviewNotes: "人工确认素材文件可用于 Moras 视频工厂。",
      reviewedAt: "2026-06-01T00:01:00Z",
    });
    vi.mocked(videoBreakdownClient.reviewMorasAssetSemanticMatch).mockResolvedValue({
      ...completedMorasAsset,
      reviewStatus: "approved",
      reviewNotes: "人工确认素材文件可用于 Moras 视频工厂。",
      reviewedAt: "2026-06-01T00:01:00Z",
      semanticReviewStatus: "passed",
      semanticReviewNotes: "人工确认真实 Moras 素材语义匹配导演计划需求。",
      semanticReviewReviewer: "factory-operator",
      semanticReviewedAt: "2026-06-01T00:02:00Z",
    });
    vi.mocked(videoBreakdownClient.listDirectorPlanAssetBindings).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.bindDirectorPlanAsset).mockResolvedValue(completedAssetBinding);
    vi.mocked(videoBreakdownClient.listDirectorRenderJobs).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.getDirectorRenderJob).mockResolvedValue(completedRenderJob);
    vi.mocked(videoBreakdownClient.listDirectorRenderArtifacts).mockResolvedValue(completedRenderArtifacts);
    vi.mocked(videoBreakdownClient.cleanupExpiredDirectorRenderArtifacts).mockResolvedValue(completedRenderArtifacts);
    vi.mocked(videoBreakdownClient.deleteDirectorRenderArtifact).mockImplementation(async artifactId => ({
      ...completedRenderArtifacts.find(artifact => artifact.id === artifactId)!,
      storageStatus: "deleted",
      deletedAt: "2026-06-01T00:10:00Z",
    }));
    vi.mocked(videoBreakdownClient.getDirectorRenderUsage).mockResolvedValue(completedRenderUsage);
    vi.mocked(videoBreakdownClient.createDirectorRenderJob).mockResolvedValue(completedRenderJob);
    vi.mocked(videoBreakdownClient.retryDirectorRenderJob).mockResolvedValue({
      ...completedRenderJob,
      id: "render-job-retry",
      status: "queued",
      outputAssetUrl: null,
      outputFilename: null,
      outputAudioUrl: null,
      outputSubtitleUrl: null,
      fileSizeBytes: 0,
      durationSec: 0,
      width: 0,
      height: 0,
      qaSummary: {},
      errorMessage: null,
      createdAt: "2026-06-01T00:03:00Z",
      updatedAt: "2026-06-01T00:03:00Z",
    });
    vi.mocked(videoBreakdownClient.reviewDirectorRenderJobQa).mockResolvedValue({
      ...completedRenderJob,
      qaReviewStatus: "approved",
      qaReviewNotes: "人工 QA 通过，可进入手动发布/交付。",
      qaReviewedAt: "2026-06-01T00:01:00Z",
    });
    vi.mocked(videoBreakdownClient.listDirectorPublishRecords).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.createDirectorPublishRecord).mockResolvedValue(completedPublishRecord);
    vi.mocked(videoBreakdownClient.markdownExportUrl).mockImplementation((id: string) => `/api/breakdowns/${id}/export/markdown`);
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("renders the social video breakdown intake", () => {
    const { container } = render(<VideoBreakdownWorkspace />);

    const primaryTabs = within(screen.getByRole("tablist", { name: "社媒视频生产 Agent模块" }));
    expect(container.querySelectorAll(".workspace-tab__icon")).toHaveLength(3);
    expect(primaryTabs.getByRole("tab", { name: "视频拆解" }).getAttribute("aria-selected")).toBe("true");
    expect(primaryTabs.getByRole("tab", { name: "视频拆解" }).querySelector(".workspace-tab__icon")).toBeTruthy();
    expect(primaryTabs.queryByRole("tab", { name: "创意仓库" })).toBeNull();
    expect(primaryTabs.getByRole("tab", { name: "脚本编辑部" }).querySelector(".workspace-tab__icon")).toBeTruthy();
    expect(primaryTabs.getByRole("tab", { name: "视频工厂" }).querySelector(".workspace-tab__icon")).toBeTruthy();
    expect(screen.getByRole("tab", { name: "创意仓库" })).toBeTruthy();
    expect(screen.getByLabelText("视频链接")).toBeTruthy();
    expect(screen.getByLabelText("上传本地视频")).toBeTruthy();
    expect(screen.getByRole("button", { name: /历史/ })).toBeTruthy();
    expect((screen.getByRole("button", { name: /开始拆解/ }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("opens the creative library from the video breakdown secondary tab and returns to the intake form", async () => {
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([completedAnalysis]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "创意仓库" }));

    expect(within(screen.getByRole("tablist", { name: "社媒视频生产 Agent模块" })).queryByRole("tab", { name: "创意仓库" })).toBeNull();
    expect(screen.getByRole("tab", { name: "视频拆解" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("button", { name: "返回上一级" })).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "开头钩子 库" })).toBeNull();
    expect(await screen.findByText("禁忌型开头钩子")).toBeTruthy();
    const creativeLibraryTabs = within(screen.getByRole("tablist", { name: "创意库类型" })).getAllByRole("tab");
    expect(creativeLibraryTabs.map(tab => tab.textContent)).toEqual(["Hook", "结构", "分镜", "CTA", "人设", "场景"]);
    fireEvent.click(screen.getByRole("tab", { name: "分镜" }));
    expect(await screen.findByText("禁忌型参考分镜")).toBeTruthy();
    const dynamicStoryboardCard = screen.getByText("禁忌型参考分镜").closest("article");
    expect(dynamicStoryboardCard).toBeTruthy();
    const dynamicStoryboard = within(dynamicStoryboardCard as HTMLElement);
    expect(dynamicStoryboard.getByText(/完整沉淀 2 个参考镜头/)).toBeTruthy();
    expect(dynamicStoryboard.getByText("Shot 01")).toBeTruthy();
    expect(dynamicStoryboard.getByText("Shot 02")).toBeTruthy();
    expect(dynamicStoryboard.getByText("竖屏近景，聚焦手机和创作者手部。")).toBeTruthy();
    expect(dynamicStoryboard.getByText("很多新手创作者就是在这里跳过证据。")).toBeTruthy();
    expect(dynamicStoryboard.getByText("先证据，再推销")).toBeTruthy();
    expect(dynamicStoryboard.getByText("低音量轻快循环音乐从开头进入。")).toBeTruthy();
    expect(dynamicStoryboard.getByText("点击声、硬切提示音")).toBeTruthy();
    expect(dynamicStoryboard.getByText("钩子字幕立刻出现，并保持短句，方便静音观看。")).toBeTruthy();
    expect(dynamicStoryboard.getByText("证据行高亮、屏幕局部裁切")).toBeTruthy();
    expect(dynamicStoryboard.getByText("高亮在点击证据的瞬间出现，让观众知道要看哪里。")).toBeTruthy();
    expect(dynamicStoryboard.getByText("滑动匹配切到证据画面。")).toBeTruthy();
    expect(screen.queryByText("角色身份、语气和信任来源")).toBeNull();
    expect(screen.queryByRole("tab", { name: /Proof/ })).toBeNull();
    expect(screen.queryByLabelText("视频链接")).toBeNull();
    expect(screen.queryByRole("button", { name: /历史/ })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "返回上一级" }));

    expect(screen.getByLabelText("视频链接")).toBeTruthy();
    expect(screen.getByRole("button", { name: /历史/ })).toBeTruthy();
  });

  it("starts script generation from a creative library card", async () => {
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([completedAnalysis]);
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockResolvedValue([completedPersonaRecord]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "创意仓库" }));
    fireEvent.click(await screen.findByRole("button", { name: "用禁忌型开头钩子生成脚本" }));

    await waitFor(() => expect(screen.getByRole("tab", { name: "脚本编辑部" }).getAttribute("aria-selected")).toBe("true"));
    await waitFor(() => expect(videoBreakdownClient.createScriptGenerationJob).toHaveBeenCalledWith({
      scriptCount: 3,
      scriptType: "Mistake List",
      sourceBreakdownIds: ["analysis-1"],
      personaId: "persona-record-aaliyah",
      personaHint: expect.objectContaining({
        display_name: "Aaliyah Brooks",
        role_task: expect.stringContaining("TikTok Shop creators"),
        proof_policy: expect.stringContaining("real Moras workflow"),
        script_agent_handoff: expect.objectContaining({
          proofAssetRules: expect.arrayContaining([expect.stringContaining("workflow-speed")]),
          forbiddenClaims: expect.arrayContaining(["guaranteed income"]),
        }),
        veo_identity_string: expect.stringContaining("Aaliyah Brooks"),
      }),
    }));
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("Mistake List");
    expect((screen.getByLabelText("人设") as HTMLSelectElement).value).toBe("persona-record-aaliyah");
  });

  it("starts script generation from a built-in Joey script pattern without a fake breakdown id", async () => {
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockResolvedValue([completedPersonaRecord]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "创意仓库" }));
    expect(await screen.findByText("Joey 数字反常识开场")).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: "用Joey 数字反常识开场生成脚本" }));

    await waitFor(() => expect(screen.getByRole("tab", { name: "脚本编辑部" }).getAttribute("aria-selected")).toBe("true"));
    await waitFor(() => expect(videoBreakdownClient.createScriptGenerationJob).toHaveBeenCalledWith(expect.objectContaining({
      scriptType: "Secret / Exposed",
      sourceBreakdownIds: [],
      personaId: "persona-record-aaliyah",
    })));
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("Secret / Exposed");
  });

  it("starts script generation from a reference storyboard creative asset", async () => {
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([completedAnalysis]);
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockResolvedValue([completedPersonaRecord]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "创意仓库" }));
    fireEvent.click(await screen.findByRole("tab", { name: "分镜" }));
    fireEvent.click(await screen.findByRole("button", { name: "用禁忌型参考分镜生成脚本" }));

    await waitFor(() => expect(screen.getByRole("tab", { name: "脚本编辑部" }).getAttribute("aria-selected")).toBe("true"));
    await waitFor(() => expect(videoBreakdownClient.createScriptGenerationJob).toHaveBeenCalledWith(expect.objectContaining({
      scriptType: "Shoppable Video Workflow",
      sourceBreakdownIds: ["analysis-1"],
      personaId: "persona-record-aaliyah",
    })));
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("Shoppable Video Workflow");
  });

  it("switches to the script editorial room and renders storyboard script detail", async () => {
    const { container } = render(<VideoBreakdownWorkspace />);

    const scriptsTab = screen.getByRole("tab", { name: "脚本编辑部" });
    fireEvent.click(scriptsTab);

    expect(scriptsTab.getAttribute("aria-selected")).toBe("true");
    expect(scriptsTab.className).toContain("workspace-tab--active");
    expect(screen.queryByRole("heading", { name: "脚本池" })).toBeNull();
    expect((await screen.findAllByText("Stop Picking Products by Commission Alone")).length).toBeGreaterThanOrEqual(2);
    expect(screen.queryByText(/来自脚本智能体/)).toBeNull();
    expect(screen.queryByText(/Moras 契合度/)).toBeNull();
    expect(screen.queryByRole("heading", { name: /^脚本$/ })).toBeNull();
    expect(screen.queryByRole("heading", { name: /^分镜$/ })).toBeNull();
    const storyboardHeading = screen.getByRole("heading", { name: /^Storyboard$/ });
    expect(storyboardHeading).toBeTruthy();
    const storyboardTable = screen.getByRole("table", { name: "Storyboard" });
    expect(within(storyboardTable).getByRole("columnheader", { name: "Shot / Time" })).toBeTruthy();
    expect(within(storyboardTable).getByRole("columnheader", { name: "Visual Action" })).toBeTruthy();
    expect(within(storyboardTable).getByRole("columnheader", { name: "Shot / Camera" })).toBeTruthy();
    expect(within(storyboardTable).getByText("Shot 01")).toBeTruthy();
    expect(within(storyboardTable).getByText("0-3s")).toBeTruthy();
    expect(within(storyboardTable).getByText("Vertical phone close-up.")).toBeTruthy();
    expect(within(storyboardTable).getByText("Don't chase commission")).toBeTruthy();
    expect(within(storyboardTable).queryByRole("columnheader", { name: "镜号 / 时间" })).toBeNull();
    expect(screen.queryByRole("heading", { name: /^分镜头脚本$/ })).toBeNull();
    const personaHeading = screen.getByRole("heading", { name: /^Creator Persona$/ });
    const videoPromptHeading = screen.getByRole("heading", { name: /^Video Prompts$/ });
    const assetPlanHeading = screen.getByRole("heading", { name: /^Asset Usage Plan$/ });
    expect(personaHeading).toBeTruthy();
    expect(videoPromptHeading).toBeTruthy();
    expect(assetPlanHeading).toBeTruthy();
    expect(storyboardHeading.compareDocumentPosition(personaHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(personaHeading.compareDocumentPosition(videoPromptHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(storyboardHeading.compareDocumentPosition(videoPromptHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(videoPromptHeading.compareDocumentPosition(assetPlanHeading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(screen.getByText("Character Reference Image Prompt")).toBeTruthy();
    const imagePromptCard = screen.getByText("Character Reference Image Prompt").closest(".script-editorial-persona__prompt");
    expect(imagePromptCard).toBeTruthy();
    const imagePromptCopyButton = within(imagePromptCard as HTMLElement).getByRole("button", { name: "Copy character reference image prompt" });
    expect(imagePromptCopyButton.textContent?.trim()).toBe("");
    expect(imagePromptCopyButton.querySelector("svg")).toBeTruthy();
    expect(screen.getByText("digital_human_avatar")).toBeTruthy();
    expect(screen.getByText("workflow_screen_recording")).toBeTruthy();
    expect(screen.getByText("Veo 3.1 Dynamic Segment Prompts")).toBeTruthy();
    expect(screen.getByText(/target final cut 38s/)).toBeTruthy();
    expect(screen.getByText("Segment 1")).toBeTruthy();
    const videoPromptSection = videoPromptHeading.closest("section");
    expect(videoPromptSection).toBeTruthy();
    const segmentCopyButtons = within(videoPromptSection as HTMLElement).getAllByRole("button", { name: /^Copy video prompt segment \d+$/ });
    expect(segmentCopyButtons).toHaveLength(completedScript.videoPrompt.segments.length);
    expect(segmentCopyButtons[0].textContent?.trim()).toBe("");
    expect(segmentCopyButtons[0].querySelector("svg")).toBeTruthy();
    expect(screen.getByText("25s-33s / 8s")).toBeTruthy();
    expect(screen.getAllByText(/Aaliyah Brooks/).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Operating Brief")).toBeTruthy();
    expect(screen.getByText("Tension Map")).toBeTruthy();
    expect(screen.getByText("Production Kit")).toBeTruthy();
    expect(screen.getByText("Trust & Compliance")).toBeTruthy();
    expect(screen.getByText("Digital Human Prompt Asset")).toBeTruthy();
    expect(screen.getByText("Voice / delivery prompt")).toBeTruthy();
    expect(screen.getByText("no_real_sample_required")).toBeTruthy();
    expect(screen.getAllByText(/Help TikTok Shop creators with followers/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/If you have TikTok Shop access but your videos still do not sell/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/desk workflow with phone backend/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/green sticky-note scorecard/).length).toBeGreaterThan(0);
    expect(screen.getByText(/Do not invent GMV, commission, payout, or product-use evidence/)).toBeTruthy();
    expect(screen.getByText("Veo Identity String")).toBeTruthy();
    expect(screen.getByRole("button", { name: "生成视频" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "AI 编辑" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "先选择人设" })).toBeTruthy();
    expect((screen.getByLabelText("数量") as HTMLSelectElement).value).toBe("3");
    expect((screen.getByLabelText("类型") as HTMLSelectElement).value).toBe("全部");
    expect(screen.getByRole("tab", { name: "脚本" }).getAttribute("aria-selected")).toBe("true");
    expect(screen.getByRole("tab", { name: "人设" })).toBeTruthy();
    expect((screen.getByLabelText("人设") as HTMLSelectElement).value).toBe("");
    expect(container.querySelector(".script-editorial-sidebar-content > .script-generation-panel")).toBeTruthy();
    expect(container.querySelector(".script-editorial-list .script-generation-panel")).toBeNull();
    expect(container.querySelector(".script-editorial-list .script-editorial-card")).toBeTruthy();
    expect(screen.getAllByRole("button", { name: /删除脚本/ }).length).toBeGreaterThan(0);
    expect(screen.queryByText("待复核")).toBeNull();
    expect(screen.queryByText("低风险")).toBeNull();
    expect(screen.queryByRole("heading", { name: "审核备注" })).toBeNull();
    expect(screen.queryByRole("button", { name: /历史/ })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "中文" }));
    const zhStoryboardTable = screen.getByRole("table", { name: "分镜头脚本" });
    expect(screen.getByRole("heading", { name: /^分镜头脚本$/ })).toBeTruthy();
    expect(within(zhStoryboardTable).getByRole("columnheader", { name: "镜号 / 时间" })).toBeTruthy();
    expect(within(zhStoryboardTable).getByText("镜头 01")).toBeTruthy();
    expect(within(zhStoryboardTable).getByText("手机竖屏近景。")).toBeTruthy();
    expect(within(zhStoryboardTable).getByText("别只看佣金")).toBeTruthy();
    expect(screen.getByText("人设参考图生图提示词")).toBeTruthy();
    expect(screen.getByText("Veo 3.1 动态分段提示词")).toBeTruthy();
    expect(screen.getByText(/目标成片 38s/)).toBeTruthy();
    expect(screen.getByText("分段 1")).toBeTruthy();
    expect(screen.getByText("运营简报")).toBeTruthy();
    expect(screen.getByText("痛点地图")).toBeTruthy();
    expect(screen.getByText("生产套件")).toBeTruthy();
    expect(screen.getByText("信任与合规")).toBeTruthy();
    expect(screen.getByText("数字人提示词资产")).toBeTruthy();
    expect(screen.getByText("声音 / 表达提示词")).toBeTruthy();
    expect(screen.getByText(/帮已开通 TikTok Shop 的创作者/)).toBeTruthy();
    expect(screen.getByText(/手机旁的绿色便利贴评分卡/)).toBeTruthy();
    expect(screen.getByText(/不要虚构 GMV、佣金、到账或产品体验证据/)).toBeTruthy();
    expect(screen.getByText("Veo 身份锚点")).toBeTruthy();
    expect(screen.getByRole("button", { name: "复制人设参考图提示词" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "复制视频提示词分段 1" })).toBeTruthy();

    const zhImagePromptCard = screen.getByText("人设参考图生图提示词").closest(".script-editorial-persona__prompt") as HTMLElement;
    const zhImagePromptText = zhImagePromptCard.querySelector("p")?.textContent?.trim() ?? "";
    fireEvent.click(within(zhImagePromptCard).getByRole("button", { name: "复制人设参考图提示词" }));
    await waitFor(() => expect(clipboardWriteText).toHaveBeenCalledWith(zhImagePromptText));
    expect(screen.getByRole("button", { name: "已复制人设参考图提示词" })).toBeTruthy();

    const zhSegmentButton = screen.getByRole("button", { name: "复制视频提示词分段 1" });
    const zhSegmentText = (zhSegmentButton.closest("li") as HTMLElement).querySelector("p")?.textContent?.trim() ?? "";
    fireEvent.click(zhSegmentButton);
    await waitFor(() => expect(clipboardWriteText).toHaveBeenCalledWith(zhSegmentText));
    expect(screen.getByRole("button", { name: "已复制视频提示词分段 1" })).toBeTruthy();
  });

  it("deduplicates repeated script card tags after localization", async () => {
    const repeatedTagScript = {
      ...completedScript,
      topicPlan: {
        ...completedScript.topicPlan,
        localized: {
          zh: {
            ...completedScript.topicPlan.localized.zh,
            template: "新手陷阱",
          },
        },
      },
      script: {
        ...completedScript.script,
        localized: {
          zh: {
            ...completedScript.script.localized.zh,
            template: "新手陷阱",
          },
        },
      },
      sourceComponentSummary: ["Contrarian hook", "Beginner Trap", "Save CTA"],
    };
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([repeatedTagScript]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    fireEvent.click(await screen.findByRole("button", { name: "中文" }));

    const card = await screen.findByLabelText("新手别再只看佣金选品");
    expect(within(card).getAllByText("新手陷阱")).toHaveLength(1);
    expect(within(card).getByText("反常识钩子")).toBeTruthy();
    expect(within(card).getByText("收藏 CTA")).toBeTruthy();
  });

  it("hides stale mock duplicate script cards when real scripts exist", async () => {
    const staleMockA = {
      ...completedScript,
      id: "mock-script-a",
      provider: "mock",
      modelName: "mock-script-agent-v1",
      creatorPersona: {
        ...completedScript.creatorPersona,
        displayName: "Elena Yazzie",
        localized: {
          zh: {
            ...completedScript.creatorPersona.localized.zh,
            displayName: "Elena Yazzie",
          },
        },
      },
    };
    const staleMockB = {
      ...staleMockA,
      id: "mock-script-b",
      creatorPersona: {
        ...staleMockA.creatorPersona,
        displayName: "Samira Haddad",
        localized: {
          zh: {
            ...staleMockA.creatorPersona.localized.zh,
            displayName: "Samira Haddad",
          },
        },
      },
    };
    const realScript = {
      ...completedScript,
      id: "gemini-script",
      provider: "gemini",
      modelName: "gemini-3.1-pro-preview",
      topicPlan: {
        ...completedScript.topicPlan,
        title: "Real Gemini Workflow Script",
        localized: {
          zh: {
            ...completedScript.topicPlan.localized.zh,
            title: "真实 Gemini 工作流脚本",
          },
        },
      },
      script: {
        ...completedScript.script,
        scriptTitle: "Real Gemini Workflow Script",
        localized: {
          zh: {
            ...completedScript.script.localized.zh,
            scriptTitle: "真实 Gemini 工作流脚本",
          },
        },
      },
    };
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([staleMockA, staleMockB, realScript]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    const scriptList = await screen.findByLabelText("脚本卡片列表");
    await waitFor(() => expect(scriptList.querySelectorAll(".script-editorial-card")).toHaveLength(1));
    expect(within(scriptList).getByText("Real Gemini Workflow Script")).toBeTruthy();
    expect(within(scriptList).queryByText("Stop Picking Products by Commission Alone")).toBeNull();
    expect(within(scriptList).queryByText(/Samira Haddad/)).toBeNull();
  });

  it("generates persona cards and uses the selected persona when generating scripts", async () => {
    vi.mocked(videoBreakdownClient.listCreatorPersonas)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([completedPersonaRecord]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    fireEvent.click(await screen.findByRole("tab", { name: "人设" }));

    expect(screen.getByText("暂无 Persona 资产，先点击生成。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "生成 Persona 资产" }));

    expect(videoBreakdownClient.createPersonaGenerationJob).toHaveBeenCalledWith({ personaCount: 3 });
    const personaGenerationCard = await screen.findByLabelText("人设任务 1 / 3，生成中");
    expect(within(personaGenerationCard).getByText("正在生成第 1 个人设，完成后会自动进入人设库。")).toBeTruthy();
    expect((await screen.findAllByText("Aaliyah Brooks")).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("heading", { name: "Aaliyah Brooks" }).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByRole("button", { name: "生成脚本" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "AI 编辑" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "删除" })).toBeTruthy();
    expect(screen.getByRole("group", { name: "人设详情语言" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: /^Creator Persona$/ })).toBeTruthy();
    expect(screen.getAllByText("Creator educator").length).toBeGreaterThan(0);
    expect(screen.getByText("A practical creator who teaches beginner KOCs how to avoid product-picking traps.")).toBeTruthy();
    expect(screen.getByLabelText("Persona quality score 92")).toBeTruthy();
    expect(screen.getAllByText(/Beginner KOC/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/Help TikTok Shop creators with followers/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/If you have TikTok Shop access but your videos still do not sell/).length).toBeGreaterThan(0);
    expect(screen.getAllByText("Creator Checkout").length).toBeGreaterThan(0);
    expect(screen.getAllByText(/green sticky-note scorecard/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/guaranteed income/).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getByRole("heading", { name: /^创作者人设$/ })).toBeTruthy();
    expect(screen.getAllByText("创作者教育者").length).toBeGreaterThan(0);
    expect(screen.getByText("实用型创作者，教新手 KOC 避开选品陷阱。")).toBeTruthy();
    expect(screen.getAllByText(/新手 KOC/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/帮已开通 TikTok Shop 的创作者/).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/如果你开通了 TikTok Shop/).length).toBeGreaterThan(0);
    expect(screen.getByText(/手机旁的绿色便利贴评分卡/)).toBeTruthy();
    expect(screen.getByText("人设参考图生图提示词")).toBeTruthy();
    expect(screen.getByText(/为 Veo 视频一致性创建高保真人设参考图/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getByRole("heading", { name: /^Creator Persona$/ })).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "生成脚本" }));

    await waitFor(() => expect(videoBreakdownClient.createScriptGenerationJob).toHaveBeenCalledWith({
      scriptCount: 3,
      scriptType: "all",
      personaId: "persona-record-aaliyah",
      personaHint: expect.objectContaining({
        display_name: "Aaliyah Brooks",
        role: "Creator educator",
        persona_type: "Beginner KOC",
        role_task: expect.stringContaining("TikTok Shop creators"),
        proof_policy: expect.stringContaining("real Moras workflow"),
        endorsement_boundary: expect.objectContaining({
          bannedClaims: expect.arrayContaining(["guaranteed income", "ai guarantees sales"]),
        }),
        script_agent_handoff: expect.objectContaining({
          proofAssetRules: expect.arrayContaining([expect.stringContaining("workflow-speed")]),
          forbiddenClaims: expect.arrayContaining(["automatic money"]),
        }),
        veo_identity_string: expect.stringContaining("Aaliyah Brooks"),
      }),
    }));
    expect(screen.getByRole("tab", { name: "脚本" }).getAttribute("aria-selected")).toBe("true");
    expect((screen.getByLabelText("人设") as HTMLSelectElement).value).toBe("persona-record-aaliyah");
  });

  it("retries failed persona generation jobs from the persona task card", async () => {
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listPersonaGenerationJobs).mockResolvedValue([
      {
        id: "persona-generation-job-failed",
        status: "failed",
        personaCount: 3,
        topicOrBrandContext: "Moras social-commerce creator workflow",
        targetAudience: "TikTok Shop creators, sellers, and MCN operators",
        requiredDemographic: null,
        completedCount: 0,
        personaIds: [],
        errorMessage: "Persona Agent failed after retries: 1 validation error for CreatorPersonaProfile",
        createdAt: "2026-06-03T04:58:12Z",
        updatedAt: "2026-06-03T05:01:05Z",
      },
    ]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    fireEvent.click(await screen.findByRole("tab", { name: "人设" }));

    expect(await screen.findByText("Persona Agent failed after retries: 1 validation error for CreatorPersonaProfile")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重试失败人设任务：人设任务 0 / 3" }));

    await waitFor(() => expect(videoBreakdownClient.retryPersonaGenerationJob).toHaveBeenCalledWith("persona-generation-job-failed"));
    expect(await screen.findByLabelText("人设任务 1 / 3，排队中")).toBeTruthy();
    expect(screen.queryByText("Persona Agent failed after retries: 1 validation error for CreatorPersonaProfile")).toBeNull();
  });

  it("keeps generated scripts in English by default and toggles script metadata to Chinese", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([completedEnglishScript]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect((await screen.findAllByText("Scale Content Without Writing")).length).toBeGreaterThan(0);
    expect(screen.getByRole("heading", { name: /^Storyboard$/ })).toBeTruthy();
    expect(screen.queryByText("不用从零写稿，也能规模化内容")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getByRole("heading", { name: /^分镜头脚本$/ })).toBeTruthy();
    expect(screen.getAllByText("不用从零写稿，也能规模化内容").length).toBeGreaterThan(0);
    expect(screen.queryByText("Scale Content Without Writing")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "EN" }));
    expect(screen.getAllByText("Scale Content Without Writing").length).toBeGreaterThan(0);
  });

  it("translates the competitive advantage script metadata in Chinese reading mode", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([completedCompetitiveScript]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    expect((await screen.findAllByText("Find Your Edge with Moras")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getAllByText("用 Moras 找到你的优势").length).toBeGreaterThan(0);
    expect(screen.getAllByText("选品 / 工作流").length).toBeGreaterThan(0);
    expect(screen.getByText("真实 Moras 录屏")).toBeTruthy();
    expect(screen.queryByText("Find Your Edge with Moras")).toBeNull();
  });

  it("uses stored Chinese script localization instead of frontend phrase fallback", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([completedStoredChineseScript]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect((await screen.findAllByText("Shelf Test Narrative")).length).toBeGreaterThan(0);
    expect(screen.getByText("Over-shoulder desk shot with product card and laptop.")).toBeTruthy();
    expect(screen.getByText("Use restrained creator footage to make the evaluation feel careful.")).toBeTruthy();
    expect(screen.queryByText("货架测试叙事")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "中文" }));

    expect(screen.getAllByText("货架测试叙事").length).toBeGreaterThan(0);
    expect(screen.getByText("桌面过肩镜头，同时看到商品卡片和电脑。")).toBeTruthy();
    expect(screen.getByText("保持同一位克制、谨慎的创作者。")).toBeTruthy();
    expect(screen.getByText("建立谨慎测试的可信理由。")).toBeTruthy();
    expect(screen.getByText("用克制的创作者素材，让评估显得更谨慎可信。")).toBeTruthy();
    expect(screen.queryByText("Over-shoulder desk shot with product card and laptop.")).toBeNull();
  });

  it("confirms destructive and generation actions in the script editorial room", async () => {
    const queuedRenderJob = {
      ...completedRenderJob,
      status: "queued",
      outputAssetUrl: null,
      outputFilename: null,
      outputAudioUrl: null,
      outputSubtitleUrl: null,
      fileSizeBytes: 0,
      durationSec: 0,
      width: 0,
      height: 0,
      qaSummary: {},
      errorMessage: null,
    };
    vi.mocked(videoBreakdownClient.createDirectorRenderJob).mockResolvedValue(queuedRenderJob);
    vi.mocked(videoBreakdownClient.getDirectorRenderJob).mockResolvedValue(completedRenderJob);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    fireEvent.click((await screen.findAllByRole("button", { name: /删除脚本/ }))[0]);

    expect(screen.getByRole("dialog", { name: "确认删除脚本" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "取消" }));
    expect(screen.queryByRole("dialog", { name: "确认删除脚本" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "生成视频" }));
    expect(screen.getByRole("dialog", { name: "确认生成视频" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "进入视频工厂" }));

    expect(screen.getByRole("tab", { name: "视频工厂" }).getAttribute("aria-selected")).toBe("true");
    expect(await screen.findByRole("heading", { name: "Stop Picking Products by Commission Alone" })).toBeTruthy();
    expect(screen.getByText("Director Agent")).toBeTruthy();
    expect(await screen.findByText("mock-director-agent-v1")).toBeTruthy();
    expect(screen.getByText("real_moras_screen_recording")).toBeTruthy();
    expect(screen.getByText("真实 Moras 素材库")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "渲染执行 / 输出视频" })).toBeTruthy();
    expect(screen.getByText("manual_veo_upload")).toBeTruthy();
    expect(screen.getByText("Opening generated Veo visual block.")).toBeTruthy();
    expect(screen.getByText("render_hyperframes_subtitle")).toBeTruthy();
    expect(screen.getByText("计划 / 待执行")).toBeTruthy();
    expect(videoBreakdownClient.createDirectorGenerationJob).toHaveBeenCalledWith("script-1");
    expect(videoBreakdownClient.getDirectorGenerationJob).toHaveBeenCalledWith("director-generation-job-1");
    expect(videoBreakdownClient.getDirectorPlan).toHaveBeenCalledWith("director-plan-1");
    expect(videoBreakdownClient.generateDirectorPlan).not.toHaveBeenCalled();
    expect(videoBreakdownClient.listManualFactoryAssets).toHaveBeenCalledWith("director-plan-1");
    expect(videoBreakdownClient.listMorasAssets).toHaveBeenCalledWith();
    expect(videoBreakdownClient.listDirectorPlanAssetBindings).toHaveBeenCalledWith("director-plan-1");
    expect(videoBreakdownClient.listDirectorRenderJobs).toHaveBeenCalledWith("director-plan-1");

    const file = new File(["fake veo clip"], "veo-1.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("上传 Veo 3.1 素材：veo_clip_1"), {
      target: { files: [file] },
    });

    expect(await screen.findByText(/veo-1\.mp4/)).toBeTruthy();
    expect(screen.getByText(/8\.0s · 720x1280/)).toBeTruthy();
    expect(screen.getByText("待审核")).toBeTruthy();
    expect(videoBreakdownClient.uploadManualFactoryAsset).toHaveBeenCalledWith("director-plan-1", "veo_clip_1", file);

    fireEvent.click(screen.getByRole("button", { name: "通过 Veo 3.1 素材审核：veo_clip_1" }));

    expect(videoBreakdownClient.reviewManualFactoryAsset).toHaveBeenCalledWith(
      "manual-asset-1",
      "approved",
      "人工确认素材文件可用于视频工厂。",
    );
    expect(await screen.findByText("审核通过")).toBeTruthy();
    expect(screen.getByText("待语义复核")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "通过 Veo 3.1 素材语义复核：veo_clip_1" }));

    expect(videoBreakdownClient.reviewManualFactoryAssetSemanticMatch).toHaveBeenCalledWith(
      "manual-asset-1",
      "passed",
      "人工确认素材语义匹配复制的提示词和时间线。",
    );
    expect(await screen.findByText("语义匹配通过")).toBeTruthy();

    const morasFile = new File(["fake Moras workflow"], "moras-workflow.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("上传真实素材：asset_2"), {
      target: { files: [morasFile] },
    });

    expect((await screen.findAllByText(/Moras workflow recording/)).length).toBeGreaterThan(0);
    expect(screen.getAllByText(/1080x1920/).length).toBeGreaterThan(0);
    expect(videoBreakdownClient.uploadMorasAsset).toHaveBeenCalledWith({
      assetType: "real_moras_screen_recording",
      morasAssetCategory: "workflow_screen_recording",
      title: "asset_2 · workflow_screen_recording",
      file: morasFile,
    });
    expect(videoBreakdownClient.bindDirectorPlanAsset).toHaveBeenCalledWith("director-plan-1", "asset_2", "moras-asset-1");

    fireEvent.click(screen.getByRole("button", { name: "通过绑定真实素材审核：asset_2" }));

    expect(videoBreakdownClient.reviewMorasAsset).toHaveBeenCalledWith(
      "moras-asset-1",
      "approved",
      "人工确认素材文件可用于 Moras 视频工厂。",
    );
    expect(await screen.findAllByText("待语义复核")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "通过绑定真实素材语义复核：asset_2" }));

    expect(videoBreakdownClient.reviewMorasAssetSemanticMatch).toHaveBeenCalledWith(
      "moras-asset-1",
      "passed",
      "人工确认真实 Moras 素材语义匹配导演计划需求。",
    );
    expect((await screen.findAllByText("语义匹配通过")).length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole("button", { name: "检查并生成视频草稿" }));

    await waitFor(() => expect(videoBreakdownClient.getDirectorRenderJob).toHaveBeenCalledWith("render-job-1"));
    expect(await screen.findByText("已输出视频草稿")).toBeTruthy();
    expect(screen.getByText(/render-job-1\.mp4/)).toBeTruthy();
    expect(screen.getByText(/38\.0s · 1080x1920/)).toBeTruthy();
    expect(screen.getByText("字幕 VTT")).toBeTruthy();
    expect(screen.getByText("合成旁白音频 / TTS")).toBeTruthy();
    expect(await screen.findByText(/视频 MP4 · 8\.0 KB · 保留中/)).toBeTruthy();
    expect(screen.getByText(/音频 M4A · 4\.0 KB · 保留中/)).toBeTruthy();
    expect(screen.getByText(/字幕 VTT · 1\.0 KB · 保留中/)).toBeTruthy();
    expect(screen.getByText(/字幕 HTML sidecar · 1\.5 KB · 保留中/)).toBeTruthy();
    expect(screen.getByText("用量记账")).toBeTruthy();
    expect(screen.getByText("local_ffmpeg_draft_v1")).toBeTruthy();
    expect(screen.getAllByText("webvtt_track_v1").length).toBeGreaterThan(0);
    expect(screen.getAllByText("WebVTT 预览").length).toBeGreaterThan(0);
    expect(screen.queryByText("HyperFrames captions")).toBeNull();
    expect(screen.getByText("312")).toBeTruthy();
    expect(screen.getByText("QA：passed")).toBeTruthy();
    expect(screen.getByText("人审：待人工 QA")).toBeTruthy();
    expect(screen.getByText("当前最新视频草稿还没有通过人工 QA，暂不能创建交付记录。")).toBeTruthy();
    expect(screen.getByText("音频轨")).toBeTruthy();
    expect(screen.getByText("字幕 cues")).toBeTruthy();
    expect(videoBreakdownClient.createDirectorRenderJob).toHaveBeenCalledWith("director-plan-1");
    expect(videoBreakdownClient.listDirectorRenderArtifacts).toHaveBeenCalledWith("render-job-1");
    expect(videoBreakdownClient.getDirectorRenderUsage).toHaveBeenCalledWith("render-job-1");

    const deletedCaptionArtifacts = completedRenderArtifacts.map(artifact =>
      artifact.id === "artifact-caption-composition-1"
        ? { ...artifact, storageStatus: "deleted", deletedAt: "2026-06-01T00:10:00Z" }
        : artifact,
    );
    vi.mocked(videoBreakdownClient.deleteDirectorRenderArtifact).mockResolvedValue(deletedCaptionArtifacts[3]);
    vi.mocked(videoBreakdownClient.listDirectorRenderArtifacts).mockResolvedValue(deletedCaptionArtifacts);
    fireEvent.click(screen.getByRole("button", { name: "删除字幕 HTML sidecar" }));

    expect(videoBreakdownClient.deleteDirectorRenderArtifact).toHaveBeenCalledWith("artifact-caption-composition-1");
    expect(await screen.findByText(/字幕 HTML sidecar · 1\.5 KB · 已删除/)).toBeTruthy();
    expect(screen.queryByRole("link", { name: /字幕 HTML sidecar/ })).toBeNull();
    expect((screen.getByRole("button", { name: "删除字幕 HTML sidecar" }) as HTMLButtonElement).disabled).toBe(true);

    const createPublishButton = screen.getByRole("button", { name: "创建交付记录" }) as HTMLButtonElement;
    expect(createPublishButton.disabled).toBe(true);
    fireEvent.click(screen.getByRole("button", { name: "通过渲染 QA：render-job-1" }));

    expect(videoBreakdownClient.reviewDirectorRenderJobQa).toHaveBeenCalledWith(
      "render-job-1",
      "approved",
      "人工 QA 通过，可进入手动发布/交付。",
    );
    expect(await screen.findByText("人工 QA 已通过，可以创建手动发布/交付记录。")).toBeTruthy();
    expect((screen.getByRole("button", { name: "创建交付记录" }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole("button", { name: "创建交付记录" }));

    expect(videoBreakdownClient.createDirectorPublishRecord).toHaveBeenCalledWith("director-plan-1", {
      renderJobId: "render-job-1",
      channel: "manual_upload",
      publishStatus: "ready_for_upload",
      caption: "",
      notes: "QA 通过后创建的手动上传/交付记录。",
    });
    expect(await screen.findByText("待手动上传")).toBeTruthy();
    expect(screen.getByText(/manual_upload · render render-j/)).toBeTruthy();
  });

  it("recovers a blocked render job and retries it from Video Factory", async () => {
    const blockedRenderJob = {
      ...completedRenderJob,
      status: "blocked",
      outputAssetUrl: null,
      outputFilename: null,
      outputAudioUrl: null,
      outputSubtitleUrl: null,
      fileSizeBytes: 0,
      durationSec: 0,
      width: 0,
      height: 0,
      readinessSummary: {
        status: "blocked",
        blockers: [
          {
            type: "manual_veo_review",
            ref: "veo_clip_1",
            message: "Veo 3.1 clip veo_clip_1 is pending review and cannot be rendered yet.",
          },
        ],
      },
      qaSummary: {},
      errorMessage: "渲染前还有素材未上传、未绑定或未审核通过。",
    };
    const retryQueuedRenderJob = {
      ...blockedRenderJob,
      id: "render-job-retry",
      status: "queued",
      readinessSummary: {},
      errorMessage: null,
      createdAt: "2026-06-01T00:03:00Z",
      updatedAt: "2026-06-01T00:03:00Z",
    };
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([completedDirectorPlan]);
    vi.mocked(videoBreakdownClient.listDirectorRenderJobs).mockResolvedValue([blockedRenderJob]);
    vi.mocked(videoBreakdownClient.retryDirectorRenderJob).mockResolvedValue(retryQueuedRenderJob);
    vi.mocked(videoBreakdownClient.getDirectorRenderJob).mockResolvedValue({
      ...retryQueuedRenderJob,
      status: "blocked",
      readinessSummary: blockedRenderJob.readinessSummary,
      errorMessage: blockedRenderJob.errorMessage,
    });
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "script-1");

    render(<VideoBreakdownWorkspace />);

    expect(await screen.findByRole("heading", { name: "Stop Picking Products by Commission Alone" })).toBeTruthy();
    expect(await screen.findByText("素材未齐，暂不能出片")).toBeTruthy();
    expect(screen.getByText("Veo 3.1 clip veo_clip_1 is pending review and cannot be rendered yet.")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "重试渲染" }));

    await waitFor(() => expect(videoBreakdownClient.retryDirectorRenderJob).toHaveBeenCalledWith("render-job-1"));
    await waitFor(() => expect(videoBreakdownClient.getDirectorRenderJob).toHaveBeenCalledWith("render-job-retry"));
  });

  it("cleans expired render artifacts without hiding the Video Factory workspace", async () => {
    const expiredArtifacts = completedRenderArtifacts.map(artifact =>
      artifact.id === "artifact-subtitle-1"
        ? { ...artifact, storageStatus: "retention_expired" }
        : artifact,
    );
    const cleanedArtifacts = expiredArtifacts.map(artifact =>
      artifact.id === "artifact-subtitle-1"
        ? { ...artifact, storageStatus: "deleted", deletedAt: "2026-06-01T00:11:00Z" }
        : artifact,
    );
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([completedDirectorPlan]);
    vi.mocked(videoBreakdownClient.listDirectorRenderJobs).mockResolvedValue([completedRenderJob]);
    vi.mocked(videoBreakdownClient.listDirectorRenderArtifacts).mockResolvedValueOnce(expiredArtifacts).mockResolvedValue(cleanedArtifacts);
    vi.mocked(videoBreakdownClient.cleanupExpiredDirectorRenderArtifacts).mockResolvedValue(cleanedArtifacts);
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "script-1");

    render(<VideoBreakdownWorkspace />);
    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));

    expect(await screen.findByText(/字幕 VTT · 1\.0 KB · 保留已过期/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "清理过期产物" }));

    expect(videoBreakdownClient.cleanupExpiredDirectorRenderArtifacts).toHaveBeenCalledWith("render-job-1");
    expect(await screen.findByText(/字幕 VTT · 1\.0 KB · 已删除/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "渲染执行 / 输出视频" })).toBeTruthy();
  });

  it("recovers available scripts directly inside Video Factory", async () => {
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));

    expect(await screen.findByText(/后端已有 1 个脚本/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(screen.getByLabelText("上传到真实 Moras 素材库")).toBeTruthy();
    expect(screen.getByLabelText("选择待生成脚本")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "生成导演计划" }));

    expect(await screen.findByRole("heading", { name: "Stop Picking Products by Commission Alone" })).toBeTruthy();
    expect(screen.getByText("Director Agent")).toBeTruthy();
    expect(videoBreakdownClient.createDirectorGenerationJob).toHaveBeenCalledWith("script-1");
  });

  it("keeps Video Factory controls visible while Director Agent is generating", async () => {
    let resolveJob: (job: typeof completedDirectorGenerationJob) => void = () => {};
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockReturnValue(
      new Promise(resolve => {
        resolveJob = resolve;
      }),
    );
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));
    expect(await screen.findByText(/后端已有 1 个脚本/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "生成导演计划" }));

    expect(await screen.findByText("导演 Agent 正在生成计划")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(screen.getByLabelText("上传到真实 Moras 素材库")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "渲染执行 / 输出视频" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "外部生成视频片段" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实素材绑定" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "剪辑时间线" })).toBeTruthy();
    expect(screen.getByText(/刷新后会自动恢复这个脚本/)).toBeTruthy();

    await act(async () => {
      resolveJob(completedDirectorGenerationJob);
    });

    expect(await screen.findByText("mock-director-agent-v1")).toBeTruthy();
    expect(screen.getByText("Director Agent")).toBeTruthy();
  });

  it("keeps Video Factory modules visible when Director Plan generation fails", async () => {
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockResolvedValue({
      ...completedDirectorGenerationJob,
      status: "failed",
      directorPlanId: null,
      errorMessage: "导演计划结构校验失败",
    });
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));
    expect(await screen.findByText(/后端已有 1 个脚本/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "生成导演计划" }));

    expect(await screen.findByRole("heading", { name: "导演计划生成失败" })).toBeTruthy();
    expect(screen.getByText("导演计划结构校验失败")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "渲染执行 / 输出视频" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "外部生成视频片段" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实素材绑定" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "剪辑时间线" })).toBeTruthy();
  });

  it("shows a recoverable error when a succeeded Director job has no plan record", async () => {
    vi.mocked(videoBreakdownClient.getDirectorPlan).mockRejectedValue(new Error("Director plan not found"));
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockResolvedValue(completedDirectorGenerationJob);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));
    expect(await screen.findByText(/后端已有 1 个脚本/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "生成导演计划" }));

    expect(await screen.findByRole("heading", { name: "导演计划生成失败" })).toBeTruthy();
    expect(screen.getByText("导演任务已完成，但没有找到可恢复的导演计划。请重试任务或重新生成导演计划。")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "渲染执行 / 输出视频" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "外部生成视频片段" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实素材绑定" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "剪辑时间线" })).toBeTruthy();
  });

  it("restores the latest Director Plan for the last active factory script after refresh", async () => {
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "script-1");
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([completedDirectorPlan]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));

    expect(await screen.findByText("mock-director-agent-v1")).toBeTruthy();
    expect(screen.getByText("Director Agent")).toBeTruthy();
    expect(videoBreakdownClient.listDirectorPlans).toHaveBeenCalledWith("script-1");
    expect(videoBreakdownClient.listDirectorGenerationJobs).toHaveBeenCalledWith("script-1", true);
    expect(videoBreakdownClient.listDirectorRenderJobs).toHaveBeenCalledWith("director-plan-1");
    expect(videoBreakdownClient.generateDirectorPlan).not.toHaveBeenCalled();
    expect(videoBreakdownClient.createDirectorGenerationJob).not.toHaveBeenCalled();
  });

  it("restores a stored factory script even when it is hidden from the visible script list", async () => {
    const hiddenScript = {
      ...completedScript,
      id: "hidden-script-with-plan",
      topicPlan: {
        ...completedScript.topicPlan,
        title: "Hidden Factory Script",
      },
      script: {
        ...completedScript.script,
        scriptTitle: "Hidden Factory Script",
      },
    };
    const hiddenPlan = {
      ...completedDirectorPlan,
      id: "hidden-director-plan",
      scriptId: "hidden-script-with-plan",
    };
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "hidden-script-with-plan");
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([completedScript]);
    vi.mocked(videoBreakdownClient.getScript).mockResolvedValue(hiddenScript);
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockImplementation((scriptId?: string) => (
      Promise.resolve(scriptId === "hidden-script-with-plan" ? [hiddenPlan] : [])
    ));
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));

    expect(await screen.findByRole("heading", { name: "Hidden Factory Script" })).toBeTruthy();
    expect(await screen.findByText("mock-director-agent-v1")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(videoBreakdownClient.getScript).toHaveBeenCalledWith("hidden-script-with-plan");
    expect(videoBreakdownClient.listDirectorPlans).toHaveBeenCalledWith("hidden-script-with-plan");
    expect(videoBreakdownClient.createDirectorGenerationJob).not.toHaveBeenCalled();
  });

  it("restores an in-flight Director generation job after refresh", async () => {
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "script-1");
    const runningJob = {
      ...completedDirectorGenerationJob,
      status: "generating",
      directorPlanId: null,
    };
    vi.mocked(videoBreakdownClient.listDirectorGenerationJobs).mockResolvedValue([runningJob]);
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockResolvedValue(runningJob);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));

    expect(await screen.findByText("导演 Agent 正在生成计划")).toBeTruthy();
    expect(screen.getByText(/导演任务 director/)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    expect(videoBreakdownClient.listDirectorGenerationJobs).toHaveBeenCalledWith("script-1", true);
    expect(videoBreakdownClient.getDirectorGenerationJob).toHaveBeenCalledWith("director-generation-job-1");
    expect(videoBreakdownClient.createDirectorGenerationJob).not.toHaveBeenCalled();
  });

  it("allows canceling an in-flight Director generation job without hiding factory modules", async () => {
    let resolveJob: (job: typeof completedDirectorGenerationJob) => void = () => {};
    vi.mocked(videoBreakdownClient.getDirectorGenerationJob).mockReturnValue(
      new Promise(resolve => {
        resolveJob = resolve;
      }),
    );
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));
    expect(await screen.findByText(/后端已有 1 个脚本/)).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "生成导演计划" }));

    expect(await screen.findByRole("button", { name: "取消任务" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "取消任务" }));

    expect(videoBreakdownClient.cancelDirectorGenerationJob).toHaveBeenCalledWith("director-generation-job-1");
    expect(await screen.findByRole("heading", { name: "已选择脚本，等待生成导演计划" })).toBeTruthy();
    expect(screen.getByText("用户取消了导演计划生成任务。")).toBeTruthy();
    expect(screen.getByRole("button", { name: "重试任务" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();

    await act(async () => {
      resolveJob(completedDirectorGenerationJob);
    });
  });

  it("retries the latest failed Director generation job restored after refresh", async () => {
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "script-1");
    const failedJob = {
      ...completedDirectorGenerationJob,
      status: "failed",
      directorPlanId: null,
      errorMessage: "导演计划结构校验失败",
    };
    vi.mocked(videoBreakdownClient.listDirectorGenerationJobs).mockResolvedValue([failedJob]);
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));
    expect(await screen.findByRole("heading", { name: "导演计划生成失败" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重试任务" }));

    expect(videoBreakdownClient.listDirectorGenerationJobs).toHaveBeenCalledWith("script-1", true);
    expect(videoBreakdownClient.retryDirectorGenerationJob).toHaveBeenCalledWith("director-generation-job-1");
    expect(await screen.findByText("导演 Agent 正在生成计划")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "真实 Moras 素材库" })).toBeTruthy();
  });

  it("uses the selected factory script after a stale active script fails", async () => {
    const staleScript = {
      ...completedScript,
      id: "stale-script",
      topicPlan: { ...completedScript.topicPlan, title: "Deleted Local Script" },
      script: { ...completedScript.script, scriptTitle: "Deleted Local Script" },
    };
    window.localStorage.setItem("moras.videoFactory.activeScriptId", "stale-script");
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([staleScript, completedScript]);
    vi.mocked(videoBreakdownClient.listDirectorPlans).mockResolvedValue([]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "视频工厂" }));
    expect(await screen.findByRole("heading", { name: "已选择脚本，等待生成导演计划" })).toBeTruthy();

    fireEvent.change(screen.getByLabelText("选择待生成脚本"), { target: { value: "script-1" } });
    fireEvent.click(screen.getByRole("button", { name: "生成导演计划" }));

    expect(await screen.findByText("Director Agent")).toBeTruthy();
    expect(videoBreakdownClient.createDirectorGenerationJob).toHaveBeenCalledWith("script-1");
  });

  it("shows generating and queued script task cards while Script Agent is running", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listCreatorPersonas).mockResolvedValue([completedPersonaRecord]);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    expect(await screen.findByText("暂无脚本，先在人设页生成并选择人设。")).toBeTruthy();
    fireEvent.change(screen.getByLabelText("人设"), { target: { value: "persona-record-aaliyah" } });

    fireEvent.click(screen.getByRole("button", { name: "生成脚本" }));

    expect(await screen.findByLabelText("脚本任务 1 / 3，生成中")).toBeTruthy();
    expect(screen.getByLabelText("脚本任务 2 / 3，排队中")).toBeTruthy();
    expect(screen.getByLabelText("脚本任务 3 / 3，排队中")).toBeTruthy();
    expect(screen.getByText("正在生成第 1 个脚本，后端 Script Agent 正在运行。")).toBeTruthy();
    expect(screen.getByText("第 2 个脚本在队列中，当前批次会按顺序返回。")).toBeTruthy();
    expect(screen.queryByText("暂无脚本，先在人设页生成并选择人设。")).toBeNull();
    expect((screen.getByLabelText("数量") as HTMLSelectElement).disabled).toBe(true);
    expect((screen.getByLabelText("类型") as HTMLSelectElement).disabled).toBe(true);
    expect(videoBreakdownClient.createScriptGenerationJob).toHaveBeenCalledWith({
      scriptCount: 3,
      scriptType: "all",
      personaId: "persona-record-aaliyah",
      personaHint: expect.objectContaining({
        display_name: "Aaliyah Brooks",
        role_task: expect.stringContaining("TikTok Shop creators"),
        proof_policy: expect.stringContaining("real Moras workflow"),
        script_agent_handoff: expect.objectContaining({
          forbiddenClaims: expect.arrayContaining(["ai guarantees sales"]),
        }),
        veo_identity_string: expect.stringContaining("Aaliyah Brooks"),
      }),
    });
  });

  it("restores queued and generating script task cards after Script Editorial remounts", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([
      {
        id: "generation-job-restored",
        status: "generating",
        scriptCount: 3,
        scriptType: "all",
        sourceBreakdownIds: [],
        completedCount: 0,
        scriptIds: [],
        errorMessage: null,
        createdAt: "2026-06-01T00:00:00Z",
        updatedAt: "2026-06-01T00:00:00Z",
      },
    ]);
    vi.mocked(videoBreakdownClient.getScriptGenerationJob).mockResolvedValue({
      id: "generation-job-restored",
      status: "generating",
      scriptCount: 3,
      scriptType: "all",
      sourceBreakdownIds: [],
      completedCount: 0,
      scriptIds: [],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:00Z",
    });
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect(await screen.findByLabelText("脚本任务 1 / 3，生成中")).toBeTruthy();
    expect(screen.getAllByLabelText("脚本任务 2 / 3，排队中").length).toBeGreaterThan(0);
    expect(screen.getByLabelText("脚本任务 3 / 3，排队中")).toBeTruthy();
    expect(screen.queryByText("暂无脚本，先在人设页生成并选择人设。")).toBeNull();
    expect((screen.getByLabelText("数量") as HTMLSelectElement).disabled).toBe(true);

    fireEvent.click(screen.getByRole("tab", { name: "视频拆解" }));
    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect(await screen.findByLabelText("脚本任务 1 / 3，生成中")).toBeTruthy();
    expect(screen.getAllByLabelText("脚本任务 2 / 3，排队中").length).toBeGreaterThan(0);
  });

  it("loads completed script cards while later script tasks continue generating", async () => {
    vi.mocked(videoBreakdownClient.listScripts)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ ...completedScript, id: "script-incremental", scriptType: "all" }]);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([
      {
        id: "generation-job-incremental",
        status: "generating",
        scriptCount: 3,
        scriptType: "all",
        sourceBreakdownIds: [],
        completedCount: 0,
        scriptIds: [],
        errorMessage: null,
        createdAt: "2026-06-01T00:00:00Z",
        updatedAt: "2026-06-01T00:00:00Z",
      },
    ]);
    vi.mocked(videoBreakdownClient.getScriptGenerationJob).mockResolvedValue({
      id: "generation-job-incremental",
      status: "generating",
      scriptCount: 3,
      scriptType: "all",
      sourceBreakdownIds: [],
      completedCount: 1,
      scriptIds: ["script-incremental"],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:04Z",
    });

    render(<VideoBreakdownWorkspace />);
    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect(await screen.findByRole("button", { name: "Stop Picking Products by Commission Alone" })).toBeTruthy();
    expect(screen.queryByLabelText("脚本任务 1 / 3，生成中")).toBeNull();
    expect(screen.getByLabelText("脚本任务 2 / 3，生成中")).toBeTruthy();
    expect(screen.getByLabelText("脚本任务 3 / 3，排队中")).toBeTruthy();
    expect(screen.getAllByText("已完成 1 / 3").length).toBeGreaterThan(0);
  });

  it("shows compact failed script task cards and deletes the persisted failed job", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([
      {
        id: "generation-job-failed",
        status: "failed",
        scriptCount: 3,
        scriptType: "all",
        sourceBreakdownIds: [],
        completedCount: 0,
        scriptIds: [],
        errorMessage: [
          "15 validation errors for ScriptAgentBatch",
          "scripts.0.storyboard.1 Value error, storyboard shot_2.facial_expression is too generic for editor use",
          "[type=value_error, input_value={'shot_id': 'shot_2', 'ti...流程和简洁操作'}}}, input_type=dict]",
          "For further information visit",
          "https://errors.pydantic.dev/2.13/v/value_error",
        ].join("\n"),
        createdAt: "2026-06-01T00:00:00Z",
        updatedAt: "2026-06-01T00:00:02Z",
      },
    ]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect(await screen.findByLabelText("脚本任务 1 / 3，生成失败")).toBeTruthy();
    expect(screen.getByText("脚本任务 1 / 3")).toBeTruthy();
    expect(screen.getByText(/15 validation errors for ScriptAgentBatch/)).toBeTruthy();
    expect(screen.queryByText(/errors\.pydantic\.dev/)).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "删除失败脚本任务：脚本任务 1 / 3" }));

    await waitFor(() => expect(videoBreakdownClient.deleteScriptGenerationJob).toHaveBeenCalledWith("generation-job-failed"));
    await waitFor(() => expect(screen.queryByText("脚本任务 1 / 3")).toBeNull());
    expect(screen.getByText("暂无脚本，先在人设页生成并选择人设。")).toBeTruthy();
  });

  it("retries failed script generation jobs from the task card", async () => {
    vi.mocked(videoBreakdownClient.listScripts).mockResolvedValue([]);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([
      {
        id: "generation-job-failed",
        status: "failed",
        scriptCount: 3,
        scriptType: "all",
        sourceBreakdownIds: [],
        completedCount: 0,
        scriptIds: [],
        errorMessage: "Server disconnected without sending a response.",
        createdAt: "2026-06-01T00:00:00Z",
        updatedAt: "2026-06-01T00:00:02Z",
      },
    ]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));

    expect(await screen.findByText("模型服务连接中断，系统已自动重试但仍失败。请点击重试任务。")).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "重试失败脚本任务：脚本任务 1 / 3" }));

    await waitFor(() => expect(videoBreakdownClient.retryScriptGenerationJob).toHaveBeenCalledWith("generation-job-failed"));
    expect(await screen.findByLabelText("脚本任务 1 / 3，排队中")).toBeTruthy();
    expect(screen.queryByText("模型服务连接中断，系统已自动重试但仍失败。请点击重试任务。")).toBeNull();
  });

  it("clears restored task cards when a persisted job succeeds", async () => {
    vi.mocked(videoBreakdownClient.listScripts)
      .mockResolvedValueOnce([])
      .mockResolvedValueOnce([{ ...completedScript, id: "script-generated", scriptType: "all" }]);
    vi.mocked(videoBreakdownClient.listScriptGenerationJobs).mockResolvedValue([
      {
        id: "generation-job-succeeded",
        status: "generating",
        scriptCount: 1,
        scriptType: "all",
        sourceBreakdownIds: [],
        completedCount: 0,
        scriptIds: [],
        errorMessage: null,
        createdAt: "2026-06-01T00:00:00Z",
        updatedAt: "2026-06-01T00:00:00Z",
      },
    ]);
    vi.mocked(videoBreakdownClient.getScriptGenerationJob).mockResolvedValue({
      id: "generation-job-succeeded",
      status: "succeeded",
      scriptCount: 1,
      scriptType: "all",
      sourceBreakdownIds: [],
      completedCount: 1,
      scriptIds: ["script-generated"],
      errorMessage: null,
      createdAt: "2026-06-01T00:00:00Z",
      updatedAt: "2026-06-01T00:00:02Z",
    });
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    expect(await screen.findByLabelText("脚本任务 1 / 1，生成中")).toBeTruthy();

    expect(await screen.findByRole("button", { name: "Stop Picking Products by Commission Alone" })).toBeTruthy();
    expect(screen.queryByLabelText("脚本任务 1 / 1，生成中")).toBeNull();
    expect((screen.getByLabelText("数量") as HTMLSelectElement).disabled).toBe(false);
  });

  it("generateScripts client mock remains available for legacy callers", async () => {
    await act(async () => {
      await expect(videoBreakdownClient.generateScripts({
        scriptCount: 3,
        scriptType: "all",
      })).resolves.toEqual([{ ...completedScript, id: "script-generated", scriptType: "all" }]);
    });
  });

  it("opens AI edit dialog and shows script editing progress after submit", async () => {
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("tab", { name: "脚本编辑部" }));
    fireEvent.click(await screen.findByRole("button", { name: "AI 编辑" }));

    expect(screen.getByRole("dialog", { name: "AI 编辑脚本" })).toBeTruthy();
    fireEvent.change(screen.getByLabelText("修改意见"), {
      target: { value: "开头更像真实创作者，减少教程感。" },
    });
    fireEvent.click(screen.getByRole("button", { name: "提交修改" }));

    expect(screen.queryByRole("dialog", { name: "AI 编辑脚本" })).toBeNull();
    expect(screen.getAllByText(/等待修改|脚本智能体正在修改/).length).toBeGreaterThan(0);
  });

  it("submits one URL and renders the result dashboard", async () => {
    vi.mocked(videoBreakdownClient.createSocialVideoAnalysis).mockResolvedValue(completedAnalysis);
    render(<VideoBreakdownWorkspace />);

    fireEvent.change(screen.getByLabelText("视频链接"), {
      target: { value: "https://www.tiktok.com/@demo/video/1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /开始拆解/ }));

    expect((await screen.findAllByText("禁忌型")).length).toBeGreaterThan(0);
    expect(screen.queryByText("脚本智能体交接")).toBeNull();
    expect(screen.queryByText("脚本智能体指令")).toBeNull();
    expect(screen.getByText("结构时间线")).toBeTruthy();
    expect(screen.getByRole("heading", { name: "爆款参考分镜脚本" })).toBeTruthy();
    const referenceStoryboardTable = screen.getByRole("table", { name: "爆款参考分镜脚本" });
    expect(within(referenceStoryboardTable).getByRole("columnheader", { name: "Shot / Time" })).toBeTruthy();
    expect(within(referenceStoryboardTable).getByText("Shot 01")).toBeTruthy();
    expect(within(referenceStoryboardTable).getByText("Save this checklist")).toBeTruthy();
    expect(screen.queryByText("结构协议")).toBeNull();
    expect(screen.getByRole("link", { name: /导出拆解文档/ })).toBeTruthy();
    expect(videoBreakdownClient.createSocialVideoAnalysis).toHaveBeenCalledWith("https://www.tiktok.com/@demo/video/1");
  });

  it("shows a reuse notice when a duplicate URL opens an existing breakdown", async () => {
    vi.mocked(videoBreakdownClient.createSocialVideoAnalysis).mockResolvedValue({
      ...completedAnalysis,
      reusedExisting: true,
    });
    render(<VideoBreakdownWorkspace />);

    fireEvent.change(screen.getByLabelText("视频链接"), {
      target: { value: "https://www.tiktok.com/@demo/video/1" },
    });
    fireEvent.click(screen.getByRole("button", { name: /开始拆解/ }));

    expect((await screen.findByRole("status")).textContent).toContain("检测到该视频已拆解过");
    expect((await screen.findAllByText("禁忌型")).length).toBeGreaterThan(0);
  });

  it("uploads one local video and renders the result dashboard", async () => {
    vi.mocked(videoBreakdownClient.uploadSocialVideoAnalysis).mockResolvedValue(completedAnalysis);
    render(<VideoBreakdownWorkspace />);

    const file = new File(["fake video"], "sample.mp4", { type: "video/mp4" });
    fireEvent.change(screen.getByLabelText("上传本地视频"), { target: { files: [file] } });

    expect(screen.getByText(/已选择本地视频：sample.mp4/)).toBeTruthy();
    expect(screen.queryByText("禁忌型")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: /开始拆解/ }));

    expect((await screen.findAllByText("禁忌型")).length).toBeGreaterThan(0);
    expect(screen.queryByText("结构协议")).toBeNull();
    expect(videoBreakdownClient.uploadSocialVideoAnalysis).toHaveBeenCalledWith(file);
  });

  it("opens the library drawer and selects a history card", async () => {
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([completedAnalysis]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /历史/ }));

    expect(await screen.findByRole("dialog", { name: "视频拆解库" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /查看视频拆解：步骤清单演示视频/ }));

    expect(screen.queryByRole("dialog", { name: "视频拆解库" })).toBeNull();
    expect((screen.getAllByText("禁忌型")).length).toBeGreaterThan(0);
    expect(screen.queryByText("脚本智能体交接")).toBeNull();
  });

  it("deletes a history card from the breakdown library", async () => {
    vi.mocked(videoBreakdownClient.listSocialVideoAnalyses).mockResolvedValue([completedAnalysis]);
    render(<VideoBreakdownWorkspace />);

    fireEvent.click(screen.getByRole("button", { name: /历史/ }));
    expect(await screen.findByRole("dialog", { name: "视频拆解库" })).toBeTruthy();
    fireEvent.click(await screen.findByRole("button", { name: /删除视频拆解：步骤清单演示视频/ }));

    expect(screen.getByRole("dialog", { name: "确认删除视频拆解" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "删除" }));

    expect(videoBreakdownClient.deleteSocialVideoAnalysis).toHaveBeenCalledWith("analysis-1");
    expect(await screen.findByText("暂无历史拆解记录。")).toBeTruthy();

    fireEvent.click(screen.getAllByRole("button", { name: "关闭历史库" })[0]);
    fireEvent.click(screen.getByRole("tab", { name: "创意仓库" }));

    expect(screen.queryByText("禁忌型开头钩子")).toBeNull();
    expect(screen.getByText("Joey 数字反常识开场")).toBeTruthy();
  });
});
