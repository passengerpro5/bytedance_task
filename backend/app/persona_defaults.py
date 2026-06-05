from __future__ import annotations

import hashlib
import re
from typing import Any


PERSONA_VARIANTS: list[dict[str, Any]] = [
    {
        "display_name": "Aaliyah Brooks",
        "demographic": "26-year-old Black American social-commerce creator, early-stage TikTok Shop product promotion creator, based in a compact city apartment studio.",
        "appearance": "Oval face, deep brown skin tone, clear dark brown eyes, shoulder-length coily dark hair pulled into a soft half-up style, natural brows, relaxed posture, expressive hands.",
        "face_hair_makeup": "Soft natural makeup with warm undertones, subtle eyeliner, muted berry lip color, clean skin texture, coily dark hair with a few loose curls framing the face.",
        "wardrobe": "Ivory ribbed knit top under a cropped sage utility jacket, small gold hoop earrings, simple black watch, neutral styling that feels creator-native rather than corporate.",
        "styling_details": "Tidy but lived-in home-office styling, short natural nails, minimal jewelry, practical desk accessories, no heavy glamour lighting.",
        "distinctive_marks_or_tattoos": "Optional tiny crescent line tattoo on the inner left wrist; keep it subtle and consistent if visible, otherwise do not add new tattoos.",
        "props": ["smartphone", "silver laptop", "sticky notes", "black gel pen", "small product note card"],
        "zh": {
            "display_name": "Aaliyah Brooks",
            "demographic": "26 岁美国黑人女性社交电商创作者，早期 TikTok Shop 商品视频创作者，住在紧凑的城市公寓工作室。",
            "appearance": "鹅蛋脸，深棕肤色，深棕色清澈眼睛，及肩深色卷发半扎，自然眉形，姿态放松，手部表达丰富。",
            "face_hair_makeup": "暖调自然淡妆、细眼线、浆果色低饱和唇妆，皮肤纹理干净，深色卷发带少量碎卷。",
            "wardrobe": "象牙色坑条针织上衣搭配短款鼠尾草绿工装外套，小金圈耳环，简洁黑色腕表，整体像真实创作者而非企业主持人。",
            "styling_details": "整洁但有生活感的家庭办公妆造，短自然指甲，少量首饰，实用桌面配件，避免重度精修棚拍感。",
            "distinctive_marks_or_tattoos": "左手腕内侧可有一个很小的新月线条纹身；如果画面中出现需保持一致，否则不要新增纹身。",
            "props": ["智能手机", "银色笔记本电脑", "便利贴", "黑色中性笔", "小商品便签卡"],
        },
    },
    {
        "display_name": "Maya Rivera",
        "demographic": "27-year-old Afro-Latina social-commerce creator, early-stage TikTok Shop product promotion creator, based in a compact city apartment studio.",
        "appearance": "Heart-shaped face, warm medium-brown skin tone, clear hazel-brown eyes, shoulder-length dark brown wavy hair tucked behind one ear, natural brows, relaxed posture, expressive hands.",
        "face_hair_makeup": "Soft natural makeup with light foundation, subtle eyeliner, muted rose lip color, clean skin texture, dark brown wavy hair with a side part and a few loose strands.",
        "wardrobe": "Cream ribbed knit top under a cropped light denim jacket, small gold hoop earrings, simple black watch, neutral styling that feels creator-native rather than corporate.",
        "styling_details": "Tidy but lived-in home-office styling, short natural nails, minimal jewelry, practical desk accessories, no heavy glamour lighting.",
        "distinctive_marks_or_tattoos": "Optional tiny line-art star tattoo on the inner left wrist; keep it subtle and consistent if visible, otherwise do not add new tattoos.",
        "props": ["smartphone", "silver laptop", "sticky notes", "black gel pen", "small product note card"],
        "zh": {
            "display_name": "Maya Rivera",
            "demographic": "27 岁 Afro-Latina 社交电商创作者，早期 TikTok Shop 商品视频创作者，住在紧凑的城市公寓工作室。",
            "appearance": "心形脸，暖调中棕肤色，榛棕色清澈眼睛，深棕及肩微卷发别到一侧耳后，自然眉形，姿态放松，手部表达丰富。",
            "face_hair_makeup": "自然淡妆、轻薄底妆、细眼线、玫瑰豆沙色唇妆，皮肤纹理干净，偏分深棕微卷发带少量碎发。",
            "wardrobe": "奶油色坑条针织上衣搭配短款浅色牛仔外套，小金圈耳环，简洁黑色腕表，整体像真实创作者而非企业主持人。",
            "styling_details": "整洁但有生活感的家庭办公妆造，短自然指甲，少量首饰，实用桌面配件，避免重度精修棚拍感。",
            "distinctive_marks_or_tattoos": "左手腕内侧可有一个很小的线条星星纹身；如果画面中出现需保持一致，否则不要新增纹身。",
            "props": ["智能手机", "银色笔记本电脑", "便利贴", "黑色中性笔", "小商品便签卡"],
        },
    },
    {
        "display_name": "Samira Haddad",
        "demographic": "29-year-old Arab-American social-commerce creator, practical beauty-and-home product promotion creator, based in a small apartment studio.",
        "appearance": "Long oval face, warm olive skin tone, clear dark amber eyes, shoulder-length dark auburn hair with soft waves, defined brows, calm upright posture, precise hand gestures.",
        "face_hair_makeup": "Natural satin makeup, thin brown eyeliner, warm nude lip color, softly waved dark auburn hair with a clean side part and controlled flyaways.",
        "wardrobe": "Soft white mock-neck top under a cropped charcoal overshirt, small brushed-gold hoops, slim black watch, understated creator-workbench styling.",
        "styling_details": "Orderly desk with a lived-in planning feel, short almond-shaped natural nails, minimal warm-metal jewelry, practical stationery and product boxes.",
        "distinctive_marks_or_tattoos": "Small beauty mark near the left cheekbone; keep it subtle and consistent if visible.",
        "props": ["smartphone", "matte gray laptop", "index cards", "brown fine-tip pen", "neutral skincare product package"],
        "zh": {
            "display_name": "Samira Haddad",
            "demographic": "29 岁阿拉伯裔美国女性社交电商创作者，偏美妆和家居商品视频，住在小型公寓工作室。",
            "appearance": "长鹅蛋脸，暖橄榄肤色，深琥珀色清澈眼睛，深栗色及肩微卷发，眉形清晰，姿态平稳，手势精准。",
            "face_hair_makeup": "自然缎光妆面，细棕色眼线，暖裸色唇妆，深栗色微卷发偏分并收拾干净。",
            "wardrobe": "柔白色半高领上衣搭配短款炭灰衬衫外套，小哑光金耳环，细黑色腕表，克制的创作者工作台风格。",
            "styling_details": "桌面有秩序但保留真实规划痕迹，短杏仁形自然指甲，少量暖金属首饰，实用文具和产品盒。",
            "distinctive_marks_or_tattoos": "左颧骨附近有很小的美人痣；如出现需保持一致。",
            "props": ["智能手机", "哑光灰笔记本电脑", "索引卡", "棕色细头笔", "中性色护肤商品包装"],
        },
    },
    {
        "display_name": "Elena Yazzie",
        "demographic": "28-year-old Indigenous and Mexican-American social-commerce creator, practical household product promotion creator, based in a compact Southwest apartment studio.",
        "appearance": "Soft square face, copper-brown skin tone, clear dark eyes, long dark wavy hair tied low with loose front strands, grounded posture, careful expressive hands.",
        "face_hair_makeup": "Minimal natural makeup, softly defined brows, muted terracotta lip color, long dark wavy hair in a low tie with a clean center part.",
        "wardrobe": "Warm oatmeal ribbed tee under a cropped rust canvas jacket, small turquoise stud earrings, simple black watch, practical home-studio styling.",
        "styling_details": "Warm practical desk setup with woven pen cup, short natural nails, minimal accessories, product notes organized without looking corporate.",
        "distinctive_marks_or_tattoos": "Small geometric line tattoo on the inner right forearm; keep it minimal and consistent if visible.",
        "props": ["smartphone", "silver laptop", "paper checklist", "black marker", "small household product package"],
        "zh": {
            "display_name": "Elena Yazzie",
            "demographic": "28 岁 Indigenous 与墨西哥裔美国女性社交电商创作者，偏实用家居商品视频，住在美国西南部紧凑公寓工作室。",
            "appearance": "柔和方脸，铜棕肤色，深色清澈眼睛，深色长卷发低扎并留少量前发，姿态稳，手部表达谨慎。",
            "face_hair_makeup": "极简自然妆，柔和眉形，陶土色低饱和唇妆，深色长卷发中分低扎。",
            "wardrobe": "暖燕麦色坑条 T 恤搭配短款铁锈色帆布外套，小绿松石耳钉，简洁黑色腕表，实用家庭工作室风格。",
            "styling_details": "温暖实用的桌面布置，有编织笔筒，短自然指甲，少量配饰，商品便签整齐但不企业化。",
            "distinctive_marks_or_tattoos": "右前臂内侧可有很小的几何线条纹身；如出现需保持极简且一致。",
            "props": ["智能手机", "银色笔记本电脑", "纸质检查清单", "黑色马克笔", "小家居商品包装"],
        },
    },
    {
        "display_name": "Zoe Baptiste",
        "demographic": "25-year-old Caribbean-American Black creator, early-stage lifestyle product promotion creator, based in a bright rental studio corner.",
        "appearance": "Round face, rich dark skin tone, clear deep brown eyes, short natural curls, bright but controlled facial expression, relaxed shoulders, animated hands.",
        "face_hair_makeup": "Fresh natural makeup, soft bronze highlighter, clear gloss lip, short defined curls, neat brows, skin texture kept realistic.",
        "wardrobe": "White fitted tee under a cropped teal overshirt, small silver hoops, slim fitness watch, relaxed creator-native styling.",
        "styling_details": "Bright compact desk corner, short glossy natural nails, small stack of product boxes, coffee cup and notebook arranged naturally.",
        "distinctive_marks_or_tattoos": "Optional tiny wave tattoo behind the right wrist; keep it subtle and consistent if visible.",
        "props": ["smartphone", "white laptop", "lined notebook", "blue gel pen", "compact beauty product package"],
        "zh": {
            "display_name": "Zoe Baptiste",
            "demographic": "25 岁加勒比裔美国黑人女性创作者，早期生活方式商品视频创作者，在明亮出租屋角落拍摄。",
            "appearance": "圆脸，深棕肤色，深棕色清澈眼睛，短自然卷发，表情明亮但克制，肩膀放松，手部动作活跃。",
            "face_hair_makeup": "清新自然妆，柔和古铜高光，透明唇蜜，短卷发轮廓清楚，眉形整洁，保留真实皮肤纹理。",
            "wardrobe": "白色合身 T 恤搭配短款青绿色衬衫外套，小银圈耳环，细运动腕表，轻松真实的创作者风格。",
            "styling_details": "明亮紧凑桌角，短亮面自然指甲，小堆产品盒，咖啡杯和笔记本自然摆放。",
            "distinctive_marks_or_tattoos": "右手腕后侧可有一个很小的波浪纹身；如出现需细微且一致。",
            "props": ["智能手机", "白色笔记本电脑", "横线笔记本", "蓝色中性笔", "小美妆商品包装"],
        },
    },
    {
        "display_name": "Camila Duarte",
        "demographic": "30-year-old Brazilian-Latina social-commerce creator, practical kitchen-and-home product promotion creator, based in a compact apartment workspace.",
        "appearance": "Angular oval face, tan golden-brown skin tone, clear green-brown eyes, voluminous chestnut curls pinned to one side, confident posture, expressive hands.",
        "face_hair_makeup": "Soft matte makeup, thin eyeliner, muted coral lip color, voluminous chestnut curls with defined texture and a side clip.",
        "wardrobe": "Black ribbed tank under a cropped cream chore jacket, small gold hoops, black watch, practical but stylish creator-workflow look.",
        "styling_details": "Compact desk beside a small kitchen shelf, short neutral nails, minimal jewelry, product notes arranged for fast posting.",
        "distinctive_marks_or_tattoos": "Tiny leaf tattoo near the left collarbone if visible; keep it subtle and consistent.",
        "props": ["smartphone", "dark laptop", "sticky tabs", "green pen", "small kitchen gadget package"],
        "zh": {
            "display_name": "Camila Duarte",
            "demographic": "30 岁巴西裔拉美女性社交电商创作者，偏厨房和家居商品视频，住在紧凑公寓工作区。",
            "appearance": "有棱角的鹅蛋脸，金棕肤色，绿棕色清澈眼睛，蓬松栗色卷发别到一侧，姿态自信，手部表达丰富。",
            "face_hair_makeup": "柔雾妆面，细眼线，低饱和珊瑚色唇妆，蓬松栗色卷发纹理清晰并用侧边发夹固定。",
            "wardrobe": "黑色坑条背心搭配短款奶油色工装外套，小金圈耳环，黑色腕表，实用但有风格的创作者工作流造型。",
            "styling_details": "桌面靠近小厨房架，短中性色指甲，少量首饰，商品便签按快速发布方式摆放。",
            "distinctive_marks_or_tattoos": "左锁骨附近可有很小的叶子纹身；如果可见需细微且一致。",
            "props": ["智能手机", "深色笔记本电脑", "标签贴", "绿色笔", "小厨房工具商品包装"],
        },
    },
    {
        "display_name": "Noa Williams",
        "demographic": "27-year-old multiracial Black and white social-commerce creator, beginner-friendly product posting coach, based in a small urban studio.",
        "appearance": "Soft rectangular face, freckled medium-brown skin tone, clear gray-brown eyes, sandy brown curly bob, thoughtful expression, relaxed posture, precise hand movement.",
        "face_hair_makeup": "Very light natural makeup, brushed brows, soft mauve lip color, sandy brown curly bob with visible texture, freckles kept natural.",
        "wardrobe": "Heather gray fitted tee under a cropped navy utility vest, small matte silver hoops, simple black watch, understated coaching style.",
        "styling_details": "Minimal desk with product notes, short natural nails, no heavy accessories, calm work-focused lighting and neutral background.",
        "distinctive_marks_or_tattoos": "Small dotwork triangle tattoo on the left wrist; keep it tiny and consistent if visible.",
        "props": ["smartphone", "space-gray laptop", "index notes", "mechanical pencil", "small tech accessory package"],
        "zh": {
            "display_name": "Noa Williams",
            "demographic": "27 岁黑人与白人混血社交电商创作者，偏新手友好的商品发布教练，在小型城市工作室拍摄。",
            "appearance": "柔和长方脸，带雀斑的中棕肤色，灰棕色清澈眼睛，沙棕色卷短发，表情思考感强，姿态放松，手部动作精准。",
            "face_hair_makeup": "很轻的自然妆，梳理过的眉毛，柔和豆沙紫唇色，沙棕卷短发纹理清楚，保留自然雀斑。",
            "wardrobe": "麻灰色合身 T 恤搭配短款藏蓝工装马甲，小哑光银耳环，简洁黑色腕表，克制的教练型风格。",
            "styling_details": "极简桌面和产品笔记，短自然指甲，无重配饰，安静工作导向灯光和中性背景。",
            "distinctive_marks_or_tattoos": "左手腕可有很小的点阵三角纹身；如果可见需保持极小且一致。",
            "props": ["智能手机", "深空灰笔记本电脑", "索引笔记", "自动铅笔", "小科技配件商品包装"],
        },
    },
    {
        "display_name": "Leila Mensah",
        "demographic": "31-year-old Ghanaian-American social-commerce creator, practical product research mentor, based in a compact home-office nook.",
        "appearance": "Long heart-shaped face, deep umber skin tone, clear black-brown eyes, long neat braids pulled over one shoulder, composed posture, measured expressive hands.",
        "face_hair_makeup": "Soft natural matte makeup, defined brows, muted plum lip color, neat long braids with a clean side part, realistic skin texture.",
        "wardrobe": "Warm beige knit top under a cropped forest-green overshirt, small gold studs, black watch, practical mentor-style creator outfit.",
        "styling_details": "Compact home-office nook with organized product notes, short natural nails, minimal jewelry, practical desk lamp and neutral wall.",
        "distinctive_marks_or_tattoos": "Optional tiny sunburst tattoo on the inner left wrist; keep it subtle and consistent if visible.",
        "props": ["smartphone", "silver laptop", "planner", "black gel pen", "small wellness product package"],
        "zh": {
            "display_name": "Leila Mensah",
            "demographic": "31 岁加纳裔美国女性社交电商创作者，偏实用产品研究导师，在紧凑家庭办公角落拍摄。",
            "appearance": "长心形脸，深褐肤色，黑棕色清澈眼睛，整齐长辫拨到一侧肩前，姿态沉稳，手部表达有分寸。",
            "face_hair_makeup": "柔和自然哑光妆，眉形清晰，低饱和梅子色唇妆，长辫整洁偏分，保留真实皮肤纹理。",
            "wardrobe": "暖米色针织上衣搭配短款森林绿衬衫外套，小金耳钉，黑色腕表，实用导师型创作者穿搭。",
            "styling_details": "紧凑家庭办公角落和有序产品笔记，短自然指甲，少量首饰，实用台灯和中性墙面。",
            "distinctive_marks_or_tattoos": "左手腕内侧可有很小的太阳线条纹身；如出现需细微且一致。",
            "props": ["智能手机", "银色笔记本电脑", "计划本", "黑色中性笔", "小健康商品包装"],
        },
    },
]


