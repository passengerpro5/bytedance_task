import { useMemo, useState } from "react";
import {
  ArrowLeft,
  Brain,
  Bot,
  Clapperboard,
  ListTree,
  MessageSquareText,
  MousePointerClick,
  Send,
  ShieldCheck,
  UserRound,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import type { JsonObject, JsonValue, SocialVideoAnalysis } from "../types";
import "./CreativeLibraryPage.css";

type LibraryKey = "hook" | "persona" | "cta" | "structure" | "storyboard" | "scene";
type LibraryStatus = "reusable" | "watch" | "blocked";

type CreativeAsset = {
  id: string;
  library: LibraryKey;
  sourceBreakdownId?: string;
  sourceBreakdownIds?: string[];
  title: string;
  summary: string;
  usage: string;
  status: LibraryStatus;
  risk: string;
  source: string;
  evidence: string;
  related: string[];
  storyboardShots?: JsonObject[];
  scriptType?: string;
};

export type CreativeAssetScriptGenerationIntent = {
  id: string;
  assetTitle: string;
  scriptType: string;
  sourceBreakdownIds: string[];
};

const libraryTabs: Array<{ key: LibraryKey; label: string; Icon: LucideIcon }> = [
  { key: "hook", label: "Hook", Icon: MousePointerClick },
  { key: "structure", label: "结构", Icon: ListTree },
  { key: "storyboard", label: "分镜", Icon: Clapperboard },
  { key: "cta", label: "CTA", Icon: Send },
  { key: "persona", label: "人设", Icon: UserRound },
  { key: "scene", label: "场景", Icon: Clapperboard },
];

const statusCopy: Record<LibraryStatus, string> = {
  reusable: "可复用",
  watch: "观察中",
  blocked: "禁用",
};

const joeyTikTokShopScriptAssets: CreativeAsset[] = [
  {
    id: "joey-tiktok-shop-number-hook",
    library: "hook",
    sourceBreakdownIds: [],
    title: "Joey 数字反常识开场",
    summary: "公式：身份 + 具体金额 + 时间段 + 反常识细节。数字只负责建立规模感，真正让人停下来的，是“不露脸”“只卖鞋”“每天不到 10 分钟”这类反常识细节。",
    usage: "适合 Moras 的 5K+ TikTok Shop creator 开场：先给真实来源里的观察数字，再立刻补一个让人意外的工作流差异。",
    status: "reusable",
    risk: "金额和排名只能作为来源观察或 approved proof，不能写成 Moras 承诺、普遍结果或 guaranteed income。",
    source: "内置学习样本：Joey TikTok Shop 口播 2 / 3 / 4 / 7 / 10",
    evidence: "用户提供的 18 条脚本中，曝光型脚本 6 条都用 creator identity + GMV/income + surprising detail 启动。",
    related: ["曝光型", "数字钩子", "反常识", "approved proof"],
    scriptType: "Secret / Exposed",
  },
  {
    id: "joey-tiktok-shop-scene-setup-hook",
    library: "hook",
    sourceBreakdownIds: [],
    title: "Let's set the scene 代入开场",
    summary: "公式：Let's set the scene + 观众正在做的事 + 观众以为做对的事 + 残酷转折。关键是说出“你明明很努力，但结果还是没有变”的日常处境。",
    usage: "适合把 Moras 接到创作者的真实卡点：选品、写脚本、拍视频、发出去，但还是没有订单或没有稳定测试节奏。",
    status: "reusable",
    risk: "不要把观众骂成失败者；结尾必须桥接到具体 Moras 工作流，而不是停在情绪攻击。",
    source: "内置学习样本：Joey TikTok Shop 口播 1",
    evidence: "用户标注的结构亮点 3：Let's set the scene 公式。",
    related: ["代入", "创作者日常", "痛点桥接", "Moras workflow"],
    scriptType: "Beginner Trap",
  },
  {
    id: "joey-tiktok-shop-wake-up-hook",
    library: "hook",
    sourceBreakdownIds: [],
    title: "骂醒型三误区钩子",
    summary: "用“你每天都在犯的 3 个错”直接切入，再把每个错误压缩成可执行命令。典型收口是 Move on. Fix it. Cut it out.",
    usage: "适合新手 TikTok Shop creator 的 mistake list：选错产品、死磕单品、口播没信心、镜头有 dead space。",
    status: "reusable",
    risk: "可以直白，但不能使用侮辱、仇恨或羞辱式表达；不要承诺按建议做就一定五位数收入。",
    source: "内置学习样本：Joey TikTok Shop 口播 1 / 8 / 13 / 14",
    evidence: "用户分类中骂醒型共 4 条，核心都是错误点 + 简短修正。",
    related: ["骂醒型", "Mistake List", "短句收口", "creator coaching"],
    scriptType: "Mistake List",
  },
  {
    id: "joey-tiktok-shop-five-category-taxonomy",
    library: "structure",
    sourceBreakdownIds: [],
    title: "Joey 五类增长脚本结构",
    summary: "18 条脚本可归为：曝光型 6 条、骂醒型 4 条、造梦型 4 条、时机型 3 条、招募型 1 条。它们不是不同话题，而是不同的观众动机入口。",
    usage: "适合给 Script Agent 做批量差异化：同一 Moras 工作流可以分别从榜单曝光、错误纠偏、生活想象、Q4 时机、创作者招募切入。",
    status: "reusable",
    risk: "分类只能指导创意角度，不能把来源人物、原口播、原金额照搬进 Moras 脚本。",
    source: "内置学习样本：用户对 18 条 Joey 口播的分类",
    evidence: "用户已给出分类：曝光型 2/3/4/6/7/10，骂醒型 1/8/13/14，造梦型 5/11/12/16，时机型 9/15/17，招募型 18。",
    related: ["曝光型", "骂醒型", "造梦型", "时机型"],
    scriptType: "Shoppable Video Workflow",
  },
  {
    id: "joey-tiktok-shop-research-for-you-structure",
    library: "structure",
    sourceBreakdownIds: [],
    title: "我替你做功课结构",
    summary: "公式：我研究了谁 + 具体时间/动作证据 + 我发现两件事 + 免费告诉你。它把创作者从“卖课的人”变成“替你研究过的人”。",
    usage: "适合 Moras 脚本里引入 creator proof、top earner screenshots、产品榜单或 Moras Data 观察结果。",
    status: "reusable",
    risk: "必须有真实来源或 approved proof 才能说研究过；不能虚构榜单、截图或合作方。",
    source: "内置学习样本：Joey TikTok Shop 口播 2 / 3 / 4 / 6 / 10",
    evidence: "多条曝光型脚本都有 studied for hours / woke up at 5AM / top earners 这类可信时间细节。",
    related: ["研究背书", "proof first", "榜单", "Data"],
    scriptType: "Secret / Exposed",
  },
  {
    id: "joey-tiktok-shop-short-closure-structure",
    library: "structure",
    sourceBreakdownIds: [],
    title: "短句砸结论节奏",
    summary: "长句堆问题后，用 2-3 个词的短句收口：Move on. Fix it. That's it. Period. 短句不解释，直接进入下一点。",
    usage: "适合压缩 Script Agent 的口播行：每段解释后用一个短句把动作钉住，避免长产品说明。",
    status: "reusable",
    risk: "短句不能变成空口号；前一句必须已经交代清楚为什么要这么做。",
    source: "内置学习样本：Joey TikTok Shop 口播 1 / 8 / 14",
    evidence: "用户标注的结构亮点 4：短句收口公式。",
    related: ["节奏", "短句", "spoken English", "line control"],
    scriptType: "Mistake List",
  },
  {
    id: "joey-tiktok-shop-cta-formula",
    library: "cta",
    sourceBreakdownIds: [],
    title: "圈人 + 一个动作 + 给你什么",
    summary: "公式：If you [圈定条件], [一个动作]. I'll [给你什么]. CTA 先圈住合格用户，再只给一个动作，不堆多个按钮。",
    usage: "适合 Moras 结尾：If you're a 5K+ TikTok Shop creator, click the button. Make your own money.",
    status: "reusable",
    risk: "Make your own money 只能作为行动邀请，不能写成固定收入、保底回报或成功保证。",
    source: "内置学习样本：Joey TikTok Shop 口播 2 / 4 / 5 / 12 / 18",
    evidence: "用户标注的结构亮点 5：CTA 公式。",
    related: ["CTA", "5K+ creator", "click the button", "qualified audience"],
    scriptType: "Comment Reply",
  },
  {
    id: "joey-tiktok-shop-study-mentor-persona",
    library: "persona",
    sourceBreakdownIds: [],
    title: "替你研究的直白导师人设",
    summary: "说话身份不是官方讲师，而是“我今天花时间替你研究了 top creators，现在免费告诉你”。语气直接、快、带一点不耐烦，但核心是帮观众少走弯路。",
    usage: "适合 Moras Persona Agent / Script Agent 的 creator-coach 方向：拿数据和画面证据说话，不把 Moras 讲成软件广告。",
    status: "watch",
    risk: "不要虚构“我研究了几个小时”或“我有内部 TikTok 代表消息”；没有证据时只能说从已提供素材里观察到。",
    source: "内置学习样本：Joey TikTok Shop 口播 1 / 2 / 4 / 6 / 10",
    evidence: "曝光型和骂醒型都稳定使用第一人称研究者/教练视角。",
    related: ["creator coach", "直白", "研究背书", "evidence"],
    scriptType: "Secret / Exposed",
  },
  {
    id: "joey-tiktok-shop-dream-proof-persona",
    library: "persona",
    sourceBreakdownIds: [],
    title: "造梦但带证据的人设",
    summary: "造梦型脚本先展示生活变化、提现截图、dream apartment 或 Q4 机会，再把它落回“每天 30-60 分钟、两到四条视频、持续练内容技能”。",
    usage: "适合 Moras 的 earning opportunity 叙事：可以讲机会和动力，但必须回到具体 creator workflow 和 approved proof。",
    status: "watch",
    risk: "不允许说 will succeed、guaranteed、一定五位数；生活变化只能来自来源案例或 approved campaign material。",
    source: "内置学习样本：Joey TikTok Shop 口播 5 / 11 / 12 / 15 / 16 / 17",
    evidence: "造梦型和时机型脚本都把生活想象与行动门槛绑定。",
    related: ["造梦型", "proof", "Q4", "earning opportunity"],
    scriptType: "POV",
  },
  {
    id: "joey-tiktok-shop-proof-scene",
    library: "scene",
    sourceBreakdownIds: [],
    title: "收益截图 / 榜单证明场景",
    summary: "典型画面是排行榜、GMV 数字、提现截图、Discord 成功案例、产品趋势页。证明画面先出现，口播再解释为什么这件事值得学。",
    usage: "适合 Moras 视频里承接 approved creator handle、GMV screenshot、income screenshot、Moras Data 或产品榜单。",
    status: "reusable",
    risk: "所有截图必须来自真实 approved material；数字要标记为 observed proof，不做普遍化。",
    source: "内置学习样本：Joey TikTok Shop 口播 2 / 3 / 4 / 11 / 17",
    evidence: "多条脚本依赖榜单、提现截图、趋势工具截图建立可信度。",
    related: ["proof scene", "GMV screenshot", "leaderboard", "Data"],
    scriptType: "Secret / Exposed",
  },
  {
    id: "joey-tiktok-shop-research-scene",
    library: "scene",
    sourceBreakdownIds: [],
    title: "凌晨研究 / 手机屏幕真实感",
    summary: "用 5AM、sun coming up、手机截图、双视频对比、滚动排行榜等细节，让观众相信创作者真的做了功课。",
    usage: "适合 Video Factory 的 B-roll 约束：真实屏幕录制、手指点击、排行榜滚动、对比画面、短停顿。",
    status: "reusable",
    risk: "不要伪造平台合作或官方数据权限；只能展示实际可用的工具和素材。",
    source: "内置学习样本：Joey TikTok Shop 口播 4 / 6 / 17",
    evidence: "用户标注“时间细节要具体到可视化”，例如 5AM 和 sun coming up。",
    related: ["screen recording", "research proof", "phone UI", "B-roll"],
    scriptType: "Shoppable Video Workflow",
  },
  {
    id: "joey-tiktok-shop-storyboard",
    library: "storyboard",
    sourceBreakdownIds: [],
    title: "Joey 曝光型参考分镜",
    summary: "完整沉淀 5 个参考镜头：数字钩子、研究证据、两点拆解、Moras 工作流桥接、合格创作者 CTA。用于学习节奏，不用于照搬原人物或原金额。",
    usage: "适合给 Script Agent / Director Agent 复用为 30-40 秒 TikTok Shop creator ad 的镜头骨架。",
    status: "reusable",
    risk: "只能学习结构和节奏；收益数字、排行榜、工具截图必须替换为 Moras approved proof。",
    source: "内置学习样本：Joey TikTok Shop 曝光型脚本组",
    evidence: "来源脚本反复使用：big number hook -> studied for hours -> two things -> free CTA。",
    related: ["storyboard", "exposed", "proof", "Moras workflow"],
    scriptType: "Shoppable Video Workflow",
    storyboardShots: [
      {
        shotId: "shot_1",
        timestamp: "0-3s",
        duration: "3s",
        camera: "竖屏近景，creator 正对镜头，旁边快速闪过 approved proof screenshot。",
        characterAction: "开口先抛出身份、数字和反常识细节，手势指向截图。",
        facialExpression: "震惊但克制，像刚发现一个被忽略的案例。",
        background: "手机屏幕、榜单截图或 Moras approved proof 并排出现。",
        props: ["手机", "approved proof screenshot"],
        voiceover: "There's a creator making serious money with less filming.",
        overlay: "Look at this creator",
        sound: "短促 hit sound，随后进入快节奏 BGM。",
        bgm: "低音量快节奏背景音乐。",
        soundEffects: ["hit", "camera tap"],
        subtitleLogic: "字幕只保留身份和反常识细节，不铺满整句。",
        visualElements: ["proof screenshot", "creator face", "large number crop"],
        visualElementLogic: "先让观众看到证据，再让口播解释。",
        transition: "硬切到研究证据。",
        purpose: "用数字和反常识细节建立停留理由。",
      },
      {
        shotId: "shot_2",
        timestamp: "3-9s",
        duration: "6s",
        camera: "越肩屏幕录制，滚动 top creator 或 product trend 页面。",
        characterAction: "创作者快速滚动、暂停、圈出关键位置。",
        facialExpression: "专注，像在替观众查资料。",
        background: "桌面或手机屏幕环境，保留真实操作感。",
        props: ["phone", "trend page", "highlight circle"],
        voiceover: "I studied the top creators this morning.",
        overlay: "I studied this for you",
        sound: "滚动和轻点击声。",
        bgm: "BGM 降低一点，突出点击。",
        soundEffects: ["scroll", "tap"],
        subtitleLogic: "字幕强调研究动作和时间细节。",
        visualElements: ["scrolling list", "highlight mark"],
        visualElementLogic: "让研究背书可视化，而不是口头自称。",
        transition: "缩放切到两点拆解。",
        purpose: "建立“我替你做过功课”的可信度。",
      },
      {
        shotId: "shot_3",
        timestamp: "9-22s",
        duration: "13s",
        camera: "镜头在 creator 和两条大字幕之间快切。",
        characterAction: "创作者按 one / two 拆解可复制动作。",
        facialExpression: "直白、肯定，偶尔短暂停顿。",
        background: "截图旁边保留简短要点卡。",
        props: ["numbered labels", "proof crop"],
        voiceover: "Two things matter. Product fit and repeatable format.",
        overlay: "1 Product fit / 2 Repeatable format",
        sound: "每个编号出现时有 click sound。",
        bgm: "快节奏持续推进。",
        soundEffects: ["click", "cut hit"],
        subtitleLogic: "字幕只打核心名词，不做完整逐字稿。",
        visualElements: ["number labels", "screen crop", "hand point"],
        visualElementLogic: "用编号降低理解成本。",
        transition: "编号二结束后切到 Moras UI。",
        purpose: "把案例拆成可迁移原则。",
      },
      {
        shotId: "shot_4",
        timestamp: "22-31s",
        duration: "9s",
        camera: "真实 Moras UI 屏幕录制，手指选择产品并点击 Generate。",
        characterAction: "创作者把案例原则桥接到 Moras：选产品、点击 Generate、检查视频。",
        facialExpression: "从分析转为行动，语气更轻快。",
        background: "Moras Discover / Create video / draft preview 画面。",
        props: ["Moras app", "product list", "Generate button"],
        voiceover: "Now I open Moras and choose a product.",
        overlay: "Choose. Generate. Check.",
        sound: "真实 UI 点击声。",
        bgm: "BGM 保持但不盖过 UI 点击。",
        soundEffects: ["tap", "soft whoosh"],
        subtitleLogic: "字幕跟随三个动作，不解释软件功能大全。",
        visualElements: ["Moras UI", "button tap", "video preview"],
        visualElementLogic: "把抽象原则落到真实工作流。",
        transition: "UI 预览切回 creator CTA。",
        purpose: "证明 Moras 是工作流工具，不是第一秒硬广。",
      },
      {
        shotId: "shot_5",
        timestamp: "31-38s",
        duration: "7s",
        camera: "中近景回到 creator，CTA 按钮方向或下载入口露出。",
        characterAction: "创作者停顿半拍，直接圈定 5K+ TikTok Shop creator。",
        facialExpression: "坚定、短促，不拖尾。",
        background: "Moras UI 或 approved proof 留在旁边。",
        props: ["CTA button", "Moras UI"],
        voiceover: "If you're a 5K+ creator, click the button.",
        overlay: "Make your own money",
        sound: "最后一个 click hit 收束。",
        bgm: "结尾快速淡出。",
        soundEffects: ["click hit"],
        subtitleLogic: "字幕只保留合格用户和动作。",
        visualElements: ["CTA button", "creator face", "proof sidecar"],
        visualElementLogic: "让行动入口和资格条件同时可见。",
        transition: "停帧到 CTA。",
        purpose: "把研究价值转成合格创作者行动。",
      },
    ],
  },
];

type CreativeLibraryPageProps = {
  analyses?: SocialVideoAnalysis[];
  onBack?: () => void;
  onGenerateScript?: (intent: CreativeAssetScriptGenerationIntent) => void;
};

export function CreativeLibraryPage({ analyses = [], onBack, onGenerateScript }: CreativeLibraryPageProps) {
  const [activeLibrary, setActiveLibrary] = useState<LibraryKey>("hook");
  const creativeAssets = useMemo(() => buildCreativeAssets(analyses), [analyses]);
  const visibleAssets = useMemo(() => creativeAssets.filter(asset => asset.library === activeLibrary), [creativeAssets, activeLibrary]);

  return (
    <section className="creative-library-page" aria-label="创意仓库">
      <header className="creative-library-header">
        {onBack && (
          <button className="creative-library-back-button" type="button" onClick={onBack} aria-label="返回上一级">
            <ArrowLeft size={24} aria-hidden="true" />
          </button>
        )}
        <div>
          <h2>创意仓库</h2>
          <p>从视频拆解结果中沉淀 Hook、人设、CTA、结构、分镜和场景资产。</p>
        </div>
      </header>

      <nav className="creative-library-tabs" role="tablist" aria-label="创意库类型">
        {libraryTabs.map(({ Icon, ...tab }) => (
          <button
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeLibrary === tab.key}
            className={`creative-library-tab${activeLibrary === tab.key ? " creative-library-tab--active" : ""}`}
            onClick={() => setActiveLibrary(tab.key)}
          >
            <Icon className="creative-library-tab__icon" size={19} aria-hidden="true" />
            <span>{tab.label}</span>
          </button>
        ))}
      </nav>

      <div className="creative-library-grid">
        {visibleAssets.map(asset => (
          <article key={asset.id} className="creative-asset-card">
            <header>
              <div>
                <h4>{asset.title}</h4>
              </div>
              <StatusBadge status={asset.status} />
            </header>
            <p>{asset.summary}</p>
            {asset.library === "storyboard" && asset.storyboardShots?.length ? (
              <StoryboardReferenceList shots={asset.storyboardShots} />
            ) : null}
            <dl>
              <div>
                <dt>适用</dt>
                <dd>{asset.usage}</dd>
              </div>
              <div>
                <dt>证据</dt>
                <dd>{asset.evidence}</dd>
              </div>
              <div>
                <dt>边界</dt>
                <dd>{asset.risk}</dd>
              </div>
            </dl>
            <footer>
              <span>{asset.source}</span>
              <div className="creative-related-tags">
                {asset.related.map(item => (
                  <span key={item}>{item}</span>
                ))}
              </div>
              {onGenerateScript && (
                <button
                  type="button"
                  className="creative-asset-card__generate"
                  onClick={() => onGenerateScript(buildScriptGenerationIntent(asset))}
                  aria-label={`用${asset.title}生成脚本`}
                >
                  <Bot size={16} aria-hidden="true" />
                  生成脚本
                </button>
              )}
            </footer>
          </article>
        ))}
        {visibleAssets.length === 0 && (
          <div className="creative-library-empty">
            <h4>暂无{libraryTabs.find(tab => tab.key === activeLibrary)?.label}资产</h4>
            <p>完成视频拆解后，系统会把可复用的创意组件同步沉淀到这里。</p>
          </div>
        )}
      </div>
    </section>
  );
}