PERSONA_ROLE_ZH: dict[str, str] = {
    "Reusable Moras creator persona": "可复用 Moras 创作者人设",
    "Practical creator friend": "实用型创作者朋友",
    "Tutorial creator friend": "教程型创作者朋友",
    "Creator educator": "创作者教育者",
    "Efficiency Expert": "效率型创作者",
    "Skeptical Reviewer": "谨慎评测者",
    "Objective workflow framing": "客观流程型创作者",
}

DEFAULT_BANNED_PERSONA_CLAIMS = [
    "guaranteed income",
    "passive income guaranteed",
    "make $10k",
    "$10k easily",
    "automatic money",
    "ai guarantees sales",
    "guaranteed sales",
]

DIGITAL_HUMAN_SAMPLE_CLAIM_TERMS = (
    "voice clone",
    "voice cloning",
    "cloned voice",
    "clone voice",
    "real voice",
    "voice sample",
    "audio sample",
    "extracted audio",
    "extracted from video",
    "source video sample",
    "真人声音",
    "声音克隆",
    "克隆声音",
    "声音样本",
    "音频样本",
    "提取声音",
    "原视频声音",
    "真人样本",
)

PERSONA_OPERATIONAL_VARIANTS: list[dict[str, Any]] = [
    {
        "persona_type": "Beginner KOC",
        "role_task": "Help TikTok Shop creators with 5K+ followers turn product interest into product videos instead of posting random content without a clear commerce path.",
        "audience_callout": "If you have TikTok Shop access but your videos still are not selling...",
        "explicit_pains": ["does not know how to pick products", "does not know how to write commerce video scripts", "posts content without a clear product workflow"],
        "inner_conflict": "They have attention and followers, but they do not know how to turn that traffic into product videos or orders.",
        "desired_state": "They want to look more professional and keep promoting products without starting every video from zero.",
        "trust_angle": "Show the product-picking and script workflow instead of pretending the creator personally earned money from one shortcut.",
        "proof_assets": ["product selection logic", "product-to-video generation process", "traditional workflow vs Moras workflow"],
        "primary_scene": "late-night phone scrolling",
        "secondary_scenes": ["product library interface", "phone backend", "desktop workflow"],
        "scene_logic": "These scenes make the beginner bottleneck visible: the creator has options, a phone, and no clear angle yet.",
        "memory_symbols": {
            "fixed_opening_pattern": "Open on a product list beside messy notes, then move into the product-angle workflow.",
            "visual_anchor": "phone showing a product list beside a messy notes page",
            "recurring_prop": "three-check product note card",
            "wardrobe_anchor": "casual creator hoodie or utility jacket",
            "column_name": "First Product Post",
        },
        "content_pillars": ["Product Picking", "Beginner Trap", "Product-to-Video Workflow"],
        "hook_preferences": [],
        "cta_style": "Save the checklist and make one product video before chasing ten angles.",
        "role": "Beginner TikTok Shop KOC learning to turn product choices into commerce video posts.",
        "zh": {
            "persona_type": "新手 KOC",
            "role_task": "帮助已经开通 TikTok Shop、但还不会把流量变成订单路径的新手创作者，把商品兴趣转成可发布的商品视频。",
            "audience_callout": "如果你已经能做 TikTok Shop，但视频还是没有销量...",
            "explicit_pains": ["不会选品", "不会写商品视频脚本", "发了内容但没有清晰商品工作流"],
            "inner_conflict": "他们已经有流量和粉丝，但不知道怎么把注意力变成商品视频或订单路径。",
            "desired_state": "他们想看起来更专业，并且不用每条视频都从零开始。",
            "trust_angle": "展示选品和脚本工作流，而不是假装创作者靠捷径亲自赚到钱。",
            "proof_assets": ["选品逻辑说明", "商品到视频的生成过程", "传统流程 vs Moras 流程"],
            "primary_scene": "深夜刷手机",
            "secondary_scenes": ["产品库界面", "手机后台", "桌面工作流"],
            "scene_logic": "这些场景能直接呈现新手卡点：有商品、有手机，但没有清晰内容角度。",
            "fixed_opening_pattern": "先展示商品列表和混乱笔记，再进入商品角度工作流。",
            "visual_anchor": "手机商品列表旁边放着混乱笔记页",
            "recurring_prop": "三项选品检查卡",
            "wardrobe_anchor": "休闲创作者连帽衫或工装外套",
            "column_name": "第一个商品发布",
            "content_pillars": ["选品避坑", "新手误区纠正", "商品到视频"],
            "hook_preferences": [],
            "cta_style": "保存检查清单，追十个角度前先做清楚一个商品视频。",
            "role": "正在学习把商品选择变成可发布商品视频的新手 TikTok Shop KOC。",
        },
    },
    {
        "persona_type": "Mom Creator",
        "role_task": "Help busy mom creators make product video drafts from product information without adding daily content-production pressure.",
        "audience_callout": "If you only have 20 minutes after the kids are asleep...",
        "explicit_pains": ["has limited time for content production", "does not want to edit every day", "wants faceless or low-burden content"],
        "inner_conflict": "She wants extra income and professional-looking output, but she does not want content work to consume family time.",
        "desired_state": "She wants a lighter workflow that lets her promote products during small pockets of time.",
        "trust_angle": "Show time saved and workflow compression with real Moras screens or before/after process proof.",
        "proof_assets": ["time saved proof", "traditional workflow vs Moras workflow", "product-to-video generation process"],
        "primary_scene": "messy kitchen",
        "secondary_scenes": ["car pickup wait", "living room with kids", "late-night phone scrolling"],
        "scene_logic": "The life context proves the time pressure before the persona says a word.",
        "memory_symbols": {
            "fixed_opening_pattern": "Open inside a small time-window routine, then switch to Moras workflow proof.",
            "visual_anchor": "phone propped against a kitchen counter",
            "recurring_prop": "half-finished grocery list with product ideas",
            "wardrobe_anchor": "soft neutral cardigan over a practical T-shirt",
            "column_name": "15-Minute Product Post",
        },
        "content_pillars": ["Product-to-Video Workflow", "Product Picking", "Faceless Creator"],
        "hook_preferences": [],
        "cta_style": "Try one product video draft before spending a full content day on one angle.",
        "role": "Busy mom creator using small time windows to post TikTok Shop product videos.",
        "zh": {
            "persona_type": "妈妈创作者",
            "role_task": "帮助忙碌妈妈创作者在不增加每天内容制作负担的情况下，用商品信息做出商品视频草稿。",
            "audience_callout": "如果你只有孩子睡着后的 20 分钟...",
            "explicit_pains": ["内容制作时间有限", "不想每天剪辑", "想做不露脸或低负担内容"],
            "inner_conflict": "她想增加收入，也想让内容看起来专业，但不希望内容工作吞掉家庭时间。",
            "desired_state": "她想用更轻的工作流，在碎片时间里持续推广商品。",
            "trust_angle": "用真实 Moras 界面或前后流程证明展示省时和流程压缩。",
            "proof_assets": ["时间节省证明", "传统流程 vs Moras 流程", "商品到视频的生成过程"],
            "primary_scene": "厨房混乱",
            "secondary_scenes": ["车里等接娃", "客厅带娃", "深夜刷手机"],
            "scene_logic": "生活场景在开口前就证明了她的时间压力。",
            "fixed_opening_pattern": "先呈现碎片时间里的生活动作，再切到 Moras 工作流证明。",
            "visual_anchor": "手机靠在厨房台面上",
            "recurring_prop": "写着商品想法的半张购物清单",
            "wardrobe_anchor": "柔和中性色开衫搭配实用 T 恤",
            "column_name": "15 分钟商品视频",
            "content_pillars": ["Workflow 教程", "商品到视频", "不露脸创作"],
            "hook_preferences": [],
            "cta_style": "花完整内容日前，先试一个商品视频草稿。",
            "role": "利用碎片时间发布 TikTok Shop 商品视频的忙碌妈妈创作者。",
        },
    },
    {
        "persona_type": "Tutorial Learner",
        "role_task": "Give checklist-driven creators clear TikTok Shop steps for product selection, script drafting, and product video posting.",
        "audience_callout": "If you need steps, not another motivational creator story...",
        "explicit_pains": ["does not know the rules", "collects tutorials but struggles to act", "does not know how product choice connects to scripts"],
        "inner_conflict": "They want a method they can trust, but emotional storytelling and vague advice do not help them move.",
        "desired_state": "They want a repeatable checklist that makes one product video draft easier to review.",
        "trust_angle": "Use transparent product-selection logic, numbered workflow steps, and Moras screen recordings.",
        "proof_assets": ["product selection logic", "TikTok Shop backend", "product-to-video generation process"],
        "primary_scene": "tutorial whiteboard",
        "secondary_scenes": ["desktop workflow", "phone backend", "product library interface"],
        "scene_logic": "Structured tutorial spaces match an audience that saves clear rules and step lists.",
        "memory_symbols": {
            "fixed_opening_pattern": "Open with a visible numbered checklist, then explain the next creator action.",
            "visual_anchor": "small whiteboard with three product checks",
            "recurring_prop": "numbered checklist marker",
            "wardrobe_anchor": "clean simple overshirt and neutral tee",
            "column_name": "Shop Posting Checklist",
        },
        "content_pillars": ["Product-to-Video Workflow", "Product Picking", "Beginner Trap"],
        "hook_preferences": [],
        "cta_style": "Save the steps and run them on one product before the next content post.",
        "role": "Checklist-first TikTok Shop tutorial creator.",
        "zh": {
            "persona_type": "教程学习型创作者",
            "role_task": "给喜欢清单和步骤的创作者明确 TikTok Shop 选品、脚本草稿和商品视频发布方法。",
            "audience_callout": "如果你要的是步骤，不是又一个鸡汤故事...",
            "explicit_pains": ["不知道规则", "收藏了教程但难以行动", "不知道选品和脚本之间的关系"],
            "inner_conflict": "他们想要可信方法，但情绪故事和泛泛建议不能帮他们真正动起来。",
            "desired_state": "他们想拥有可重复检查清单，在发布前感觉自己准备好了。",
            "trust_angle": "用透明选品逻辑、编号步骤和 Moras 录屏建立信任。",
            "proof_assets": ["选品逻辑说明", "TikTok Shop 后台", "商品到视频的生成过程"],
            "primary_scene": "教程白板",
            "secondary_scenes": ["桌面工作流", "手机后台", "产品库界面"],
            "scene_logic": "结构化教程空间匹配会收藏明确规则和步骤的受众。",
            "fixed_opening_pattern": "先展示可见编号清单，再说明下一个创作者动作。",
            "visual_anchor": "写着三个选品检查点的小白板",
            "recurring_prop": "编号检查清单马克笔",
            "wardrobe_anchor": "干净简洁的衬衫外套和中性色 T 恤",
            "column_name": "商品发布清单",
            "content_pillars": ["Workflow 教程", "选品避坑", "新手误区纠正"],
            "hook_preferences": [],
            "cta_style": "保存步骤，下次内容发布前先套到一个商品上。",
            "role": "清单优先的 TikTok Shop 教程型创作者。",
        },
    },
    {
        "persona_type": "Skeptical Creator",
        "role_task": "Help AI-skeptical TikTok Shop creators understand what Moras does and does not do through transparent workflow proof.",
        "audience_callout": "If AI side-hustle videos make you suspicious, same...",
        "explicit_pains": ["does not trust AI tools", "worries about payout or commission scams", "has posted many videos without sales"],
        "inner_conflict": "They want a real workflow advantage, but they do not want to be fooled by miracle-tool claims.",
        "desired_state": "They want proof, boundaries, and a low-risk way to review without feeling naive.",
        "trust_angle": "Lead with skepticism, show proof assets, and explicitly state what Moras cannot guarantee.",
        "proof_assets": ["comment feedback", "TikTok Shop backend", "traditional workflow vs Moras workflow"],
        "primary_scene": "comment screenshot",
        "secondary_scenes": ["TikTok Shop backend", "street interview", "desktop workflow"],
        "scene_logic": "Objection-first scenes let the persona answer doubt instead of hiding it.",
        "memory_symbols": {
            "fixed_opening_pattern": "Open on an objection or proof screen before explaining the boundary.",
            "visual_anchor": "comment screenshot beside a Moras workflow proof clip",
            "recurring_prop": "red pen for marking claims that need proof",
            "wardrobe_anchor": "dark overshirt and plain tee",
            "column_name": "Proof Before Hype",
        },
        "content_pillars": ["Comment Reply", "Contrarian Take", "Tool Reveal"],
        "hook_preferences": [],
        "cta_style": "Check the workflow first, then decide if it is worth one product video.",
        "role": "Proof-first skeptical TikTok Shop creator who checks AI workflows without hype.",
        "zh": {
            "persona_type": "怀疑型创作者",
            "role_task": "帮助不信 AI 的 TikTok Shop 创作者通过透明工作流证据理解 Moras 能做什么、不能做什么。",
            "audience_callout": "如果 AI 副业视频让你很警惕，我也一样...",
            "explicit_pains": ["不信 AI 工具", "担心佣金或 payout 骗局", "发了很多视频但没有销量"],
            "inner_conflict": "他们想要真实的工作流优势，但不想被神奇工具话术骗。",
            "desired_state": "他们想看到证据、边界和低风险检查方式，而不是显得自己天真。",
            "trust_angle": "先承认怀疑，再展示证据，并明确 Moras 不能保证什么。",
            "proof_assets": ["评论区反馈", "TikTok Shop 后台", "传统流程 vs Moras 流程"],
            "primary_scene": "评论区截图",
            "secondary_scenes": ["TikTok Shop 后台", "街访", "桌面工作流"],
            "scene_logic": "先回应质疑的场景让人设直接处理怀疑，而不是回避。",
            "fixed_opening_pattern": "先展示质疑或证明画面，再解释边界。",
            "visual_anchor": "评论截图旁边接 Moras 工作流证据片段",
            "recurring_prop": "用来标记需要证据话术的红笔",
            "wardrobe_anchor": "深色衬衫外套和纯色 T 恤",
            "column_name": "先看证据",
            "content_pillars": ["评论回应", "反常识观点", "工具爆料"],
            "hook_preferences": [],
            "cta_style": "先检查工作流，再决定要不要做一个商品视频。",
            "role": "证据优先、拒绝夸张话术的 TikTok Shop 怀疑型创作者。",
        },
    },
    {
        "persona_type": "Lazy-but-Ambitious Creator",
        "role_task": "Help shortcut-seeking TikTok Shop creators remove unnecessary work from product posting without turning the promise into a scam.",
        "audience_callout": "If you want TikTok Shop money but hate complicated workflows...",
        "explicit_pains": ["hates complex courses", "does not want pointless work", "wants faceless content and faster drafts"],
        "inner_conflict": "They are ambitious but know they will quit if the workflow feels too heavy.",
        "desired_state": "They want the shortest honest path from product idea to a reviewable product video.",
        "trust_angle": "Show the shortened workflow and the limits clearly: faster drafts, not automatic money.",
        "proof_assets": ["traditional workflow vs Moras workflow", "time saved proof", "product-to-video generation process"],
        "primary_scene": "bed collapse",
        "secondary_scenes": ["late-night phone scrolling", "phone backend", "friend chat"],
        "scene_logic": "Low-energy scenes fit the desire to skip waste while keeping the promise honest.",
        "memory_symbols": {
            "fixed_opening_pattern": "Open with low-energy product browsing, then reveal the shortest honest workflow.",
            "visual_anchor": "phone screen over a blanket with a half-open product tab",
            "recurring_prop": "tiny lazy checklist card",
            "wardrobe_anchor": "oversized sweatshirt with clean neutral colors",
            "column_name": "Lazy Shop Shortcut",
        },
        "content_pillars": ["Tool Reveal", "Product-to-Video Workflow", "Faceless Creator"],
        "hook_preferences": [],
        "cta_style": "Try the shortest product-to-draft workflow once before doing the long version.",
        "role": "Shortcut-seeking TikTok Shop creator who removes waste without promising effortless income.",
        "zh": {
            "persona_type": "懒但有野心的创作者",
            "role_task": "帮助想走捷径的 TikTok Shop 创作者减少商品发布里的无效劳动，同时不把承诺说成骗局。",
            "audience_callout": "如果你想做 TikTok Shop 赚钱，但讨厌复杂流程...",
            "explicit_pains": ["讨厌复杂课程", "不想做无效劳动", "想要不露脸内容和更快草稿"],
            "inner_conflict": "他们有野心，但也知道流程一重自己就会放弃。",
            "desired_state": "他们想要从商品想法到可检查商品视频的最短诚实路径。",
            "trust_angle": "展示缩短后的流程和边界：更快出草稿，不是自动赚钱。",
            "proof_assets": ["传统流程 vs Moras 流程", "时间节省证明", "商品到视频的生成过程"],
            "primary_scene": "床上崩溃",
            "secondary_scenes": ["深夜刷手机", "手机后台", "朋友聊天"],
            "scene_logic": "低能量场景匹配想跳过无效劳动的心理，同时保持承诺诚实。",
            "fixed_opening_pattern": "先呈现低能量浏览商品，再展示最短诚实工作流。",
            "visual_anchor": "毯子上方的手机屏幕停在半打开的商品页",
            "recurring_prop": "很小一张懒人检查卡",
            "wardrobe_anchor": "干净中性色 oversized 卫衣",
            "column_name": "懒人商品捷径",
            "content_pillars": ["工具爆料", "商品到视频", "不露脸创作"],
            "hook_preferences": [],
            "cta_style": "先跑一次最短商品到草稿流程，再决定要不要做长流程。",
            "role": "会删掉无效步骤但不承诺轻松赚钱的 TikTok Shop 捷径型创作者。",
        },
    },
]


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def localized_persona_role(role: Any) -> str:
    text = str(role or "").strip()
    if not text or has_cjk(text):
        return text
    return PERSONA_ROLE_ZH.get(text, text)


def normalize_persona_localized_zh(persona: dict[str, Any]) -> None:
    localized = persona.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        persona["localized"] = localized
    zh = localized.get("zh")
    if not isinstance(zh, dict):
        zh = {}
        localized["zh"] = zh
    if persona.get("display_name"):
        zh["display_name"] = persona["display_name"]
    existing_role_zh = str(zh.get("role") or "").strip()
    role_zh = existing_role_zh if has_cjk(existing_role_zh) else localized_persona_role(persona.get("role"))
    if role_zh:
        zh["role"] = role_zh


def choose_operational_variant(
    *,
    persona: dict[str, Any] | None = None,
    seed: str | None = None,
    variant_index: int | None = None,
) -> dict[str, Any]:
    persona = persona or {}
    persona_type = str(persona.get("persona_type") or persona.get("personaType") or "").strip()
    if persona_type:
        for variant in PERSONA_OPERATIONAL_VARIANTS:
            if variant["persona_type"] == persona_type:
                return variant
    text = " ".join(str(persona.get(key) or "") for key in ("role", "creator_background", "personality", "trust_stance")).lower()
    keyword_map = [
        ("Mom Creator", ("mom", "mother", "parent", "kids", "school pickup", "妈妈", "宝妈", "带娃")),
        ("Tutorial Learner", ("tutorial", "checklist", "whiteboard", "steps", "教程", "清单", "步骤")),
        ("Skeptical Creator", ("skeptic", "suspicious", "proof", "transparent", "怀疑", "证据", "透明")),
        ("Lazy-but-Ambitious Creator", ("lazy", "shortcut", "bed", "low-burden", "懒", "捷径", "低负担")),
        ("Beginner KOC", ("beginner", "koc", "micro", "new creator", "新手")),
    ]
    for persona_type, keywords in keyword_map:
        if any(keyword in text for keyword in keywords):
            return next(variant for variant in PERSONA_OPERATIONAL_VARIANTS if variant["persona_type"] == persona_type)
    start = variant_index if variant_index is not None else stable_index(seed or "")
    return PERSONA_OPERATIONAL_VARIANTS[start % len(PERSONA_OPERATIONAL_VARIANTS)]