function StoryboardReferenceList({ shots }: { shots: JsonObject[] }) {
  return (
    <div className="creative-storyboard-reference" aria-label="完整参考分镜">
      {shots.map((shot, index) => {
        const shotId = firstString(shot.shotId, shot.shot_id, `shot_${index + 1}`);
        const zh = asObject(asObject(shot.localized)?.zh);
        const props = jsonStrings(shot.props).join("、");
        const zhProps = jsonStrings(zh?.props).join("、");
        const soundEffects = jsonStrings(firstJsonValue(zh?.soundEffects, zh?.sound_effects, shot.soundEffects, shot.sound_effects)).join("、");
        const visualElements = jsonStrings(firstJsonValue(zh?.visualElements, zh?.visual_elements, shot.visualElements, shot.visual_elements)).join("、");
        return (
          <section className="creative-storyboard-shot" key={`${shotId}-${index}`}>
            <header>
              <strong>{formatShotLabel(shotId, index)}</strong>
              <span>{firstString(shot.timestamp, shot.duration, zh?.duration)}</span>
            </header>
            <dl>
              <div>
                <dt>镜头</dt>
                <dd>{firstString(zh?.camera, shot.camera)}</dd>
              </div>
              <div>
                <dt>动作</dt>
                <dd>{firstString(zh?.characterAction, zh?.character_action, shot.characterAction, shot.character_action)}</dd>
              </div>
              <div>
                <dt>表情</dt>
                <dd>{firstString(zh?.facialExpression, zh?.facial_expression, shot.facialExpression, shot.facial_expression)}</dd>
              </div>
              <div>
                <dt>背景</dt>
                <dd>{firstString(zh?.background, shot.background)}</dd>
              </div>
              <div>
                <dt>道具</dt>
                <dd>{firstString(zhProps, props, "无明确道具")}</dd>
              </div>
              <div>
                <dt>口播</dt>
                <dd>{firstString(zh?.voiceover, shot.voiceover)}</dd>
              </div>
              <div>
                <dt>重点字幕</dt>
                <dd>{firstString(zh?.overlay, shot.overlay, "无明确重点字幕")}</dd>
              </div>
              <div>
                <dt>声音</dt>
                <dd>{firstString(zh?.sound, shot.sound)}</dd>
              </div>
              <div>
                <dt>BGM</dt>
                <dd>{firstString(zh?.bgm, shot.bgm, "未观察到明确 BGM")}</dd>
              </div>
              <div>
                <dt>音效</dt>
                <dd>{firstString(soundEffects, "未观察到明确音效")}</dd>
              </div>
              <div>
                <dt>字幕逻辑</dt>
                <dd>{firstString(zh?.subtitleLogic, zh?.subtitle_logic, shot.subtitleLogic, shot.subtitle_logic, "未拆出字幕逻辑")}</dd>
              </div>
              <div>
                <dt>画面要素</dt>
                <dd>{firstString(visualElements, "未拆出额外画面要素")}</dd>
              </div>
              <div>
                <dt>要素逻辑</dt>
                <dd>{firstString(zh?.visualElementLogic, zh?.visual_element_logic, shot.visualElementLogic, shot.visual_element_logic, "未拆出画面要素逻辑")}</dd>
              </div>
              <div>
                <dt>转场</dt>
                <dd>{firstString(zh?.transition, shot.transition)}</dd>
              </div>
              <div>
                <dt>目的</dt>
                <dd>{firstString(zh?.purpose, shot.purpose)}</dd>
              </div>
            </dl>
          </section>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: LibraryStatus }) {
  const Icon = status === "reusable" ? ShieldCheck : status === "watch" ? Brain : MessageSquareText;

  return (
    <span className={`creative-status creative-status--${status}`}>
      <Icon size={14} aria-hidden="true" />
      {statusCopy[status]}
    </span>
  );
}

function buildCreativeAssets(analyses: SocialVideoAnalysis[]): CreativeAsset[] {
  const dynamicAssets = analyses.flatMap(analysis => {
    if (analysis.status !== "succeeded") return [];

    const sourceTitle = firstString(analysis.sourceVideo?.title, analysis.sourceVideo?.contentSummary, analysis.id);
    const category = firstString(analysis.classification?.hookType, ...jsonStrings(analysis.classification?.structureFactors), "视频拆解");
    const related = uniqueStrings([
      category,
      ...jsonStrings(analysis.classification?.personaFactors),
      ...jsonStrings(analysis.classification?.sceneFactors),
      ...jsonStrings(analysis.classification?.ctaFactors),
      ...jsonStrings(analysis.classification?.structureFactors),
    ]);
    const source = `来源：${sourceTitle}`;
    const risk = firstString(...jsonStrings(asObject(analysis.structureProtocol)?.riskFlags), "不能照搬原视频表达、人物、镜头顺序或收益承诺。");
    const classificationEvidence = jsonStrings(analysis.classification?.evidence).join("；");
    const baseEvidence = firstString(classificationEvidence, analysis.classification?.factorReasoning, analysis.decomposition?.oneSentenceSummary, "来自视频拆解结果。");

    const assets: CreativeAsset[] = [];
    const referenceStoryboard = referenceStoryboardFromAnalysis(analysis);
    const referenceStoryboardSummary = referenceStoryboard.length
      ? `完整沉淀 ${referenceStoryboard.length} 个参考镜头，包含时间、镜头、动作、表情、背景、道具、口播、重点字幕、BGM、音效、字幕逻辑、画面要素逻辑、转场和目的，可作为脚本智能体的全量分镜参考。`
      : "";
    const hookSummary = firstString(
      analysis.decomposition?.hook,
      asObject(analysis.decomposition?.openingHook)?.observedContent,
      analysis.decomposition?.oneSentenceSummary,
    );
    if (hookSummary) {
      assets.push({
        id: `${analysis.id}-hook`,
        sourceBreakdownId: analysis.id,
        library: "hook",
        title: `${category}开头钩子`,
        summary: hookSummary,
        usage: firstString(analysis.decomposition?.performanceLogic, "适合复用同类前三秒停留理由。"),
        status: "reusable",
        risk,
        source,
        evidence: baseEvidence,
        related,
      });
    }

    const personaSummary = firstString(
      analysis.decomposition?.performanceLogic,
      analysis.decomposition?.oneSentenceSummary,
      analysis.classification?.factorReasoning,
    );
    if (personaSummary) {
      assets.push({
        id: `${analysis.id}-persona`,
        sourceBreakdownId: analysis.id,
        library: "persona",
        title: `${category}目标人设`,
        summary: personaSummary,
        usage: "适合拆成脚本里的说话身份、信任来源和用户代入点。",
        status: "watch",
        risk: "人设只能基于公开表达和画面证据推断，不能放大刻板标签。",
        source,
        evidence: baseEvidence,
        related,
      });
    }

    const ctaSummary = firstString(analysis.decomposition?.interactionOrCta, ...jsonStrings(analysis.scriptAgentBridge?.usableInsights));
    if (ctaSummary) {
      assets.push({
        id: `${analysis.id}-cta`,
        sourceBreakdownId: analysis.id,
        library: "cta",
        title: `${category}行动引导`,
        summary: ctaSummary,
        usage: "适合复用为评论、收藏、私信或试用引导。",
        status: "reusable",
        risk: "行动引导必须承接前面交付的信息价值，不能制造虚假稀缺或承诺结果。",
        source,
        evidence: baseEvidence,
        related,
      });
    }

    const structureProtocol = asObject(analysis.structureProtocol);
    const structureSummary = firstString(
      structureProtocol?.corePattern,
      ...jsonStrings(analysis.decomposition?.narrativeStructure),
      ...jsonStrings(analysis.decomposition?.contentStructure),
    );
    if (structureSummary) {
      assets.push({
        id: `${analysis.id}-structure`,
        sourceBreakdownId: analysis.id,
        library: "structure",
        title: `${category}内容结构`,
        summary: structureSummary,
        usage: firstString(...jsonStrings(structureProtocol?.reuseRules), "适合给脚本智能体复用为段落推进方式。"),
        status: "reusable",
        risk,
        source,
        evidence: baseEvidence,
        related,
      });
    }

    if (referenceStoryboardSummary) {
      assets.push({
        id: `${analysis.id}-storyboard`,
        sourceBreakdownId: analysis.id,
        library: "storyboard",
        title: `${category}参考分镜`,
        summary: referenceStoryboardSummary,
        usage: "适合给脚本智能体复用镜头粒度、时间节奏、素材切换和 CTA 位置。",
        status: "reusable",
        risk: "只能学习分镜结构和节奏，不能照搬原人物、原口播、标志性镜头、音乐、水印或收益说法。",
        source,
        evidence: baseEvidence,
        related,
        storyboardShots: referenceStoryboard,
      });
    }

    const sceneSummary = firstString(
      analysis.decomposition?.visualLanguage,
      ...jsonStrings(analysis.decomposition?.keyShots),
      ...jsonStrings(analysis.decomposition?.segments),
    );
    if (sceneSummary) {
      assets.push({
        id: `${analysis.id}-scene`,
        sourceBreakdownId: analysis.id,
        library: "scene",
        title: `${category}视觉场景`,
        summary: sceneSummary,
        usage: "适合复用为镜头环境、动作节奏和视频提示词的视觉约束。",
        status: "reusable",
        risk: "只复用视觉组织方式，不复刻原人物、标志性动作、音乐和具体镜头。",
        source,
        evidence: baseEvidence,
        related,
      });
    }

    return assets;
  });
  return [...joeyTikTokShopScriptAssets, ...dynamicAssets];
}

function asObject(value: JsonValue | undefined | null): JsonObject | null {
  if (!value || typeof value !== "object" || Array.isArray(value)) return null;
  return value;
}

function jsonStrings(value: JsonValue | undefined | null): string[] {
  if (typeof value === "string") return value.trim() ? [value] : [];
  if (Array.isArray(value)) {
    return value.flatMap(item => jsonStrings(item));
  }
  if (value && typeof value === "object") {
    return Object.values(value).flatMap(item => jsonStrings(item));
  }
  if (typeof value === "number" || typeof value === "boolean") return [String(value)];
  return [];
}

function firstString(...values: Array<JsonValue | undefined | null>): string {
  for (const value of values) {
    const strings = jsonStrings(value);
    const first = strings.find(item => item.trim().length > 0);
    if (first) return first;
  }
  return "";
}

function firstJsonValue(...values: Array<JsonValue | undefined | null>): JsonValue | undefined {
  return values.find(value => value !== undefined && value !== null) ?? undefined;
}

function uniqueStrings(values: string[]): string[] {
  return Array.from(new Set(values.filter(Boolean))).slice(0, 4);
}

function formatShotLabel(value: string, index: number): string {
  const match = value.match(/(\d+)/);
  if (!match) return `Shot ${String(index + 1).padStart(2, "0")}`;
  return `Shot ${String(Number(match[1])).padStart(2, "0")}`;
}

function buildScriptGenerationIntent(asset: CreativeAsset): CreativeAssetScriptGenerationIntent {
  return {
    id: `${asset.id}-${Date.now()}`,
    assetTitle: asset.title,
    scriptType: asset.scriptType ?? inferScriptType(asset),
    sourceBreakdownIds: asset.sourceBreakdownIds ?? (asset.sourceBreakdownId ? [asset.sourceBreakdownId] : []),
  };
}

function referenceStoryboardFromAnalysis(analysis: SocialVideoAnalysis): JsonObject[] {
  if (analysis.referenceStoryboard?.length) return analysis.referenceStoryboard;
  return asObjectList(analysis.decomposition?.segments).slice(0, 6).map((segment, index) => {
    const start = typeof segment.startSecond === "number" ? `${segment.startSecond}s` : "";
    const end = typeof segment.endSecond === "number" ? `${segment.endSecond}s` : "";
    const timestamp = start && end ? `${start}-${end}` : `segment_${index + 1}`;
    return {
      shotId: `shot_${index + 1}`,
      timestamp,
      duration: timestamp,
      camera: firstString(analysis.decomposition?.visualLanguage, "旧版拆解未单独返回镜头字段。"),
      characterAction: firstString(segment.content, "旧版拆解未单独返回主体动作字段。"),
      background: firstString(segment.role, "旧版拆解未单独返回背景字段。"),
      voiceover: "旧版拆解未单独返回口播字段。",
      overlay: "",
      sound: firstString(analysis.decomposition?.audioLanguage, "旧版拆解未单独返回声音字段。"),
      bgm: "",
      soundEffects: [],
      subtitleLogic: "旧版拆解未单独返回字幕逻辑。",
      visualElements: [],
      visualElementLogic: "旧版拆解未单独返回画面要素逻辑。",
      transition: firstString(segment.technique, "旧版拆解未单独返回转场字段。"),
      purpose: firstString(segment.role, "由旧版分段拆解映射。"),
    };
  });
}

function asObjectList(value: JsonValue | undefined | null): JsonObject[] {
  return Array.isArray(value) ? value.map(asObject).filter(Boolean) as JsonObject[] : [];
}

function inferScriptType(asset: CreativeAsset): string {
  if (asset.library === "storyboard") return "Shoppable Video Workflow";
  if (asset.library === "structure") return "Shoppable Video Workflow";
  if (asset.library === "persona") return "POV";
  if (asset.library === "cta") return "Comment Reply";
  const signature = [asset.title, asset.summary, asset.usage, ...asset.related].join(" ").toLocaleLowerCase();
  if (signature.includes("mistake") || signature.includes("误区") || signature.includes("禁忌") || signature.includes("trap")) return "Mistake List";
  if (signature.includes("exposed") || signature.includes("揭秘") || signature.includes("爆料")) return "Secret / Exposed";
  if (signature.includes("comment") || signature.includes("评论")) return "Comment Reply";
  if (signature.includes("product") || signature.includes("选品")) return "Product Picking";
  if (signature.includes("shoppable") || signature.includes("workflow") || signature.includes("工作流")) return "Shoppable Video Workflow";
  if (signature.includes("faceless") || signature.includes("不露脸")) return "Faceless Creator";
  if (signature.includes("pov")) return "POV";
  return "全部";
}

export default CreativeLibraryPage;