def default_persona_quality_score() -> dict[str, Any]:
    return {
        "score": 92,
        "checks": {
            "target_audience_clear": True,
            "role_task_clear": True,
            "three_layer_problem_complete": True,
            "recurring_scenes_present": True,
            "memory_symbols_present": True,
            "trust_assets_defined": True,
            "endorsement_boundary_safe": True,
            "not_overprofessionalized": True,
            "distinct_from_existing_personas": True,
            "script_agent_ready": True,
        },
        "review_notes": [
            "Persona is ready for Script Agent handoff.",
            "Bind approved Moras proof assets before scripts make specific workflow or result claims.",
        ],
    }


def ensure_list(value: Any, fallback: list[str]) -> list[str]:
    if isinstance(value, list):
        output = [str(item).strip() for item in value if str(item).strip()]
        if output:
            return output
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return list(fallback)


def ensure_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def ensure_creator_persona_v2_fields(
    persona: dict[str, Any],
    *,
    seed: str | None = None,
    variant_index: int | None = None,
) -> dict[str, Any]:
    variant = choose_operational_variant(persona=persona, seed=seed, variant_index=variant_index)
    zh_variant = variant["zh"]

    persona.setdefault("persona_type", variant["persona_type"])
    persona.setdefault("role_task", variant["role_task"])
    persona.setdefault("audience_callout", variant["audience_callout"])
    if not str(persona.get("role") or "").strip() or str(persona.get("role")).strip() in {"Reusable Moras creator persona", "Practical creator friend"}:
        persona["role"] = variant["role"]

    problem = ensure_mapping(persona.get("target_problem_profile"))
    problem["explicit_pains"] = ensure_list(problem.get("explicit_pains"), variant["explicit_pains"])
    if not problem.get("inner_conflict") and problem.get("inner_conflicts"):
        problem["inner_conflict"] = " / ".join(ensure_list(problem.get("inner_conflicts"), []))
    if not problem.get("desired_state") and problem.get("desired_states"):
        problem["desired_state"] = " / ".join(ensure_list(problem.get("desired_states"), []))
    problem.pop("inner_conflicts", None)
    problem.pop("desired_states", None)
    problem.setdefault("inner_conflict", variant["inner_conflict"])
    problem.setdefault("desired_state", variant["desired_state"])
    persona["target_problem_profile"] = problem

    trust = ensure_mapping(persona.get("trust_basis"))
    if isinstance(persona.get("trust_basis"), list):
        trust["usable_proof_assets"] = ensure_list(persona.get("trust_basis"), variant["proof_assets"])
    trust.setdefault("primary_trust_angle", variant["trust_angle"])
    trust["usable_proof_assets"] = ensure_list(trust.get("usable_proof_assets"), variant["proof_assets"])
    trust.setdefault("proof_insertion_rule", "When the script mentions speed, product choice, AI workflow value, or credibility, insert a visible approved Moras proof asset instead of relying on personal experience claims.")
    persona["trust_basis"] = trust
    persona.setdefault("proof_policy", trust["proof_insertion_rule"])

    scene_pair = ensure_mapping(persona.get("persona_scene_pair"))
    if isinstance(persona.get("persona_scene_pair"), str) and persona.get("persona_scene_pair"):
        scene_pair["primary_scene"] = str(persona["persona_scene_pair"]).strip()
    scene_pair.setdefault("primary_scene", variant["primary_scene"])
    scene_pair["secondary_scenes"] = ensure_list(scene_pair.get("secondary_scenes"), variant["secondary_scenes"])
    scene_pair.setdefault("scene_logic", variant["scene_logic"])
    persona["persona_scene_pair"] = scene_pair
    recurring_scenes = ensure_list(persona.get("recurring_scenes"), [scene_pair["primary_scene"], *scene_pair["secondary_scenes"]])
    if scene_pair["primary_scene"] not in recurring_scenes:
        recurring_scenes.insert(0, scene_pair["primary_scene"])
    persona["recurring_scenes"] = list(dict.fromkeys(recurring_scenes))

    symbols = ensure_mapping(persona.get("memory_symbols"))
    if isinstance(persona.get("memory_symbols"), list):
        symbol_values = ensure_list(persona.get("memory_symbols"), [])
        for key, value in zip(
            ["fixed_opening_pattern", "visual_anchor", "recurring_prop", "wardrobe_anchor", "column_name"],
            symbol_values,
            strict=False,
        ):
            symbols.setdefault(key, value)
    for key, value in variant["memory_symbols"].items():
        symbols.setdefault(key, value)
    persona["memory_symbols"] = symbols

    persona["content_pillars"] = ensure_list(persona.get("content_pillars"), variant["content_pillars"])[:5]
    if len(persona["content_pillars"]) < 3:
        persona["content_pillars"] = list(dict.fromkeys([*persona["content_pillars"], *variant["content_pillars"]]))[:5]
    # Kept for legacy records only. Hook strategy belongs to Script Agent.
    persona["hook_preferences"] = []
    persona.setdefault("cta_style", variant["cta_style"])

    boundary = ensure_mapping(persona.get("endorsement_boundary"))
    boundary["allowed_claims"] = ensure_list(
        boundary.get("allowed_claims"),
        ["promote products faster", "start from a structured script", "create commerce video drafts", "reduce blank-page work"],
    )
    boundary["banned_claims"] = ensure_list(boundary.get("banned_claims"), DEFAULT_BANNED_PERSONA_CLAIMS)
    for claim in DEFAULT_BANNED_PERSONA_CLAIMS:
        if claim not in boundary["banned_claims"]:
            boundary["banned_claims"].append(claim)
    boundary.setdefault(
        "experience_rule",
        "Do not claim personal purchase, product usage, payout, income, or sales unless a real approved proof asset supports that exact statement.",
    )
    persona["endorsement_boundary"] = boundary
    persona.pop("ai_disclosure_note", None)

    quality = ensure_mapping(persona.get("persona_quality_score"))
    default_quality = default_persona_quality_score()
    quality["score"] = int(quality.get("score") or default_quality["score"])
    checks = ensure_mapping(quality.get("checks"))
    checks.update({key: True for key in default_quality["checks"] if checks.get(key) is not False})
    quality["checks"] = checks
    quality["review_notes"] = ensure_list(quality.get("review_notes"), default_quality["review_notes"])
    persona["persona_quality_score"] = quality

    handoff = ensure_mapping(persona.get("script_agent_handoff"))
    handoff.setdefault("primary_directive", f"Write TikTok Shop scripts as {persona['display_name']}, using the persona mission: {persona['role_task']}")
    handoff["opening_scene_rules"] = ensure_list(
        handoff.get("opening_scene_rules"),
        [f"Open from {scene_pair['primary_scene']} when it fits the script type.", f"Keep recurring scenes available: {', '.join(persona['recurring_scenes'][:4])}."],
    )
    handoff["hook_rules"] = [
        "Script Agent owns hook selection: learn from source breakdowns and reference storyboards, then generate varied hook candidates for this persona.",
        "Do not reuse persona.audience_callout, memory_symbols.fixed_opening_pattern, or persona fields as final hook copy by default.",
    ]
    handoff["proof_asset_rules"] = ensure_list(
        handoff.get("proof_asset_rules"),
        [trust["proof_insertion_rule"], f"Preferred proof assets: {', '.join(trust['usable_proof_assets'][:4])}."],
    )
    handoff["forbidden_claims"] = ensure_list(handoff.get("forbidden_claims"), boundary["banned_claims"])
    for claim in boundary["banned_claims"]:
        if claim not in handoff["forbidden_claims"]:
            handoff["forbidden_claims"].append(claim)
    handoff.setdefault("cta_rule", persona["cta_style"])
    handoff.setdefault("compliance_note_rule", "Every script must include a compliance_note that repeats the no-income-guarantee and no-fake-experience boundary.")
    handoff.pop("ai_disclosure_rule", None)
    persona["script_agent_handoff"] = handoff

    localized = persona.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        persona["localized"] = localized
    zh = localized.get("zh")
    if not isinstance(zh, dict):
        zh = {}
        localized["zh"] = zh
    zh.setdefault("persona_type", zh_variant["persona_type"])
    zh.setdefault("role_task", zh_variant["role_task"])
    zh.setdefault("audience_callout", zh_variant["audience_callout"])
    zh.setdefault(
        "target_problem_profile",
        {
            "explicit_pains": zh_variant["explicit_pains"],
            "inner_conflict": zh_variant["inner_conflict"],
            "desired_state": zh_variant["desired_state"],
        },
    )
    zh.setdefault(
        "trust_basis",
        {
            "primary_trust_angle": zh_variant["trust_angle"],
            "usable_proof_assets": zh_variant["proof_assets"],
            "proof_insertion_rule": "只要脚本涉及效率、选品、AI 工作流价值或可信度，就必须插入可见且已批准的 Moras 证明素材。",
        },
    )
    zh.setdefault("proof_policy", zh["trust_basis"]["proof_insertion_rule"])
    zh.setdefault(
        "persona_scene_pair",
        {
            "primary_scene": zh_variant["primary_scene"],
            "secondary_scenes": zh_variant["secondary_scenes"],
            "scene_logic": zh_variant["scene_logic"],
        },
    )
    zh.setdefault("recurring_scenes", [zh_variant["primary_scene"], *zh_variant["secondary_scenes"]])
    zh.setdefault(
        "memory_symbols",
        {
            "fixed_opening_pattern": zh_variant["fixed_opening_pattern"],
            "visual_anchor": zh_variant["visual_anchor"],
            "recurring_prop": zh_variant["recurring_prop"],
            "wardrobe_anchor": zh_variant["wardrobe_anchor"],
            "column_name": zh_variant["column_name"],
        },
    )
    zh.setdefault("content_pillars", zh_variant["content_pillars"])
    zh["hook_preferences"] = []
    zh.setdefault("cta_style", zh_variant["cta_style"])
    zh.setdefault(
        "endorsement_boundary",
        {
            "allowed_claims": ["更快推广商品", "从结构化脚本开始", "生成商品视频草稿", "减少空白页工作"],
            "banned_claims": DEFAULT_BANNED_PERSONA_CLAIMS,
            "experience_rule": "除非有已批准的真实证明素材支持，否则不要声称亲自购买、使用、到账、赚钱或出单。",
        },
    )
    zh.pop("ai_disclosure_note", None)
    zh.setdefault("persona_quality_score", persona["persona_quality_score"])
    zh_handoff = ensure_mapping(zh.get("script_agent_handoff"))
    zh_handoff.setdefault("primary_directive", f"以 {persona['display_name']} 的身份写 TikTok Shop 脚本，遵守该人设任务。")
    zh_handoff["opening_scene_rules"] = ensure_list(zh_handoff.get("opening_scene_rules"), [f"适合时从 {zh_variant['primary_scene']} 开场。"])
    zh_handoff["hook_rules"] = [
        "Hook 由脚本 Agent 决定：根据视频拆解和参考 storyboard 学习爆款开头，再为该人设生成多种候选。",
        "不要默认把 audience_callout、人设固定开场或其他人设字段直接当成最终 Hook 文案。",
    ]
    zh_handoff["proof_asset_rules"] = ensure_list(zh_handoff.get("proof_asset_rules"), [zh["trust_basis"]["proof_insertion_rule"]])
    zh_handoff["forbidden_claims"] = ensure_list(zh_handoff.get("forbidden_claims"), DEFAULT_BANNED_PERSONA_CLAIMS)
    zh_handoff.setdefault("cta_rule", zh_variant["cta_style"])
    zh_handoff.setdefault("compliance_note_rule", "每条脚本必须写合规提醒，说明不保证收益且不虚构体验。")
    zh["script_agent_handoff"] = zh_handoff
    zh["script_agent_handoff"].pop("ai_disclosure_rule", None)
    ensure_digital_human_prompt_assets(persona)
    return persona


def default_creator_persona_payload(
    script: dict[str, Any],
    topic_plan: dict[str, Any],
    *,
    seed: str | None = None,
    variant_index: int | None = None,
    excluded_names: set[str] | None = None,
) -> dict[str, Any]:
    persona_text = str(script.get("persona") or topic_plan.get("persona") or "Practical creator workflow reviewer").strip()
    variant = choose_persona_variant(seed=seed, variant_index=variant_index, excluded_names=excluded_names)
    operational = choose_operational_variant(seed=seed, variant_index=variant_index)
    payload = {
        "persona_id": f"creator_persona_{slugify(variant['display_name'])}",
        "display_name": variant["display_name"],
        "role": operational["role"] if persona_text in {"Reusable Moras creator persona", "Practical creator workflow reviewer"} else persona_text,
        "demographic": variant["demographic"],
        "creator_background": (
            "Former marketplace operations assistant who became a part-time social-commerce creator after learning how much "
            "product selection, content planning, and review discipline affect posting speed."
        ),
        "personality": "Observant, practical, slightly skeptical at the start, then warm and direct once a workflow actually saves time.",
        "trust_stance": "Does not hype tools blindly; explains what is checked, what is ignored, and why the workflow is useful for low-budget creators.",
        "speech_style": "Conversational short-video coaching voice, brisk but calm, with concrete checklist language and no exaggerated income claims.",
        "hobbies_interests": ["desk setup optimization", "product teardown notes", "street coffee shops", "minimal skincare", "short-form editing"],
        "appearance": variant["appearance"],
        "face_hair_makeup": variant["face_hair_makeup"],
        "wardrobe": variant["wardrobe"],
        "styling_details": variant["styling_details"],
        "distinctive_marks_or_tattoos": variant["distinctive_marks_or_tattoos"],
        "props": variant["props"],
        "consistency_rules": [
            "Keep the same face shape, hair length, wardrobe palette, and wrist detail across every video clip.",
            "Use the same warm practical home-office mood and avoid changing the person into a corporate presenter.",
            "Hands should look natural and proportionate; do not add extra jewelry, tattoos, or dramatic makeup changes.",
        ],
    }
    payload["veo_identity_string"] = veo_identity_string_from_persona(payload)
    payload["reference_image_prompt"] = reference_image_prompt_from_persona(payload)
    zh_variant = variant["zh"]
    payload["localized"] = {
        "zh": {
            "display_name": zh_variant["display_name"],
            "role": localized_persona_role(persona_text),
            "demographic": zh_variant["demographic"],
            "creator_background": "曾做过电商平台运营助理，后来转为兼职社交电商创作者，熟悉选品、内容规划和复查纪律对发布速度的影响。",
            "personality": "观察力强、务实，开头略带怀疑，确认流程有效后会变得温和直接。",
            "trust_stance": "不会盲目吹捧工具，会解释自己检查什么、忽略什么，以及低预算创作者为什么能用上这个流程。",
            "speech_style": "短视频教练式口吻，节奏利落但平稳，使用具体清单语言，不做夸张收益承诺。",
            "hobbies_interests": ["桌面布置优化", "产品拆解笔记", "街边咖啡店", "极简护肤", "短视频剪辑"],
            "appearance": zh_variant["appearance"],
            "face_hair_makeup": zh_variant["face_hair_makeup"],
            "wardrobe": zh_variant["wardrobe"],
            "styling_details": zh_variant["styling_details"],
            "distinctive_marks_or_tattoos": zh_variant["distinctive_marks_or_tattoos"],
            "props": zh_variant["props"],
            "consistency_rules": [
                "每个视频片段保持相同脸型、发长、服装色系和手腕细节。",
                "保持温暖实用的家庭办公氛围，不要把人物变成企业主持人。",
                "手部自然且比例正确，不要额外增加首饰、纹身或夸张妆容。",
            ],
            "veo_identity_string": payload["veo_identity_string"],
            "reference_image_prompt": payload["reference_image_prompt"],
        }
    }
    ensure_creator_persona_v2_fields(payload, seed=seed, variant_index=variant_index)
    normalize_persona_localized_zh(payload)
    return payload


def normalize_creator_persona_payload(
    value: Any,
    topic_plan: dict[str, Any],
    script: dict[str, Any],
    *,
    seed: str | None = None,
    variant_index: int | None = None,
    excluded_names: set[str] | None = None,
) -> dict[str, Any]:
    if creator_persona_needs_refresh(value, excluded_names=excluded_names):
        return default_creator_persona_payload(script, topic_plan, seed=seed, variant_index=variant_index, excluded_names=excluded_names)
    cleaned = dict(value)
    cleaned.pop("reference_image_negative_prompt", None)
    cleaned.pop("ai_disclosure_note", None)
    localized = cleaned.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else None
    if zh is not None:
        zh.pop("reference_image_negative_prompt", None)
        zh.pop("ai_disclosure_note", None)
        zh_handoff = zh.get("script_agent_handoff")
        if isinstance(zh_handoff, dict):
            zh_handoff.pop("ai_disclosure_rule", None)
    handoff = cleaned.get("script_agent_handoff")
    if isinstance(handoff, dict):
        handoff.pop("ai_disclosure_rule", None)
    if not str(cleaned.get("veo_identity_string") or "").strip():
        cleaned["veo_identity_string"] = veo_identity_string_from_persona(cleaned)
        if zh is not None:
            zh["veo_identity_string"] = cleaned["veo_identity_string"]
    reference_prompt = str(cleaned.get("reference_image_prompt") or "")
    if reference_prompt_needs_refresh(reference_prompt):
        cleaned["reference_image_prompt"] = reference_image_prompt_from_persona(cleaned)
        if zh is not None:
            zh["reference_image_prompt"] = cleaned["reference_image_prompt"]
    ensure_creator_persona_v2_fields(cleaned, seed=seed, variant_index=variant_index)
    normalize_persona_localized_zh(cleaned)
    return cleaned


def creator_persona_needs_refresh(value: Any, *, excluded_names: set[str] | None = None) -> bool:
    if not isinstance(value, dict) or not value:
        return True
    required_fields = [
        "display_name",
        "role",
        "appearance",
        "face_hair_makeup",
        "wardrobe",
        "styling_details",
        "reference_image_prompt",
    ]
    if any(not str(value.get(field) or "").strip() for field in required_fields):
        return True
    display_name = str(value.get("display_name") or "").strip()
    if excluded_names and display_name in excluded_names:
        return True
    text = " ".join(
        str(value.get(field) or "")
        for field in ["display_name", "demographic", "appearance", "face_hair_makeup", "wardrobe", "reference_image_prompt"]
    ).lower()
    if re.search(r"\basian\b", text) or "亚洲" in text or "mia chen" in text or "米娅" in text:
        return True
    if value.get("reference_image_negative_prompt"):
        return True
    localized = value.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else None
    if zh is not None and zh.get("reference_image_negative_prompt"):
        return True
    return reference_prompt_needs_refresh(str(value.get("reference_image_prompt") or ""))


def reference_prompt_needs_refresh(value: str) -> bool:
    lowered = value.lower()
    return not value.strip() or "script" in lowered or "脚本" in value or "theme" in lowered or "plot" in lowered or "campaign" in lowered


def veo_identity_string_from_persona(persona: dict[str, Any]) -> str:
    display_name = str(persona.get("display_name") or "the creator").strip()
    demographic = str(persona.get("demographic") or "social-commerce creator").strip()
    appearance = str(persona.get("appearance") or "natural face, consistent hair, realistic posture").strip()
    face_hair_makeup = str(persona.get("face_hair_makeup") or "natural makeup and consistent hair").strip()
    wardrobe = str(persona.get("wardrobe") or "creator-native outfit").strip()
    marks = str(persona.get("distinctive_marks_or_tattoos") or "").strip()
    props_value = persona.get("props") or []
    props = ", ".join(str(item).strip() for item in props_value if str(item).strip()) if isinstance(props_value, list) else str(props_value)
    demographic = compact_identity_fragment(demographic, 105)
    appearance = compact_identity_fragment(appearance, 105)
    face_hair_makeup = compact_identity_fragment(face_hair_makeup, 80)
    wardrobe = compact_identity_fragment(wardrobe, 85)
    marks = compact_identity_fragment(marks, 55)
    props = compact_identity_fragment(props, 70)
    return (
        f"{display_name}, {demographic}; {appearance}; {face_hair_makeup}; "
        f"wardrobe: {wardrobe}; consistent details: {marks}; props: {props}."
    )


def compact_identity_fragment(value: str, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", value).strip()
    if len(text) <= max_chars:
        return text
    clipped = text[: max_chars + 1].rsplit(" ", 1)[0].strip(" ,.;:，。；：")
    return clipped or text[:max_chars].strip(" ,.;:，。；：")


def reference_image_prompt_from_persona(persona: dict[str, Any]) -> str:
    display_name = str(persona.get("display_name") or "the creator").strip()
    demographic = str(persona.get("demographic") or "social-commerce creator").strip()
    appearance = str(persona.get("appearance") or "consistent face shape, natural posture, expressive hands").strip()
    face_hair_makeup = str(persona.get("face_hair_makeup") or "natural makeup, clean hair styling, detailed facial features").strip()
    wardrobe = str(persona.get("wardrobe") or "creator-native neutral outfit with consistent accessories").strip()
    styling = str(persona.get("styling_details") or "tidy lived-in creator desk styling with practical accessories").strip()
    marks = str(persona.get("distinctive_marks_or_tattoos") or "subtle consistent distinguishing details").strip()
    props_value = persona.get("props") or []
    props = ", ".join(str(item) for item in props_value if str(item).strip()) if isinstance(props_value, list) else str(props_value)
    if not props:
        props = "smartphone, laptop, notes, and small product package"
    return (
        "A portrait photograph of a high fidelity realistic character reference for Veo video consistency. "
        f"Subject: {display_name}, {demographic}. "
        f"Appearance: {appearance}. "
        f"Face, hair, and makeup: {face_hair_makeup}. "
        f"Wardrobe: {wardrobe}. "
        f"Styling details and distinguishing marks: {styling}; {marks}. "
        f"Composition: clean three-quarter portrait plus visible hands at a creator desk, neutral studio-like home office background, with {props} nearby. "
        "Style: realistic natural light, high fidelity, cinematic but practical, sharp facial detail, consistent wardrobe colors, plain non-branded background elements, against a neutral seamless studio backdrop, high resolution, 85mm lens."
    )


def digital_human_prompt_assets_from_persona(persona: dict[str, Any]) -> dict[str, Any]:
    display_name = str(persona.get("display_name") or "the creator").strip()
    identity = str(persona.get("veo_identity_string") or veo_identity_string_from_persona(persona)).strip()
    reference_prompt = str(persona.get("reference_image_prompt") or reference_image_prompt_from_persona(persona)).strip()
    speech_style = str(persona.get("speech_style") or "conversational short-video coaching voice, brisk but calm").strip()
    personality = str(persona.get("personality") or "practical, warm, and direct").strip()
    trust_stance = str(persona.get("trust_stance") or "explains what is checked without hype").strip()
    wardrobe = str(persona.get("wardrobe") or "creator-native outfit").strip()
    props = ", ".join(str(item).strip() for item in persona.get("props") or [] if str(item).strip()) or "phone, laptop, and product notes"
    visual_identity = compact_identity_fragment(identity, 520)
    return {
        "visual_reference_prompt": reference_prompt,
        "avatar_motion_prompt": (
            f"Generate vertical 9:16 synthetic creator source footage featuring {visual_identity}. "
            f"Keep {display_name} in a compact creator workspace with {props}, natural face and hand movement, "
            f"visible mouth movement aligned to short spoken lines, creator-native posture, and wardrobe continuity: {wardrobe}."
        ),
        "voice_style_prompt": (
            f"Synthetic TTS delivery for {display_name}: {speech_style}. "
            f"Personality should feel {personality}. Trust stance: {trust_stance}. "
            "Use plain social-video phrasing, short pauses after checklist points, and a grounded direct-to-phone rhythm."
        ),
        "script_delivery_rules": [
            "Write short spoken lines that match the persona speech_style and can be read naturally by synthetic TTS.",
            "Carry the persona voice through pacing, emphasis, pauses, and plain creator phrasing instead of post-production claims.",
            "Keep Moras as one mid-script selected-product/Create-video workflow moment, not an opening hero or closing sales pitch.",
        ],
        "sample_requirement": "no_real_sample_required",
        "synthetic_disclosure_note": "Persona Agent defines the visual identity and voice direction as text prompts; generation uses synthetic media direction without uploaded media.",
        "keep_consistent": [
            "same face shape, skin tone, hair, makeup or grooming, and distinctive marks",
            "same wardrobe palette, creator workspace mood, and recurring props",
            "same speech rhythm, trust stance, and short-video coaching energy",
        ],
        "avoid": [
            "do not change age, face, hair length, wardrobe palette, or recurring props between clips",
            "do not imitate a real person or celebrity",
            "do not imply uploaded media was used to define the persona",
        ],
    }


def localized_digital_human_prompt_assets_from_persona(persona: dict[str, Any]) -> dict[str, Any]:
    display_name = str(persona.get("display_name") or "该创作者").strip()
    localized = persona.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else {}
    reference_prompt = str(zh.get("reference_image_prompt") or persona.get("reference_image_prompt") or reference_image_prompt_from_persona(persona)).strip()
    speech_style = str(zh.get("speech_style") or persona.get("speech_style") or "短视频教练式口吻，利落但平稳").strip()
    trust_stance = str(zh.get("trust_stance") or persona.get("trust_stance") or "说明自己检查什么，不夸大承诺").strip()
    appearance = str(zh.get("appearance") or persona.get("appearance") or "").strip()
    wardrobe = str(zh.get("wardrobe") or persona.get("wardrobe") or "").strip()
    props_value = zh.get("props") if isinstance(zh.get("props"), list) else persona.get("props")
    props = "、".join(str(item).strip() for item in props_value or [] if str(item).strip()) or "手机、电脑和产品笔记"
    return {
        "visual_reference_prompt": reference_prompt,
        "avatar_motion_prompt": (
            f"生成 9:16 竖屏合成创作者素材，主角为 {display_name}。"
            f"保持外貌：{appearance}；服饰：{wardrobe}；道具：{props}。"
            "动作是自然面对手机口播、手部动作真实、嘴型跟随短句节奏、整体像社媒创作者而不是广告主持人。"
        ),
        "voice_style_prompt": f"{display_name} 的合成旁白方向：{speech_style}。可信立场：{trust_stance}。语速利落但不夸张，清单点后留短暂停顿。",
        "script_delivery_rules": [
            "口播短句要符合该人设的说话方式，便于合成旁白自然朗读。",
            "通过节奏、重音、停顿和创作者口吻体现声音特征，不暗示后期能力。",
            "Moras 只作为中段选中商品 / Create video 工作流出现一次，不做开场主角或结尾硬广。",
        ],
        "sample_requirement": "no_real_sample_required",
        "synthetic_disclosure_note": "人设 Agent 用文本定义视觉身份和声音方向；生成链路使用合成媒体提示词，不依赖上传媒体。",
        "keep_consistent": [
            "脸型、肤色、发型、妆造或修容、固定特征保持一致",
            "服饰色系、创作者工作空间氛围、固定道具保持一致",
            "说话节奏、可信立场、短视频教练感保持一致",
        ],
        "avoid": [
            "不要在不同片段中改变年龄、脸、发长、服饰色系或固定道具",
            "不要模仿真实个人或名人",
            "不要暗示使用了上传媒体来定义人设",
        ],
    }


def prompt_asset_claims_samples(value: Any) -> bool:
    if isinstance(value, dict):
        text = " ".join(str(child) for child in value.values())
    elif isinstance(value, list):
        text = " ".join(str(child) for child in value)
    else:
        text = str(value or "")
    lowered = text.lower()
    return any(term in lowered or term in text for term in DIGITAL_HUMAN_SAMPLE_CLAIM_TERMS)


def normalize_digital_human_prompt_assets(value: Any) -> dict[str, Any]:
    aliases = {
        "visualReferencePrompt": "visual_reference_prompt",
        "visualPrompt": "visual_reference_prompt",
        "referencePrompt": "visual_reference_prompt",
        "avatarMotionPrompt": "avatar_motion_prompt",
        "motionPrompt": "avatar_motion_prompt",
        "voiceStylePrompt": "voice_style_prompt",
        "voicePrompt": "voice_style_prompt",
        "scriptDeliveryRules": "script_delivery_rules",
        "deliveryRules": "script_delivery_rules",
        "sampleRequirement": "sample_requirement",
        "syntheticDisclosureNote": "synthetic_disclosure_note",
        "keepConsistent": "keep_consistent",
    }
    raw = ensure_mapping(value)
    normalized: dict[str, Any] = {}
    for key, child in raw.items():
        normalized[aliases.get(str(key), str(key))] = child
    return normalized


def ensure_digital_human_prompt_assets(persona: dict[str, Any]) -> None:
    defaults = digital_human_prompt_assets_from_persona(persona)
    existing = normalize_digital_human_prompt_assets(
        persona.get("digital_human_prompt_assets") or persona.get("digitalHumanPromptAssets")
    )
    if prompt_asset_claims_samples(existing):
        existing = {}
    assets = dict(defaults)
    for key in ("avatar_motion_prompt", "voice_style_prompt", "synthetic_disclosure_note"):
        text = str(existing.get(key) or "").strip()
        if text and not prompt_asset_claims_samples(text):
            assets[key] = text
    assets["visual_reference_prompt"] = defaults["visual_reference_prompt"]
    assets["script_delivery_rules"] = ensure_list(existing.get("script_delivery_rules"), defaults["script_delivery_rules"])[:5]
    assets["keep_consistent"] = ensure_list(existing.get("keep_consistent"), defaults["keep_consistent"])[:6]
    assets["avoid"] = ensure_list(existing.get("avoid"), defaults["avoid"])[:6]
    assets["sample_requirement"] = "no_real_sample_required"
    persona["digital_human_prompt_assets"] = assets
    persona.pop("digitalHumanPromptAssets", None)

    localized = persona.setdefault("localized", {})
    if not isinstance(localized, dict):
        localized = {}
        persona["localized"] = localized
    zh = localized.setdefault("zh", {})
    if not isinstance(zh, dict):
        zh = {}
        localized["zh"] = zh
    zh["digital_human_prompt_assets"] = localized_digital_human_prompt_assets_from_persona(persona)


def choose_persona_variant(
    *,
    seed: str | None,
    variant_index: int | None,
    excluded_names: set[str] | None,
) -> dict[str, Any]:
    start = variant_index if variant_index is not None else stable_index(seed or "")
    excluded = excluded_names or set()
    for offset in range(len(PERSONA_VARIANTS)):
        variant = PERSONA_VARIANTS[(start + offset) % len(PERSONA_VARIANTS)]
        if variant["display_name"] not in excluded:
            return variant
    return PERSONA_VARIANTS[start % len(PERSONA_VARIANTS)]


def stable_index(seed: str) -> int:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % len(PERSONA_VARIANTS)


def slugify(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "default"
