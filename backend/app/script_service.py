from __future__ import annotations

import asyncio
import copy
import json
import math
import re
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .config import get_settings
from .errors import conflict, unprocessable
from .persona_defaults import (
    creator_persona_needs_refresh,
    default_creator_persona_payload,
    ensure_digital_human_prompt_assets,
    normalize_creator_persona_payload,
    veo_identity_string_from_persona,
)
from .provider import generate_gemini_text
from .repository import BreakdownRepository, utc_now
from .schemas import (
    BANNED_SCRIPT_CLAIM_PATTERNS,
    CreatorPersonaRecord,
    CreatorPersonaProfile,
    MAX_SCRIPT_VOICEOVER_ENGLISH_WORDS,
    MAX_STORYBOARD_ROW_DURATION_SEC,
    MAX_STORYBOARD_VOICEOVER_ENGLISH_WORDS,
    MAX_VOICEOVER_SENTENCE_CHUNKS,
    MIN_SCRIPT_SPOKEN_DURATION_SEC,
    MIN_SCRIPT_VOICEOVER_LINES,
    MIN_SCRIPT_VOICEOVER_TOTAL_ENGLISH_WORDS,
    MORAS_ASSET_CATEGORIES,
    PersonaEditRequest,
    PersonaGenerationJobRecord,
    PersonaGenerationJobStatus,
    PersonaGenerationRequest,
    ScriptAgentBatch,
    ScriptAgentItem,
    ScriptEditRequest,
    ScriptGenerationJobStatus,
    ScriptGenerationRequest,
    ScriptRecord,
    ScriptStatus,
    english_word_count,
    localized_zh_field,
    sentence_chunk_count,
    script_spoken_lines_for_length,
    script_voiceover_estimated_duration_sec,
    storyboard_voiceover_min_duration_sec,
)
from .service import error_message, strip_json_fence


PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
PROMPT_PATH = PROMPTS_DIR / "script_agent_v1.md"
SCRIPT_SKILLS_DIR = PROMPTS_DIR / "script_agent_skills"
SCRIPT_OUTPUT_CONTRACT_PATH = PROMPTS_DIR / "script_agent_output_contract.md"
SCRIPT_EDIT_OUTPUT_CONTRACT_PATH = PROMPTS_DIR / "script_agent_edit_output_contract.md"
VOICEOVER_EXPERT_PROMPT_PATH = PROMPTS_DIR / "script_voiceover_expert_v1.md"
PERSONA_PROMPT_PATH = PROMPTS_DIR / "persona_agent_v1.md"
REFERENCE_SKELETONS_PATH = PROMPTS_DIR / "reference_teardown_skeletons_v1.json"
PROMPT_VERSION = "moras_script_agent_v1"
VOICEOVER_EXPERT_PROMPT_VERSION = "moras_script_voiceover_expert_v1"
PERSONA_PROMPT_VERSION = "moras_persona_agent_v2"
DEFAULT_TARGET_DURATION_SEC = 38.0
MAX_VEO_SEGMENT_SECONDS = 8.0
MAX_DYNAMIC_VEO_SEGMENTS = 7
MIN_VEO_SEGMENT_SECONDS = 0.5
SCRIPT_AGENT_SKILL_ORDER = (
    "campaign-boundaries",
    "persona-and-diversity",
    "script-copywriting",
    "visual-production",
    "veo-prompting",
)
REAL_MORAS_ASSET_TYPES = {"real_moras_screen_recording", "real_moras_screenshot", "moras_product_workflow"}
SCRIPT_SAFE_STYLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"^listen up$", "Creator callout"),
    (r"\bsix months of guessing with no clear workflow\.?\s*now i promote products with a clearer workflow\.?", "I finally stopped guessing which products fit my page. Instead, I use Moras to choose what to promote next."),
    (r"\bsix months of guessing with no clear workflow\b", "I finally stopped guessing which products fit my page"),
    (r"\bten thousand followers\.?\s*no clear product workflow\b", "Ten thousand followers, but the product workflow was unclear"),
    (r"\b10k followers\.?\s*unclear product workflow\b", "10K followers. Product workflow unclear"),
    (r"^now i promote products with a clearer workflow\.?$", "Instead, I choose what to promote with a clearer workflow."),
    (r"\bunclear product workflow at the start of the month\.?\s*a working system by the end\b", "The product workflow was unclear at first. A working system came after that"),
    (r"^unclear product workflow at the start of$", "The product workflow was unclear at first"),
    (r"^the month\.?\s*a working system by the end\.?$", "A working system came after that."),
    (r"\bno clear product workflow\b", "unclear product workflow"),
    (r"\bsix months of zero conversions\.?\s*now i test products every day\.?", "I finally stopped guessing which products fit my page. Instead, I use Moras to choose what to promote next."),
    (r"\bsix months of zero conversions\b", "I finally stopped guessing which products fit my page"),
    (r"\bnow i test products every day\b", "Instead, I use Moras to choose what to promote next"),
    (r"\bmade zero sales\b", "could not find the right product angle"),
    (r"\b0 conversions\b", "unclear product workflow"),
    (r"\b0 conversion\b", "unclear product workflow"),
    (r"\b0 sales\b", "unclear product workflow"),
    (r"\b0 orders\b", "unclear product workflow"),
    (r"\b0 posts\b", "an empty posting calendar"),
    (r"\bzero conversions\b", "unclear product workflow"),
    (r"\bzero conversion\b", "unclear product workflow"),
    (r"\bzero sales\b", "unclear product workflow"),
    (r"\bzero orders\b", "unclear product workflow"),
    (r"\bzero posts\b", "an empty posting calendar"),
    (r"\bno conversions\b", "unclear product workflow"),
    (r"\bno sales\b", "unclear product workflow"),
    (r"\bno orders\b", "unclear product workflow"),
    (r"\bstill no post\b", "still no clear posting plan"),
    (r"\btest products every day\b", "promote products with a clearer workflow"),
    (r"\btesting products every day\b", "promoting products with a clearer workflow"),
    (r"\btest products\b", "promote products"),
    (r"\btesting products\b", "promoting products"),
    (r"\bproduct tests\b", "product promotion videos"),
    (r"\bproduct testing\b", "product promotion"),
    (r"\bproduct tester\b", "product promotion creator"),
    (r"\bproduct testing coach\b", "product posting coach"),
    (r"\btestable workflow video draft\b", "reviewable product video"),
    (r"\btestable workflow video drafts\b", "reviewable product videos"),
    (r"\btestable product video draft\b", "reviewable product video"),
    (r"\btestable product video drafts\b", "reviewable product videos"),
    (r"\btestable video draft\b", "reviewable product video"),
    (r"\btestable video drafts\b", "reviewable product videos"),
    (r"\btestable videos\b", "reviewable product videos"),
    (r"\bcontent tests?\b", "content posts"),
    (r"\bsales tests?\b", "sales-path videos"),
    (r"\bproduct idea to a testable\b", "product idea to a reviewable"),
    (r"\btest every day\b", "post more often"),
    (r"\btesting speed\b", "posting speed"),
    (r"\btesting efficiency\b", "posting consistency"),
    (r"\bstop guessing, start testing\b", "Stop guessing, start posting"),
    (r"\bthat gives me another test before i buy samples\b", "That gives me another video I can actually post"),
    (r"\bthat gives me another test before i spend more money\b", "That gives me another video before the day disappears"),
    (r"\bso i open moras before i buy samples\b", "So I open Moras before I miss another posting window"),
    (r"\bzero[- ]sample costs?\b", "lower blank-page costs"),
    (r"\bzero[- ]sample testing\b", "Product-to-Video Posting"),
    (r"\bzero[- ]sample\b", "Product-to-Video"),
    (r"\bsample cost\b", "Blank-Page Cost"),
    (r"\bzero[- ]blank draft posting\b", "Product-to-Video Posting"),
    (r"\bzero[- ]blank draft\b", "Product-to-Video"),
    (r"\bthe blank draft cost\b", "The Blank-Page Cost"),
    (r"\bproduct-to-video posting\b", "Product-to-Video Posting"),
    (r"\bproduct-to-video\b", "Product-to-Video"),
    (r"\bthe blank-page cost\b", "The Blank-Page Cost"),
    (r"\bthe sample excuse is expensive\b", "the blank-page loop costs real money"),
    (r"\bi used to buy samples before i knew the angle\b", "I used to start every product from zero"),
    (r"\bi stopped buying samples first\b", "I stopped starting every product from zero"),
    (r"\bno samples on my desk\b", "no blank drafts on my desk"),
    (r"\bbefore i buy samples\b", "before I miss another posting window"),
    (r"\bbefore i spend on samples\b", "before I miss another posting window"),
    (r"\bspend on samples\b", "miss another posting window"),
    (r"\bwithout buying physical samples\b", "without starting every product from zero"),
    (r"\bwithout physical samples\b", "from selected products"),
    (r"\bphysical samples\b", "selected products"),
    (r"\bsample costs\b", "blank-page costs"),
    (r"\bbuying samples\b", "starting from zero"),
    (r"\bbuy samples\b", "start from zero"),
    (r"\bbuy sample\b", "start from zero"),
    (r"\bsample decision\b", "posting decision"),
    (r"\bproduct samples\b", "product packages"),
    (r"\bproduct sample\b", "product package"),
    (r"\bskincare product sample\b", "skincare product package"),
    (r"\bhousehold product sample\b", "household product package"),
    (r"\bbeauty product sample\b", "beauty product package"),
    (r"\bkitchen gadget sample\b", "kitchen gadget package"),
    (r"\btech accessory sample\b", "tech accessory package"),
    (r"\bwellness product sample\b", "wellness product package"),
    (r"\bsample box\b", "product notes"),
    (r"\bsamples\b", "blank drafts"),
    (r"\bsample\b", "blank draft"),
    (r"\bproduct i want to test\b", "product I want to promote"),
    (r"\bproduct to test\b", "product to promote"),
    (r"\bto test today\b", "to post today"),
    (r"\bone more test\b", "one more post"),
    (r"\banother test\b", "another post"),
    (r"\bultimate\b", "practical"),
    (r"\bmust[- ]have\b", "useful"),
    (r"\ball[- ]in[- ]one\b", "product-to-video"),
    (r"\bgame changer\b", "workflow shift"),
    (r"\brevolutionary\b", "new"),
    (r"\bseamless experience\b", "smoother workflow"),
    (r"\brandom inventory\b", "random product list"),
    (r"\bhoard inventory\b", "pile up product choices"),
    (r"\binventory\b", "product list"),
    (r"\bunlock\b", "start"),
    (r"\btransform your\b", "change your"),
    (r"\bboost your\b", "improve your"),
    (r"\bsupercharge\b", "speed up"),
    (r"\blevel up\b", "improve"),
    (r"\bprove me wrong\b", "check this"),
    (r"\bdoing it the hard way\b", "starting from a blank page"),
    (r"\btesting\b", "posting"),
    (r"\btested\b", "posted"),
    (r"\btests\b", "posts"),
    (r"\btest\b", "post"),
    (r"\btest smarter\b", "post smarter"),
    (r"\btesting routine\b", "posting routine"),
    (r"\btest list\b", "posting checklist"),
    (r"\bangle-testing routine\b", "posting routine"),
    (r"\bready[- ]to[- ]post\b", "reviewable"),
    (r"\bready[- ]to[- ]publish instantly\b", "ready to review"),
    (r"\bpublish[- ]ready instantly\b", "ready to review"),
    (r"\binstantly ready\b", "ready to review"),
    (r"\bshoppable\b", "workflow"),
    (r"\bvideo with cart\b", "video output with the next step visible"),
    (r"\bwith the cart attached\b", "with the next step visible"),
    (r"\bcart attached\b", "next step visible"),
    (r"\bwith cart\b", "with the next step visible"),
    (r"\bproduct[- ]cards\b", "selected products"),
    (r"\bproduct[- ]card\b", "selected product"),
    (r"\bmarket segment\b", "customer problem"),
    (r"\bvertical market\b", "creator problem"),
    (r"\bniche\b", "product type"),
    (r"\bframework\b", "workflow"),
    (r"\bmechanism\b", "reason"),
    (r"\boptimization\b", "improvement"),
    (r"\boptimize\b", "improve"),
    (r"\bleverage\b", "use"),
    (r"\brough cut\b", "first draft"),
    (r"\brough edit\b", "first draft"),
    (r"\beditable rough cut\b", "reviewable first draft"),
    (r"\beditable cut\b", "reviewable draft"),
    (r"\binstant draft\b", "first draft"),
    (r"\binstantly get\b", "get"),
    (r"\bin minutes\b", "without starting from a blank page"),
    (r"\blink is right there\b", "click the button"),
    (r"商品卡", "选中商品"),
    (r"细分市场", "商品问题"),
    (r"细分领域", "商品问题"),
    (r"赛道", "商品问题"),
    (r"可发布视频", "可检查视频"),
    (r"可发布商品视频", "可检查视频"),
    (r"可发布可购物视频", "可检查视频"),
    (r"可购物视频", "工作流视频"),
    (r"可购物", "带货路径清晰"),
    (r"商品视频", "工作流视频"),
    (r"带购物车的可发布", "带下一步入口的可检查"),
    (r"带购物车视频", "带下一步入口的视频"),
    (r"购物车", "带货路径"),
    (r"带带货路径的可发布", "带下一步入口的可检查"),
    (r"带带货路径视频", "带下一步入口的视频"),
    (r"带车成片", "带下一步入口的视频"),
    (r"粗剪草稿", "初版视频"),
    (r"粗剪", "初版视频"),
    (r"剪辑草稿", "初版视频"),
    (r"可编辑视频", "可检查视频"),
    (r"可直接编辑", "可先检查"),
    (r"直接上手改", "先检查"),
    (r"瞬间拿到", "拿到"),
    (r"马上拿到", "拿到"),
    (r"立刻拿到", "拿到"),
    (r"立即拿到", "拿到"),
    (r"立刻生成", "生成一个可检查版本"),
    (r"立即生成", "生成一个可检查版本"),
    (r"点击链接", "点击按钮"),
    (r"买样品这个借口，其实很贵", "空白稿这个循环，其实很贵"),
    (r"买样品这个借口很贵", "空白稿这个循环很贵"),
    (r"以前我还没想清角度，就先买样品", "以前我每个商品都从零开始"),
    (r"我先不买样品了", "我不再从空白页开始"),
    (r"买样品前", "错过发布窗口前"),
    (r"样品到之前", "发布窗口错过之前"),
    (r"产品测试员", "商品发布教练"),
    (r"产品测试教练", "商品发布教练"),
    (r"产品测评博主", "商品视频创作者"),
    (r"产品测评", "商品视频"),
    (r"商品测试方法", "商品发布方法"),
    (r"内容测试", "内容发布"),
    (r"测试速度", "发布速度"),
    (r"测试效率", "发布稳定性"),
    (r"样品盒", "商品便签"),
    (r"想测试的商品", "想推广的商品"),
    (r"选择一个商品来测试", "选择一个商品来推广"),
    (r"选择自己想测试的商品", "选择自己想推广的商品"),
    (r"下个测试方向", "下条发布内容"),
    (r"测试清单", "发布清单"),
    (r"测试习惯", "发布节奏"),
    (r"先测再买", "直接做能发布的视频"),
    (r"先低成本测试", "低成本出片"),
    (r"多测几个方向", "多做几条可发布内容"),
    (r"多测一个方向", "多做一条可发布内容"),
    (r"多测一个想法", "多做一条内容"),
    (r"测试流程", "发布流程"),
    (r"^听我说$", "开头卡点"),
    (r"测试", "发布"),
    (r"样品", "商品"),
)
SCRIPT_REPAIR_CTA_EN = "If you're a 5K+ TikTok Shop creator, click the button. Make your own money."
SCRIPT_REPAIR_CTA_ZH = "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。"
SCRIPT_VOICEOVER_REPAIR_BEAT_SETS: tuple[tuple[tuple[str, str], ...], ...] = (
    (
        ("I used to start every product from zero.", "以前我每个商品都从零开始。"),
        ("That made every wrong product feel expensive.", "每次选错商品，成本都会变得很重。"),
        ("My notes would turn into another messy draft.", "我的笔记最后总会变成另一版乱草稿。"),
        ("So I stop guessing and protect the posting window.", "所以我停止瞎猜，也保住发布时间。"),
        ("Now I open Moras.", "现在我会先打开 Moras。"),
        ("I choose the product I want to promote.", "我选择自己想推广的商品。"),
        ("Then I hit Generate.", "然后我点击 Generate。"),
        ("Moras makes the video for that product.", "Moras 会为这个商品做出视频。"),
        ("The commerce path is visible so the shopper has a next step.", "它会展示带货路径，让买家有下一步动作。"),
        ("I watch it like a real shopper would.", "我会像真实买家一样看一遍。"),
        ("I check the copy before I post.", "发布前，我还会检查文案。"),
        ("That gives me another video I can actually post.", "这样我又多了一条真正能发布的视频。"),
        ("Then I can put effort where earning can happen.", "然后我把精力放到真的可能赚钱的地方。"),
    ),
    (
        ("My draft folder was full of products I never explained well.", "我的草稿箱里全是没讲清楚的商品。"),
        ("I kept filming, deleting, and calling it research.", "我一直拍、一直删，还骗自己这是调研。"),
        ("That is how one product steals the whole afternoon.", "一个商品就这样偷走整个下午。"),
        ("So I stop starting from a blank phone screen.", "所以我不再从空白手机屏幕开始。"),
        ("I open Moras before I talk myself out of it.", "我会先打开 Moras，不给自己拖延机会。"),
        ("I choose the product that needs a clearer angle.", "我选择那个需要更清楚角度的商品。"),
        ("Then I tap Create video.", "然后我点击 Create video。"),
        ("Moras builds the first video path around that product.", "Moras 会围绕那个商品做出第一条视频路径。"),
        ("It shows the cart step so the viewer has somewhere to go.", "它会展示带货路径步骤，让观众知道下一步。"),
        ("I read the hook like a shopper would hear it.", "我会像买家一样听那个开头。"),
        ("I check the result before I post anything.", "发布任何内容前，我先检查结果。"),
        ("That gives me one more video to post today.", "这让我今天还能多发一条视频。"),
        ("Then the next product decision feels less random.", "然后下一个商品决定就没那么随机。"),
    ),
    (
        ("The commission looked good, but I still had no angle.", "佣金看起来不错，但我还是没有角度。"),
        ("That used to make me guess first and post later.", "以前这会让我先瞎猜，后面才发布。"),
        ("Then one bad product would eat my filming window.", "结果一个不合适的商品就吃掉拍摄时间。"),
        ("Now I move faster before the posting window disappears.", "现在我会在发布窗口消失前更快行动。"),
        ("I open Moras and choose one product to promote.", "我打开 Moras，选择一个商品来推广。"),
        ("I look for the part a real buyer would question.", "我先看真实买家可能会问的部分。"),
        ("Then I hit Generate.", "然后我点击 Generate。"),
        ("Moras makes a video path for that exact product.", "Moras 会为那个具体商品做出视频路径。"),
        ("The cart step is visible, but I still check the story.", "带货路径步骤可见，但我还是会检查故事。"),
        ("I watch the draft like someone scrolling at night.", "我会像晚上刷视频的人一样看草稿。"),
        ("I fix the weak line before I post.", "发布前，我先改掉弱的那句。"),
        ("That gives me a cleaner post without guessing all day.", "这样我不用猜一整天，也能发得更清楚。"),
        ("Then I can chase the products that can actually earn.", "然后我能追那些真的可能赚钱的商品。"),
    ),
)
SCRIPT_TEXT_FIELDS = (
    "script_title",
    "target_audience",
    "persona",
    "template",
    "core_pain",
    "emotional_angle",
    "hook",
    "visual",
    "sound_effect",
    "proof_insert",
    "cta",
    "compliance_note",
    "version",
)
PRODUCTION_ASSET_FALLBACK_CATEGORIES = {
    "real_moras_screen_recording": "workflow_screen_recording",
    "moras_product_workflow": "workflow_screen_recording",
    "real_moras_screenshot": "approved_feature_screenshot",
}
PRODUCTION_ASSET_LAYER_ALIASES = {
    "base": "base_track",
    "base layer": "base_track",
    "base_track": "base_track",
    "cutaway": "cutaway",
    "cutaway_track": "cutaway",
    "overlay": "overlay",
    "overlay_track": "overlay",
    "top layer": "overlay",
    "top_layer": "overlay",
    "foreground": "overlay",
    "audio_track": "audio",
    "sound": "audio",
}
PERSONA_GENERATION_MAX_ATTEMPTS = 3
PERSONA_LIFESTYLE_MARKER_PATTERNS: tuple[tuple[str, str], ...] = (
    ("mechanical keyboards", r"\bmechanical keyboards?\b"),
    ("bullet journaling", r"\bbullet\s+journal(?:ing)?\b"),
    ("espresso brewing", r"\bespresso\b"),
)
MOCK_PERSONA_LIFESTYLE_VARIANTS: tuple[dict[str, list[str]], ...] = (
    {
        "role": ["Part-time thrift-find creator promoting small product angles", "兼职二手好物达人，推广小商品内容角度"],
        "creator_background": ["Runs a small weekend resale page after a weekday service job, sharing low-budget product posts and practical creator routines.", "工作日做服务业岗位，周末运营小型二手转售账号，分享低预算商品发布和实用创作流程。"],
        "hobbies_interests": ["thrift sourcing", "weekend market walks", "phone photography"],
        "hobbies_interests_zh": ["二手淘货", "周末市集散步", "手机摄影"],
        "props": ["canvas tote", "price-tag stickers", "well-used smartphone"],
        "props_zh": ["帆布托特包", "价格标签贴纸", "常用智能手机"],
    },
    {
        "role": ["Home-kitchen micro creator promoting family-friendly product demos", "家庭厨房微型达人，推广适合家庭场景的产品演示"],
        "creator_background": ["Creates short videos around home routines between caregiving and part-time work, focusing on simple products she can explain clearly at home.", "在照顾家庭和兼职工作之间拍摄居家流程短视频，重点讲清楚适合家庭场景的小产品。"],
        "hobbies_interests": ["home cooking demos", "school-run planning", "coupon clipping"],
        "hobbies_interests_zh": ["家常菜演示", "接送安排规划", "优惠券整理"],
        "props": ["recipe notebook", "mini tripod", "kitchen timer"],
        "props_zh": ["食谱笔记本", "迷你三脚架", "厨房计时器"],
    },
    {
        "role": ["Small fashion-and-dance creator learning TikTok Shop product posting", "正在学习 TikTok Shop 商品发布的小型穿搭舞蹈达人"],
        "creator_background": ["Posts outfit and dance clips after classes or shifts, then experiments with affordable accessories and creator-shop formats.", "在上课或轮班后发布穿搭和舞蹈短视频，并尝试用平价配饰做创作者带货内容。"],
        "hobbies_interests": ["dance practice", "mall-window trend spotting", "budget outfit styling"],
        "hobbies_interests_zh": ["舞蹈练习", "商场橱窗趋势观察", "低预算穿搭搭配"],
        "props": ["wireless earbuds", "foldable ring light", "fabric swatches"],
        "props_zh": ["无线耳机", "折叠补光灯", "布料小样"],
    },
    {
        "role": ["Neighborhood plant-and-home creator packing small creator-shop orders", "社区植物家居达人，兼职打包小型创作者店铺订单"],
        "creator_background": ["Started as a hobby plant account and slowly added small home products, learning creator commerce through weekend order packing.", "从兴趣植物账号起步，逐渐加入小型家居产品，通过周末打包订单学习创作者电商。"],
        "hobbies_interests": ["plant care", "community swap meets", "packing small orders"],
        "hobbies_interests_zh": ["植物养护", "社区交换市集", "小订单打包"],
        "props": ["watering can", "parcel scale", "recycled mailers"],
        "props_zh": ["浇水壶", "包裹电子秤", "回收快递袋"],
    },
    {
        "role": ["Budget travel micro creator turning local shop finds into product posts", "预算旅行微型达人，把本地小店发现转成商品发布内容"],
        "creator_background": ["Shares local errands, snacks, and affordable travel finds, using short videos to explain which small discoveries deserve a shop link.", "分享本地出行、街边小吃和平价旅行发现，用短视频讲清楚哪些小发现值得挂商品链接。"],
        "hobbies_interests": ["budget travel planning", "street snack reviews", "local shop chats"],
        "hobbies_interests_zh": ["低预算旅行规划", "街边小吃测评", "本地小店闲聊"],
        "props": ["crossbody bag", "metro card", "compact camera"],
        "props_zh": ["斜挎包", "地铁卡", "便携相机"],
    },
    {
        "role": ["Handmade-market hobby creator using simple creator-commerce workflows", "手作市集兴趣达人，使用简单创作者电商流程"],
        "creator_background": ["Makes casual craft-fair and handmade-product posts, then experiments with labels, bundles, and beginner-friendly product demos.", "日常发布手作市集和手工产品内容，并尝试标签、组合套装和新手友好的产品演示。"],
        "hobbies_interests": ["craft fair browsing", "handmade label design", "phone note checklists"],
        "hobbies_interests_zh": ["逛手作市集", "手工标签设计", "手机备忘录清单"],
        "props": ["sticker labels", "gel pens", "product notes"],
        "props_zh": ["贴纸标签", "中性笔", "商品便签"],
    },
)
LOCALIZED_LANGUAGE_KEY = "zh"
LOCALIZED_OBJECT_FIELDS = {
    "topic_plan": [
        "title",
        "target_audience",
        "content_angle",
        "trend_source",
        "template",
        "persona",
        "hook_candidates",
        "cta_candidates",
        "recommended_platform",
    ],
    "script": [
        "script_title",
        "target_audience",
        "persona",
        "template",
        "core_pain",
        "emotional_angle",
        "hook",
        "voiceover",
        "visual",
        "overlay",
        "sound_effect",
        "proof_insert",
        "cta",
        "compliance_note",
    ],
    "storyboard": [
        "duration",
        "camera",
        "character_action",
        "facial_expression",
        "background",
        "props",
        "voiceover",
        "overlay",
        "sound",
        "bgm",
        "sound_effects",
        "subtitle_logic",
        "visual_elements",
        "visual_element_logic",
        "transition",
        "purpose",
    ],
    "creator_persona": [
        "display_name",
        "persona_type",
        "role_task",
        "audience_callout",
        "proof_policy",
        "recurring_scenes",
        "content_pillars",
        "role",
        "demographic",
        "creator_background",
        "personality",
        "trust_stance",
        "speech_style",
        "hobbies_interests",
        "appearance",
        "face_hair_makeup",
        "wardrobe",
        "styling_details",
        "distinctive_marks_or_tattoos",
        "props",
        "consistency_rules",
        "veo_identity_string",
        "reference_image_prompt",
        "digital_human_prompt_assets",
    ],
    "video_prompt": [
        "prompt_title",
        "target_model",
        "veo_model_id",
        "veo_generation_mode",
        "character_lock",
        "scene_lock",
        "generation_prompt",
        "overlay_exclusion_note",
        "consistency_notes",
    ],
    "video_prompt_segments": [
        "veo_prompt",
    ],
    "production_asset_plan": [
        "narrative_phase",
        "usage_reason",
        "editor_note",
    ],
}
VEO_PROMPT_FORBIDDEN_TERMS = [
    "overlay",
    "screen recording",
    "screenshot",
    "user interface",
    "subtitle",
    "caption",
    "typography",
    "ui label",
    "written words",
    "call-to-action",
    "cta",
    "字幕",
    "录屏",
    "截图",
    "界面",
    "文字",
    "标语",
    "界面文案",
]
EXACT_CHINESE_LOCALIZATIONS = {
    "Skeptical Creator Workflow Shift": "怀疑型创作者工作流转变",
    "Car POV Product-to-Video Hack": "车内 POV 商品到视频脚本",
    "Busy Creator Time Saver": "忙碌创作者省时脚本",
    "Faceless Creator": "非出镜创作者",
    "Skeptical Workflow Teardown": "怀疑型工作流拆解",
    "Skeptical review turning into a genuine workflow recommendation based on time saved.": "从怀疑评测转向基于省时效果的真实工作流推荐。",
    "Beginner KOC / Professional but skeptical tech/marketing reviewer in a modern home office": "新手 KOC / 在现代居家办公室里的专业但持怀疑态度的科技或营销评测者",
    "Secret / Exposed": "秘密 / 揭示",
    "Skeptical creator hook": "怀疑型创作者钩子",
    "Dashboard reveal structure": "仪表盘揭示结构",
    "Doubt turning into pleasant surprise and relief.": "从怀疑转为惊喜和放松。",
    "Wasting hours writing scripts and editing videos with no guarantee they will perform.": "花大量时间写脚本和剪视频，却不能确定内容会有效。",
    "TikTok": "TikTok",
    "Scale Content Without Writing": "不用从零写稿，也能规模化内容",
    "Find Your Edge with Moras": "用 Moras 找到你的优势",
    "The Blank Page Solution": "空白页解决方案",
    "Workflow Efficiency & Trial-and-Error Reduction": "工作流提效与减少试错",
    "Product-to-Video Workflow": "商品视频工作流",
    "Product Picking / Workflow": "选品 / 工作流",
    "Product Picking": "选品",
    "Workflow": "工作流",
    "Beginner Trap": "新手陷阱",
    "Beginner KOC": "新手 KOC",
    "Lazy-but-Ambitious Creators": "想偷懒但有野心的创作者",
    "Tech Reviewer": "科技评测者",
    "Professional Operations": "专业运营人设",
    "Hook": "开头钩子",
    "Solution / Proof": "解决方案 / 证明",
    "CTA / Resolution": "行动引导 / 收束",
    "Comment 'WORKFLOW' for access.": "评论「WORKFLOW」获取入口。",
    "No income or sales guarantees.": "不承诺收入或销量。",
}
PHRASE_CHINESE_LOCALIZATIONS = [
    ("Moras AI agent", "Moras AI 智能体"),
    ("Moras workflow", "Moras 工作流"),
    ("screen recording", "录屏"),
    ("product-selection-to-commerce-path-video", "选品到带货路径视频"),
    ("before/after", "前后对比"),
    ("commerce-path video outputs", "带货路径视频输出"),
    ("video drafts", "视频草稿"),
    ("video outputs", "视频输出"),
    ("content creation", "内容创作"),
    ("product data", "商品数据"),
    ("from zero", "从零开始"),
    ("trial and error", "试错"),
    ("workflow speed", "工作流提速"),
    ("workflow", "工作流"),
    ("voiceover", "口播"),
    ("visual", "画面"),
    ("hook", "钩子"),
    ("creator", "创作者"),
    ("script", "脚本"),
    ("video", "视频"),
]
SCRIPT_GENERATION_QUEUE_LOCK = threading.Lock()
PERSONA_GENERATION_QUEUE_LOCK = threading.Lock()
MAX_SCRIPT_PROMPT_SOURCE_RECORDS = 1
MAX_EXISTING_SCRIPT_SIGNATURES_FOR_PROMPT = 8
SCRIPT_AGENT_GENERATION_MAX_ATTEMPTS = 3
VOICEOVER_EXPERT_MAX_ATTEMPTS = 2
SCRIPT_AGENT_RETRYABLE_OUTPUT_ERROR_PATTERNS = (
    "banned claims found in script output",
    "off-brand Script Agent copy",
    "Moras recommendation",
    "Moras as the hero",
    "negative failure metrics",
    "generic attention cue",
    "attention-first",
    "contrarian",
    "distinct script titles",
    "distinct selected hooks",
    "opening voiceover signatures",
    "UGC voiceover must mention Moras",
    "UGC voiceover must not overuse Moras",
    "UGC voiceover lines must stay short",
    "short spoken lines so short sentences do not remove content",
    "UGC voiceover is too short",
    "long product-pitch sentences",
    "split rows longer",
    "voiceover needs about",
    "short voiceover only supports",
    "visual_elements must change by shot",
    "localized.zh",
    "SCRIPT_OUTPUT_SCHEMA_INVALID",
)


class ScriptAgentService:
    def __init__(self, repo: BreakdownRepository | None = None) -> None:
        self.repo = repo or BreakdownRepository()

    def start_generation_job(self, job_id: str) -> None:
        worker = threading.Thread(
            target=self._run_generation_job_thread,
            args=(job_id,),
            daemon=True,
            name=f"script-generation-{job_id[:8]}",
        )
        worker.start()

    def _run_generation_job_thread(self, job_id: str) -> None:
        asyncio.run(self.run_generation_job(job_id))

    async def generate_scripts(self, request: ScriptGenerationRequest) -> list[ScriptRecord]:
        return await self._generate_script_records(request, generation_job_id=None)

    async def generate_creator_personas(self, request: PersonaGenerationRequest) -> list[CreatorPersonaRecord]:
        return await self._generate_creator_persona_records(request, persona_generation_job_id=None)

    def start_persona_generation_job(self, job_id: str) -> None:
        worker = threading.Thread(
            target=self._run_persona_generation_job_thread,
            args=(job_id,),
            daemon=True,
            name=f"persona-generation-{job_id[:8]}",
        )
        worker.start()

    def _run_persona_generation_job_thread(self, job_id: str) -> None:
        asyncio.run(self.run_persona_generation_job(job_id))

    async def run_persona_generation_job(self, job_id: str) -> None:
        with PERSONA_GENERATION_QUEUE_LOCK:
            job = self.repo.get_persona_generation_job(job_id)
            if job.status not in {PersonaGenerationJobStatus.QUEUED, PersonaGenerationJobStatus.GENERATING}:
                return
            request = PersonaGenerationRequest(
                persona_count=job.persona_count,
                topic_or_brand_context=job.topic_or_brand_context,
                target_audience=job.target_audience,
                required_demographic=job.required_demographic,
            )
            self.repo.mark_persona_generation_job(job_id, PersonaGenerationJobStatus.GENERATING)
            try:
                created = await self._generate_creator_persona_records(request, persona_generation_job_id=job_id)
                self.repo.finish_persona_generation_job(
                    job_id,
                    status=PersonaGenerationJobStatus.SUCCEEDED,
                    persona_ids=[persona.id for persona in created],
                )
            except Exception as exc:
                self.repo.finish_persona_generation_job(
                    job_id,
                    status=PersonaGenerationJobStatus.FAILED,
                    error_message=error_message(exc),
                )

    def create_persona_generation_job(self, request: PersonaGenerationRequest) -> PersonaGenerationJobRecord:
        job = self.repo.create_persona_generation_job(request)
        self.start_persona_generation_job(job.id)
        return job

    def retry_persona_generation_job(self, job_id: str) -> PersonaGenerationJobRecord:
        job = self.repo.get_persona_generation_job(job_id)
        if job.status != PersonaGenerationJobStatus.FAILED:
            raise conflict("PERSONA_GENERATION_JOB_NOT_FAILED", "Only failed persona generation jobs can be retried")
        request = PersonaGenerationRequest(
            persona_count=job.persona_count,
            topic_or_brand_context=job.topic_or_brand_context,
            target_audience=job.target_audience,
            required_demographic=job.required_demographic,
        )
        retry_job = self.repo.create_persona_generation_job(request)
        self.repo.delete_persona_generation_job(job_id)
        self.start_persona_generation_job(retry_job.id)
        return retry_job

    async def _generate_creator_persona_records(
        self,
        request: PersonaGenerationRequest,
        persona_generation_job_id: str | None,
    ) -> list[CreatorPersonaRecord]:
        existing_personas = [record.creator_persona for record in self.repo.list_creator_personas()]
        existing_personas.extend(script.creator_persona for script in self.repo.list_scripts() if script.creator_persona)
        existing_names = {persona_display_name(persona) for persona in existing_personas}
        used_names = {name for name in existing_names if name}
        used_lifestyle_markers = set()
        used_interest_values = set()
        for persona in existing_personas:
            used_lifestyle_markers.update(persona_lifestyle_markers(persona))
            used_interest_values.update(persona_interest_values(persona))
        existing_signatures = persona_diversity_signatures(existing_personas)
        settings = get_settings()
        single_persona_request = request.model_copy(update={"persona_count": 1})
        initial_prompt = build_persona_prompt(
            single_persona_request,
            sorted(used_names),
            existing_signatures,
            batch_target_count=request.persona_count,
            batch_position=1,
        )
        model_name = "mock-persona-agent-v1" if settings.provider == "mock" else settings.gemini_persona_model
        model_run_id = self.repo.create_script_model_run(
            script_id=None,
            status="running",
            model_name=model_name,
            prompt_version=PERSONA_PROMPT_VERSION,
            request={
                "persona_count": request.persona_count,
                "persona_generation_mode": "sequential_single_persona_calls",
                "topic_or_brand_context": request.topic_or_brand_context,
                "target_audience": request.target_audience,
                "required_demographic": request.required_demographic,
                "persona_generation_job_id": persona_generation_job_id,
                "existing_names": sorted(used_names),
                "existing_persona_signatures": existing_signatures,
                "per_call_prompt_chars": len(initial_prompt),
            },
        )
        raw_text: str | None = None
        created_records: list[CreatorPersonaRecord] = []
        pending_personas: list[dict[str, Any]] = []

        def persist_persona(persona: dict[str, Any], provider: str, current_model_name: str) -> None:
            if persona_generation_job_id:
                created = self.repo.create_creator_persona_records(
                    personas=[persona],
                    provider=provider,
                    model_name=current_model_name,
                )
                created_records.append(created[0])
                self.repo.update_persona_generation_job_progress(
                    persona_generation_job_id,
                    persona_ids=[record.id for record in created_records],
                )
                return
            pending_personas.append(persona)

        try:
            if settings.provider == "mock":
                raw_responses = []
                for index in range(request.persona_count):
                    persona = build_mock_personas(
                        single_persona_request,
                        used_names,
                        offset=index,
                    )[0]
                    ensure_persona_lifestyle_is_fresh(persona, used_lifestyle_markers, used_interest_values)
                    persist_persona(persona, "mock", model_name)
                    name = persona_display_name(persona)
                    if name:
                        used_names.add(name)
                    used_lifestyle_markers.update(persona_lifestyle_markers(persona))
                    used_interest_values.update(persona_interest_values(persona))
                    existing_signatures.append(persona_diversity_signature(persona))
                    raw_responses.append({"call_index": index + 1, "personas": [persona]})
                raw_text = json.dumps({"sequential_responses": raw_responses}, ensure_ascii=False)
                provider = "mock"
            else:
                raw_responses = []
                for index in range(request.persona_count):
                    rejection_notes: list[str] = []
                    persona = None
                    last_rejection = ""
                    for attempt in range(PERSONA_GENERATION_MAX_ATTEMPTS):
                        prompt = build_persona_prompt(
                            single_persona_request,
                            sorted(used_names),
                            existing_signatures,
                            batch_target_count=request.persona_count,
                            batch_position=index + 1,
                            rejected_lifestyle_notes=rejection_notes,
                        )
                        result = await generate_gemini_text(prompt, settings.gemini_persona_model)
                        raw_response = {
                            "call_index": index + 1,
                            "attempt": attempt + 1,
                            "raw_response_text": result.text,
                        }
                        try:
                            parsed_personas = parse_persona_agent_batch(result.text, single_persona_request, used_names)
                        except Exception as exc:
                            last_rejection = error_message(exc)
                            raw_response["rejected_reason"] = last_rejection
                            raw_responses.append(raw_response)
                            rejection_notes.append(
                                "Previous attempt failed schema validation. Return a complete persona with detailed visual fields and a reference_image_prompt that explicitly includes portrait or three-quarter reference, wardrobe, realistic or high fidelity style, face, hair, skin, eyes, and natural light."
                            )
                            continue
                        candidate = parsed_personas[0]
                        try:
                            ensure_persona_lifestyle_is_fresh(candidate, used_lifestyle_markers, used_interest_values)
                        except PersonaLifestyleRepeatError as exc:
                            last_rejection = str(exc)
                            raw_response["rejected_reason"] = str(exc)
                            raw_responses.append(raw_response)
                            rejection_notes.append(str(exc))
                            continue
                        raw_responses.append(raw_response)
                        persona = candidate
                        model_name = result.model_name
                        break
                    if persona is None:
                        raise unprocessable(
                            "PERSONA_AGENT_RETRY_EXHAUSTED",
                            f"Persona Agent failed after retries: {last_rejection or 'unknown rejection'}",
                        )
                    persist_persona(persona, "gemini", model_name)
                    name = persona_display_name(persona)
                    if name:
                        used_names.add(name)
                    used_lifestyle_markers.update(persona_lifestyle_markers(persona))
                    used_interest_values.update(persona_interest_values(persona))
                    existing_signatures.append(persona_diversity_signature(persona))
                raw_text = json.dumps({"sequential_responses": raw_responses}, ensure_ascii=False)
                provider = "gemini"
            if not persona_generation_job_id:
                created_records = self.repo.create_creator_persona_records(
                    personas=pending_personas,
                    provider=provider,
                    model_name=model_name,
                )
            self.repo.finish_script_model_run(
                model_run_id,
                "succeeded",
                raw_response_text=raw_text,
                parsed_output={"personas": [record.creator_persona for record in created_records]},
            )
            return created_records
        except Exception as exc:
            message = error_message(exc)
            self.repo.finish_script_model_run(model_run_id, "failed", raw_response_text=raw_text, error_message=message)
            raise unprocessable("PERSONA_AGENT_FAILED", message) from exc

    def edit_creator_persona(self, record_id: str, request: PersonaEditRequest) -> CreatorPersonaRecord:
        record = self.repo.get_creator_persona(record_id)
        persona = apply_creator_persona_instruction(record.creator_persona, request.instruction)
        return self.repo.update_creator_persona(
            record_id,
            creator_persona=persona,
            provider="local",
            model_name="moras-persona-library-v1",
        )

    async def run_generation_job(self, job_id: str) -> None:
        with SCRIPT_GENERATION_QUEUE_LOCK:
            job = self.repo.get_script_generation_job(job_id)
            if job.status not in {ScriptGenerationJobStatus.QUEUED, ScriptGenerationJobStatus.GENERATING}:
                return
            request = ScriptGenerationRequest(
                script_count=job.script_count,
                script_type=job.script_type,
                source_breakdown_ids=job.source_breakdown_ids,
                persona_id=job.persona_id,
                persona_hint=job.persona_hint,
            )
            request = self.resolve_script_generation_request(request)
            self.repo.mark_script_generation_job(job_id, ScriptGenerationJobStatus.GENERATING)
            try:
                created = await self._generate_script_records(request, generation_job_id=job_id)
                self.repo.finish_script_generation_job(
                    job_id,
                    status=ScriptGenerationJobStatus.SUCCEEDED,
                    script_ids=[script.id for script in created],
                )
            except Exception as exc:
                latest_job = self.repo.get_script_generation_job(job_id)
                self.repo.finish_script_generation_job(
                    job_id,
                    status=ScriptGenerationJobStatus.FAILED,
                    script_ids=[str(script_id) for script_id in latest_job.script_ids],
                    error_message=error_message(exc),
                )

    def retry_generation_job(self, job_id: str) -> ScriptGenerationJobRecord:
        job = self.repo.get_script_generation_job(job_id)
        if job.status != ScriptGenerationJobStatus.FAILED:
            raise conflict("SCRIPT_GENERATION_JOB_NOT_FAILED", "Only failed script generation jobs can be retried")
        request = ScriptGenerationRequest(
            script_count=job.script_count,
            script_type=job.script_type,
            source_breakdown_ids=[str(item) for item in job.source_breakdown_ids],
            persona_id=job.persona_id,
            persona_hint=job.persona_hint,
        )
        request = self.resolve_script_generation_request(request)
        retry_job = self.repo.create_script_generation_job(request)
        self.repo.delete_script_generation_job(job_id)
        self.start_generation_job(retry_job.id)
        return retry_job

    async def _generate_script_records(
        self,
        request: ScriptGenerationRequest,
        generation_job_id: str | None,
    ) -> list[ScriptRecord]:
        settings = get_settings()
        request = self.resolve_script_generation_request(request)
        selected_persona = normalized_selected_creator_persona(request)
        source_records = self._select_source_breakdowns(request.source_breakdown_ids)
        existing_script_signatures = [
            compact_script_signature(record)
            for record in self.repo.list_scripts()[:MAX_EXISTING_SCRIPT_SIGNATURES_FOR_PROMPT]
        ]
        if settings.provider == "mock":
            prompt = build_script_prompt(request, source_records, existing_script_signatures)
            model_run_id = self.repo.create_script_model_run(
                script_id=None,
                status="running",
                model_name=self._model_name(),
                prompt_version=PROMPT_VERSION,
                request={
                    "script_count": request.script_count,
                    "script_type": request.script_type,
                    "source_breakdown_ids": [record.id for record in source_records],
                    "persona_id": request.persona_id,
                    "persona_hint": compact_persona_for_prompt(request.persona_hint),
                    "generation_job_id": generation_job_id,
                    "prompt_chars": len(prompt),
                },
            )
            raw_text: str | None = None
            try:
                batch = build_mock_script_batch(request, source_records)
                raw_text = batch.model_dump_json()
                model_name = "mock-script-agent-v1"
                provider = "mock"
                if len(batch.scripts) > request.script_count:
                    batch.scripts = batch.scripts[: request.script_count]
                created: list[ScriptRecord] = []
                for item in batch.scripts:
                    record = self.repo.create_script_records(
                        items=[item],
                        provider=provider,
                        model_name=model_name,
                        script_type=request.script_type,
                        allow_duplicate_persona=bool(compact_persona_for_prompt(request.persona_hint)),
                        preserve_creator_persona=bool(selected_persona),
                    )[0]
                    created.append(record)
                    if request.persona_id:
                        self.repo.attach_creator_persona_scripts(request.persona_id, [record.id])
                    if generation_job_id:
                        self.repo.update_script_generation_job_progress(generation_job_id, [script.id for script in created])
                self.repo.finish_script_model_run(
                    model_run_id,
                    "succeeded",
                    raw_response_text=raw_text,
                    parsed_output=batch.model_dump(mode="json"),
                )
                return created
            except Exception as exc:
                message = error_message(exc)
                self.repo.finish_script_model_run(model_run_id, "failed", raw_response_text=raw_text, error_message=message)
                raise unprocessable("SCRIPT_AGENT_FAILED", message) from exc
        try:
            created: list[ScriptRecord] = []

            def persist_generated_script(item: ScriptAgentItem, model_name: str) -> None:
                record = self.repo.create_script_records(
                    items=[item],
                    provider="gemini",
                    model_name=model_name,
                    script_type=request.script_type,
                    allow_duplicate_persona=bool(compact_persona_for_prompt(request.persona_hint)),
                    preserve_creator_persona=bool(selected_persona),
                )[0]
                created.append(record)
                if request.persona_id:
                    self.repo.attach_creator_persona_scripts(request.persona_id, [record.id])
                if generation_job_id:
                    self.repo.update_script_generation_job_progress(generation_job_id, [script.id for script in created])

            batch, model_name = await self._generate_gemini_script_batch(
                request,
                source_records,
                existing_script_signatures,
                selected_persona,
                generation_job_id,
                persist_generated_script if generation_job_id else None,
            )
            provider = "gemini"
            if len(batch.scripts) > request.script_count:
                batch.scripts = batch.scripts[: request.script_count]
            if generation_job_id:
                return created
            created = self.repo.create_script_records(
                items=batch.scripts,
                provider=provider,
                model_name=model_name,
                script_type=request.script_type,
                allow_duplicate_persona=bool(compact_persona_for_prompt(request.persona_hint)),
                preserve_creator_persona=bool(selected_persona),
            )
            if request.persona_id:
                self.repo.attach_creator_persona_scripts(request.persona_id, [script.id for script in created])
            return created
        except Exception as exc:
            message = error_message(exc)
            raise unprocessable("SCRIPT_AGENT_FAILED", message) from exc

    async def _generate_gemini_script_batch(
        self,
        request: ScriptGenerationRequest,
        source_records: list[Any],
        existing_script_signatures: list[dict[str, Any]],
        selected_persona: dict[str, Any] | None,
        generation_job_id: str | None,
        on_script_item: Callable[[ScriptAgentItem, str], None] | None = None,
    ) -> tuple[ScriptAgentBatch, str]:
        settings = get_settings()
        source_ids = [record.id for record in source_records]
        signatures = list(existing_script_signatures)
        scripts: list[ScriptAgentItem] = []
        model_name = settings.gemini_script_model
        for index in range(request.script_count):
            single_request = request.model_copy(update={"script_count": 1})
            voiceover_seed = await self._generate_script_voiceover_seed_with_gemini(
                request,
                source_records,
                signatures,
                source_ids,
                generation_job_id,
                batch_index=index + 1,
                batch_target_count=request.script_count,
            )
            rejection_notes: list[str] = []
            for attempt in range(1, SCRIPT_AGENT_GENERATION_MAX_ATTEMPTS + 1):
                prompt = build_script_prompt(
                    single_request,
                    source_records,
                    signatures,
                    rejection_notes=rejection_notes,
                    pre_generated_voiceover=voiceover_seed,
                )
                model_run_id = self.repo.create_script_model_run(
                    script_id=None,
                    status="running",
                    model_name=settings.gemini_script_model,
                    prompt_version=PROMPT_VERSION,
                    request={
                        "script_count": 1,
                        "script_type": request.script_type,
                        "source_breakdown_ids": source_ids,
                        "persona_id": request.persona_id,
                        "persona_hint": compact_persona_for_prompt(request.persona_hint),
                        "generation_job_id": generation_job_id,
                        "generation_mode": "sequential_single_script_calls",
                        "batch_index": index + 1,
                        "batch_target_count": request.script_count,
                        "attempt": attempt,
                        "rejected_script_output_notes": list(rejection_notes),
                        "prompt_chars": len(prompt),
                    },
                )
                raw_text: str | None = None
                try:
                    result = await generate_gemini_text(prompt, settings.gemini_script_model)
                    raw_text = result.text
                    parsed = parse_script_agent_batch(raw_text, source_ids, selected_persona=selected_persona)
                    item = parsed.scripts[0]
                    item = apply_pre_generated_voiceover_seed(
                        item,
                        voiceover_seed,
                        source_ids,
                        selected_persona=selected_persona,
                    )
                    item = await self._review_script_voiceover_fit_with_gemini(
                        item,
                        request,
                        source_ids,
                        selected_persona,
                        generation_job_id,
                        batch_index=index + 1,
                        batch_target_count=request.script_count,
                        generation_attempt=attempt,
                        parent_model_run_id=model_run_id,
                    )
                    ScriptAgentBatch(scripts=[*scripts, item])
                    scripts.append(item)
                    signatures.append(compact_script_item_signature(item))
                    model_name = result.model_name
                    self.repo.finish_script_model_run(
                        model_run_id,
                        "succeeded",
                        raw_response_text=raw_text,
                        parsed_output={"scripts": [item.model_dump(mode="json")]},
                    )
                    if on_script_item:
                        on_script_item(item, model_name)
                    break
                except Exception as exc:
                    message = error_message(exc)
                    self.repo.finish_script_model_run(
                        model_run_id,
                        "failed",
                        raw_response_text=raw_text,
                        error_message=message,
                    )
                    if attempt < SCRIPT_AGENT_GENERATION_MAX_ATTEMPTS and is_retryable_script_agent_output_error(message):
                        rejection_notes.append(script_agent_rejection_note(message))
                        continue
                    raise
            else:
                raise RuntimeError("Script Agent exhausted generation attempts without a terminal result.")
        return ScriptAgentBatch(scripts=scripts), model_name

    async def _generate_script_voiceover_seed_with_gemini(
        self,
        request: ScriptGenerationRequest,
        source_records: list[Any],
        existing_script_signatures: list[dict[str, Any]],
        source_ids: list[str],
        generation_job_id: str | None,
        *,
        batch_index: int,
        batch_target_count: int,
    ) -> dict[str, Any]:
        settings = get_settings()
        rejection_notes: list[str] = []
        for attempt in range(1, VOICEOVER_EXPERT_MAX_ATTEMPTS + 1):
            prompt = build_script_voiceover_expert_prompt(
                "PRE_GENERATION",
                request=request,
                source_records=source_records,
                existing_script_signatures=existing_script_signatures,
                rejection_notes=rejection_notes,
                batch_index=batch_index,
                batch_target_count=batch_target_count,
            )
            model_run_id = self.repo.create_script_model_run(
                script_id=None,
                status="running",
                model_name=settings.gemini_script_voiceover_model,
                prompt_version=VOICEOVER_EXPERT_PROMPT_VERSION,
                request={
                    "script_count": 1,
                    "script_type": request.script_type,
                    "source_breakdown_ids": source_ids,
                    "persona_id": request.persona_id,
                    "persona_hint": compact_persona_for_prompt(request.persona_hint),
                    "generation_job_id": generation_job_id,
                    "generation_mode": "voiceover_pre_generation",
                    "batch_index": batch_index,
                    "batch_target_count": batch_target_count,
                    "attempt": attempt,
                    "rejected_voiceover_notes": list(rejection_notes),
                    "prompt_chars": len(prompt),
                },
            )
            raw_text: str | None = None
            try:
                result = await generate_gemini_text(prompt, settings.gemini_script_voiceover_model)
                raw_text = result.text
                seed = parse_script_voiceover_seed(raw_text)
                self.repo.finish_script_model_run(
                    model_run_id,
                    "succeeded",
                    raw_response_text=raw_text,
                    parsed_output={"voiceover_seed": seed},
                )
                return seed
            except Exception as exc:
                message = error_message(exc)
                self.repo.finish_script_model_run(
                    model_run_id,
                    "failed",
                    raw_response_text=raw_text,
                    error_message=message,
                )
                if attempt < VOICEOVER_EXPERT_MAX_ATTEMPTS:
                    rejection_notes.append(compact_text(message, 700))
                    continue
                raise
        raise RuntimeError("Voiceover Expert exhausted pre-generation attempts without a terminal result.")

    async def _review_script_voiceover_fit_with_gemini(
        self,
        item: ScriptAgentItem,
        request: ScriptGenerationRequest,
        source_ids: list[str],
        selected_persona: dict[str, Any] | None,
        generation_job_id: str | None,
        *,
        batch_index: int,
        batch_target_count: int,
        generation_attempt: int,
        parent_model_run_id: str,
    ) -> ScriptAgentItem:
        settings = get_settings()
        rejection_notes: list[str] = []
        for attempt in range(1, VOICEOVER_EXPERT_MAX_ATTEMPTS + 1):
            prompt = build_script_voiceover_expert_prompt(
                "POST_REVIEW",
                request=request,
                script_item=item,
                rejection_notes=rejection_notes,
                batch_index=batch_index,
                batch_target_count=batch_target_count,
            )
            model_run_id = self.repo.create_script_model_run(
                script_id=None,
                status="running",
                model_name=settings.gemini_script_voiceover_model,
                prompt_version=VOICEOVER_EXPERT_PROMPT_VERSION,
                request={
                    "script_count": 1,
                    "script_type": request.script_type,
                    "source_breakdown_ids": source_ids,
                    "persona_id": request.persona_id,
                    "persona_hint": compact_persona_for_prompt(request.persona_hint),
                    "generation_job_id": generation_job_id,
                    "generation_mode": "voiceover_post_review",
                    "parent_generation_model_run_id": parent_model_run_id,
                    "batch_index": batch_index,
                    "batch_target_count": batch_target_count,
                    "generation_attempt": generation_attempt,
                    "attempt": attempt,
                    "rejected_voiceover_notes": list(rejection_notes),
                    "prompt_chars": len(prompt),
                },
            )
            raw_text: str | None = None
            try:
                result = await generate_gemini_text(prompt, settings.gemini_script_voiceover_model)
                raw_text = result.text
                reviewed = apply_script_voiceover_review_patch(
                    item,
                    raw_text,
                    source_ids,
                    selected_persona=selected_persona,
                )
                self.repo.finish_script_model_run(
                    model_run_id,
                    "succeeded",
                    raw_response_text=raw_text,
                    parsed_output={
                        "script": {
                            "voiceover": reviewed.script.voiceover,
                            "cta": reviewed.script.cta,
                        },
                        "storyboard_voiceover": [
                            {"shot_id": shot.shot_id, "voiceover": shot.voiceover}
                            for shot in reviewed.storyboard
                        ],
                    },
                )
                return reviewed
            except Exception as exc:
                message = error_message(exc)
                self.repo.finish_script_model_run(
                    model_run_id,
                    "failed",
                    raw_response_text=raw_text,
                    error_message=message,
                )
                if attempt < VOICEOVER_EXPERT_MAX_ATTEMPTS:
                    rejection_notes.append(compact_text(message, 700))
                    continue
                return item
        return item

    async def edit_script(self, script_id: str, request: ScriptEditRequest) -> ScriptRecord:
        existing = self.repo.get_script(script_id)
        settings = get_settings()
        self.repo.mark_script_status(script_id, ScriptStatus.EDITING)
        prompt = build_edit_prompt(existing, request.instruction)
        model_run_id = self.repo.create_script_model_run(
            script_id=script_id,
            status="running",
            model_name=self._model_name(),
            prompt_version=f"{PROMPT_VERSION}_edit",
            request={
                "script_id": script_id,
                "instruction_chars": len(request.instruction),
                "prompt_chars": len(prompt),
            },
        )
        raw_text: str | None = None
        try:
            if settings.provider == "mock":
                item = build_mock_edited_script(existing, request.instruction)
                raw_text = item.model_dump_json()
            else:
                result = await generate_gemini_text(prompt, settings.gemini_script_model)
                raw_text = result.text
                item = parse_script_agent_item(
                    raw_text,
                    existing.source_breakdown_ids,
                    selected_persona=existing.creator_persona,
                )
            revision = {
                "id": f"revision_{utc_now()}",
                "instruction": request.instruction,
                "submitted_at": utc_now(),
                "previous_script": {
                    "topic_plan": existing.topic_plan,
                    "script": existing.script,
                    "storyboard": existing.storyboard,
                    "video_prompt": existing.video_prompt,
                    "production_asset_plan": existing.production_asset_plan,
                    "risk_check": existing.risk_check,
                },
            }
            updated = self.repo.replace_script_content(record_id=script_id, item=item, revision=revision)
            self.repo.finish_script_model_run(
                model_run_id,
                "succeeded",
                raw_response_text=raw_text,
                parsed_output=item.model_dump(mode="json"),
            )
            return updated
        except Exception as exc:
            message = error_message(exc)
            self.repo.mark_script_status(script_id, ScriptStatus.FAILED, message)
            self.repo.finish_script_model_run(model_run_id, "failed", raw_response_text=raw_text, error_message=message)
            raise unprocessable("SCRIPT_EDIT_FAILED", message) from exc

    def _select_source_breakdowns(self, source_breakdown_ids: list[str]):
        if source_breakdown_ids:
            return [self.repo.get(record_id) for record_id in source_breakdown_ids]
        return [
            record
            for record in self.repo.list()
            if record.status == "succeeded" and record.classification and record.decomposition
        ][:5]

    def _model_name(self) -> str:
        settings = get_settings()
        return "mock-script-agent-v1" if settings.provider == "mock" else settings.gemini_script_model

    def resolve_script_generation_request(self, request: ScriptGenerationRequest) -> ScriptGenerationRequest:
        if not request.persona_id:
            raise unprocessable("SCRIPT_PERSONA_REQUIRED", "请选择一个人设后再生成脚本。")
        selected = self._find_creator_persona_record(request.persona_id)
        if selected is None:
            raise unprocessable("SCRIPT_PERSONA_NOT_FOUND", "选中的人设不存在，请重新选择。")
        return ScriptGenerationRequest(
            script_count=request.script_count,
            script_type=request.script_type,
            source_breakdown_ids=request.source_breakdown_ids,
            persona_id=selected.id,
            persona_hint=selected.creator_persona,
        )

    def _find_creator_persona_record(self, persona_id: str) -> CreatorPersonaRecord | None:
        for record in self.repo.list_creator_personas():
            inner_id = str(record.creator_persona.get("persona_id") or record.creator_persona.get("personaId") or "")
            if persona_id in {record.id, inner_id}:
                return record
        return None


def visible_script_records(records: list[ScriptRecord], *, current_provider: str) -> list[ScriptRecord]:
    has_real_provider_scripts = any(not is_mock_script_record(record) for record in records)
    candidates = [
        record
        for record in records
        if not (current_provider != "mock" and has_real_provider_scripts and is_mock_script_record(record))
    ]
    visible: list[ScriptRecord] = []
    seen_keys: set[str] = set()
    for record in candidates:
        key = script_duplicate_key(record)
        if key and key in seen_keys:
            continue
        if key:
            seen_keys.add(key)
        visible.append(record)
    return visible


def is_mock_script_record(record: ScriptRecord) -> bool:
    return record.provider == "mock" or record.model_name.startswith("mock-")


def script_duplicate_key(record: ScriptRecord) -> str:
    title = first_present(
        record.script.get("script_title"),
        record.topic_plan.get("title"),
        nested_zh_value(record.script, "script_title"),
        nested_zh_value(record.topic_plan, "title"),
    )
    return normalize_duplicate_key(title)


def normalize_duplicate_key(value: Any) -> str:
    text = str(value or "").strip().lower()
    if not text:
        return ""
    return re.sub(r"\s+", " ", text)


def build_script_prompt(
    request: ScriptGenerationRequest,
    source_records: list[Any],
    existing_script_signatures: list[dict[str, Any]] | None = None,
    rejection_notes: list[str] | None = None,
    pre_generated_voiceover: dict[str, Any] | None = None,
) -> str:
    resident_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    loaded_skill_names = select_script_agent_skill_names(request)
    skill_pack = build_script_agent_skill_pack(loaded_skill_names)
    prompt_source_records = source_records[:MAX_SCRIPT_PROMPT_SOURCE_RECORDS]
    context = {
        "loaded_script_agent_skills": loaded_skill_names,
        "script_count": request.script_count,
        "script_type": request.script_type,
        "selected_creator_persona": compact_persona_for_prompt(request.persona_hint),
        "source_breakdowns": [compact_breakdown(record) for record in prompt_source_records],
        "omitted_source_breakdown_ids": [record.id for record in source_records[MAX_SCRIPT_PROMPT_SOURCE_RECORDS:]],
        "avoid_existing_script_signatures": existing_script_signatures or [],
        "pre_generated_vo": pre_generated_voiceover or {},
        "rejected_script_output_notes": rejection_notes or [],
        "moras_assets": default_moras_assets(),
        "omitted_modules": ["audience_insight_from_comments", "reddit", "quora", "reviews"],
    }
    voiceover_seed_instruction = ""
    if pre_generated_voiceover:
        voiceover_seed_instruction = (
            "Use the provided `pre_generated_vo` as the exact foundation for `script.hook`, `script.voiceover`, and `script.cta`. "
            "Do not alter the English lines unless a later explicit voiceover review patch changes them. "
            "Build topic_plan, storyboard visuals, video_prompt, and production_asset_plan around this spoken script "
            "so audio and visuals stay synchronized. "
        )
    return (
        f"{resident_prompt}\n\n"
        f"{skill_pack}\n\n"
        "Generate scripts from this input JSON. Use only provided teardown assets and Moras assets. "
        f"{voiceover_seed_instruction}"
        "Return JSON only.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def build_script_voiceover_expert_prompt(
    mode: str,
    *,
    request: ScriptGenerationRequest,
    source_records: list[Any] | None = None,
    existing_script_signatures: list[dict[str, Any]] | None = None,
    script_item: ScriptAgentItem | None = None,
    rejection_notes: list[str] | None = None,
    batch_index: int,
    batch_target_count: int,
) -> str:
    expert_prompt = VOICEOVER_EXPERT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    context: dict[str, Any] = {
        "mode": mode,
        "script_type": request.script_type,
        "selected_creator_persona": compact_persona_for_prompt(request.persona_hint),
        "batch_index": batch_index,
        "batch_target_count": batch_target_count,
        "rejected_voiceover_notes": rejection_notes or [],
    }
    if mode == "PRE_GENERATION":
        prompt_source_records = (source_records or [])[:MAX_SCRIPT_PROMPT_SOURCE_RECORDS]
        context.update(
            {
                "source_breakdowns": [compact_breakdown(record) for record in prompt_source_records],
                "omitted_source_breakdown_ids": [
                    record.id for record in (source_records or [])[MAX_SCRIPT_PROMPT_SOURCE_RECORDS:]
                ],
                "avoid_existing_script_signatures": existing_script_signatures or [],
                "moras_assets": default_moras_assets(),
            }
        )
        instruction = "Generate the PRE_GENERATION voiceover seed. Return JSON only."
    elif mode == "POST_REVIEW":
        if script_item is None:
            raise ValueError("script_item is required for POST_REVIEW voiceover expert prompts")
        context["script_item"] = compact_script_item_for_voiceover_review(script_item)
        instruction = "Review the complete script voiceover fit. Return the POST_REVIEW JSON only."
    else:
        raise ValueError(f"Unsupported voiceover expert mode: {mode}")
    return f"{expert_prompt}\n\n{instruction}\n\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def parse_script_voiceover_seed(raw_text: str) -> dict[str, Any]:
    try:
        data = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("VOICEOVER_SEED_NOT_JSON", f"Voiceover Expert output was not valid JSON: {exc}") from exc
    if isinstance(data, dict) and isinstance(data.get("voiceover_seed"), dict):
        data = data["voiceover_seed"]
    if not isinstance(data, dict):
        raise unprocessable("VOICEOVER_SEED_NOT_OBJECT", "Voiceover Expert output must be a JSON object")
    seed = normalize_script_voiceover_seed(data)
    validate_script_voiceover_seed(seed)
    return seed


def normalize_script_voiceover_seed(data: dict[str, Any]) -> dict[str, Any]:
    script = data.get("script") if isinstance(data.get("script"), dict) else {}
    localized_zh = data.get("localized_zh") if isinstance(data.get("localized_zh"), dict) else {}
    localized = data.get("localized") if isinstance(data.get("localized"), dict) else {}
    zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized.get(LOCALIZED_LANGUAGE_KEY), dict) else {}
    hook = str(first_present(data.get("hook"), script.get("hook")) or "").strip()
    lines = script_voiceover_lines_for_repair(
        first_present(data.get("script_voiceover"), data.get("voiceover"), script.get("voiceover"))
    )
    cta = str(first_present(data.get("cta"), script.get("cta")) or "").strip()
    hook_zh = str(
        first_present(
            localized_zh.get("hook"),
            zh.get("hook"),
        ) or ""
    ).strip()
    zh_lines = script_voiceover_lines_for_repair(
        first_present(
            localized_zh.get("script_voiceover"),
            localized_zh.get("voiceover"),
            zh.get("script_voiceover"),
            zh.get("voiceover"),
        )
    )
    cta_zh = str(first_present(localized_zh.get("cta"), zh.get("cta")) or "").strip()
    hook = repair_safe_style_text(hook)
    lines = [repair_safe_style_text(line) for line in lines if str(line).strip()]
    cta = repair_safe_style_text(cta)
    if not has_cjk(hook_zh):
        hook_zh = localize_to_chinese(hook)
    if len(zh_lines) != len(lines):
        zh_lines = [script_voiceover_repair_zh(line, index, zh_lines) for index, line in enumerate(lines)]
    if not has_cjk(cta_zh):
        cta_zh = SCRIPT_REPAIR_CTA_ZH if normalized_line_signature(cta) == normalized_line_signature(SCRIPT_REPAIR_CTA_EN) else localize_to_chinese(cta)
    return {
        "hook": hook,
        "script_voiceover": lines,
        "cta": cta,
        "localized_zh": {
            "hook": hook_zh,
            "script_voiceover": zh_lines,
            "cta": cta_zh,
        },
    }


def validate_script_voiceover_seed(seed: dict[str, Any]) -> None:
    lines = [str(line or "").strip() for line in seed.get("script_voiceover") or [] if str(line or "").strip()]
    hook = str(seed.get("hook") or "").strip()
    cta = str(seed.get("cta") or "").strip()
    if not hook:
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must include a Hook")
    if "moras" in hook.lower():
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed Hook must not start from Moras as the hero")
    if not (MIN_SCRIPT_VOICEOVER_LINES <= len(lines) <= 14):
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must contain 11-14 English lines")
    long_lines = [line for line in lines if english_word_count(line) > MAX_SCRIPT_VOICEOVER_ENGLISH_WORDS]
    if long_lines:
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed lines must stay under 14 English words")
    spoken_lines = script_spoken_lines_for_length(lines, cta)
    if sum(english_word_count(line) for line in spoken_lines) < MIN_SCRIPT_VOICEOVER_TOTAL_ENGLISH_WORDS:
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must contain at least 90 spoken English words")
    if script_voiceover_estimated_duration_sec(spoken_lines) < MIN_SCRIPT_SPOKEN_DURATION_SEC:
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must support at least 35s of spoken delivery")
    if not any("moras" in line.lower() for line in lines):
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must mention Moras in the spoken body")
    publishable_text = json.dumps(
        {
            "hook": hook,
            "script_voiceover": lines,
            "cta": cta,
            "localized_zh": seed.get("localized_zh") or {},
        },
        ensure_ascii=False,
    ).lower()
    claim_hits = [pattern for pattern in BANNED_SCRIPT_CLAIM_PATTERNS if pattern in publishable_text]
    if claim_hits:
        raise unprocessable(
            "VOICEOVER_SEED_INVALID",
            "Voiceover seed must not repeat banned income/sales claim labels, even when negating them: "
            + ", ".join(sorted(claim_hits)),
        )
    zh_lines = (seed.get("localized_zh") or {}).get("script_voiceover")
    if not has_cjk(str((seed.get("localized_zh") or {}).get("hook") or "")):
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must include a Chinese Hook translation")
    if not isinstance(zh_lines, list) or len(zh_lines) != len(lines) or not all(has_cjk(str(line)) for line in zh_lines):
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must include Chinese translations for every line")
    if not has_cjk(str((seed.get("localized_zh") or {}).get("cta") or "")):
        raise unprocessable("VOICEOVER_SEED_INVALID", "Voiceover seed must include a Chinese CTA translation")


def apply_pre_generated_voiceover_seed(
    item: ScriptAgentItem,
    seed: dict[str, Any],
    fallback_source_ids: list[str],
    *,
    selected_persona: dict[str, Any] | None,
) -> ScriptAgentItem:
    data = item.model_dump(mode="json")
    script = data.setdefault("script", {})
    script["hook"] = str(seed["hook"])
    script["voiceover"] = list(seed["script_voiceover"])
    script["cta"] = str(seed["cta"])
    set_localized_zh(
        script,
        {
            "hook": str((seed.get("localized_zh") or {}).get("hook") or ""),
            "voiceover": list((seed.get("localized_zh") or {}).get("script_voiceover") or []),
            "cta": str((seed.get("localized_zh") or {}).get("cta") or ""),
        },
    )
    normalized = normalize_script_item(
        data,
        fallback_source_ids,
        selected_persona=selected_persona or item.creator_persona.model_dump(mode="json"),
        auto_fill_localizations=False,
    )
    return ScriptAgentItem.model_validate(normalized)


def apply_script_voiceover_review_patch(
    item: ScriptAgentItem,
    raw_text: str,
    fallback_source_ids: list[str],
    *,
    selected_persona: dict[str, Any] | None,
) -> ScriptAgentItem:
    try:
        patch = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("VOICEOVER_REVIEW_NOT_JSON", f"Voiceover Expert review was not valid JSON: {exc}") from exc
    if isinstance(patch, dict) and isinstance(patch.get("voiceover_patch"), dict):
        patch = patch["voiceover_patch"]
    if not isinstance(patch, dict):
        raise unprocessable("VOICEOVER_REVIEW_NOT_OBJECT", "Voiceover Expert review must be a JSON object")
    if patch.get("requires_patch") is False:
        return item
    data = item.model_dump(mode="json")
    script = data.setdefault("script", {})
    hook = str(first_present(patch.get("patched_hook"), patch.get("hook")) or "").strip()
    if hook:
        script["hook"] = repair_safe_style_text(hook)
    lines = script_voiceover_lines_for_repair(first_present(patch.get("patched_script_voiceover"), patch.get("script_voiceover")))
    if lines:
        script["voiceover"] = [repair_safe_style_text(line) for line in lines]
    cta = str(first_present(patch.get("patched_cta"), patch.get("cta")) or "").strip()
    if cta:
        script["cta"] = repair_safe_style_text(cta)
    patched_zh = patch.get("patched_localized_zh") if isinstance(patch.get("patched_localized_zh"), dict) else {}
    zh_lines = script_voiceover_lines_for_repair(
        first_present(patched_zh.get("script_voiceover"), patched_zh.get("voiceover"))
    )
    zh_cta = str(patched_zh.get("cta") or "").strip()
    zh_updates: dict[str, Any] = {}
    zh_hook = str(patched_zh.get("hook") or "").strip()
    if zh_hook:
        zh_updates["hook"] = zh_hook
    if zh_lines:
        zh_updates["voiceover"] = zh_lines
    if zh_cta:
        zh_updates["cta"] = zh_cta
    if zh_updates:
        set_localized_zh(script, zh_updates)
    apply_storyboard_voiceover_review_updates(data, patch.get("patched_storyboard_voiceovers"))
    normalized = normalize_script_item(
        data,
        fallback_source_ids,
        selected_persona=selected_persona or item.creator_persona.model_dump(mode="json"),
        auto_fill_localizations=False,
    )
    return ScriptAgentItem.model_validate(normalized)


def apply_storyboard_voiceover_review_updates(item: dict[str, Any], updates: Any) -> None:
    storyboard = item.get("storyboard")
    if not isinstance(storyboard, list) or not isinstance(updates, list):
        return
    shots_by_id = {
        str(shot.get("shot_id")): shot
        for shot in storyboard
        if isinstance(shot, dict) and str(shot.get("shot_id") or "").strip()
    }
    for update in updates:
        if not isinstance(update, dict):
            continue
        indices = update.get("source_voiceover_line_indices")
        if isinstance(indices, list):
            numeric_indices = [index for index in indices if isinstance(index, int)]
            if len(numeric_indices) > 3:
                raise unprocessable("VOICEOVER_REVIEW_INVALID", "Storyboard voiceover patch may join at most 3 spoken beats")
            if numeric_indices and sorted(numeric_indices) != list(range(min(numeric_indices), max(numeric_indices) + 1)):
                raise unprocessable("VOICEOVER_REVIEW_INVALID", "Storyboard voiceover patch beat indices must be consecutive")
        shot = shots_by_id.get(str(update.get("shot_id") or ""))
        if shot is None:
            continue
        voiceover = str(update.get("voiceover") or "").strip()
        if voiceover:
            shot["voiceover"] = repair_safe_style_text(voiceover)
        zh_voiceover = str(update.get("localized_zh_voiceover") or "").strip()
        if zh_voiceover:
            set_localized_zh(shot, {"voiceover": zh_voiceover})


def compact_script_item_for_voiceover_review(item: ScriptAgentItem) -> dict[str, Any]:
    return {
        "topic_plan": {
            "title": item.topic_plan.title,
            "content_angle": item.topic_plan.content_angle,
            "template": item.topic_plan.template,
            "persona": item.topic_plan.persona,
        },
        "script": {
            "script_title": item.script.script_title,
            "hook": item.script.hook,
            "voiceover": item.script.voiceover,
            "cta": item.script.cta,
            "localized_zh": {
                "hook": localized_zh_field(item.script.localized, "hook"),
                "voiceover": localized_zh_field(item.script.localized, "voiceover"),
                "cta": localized_zh_field(item.script.localized, "cta"),
            },
        },
        "storyboard": [
            {
                "shot_id": shot.shot_id,
                "timestamp": shot.timestamp,
                "duration": shot.duration,
                "camera": shot.camera,
                "character_action": shot.character_action,
                "background": shot.background,
                "voiceover": shot.voiceover,
                "localized_zh_voiceover": localized_zh_field(shot.localized, "voiceover"),
                "purpose": shot.purpose,
            }
            for shot in item.storyboard
        ],
    }


def select_script_agent_skill_names(request: ScriptGenerationRequest) -> list[str]:
    _ = request
    return list(SCRIPT_AGENT_SKILL_ORDER)


def build_script_agent_skill_pack(
    skill_names: list[str],
    *,
    output_contract_path: Path = SCRIPT_OUTPUT_CONTRACT_PATH,
) -> str:
    sections = ["# Loaded Script Agent Skills"]
    for skill_name in skill_names:
        sections.append(load_script_agent_skill(skill_name))
    output_contract = build_script_agent_output_contract(output_contract_path)
    sections.append(f"# Output Contract\n\n{output_contract}")
    return "\n\n".join(sections)


def load_script_agent_skill(skill_name: str) -> str:
    skill_path = SCRIPT_SKILLS_DIR / skill_name / "SKILL.md"
    skill_body = skill_path.read_text(encoding="utf-8").strip()
    if skill_name == "veo-prompting":
        skill_body = f"{skill_body}\n\n{build_veo_prompt_forbidden_terms_section()}"
    return f"## Skill: {skill_name}\n\n{skill_body}"


def build_script_agent_output_contract(output_contract_path: Path) -> str:
    output_contract = output_contract_path.read_text(encoding="utf-8").strip()
    return f"{output_contract}\n\n{build_localization_glossary_section()}"


def build_veo_prompt_forbidden_terms_section() -> str:
    terms = ", ".join(f"`{term}`" for term in VEO_PROMPT_FORBIDDEN_TERMS)
    return (
        "## Backend Validator Negative Terms\n\n"
        "The backend rejects Veo prompt text that contains these terms. Do not use them in "
        "`video_prompt.generation_prompt` or `video_prompt.segments[].veo_prompt`, including translated "
        f"variants or near-synonyms that ask Veo to render text/UI artifacts:\n\n{terms}"
    )


def build_localization_glossary_section() -> str:
    exact_pairs = "\n".join(
        f"- `{english}` => `{chinese}`" for english, chinese in EXACT_CHINESE_LOCALIZATIONS.items()
    )
    phrase_pairs = "\n".join(
        f"- `{english}` => `{chinese}`" for english, chinese in PHRASE_CHINESE_LOCALIZATIONS
    )
    return (
        "## Required Chinese Glossary\n\n"
        "When a canonical English field contains one of these exact terms or phrases, use the listed "
        "`localized.zh` translation. Do not invent alternate wording for these glossary entries.\n\n"
        "Exact phrases:\n"
        f"{exact_pairs}\n\n"
        "Reusable phrase mappings:\n"
        f"{phrase_pairs}"
    )


def is_retryable_script_agent_output_error(message: str) -> bool:
    return any(pattern in message for pattern in SCRIPT_AGENT_RETRYABLE_OUTPUT_ERROR_PATTERNS)


def script_agent_rejection_note(message: str) -> str:
    compact_message = compact_text(message, 700)
    if "UGC voiceover must mention Moras" in message or "UGC voiceover must not overuse Moras" in message:
        return (
            "Previous attempt failed validation because the English script.voiceover had a bad Moras mention pattern. "
            "Rewrite the same concept with one or two spoken Moras lines in the middle. Do not mention Moras in the hook, "
            "the first voiceover line, or the closing CTA. At least one Moras line must be personal creator usage "
            "of the real selected-product/Generate or Custom Create workflow that produces a video with the commerce path visible. "
            f"Validation message: {compact_message}"
        )
    if "negative failure metrics" in message or "test products" in message or "test every day" in message:
        return (
            "Previous attempt failed validation because the opening leaned on a negative failure metric or made product testing the main value. "
            "Rewrite the first two voiceover lines with a curiosity, routine-change, or workflow-pressure hook. "
            "Line 2 must logically bridge line 1 with causality or contrast, and the creator action must be promote/post/create another video, not test products. "
            f"Validation message: {compact_message}"
        )
    if "generic attention cue" in message:
        return (
            "Previous attempt failed validation because a caption highlight was generic. "
            "Rewrite overlay/caption highlights as 2-4 word concrete beat labels from the hook or scene, such as Angle first, Product fit, or Creator callout. "
            "Do not use Listen up or similar empty attention cues. "
            f"Validation message: {compact_message}"
        )
    if "localized.zh" in message:
        return (
            "Previous attempt failed validation because one or more localized.zh fields were missing readable Chinese. "
            "Rewrite and ensure every localized.zh human-readable field is fully translated into Chinese CJK text, especially storyboard.localized.zh.character_action/background/camera/voiceover/overlay/sound/bgm/sound_effects/subtitle_logic/visual_elements/visual_element_logic/transition/purpose and production_asset_plan.localized.zh. "
            "Do not leave English UI or scene descriptions in localized.zh, except fixed product names such as Moras, TikTok, Create video, or Custom Create. "
            f"Validation message: {compact_message}"
        )
    if "UGC voiceover lines must stay short" in message or "long product-pitch sentences" in message:
        return (
            "Previous attempt failed validation because one or more English voiceover lines were too long or sounded like a product pitch. "
            "Rewrite with 11-14 short spoken lines, each under 14 words. Keep Moras workflow lines under 14 words and place them in the middle. "
            "Split creator pain, Moras Generate workflow, completed product-video output, and click-button CTA into separate short lines. "
            f"Validation message: {compact_message}"
        )
    if "short spoken lines so short sentences do not remove content" in message or "UGC voiceover is too short" in message:
        return (
            "Previous attempt failed validation because the voiceover became too thin. "
            "Rewrite with 11-14 short spoken lines, each under 14 words, totaling at least 90 spoken English words and enough natural delivery for a 35-45s ad. "
            "Preserve the full content chain: hook, pain, old-way cost, delay or money cost, proof cue, open Moras, choose product, hit Generate, Moras-made video, commerce path visible, check/post step, next post, then CTA. "
            f"Validation message: {compact_message}"
        )
    if "split rows longer" in message:
        return (
            "Previous attempt failed validation because a storyboard row exceeded 8 seconds. "
            "Do not split just because there are multiple short spoken lines. Split only when the visible state changes; "
            "otherwise keep the continuous shot and set a duration that matches the full spoken text. "
            f"Validation message: {compact_message}"
        )
    if "voiceover needs about" in message:
        return (
            "Previous attempt failed validation because a storyboard row duration was too short for the spoken line. "
            "Do not shorten or truncate the voiceover. Increase that row's duration to match natural spoken pacing, "
            "or split the sentence into another storyboard row if it would exceed 8 seconds. Do not assign every row 4s. "
            f"Validation message: {compact_message}"
        )
    if "short voiceover only supports" in message:
        return (
            "Previous attempt failed validation because a storyboard row stretched a short spoken line into an unjustified long shot. "
            "Set duration from the English spoken text first. If extra seconds are needed, explicitly describe the non-speaking "
            "visual hold, reaction, UI demo, or transition in character_action/purpose; otherwise shorten the row duration. "
            f"Validation message: {compact_message}"
        )
    if "visual_elements must change by shot" in message:
        return (
            "Previous attempt failed validation because multiple storyboard rows reused the same visual_elements list. "
            "Rewrite visual_elements so every row names the exact elements for that shot: hook gesture, proof card, "
            "Moras UI zoom, Generate click highlight, completed-output hold, review controls, posting checklist, CTA arrow, etc. "
            f"Validation message: {compact_message}"
        )
    if "banned claims found in script output" in message:
        return (
            "Previous attempt failed validation because a banned income/sales claim label appeared in a publishable script field. "
            "Do not repeat forbidden-claim labels verbatim anywhere in topic_plan, script, storyboard, localized.zh, or purpose text, even when negating them. "
            "Use safer wording such as unsupported outcome promise, sales promise, fixed-result claim, or no fixed result instead. "
            "Keep Moras scoped to workflow proof: Discover/product library, product selection, Generate or Custom Create, video output, posting entry, and Data feedback. "
            f"Validation message: {compact_message}"
        )
    return (
        "Previous attempt failed validation. Rewrite from a different creative axis; keep Hook quality first; "
        "mention Moras as personal use of the selected-product/Generate workflow; use a direct click-button CTA; avoid the exact rejected wording. "
        f"Validation message: {compact_message}"
    )


def compact_script_signature(record: ScriptRecord) -> dict[str, Any]:
    return {
        "title": compact_text(first_present(record.script.get("script_title"), record.topic_plan.get("title")), 90),
        "localized_zh_title": first_present(
            compact_text(nested_zh_value(record.script, "script_title"), 90),
            compact_text(nested_zh_value(record.topic_plan, "title"), 90),
        ),
        "hook": compact_text(record.script.get("hook"), 120),
        "first_two_voiceover_lines": compact_string_list(record.script.get("voiceover"), max_items=2, max_chars=120),
        "template": compact_text(first_present(record.script.get("template"), record.topic_plan.get("template")), 80),
        "core_pain": compact_text(record.script.get("core_pain"), 120),
        "source_component_summary": compact_string_list(record.source_component_summary, max_items=3, max_chars=80),
    }


def compact_script_item_signature(item: ScriptAgentItem) -> dict[str, Any]:
    return {
        "title": compact_text(first_present(item.script.script_title, item.topic_plan.title), 90),
        "localized_zh_title": compact_text(
            first_present(
                localized_zh_field(item.script.localized, "script_title"),
                localized_zh_field(item.topic_plan.localized, "title"),
            ),
            90,
        ),
        "hook": compact_text(item.script.hook, 120),
        "first_two_voiceover_lines": compact_string_list(item.script.voiceover, max_items=2, max_chars=120),
        "template": compact_text(first_present(item.script.template, item.topic_plan.template), 80),
        "core_pain": compact_text(item.script.core_pain, 120),
        "source_component_summary": compact_string_list(item.source_component_summary, max_items=3, max_chars=80),
    }


class PersonaLifestyleRepeatError(ValueError):
    pass


def build_persona_prompt(
    request: PersonaGenerationRequest,
    existing_names: list[str],
    existing_persona_signatures: list[dict[str, Any]] | None = None,
    *,
    batch_target_count: int | None = None,
    batch_position: int | None = None,
    rejected_lifestyle_notes: list[str] | None = None,
) -> str:
    system_prompt = PERSONA_PROMPT_PATH.read_text(encoding="utf-8")
    context = {
        "persona_count": request.persona_count,
        "topic_or_brand_context": request.topic_or_brand_context,
        "target_audience": request.target_audience,
        "required_demographic": request.required_demographic,
        "batch_target_count": batch_target_count or request.persona_count,
        "batch_position": batch_position,
        "background_mix_target": "For a multi-persona library, keep most personas amateur, part-time, beginner, or small/mid-tier creator backgrounds. Use only a minority of professional ecommerce, MCN, agency, or operator backgrounds.",
        "existing_persona_names": existing_names,
        "existing_persona_signatures": existing_persona_signatures or [],
        "rejected_lifestyle_notes": rejected_lifestyle_notes or [],
        "platform": "TikTok",
        "persona_mission_types": [
            "Beginner KOC",
            "Mom Creator",
            "Tutorial Learner",
            "Skeptical Creator",
            "Lazy-but-Ambitious Creator",
        ],
        "moras_persona_mission": (
            "Help TikTok Shop creators who already have accounts but cannot monetize: reduce blank-page product work, "
            "turn selected Moras products into videos with the commerce path visible, avoid writing scripts from zero, use approved creator proof, "
            "support faceless or low-burden content, and move creators from manual guessing into a Generate-to-post earning workflow."
        ),
        "target_problem_system": {
            "explicit_pains": [
                "does not know how to pick products",
                "does not know how to write scripts",
                "does not know how to edit",
                "does not want to show face",
                "does not know which products can create earning opportunities",
                "has limited time for content production",
                "posts videos without a clear commerce path",
                "does not know how to make product videos",
                "does not know beginner-friendly TikTok Shop products",
                "daily content ideation feels exhausting",
            ],
            "inner_conflicts": [
                "wants to earn but has limited time for content production",
                "has followers but cannot monetize",
                "thinks high commission automatically means a good product",
                "does not want to show face but wants TikTok Shop content",
                "wants a side hustle but hates complicated courses",
                "has posted many videos but has no clear product workflow",
                "assumes AI video must look fake",
                "is not lazy, but does not know the right method",
                "does not understand the connection between product choice and script angle",
            ],
            "desired_states": [
                "earn with less waste",
                "discover promising products earlier",
                "use less time to publish more product videos",
                "look more professional",
                "move from zero to a creator who knows how to post product videos",
                "use AI without seeming dependent on AI",
                "make content without showing face",
            ],
        },
        "trust_asset_categories": [
            "GMV screenshot",
            "commission screenshot",
            "creator testimonial",
            "7-day challenge result",
            "product-to-video before/after",
            "traditional workflow vs Moras workflow",
            "product-to-video workflow recording",
            "comment feedback",
            "TikTok Shop backend",
            "product selection logic",
            "time saved proof",
        ],
        "content_pillar_options": [
            "POV",
            "Mistake List",
            "Contrarian Take",
            "Tool Reveal",
            "Comment Reply",
            "Product Picking",
            "Product-to-Video Workflow",
            "Product-to-Video Workflow",
            "Faceless Creator",
            "Beginner Trap",
        ],
        "scene_options": [
            "messy kitchen",
            "living room with kids",
            "car pickup wait",
            "late-night phone scrolling",
            "shopping bags",
            "bed collapse",
            "desktop workflow",
            "phone backend",
            "comment screenshot",
            "product library interface",
            "TikTok Shop backend",
            "friend chat",
            "couple conflict",
            "street interview",
            "tutorial whiteboard",
        ],
        "commercial_boundaries": [
            "no guaranteed income",
            "no passive income guaranteed",
            "no make $10K easily",
            "no automatic money",
            "no AI guarantees sales",
            "no fake personal purchase, product use, payout, or income claim without approved proof asset",
            "realistic AI-person footage should be labeled as AI-generated or synthetic where required",
        ],
        "positive_demographic_pool": [
            "Black",
            "Afro-Latina",
            "Arab-American",
            "Indigenous and Mexican-American",
            "Caribbean-American Black",
            "Brazilian-Latina",
            "multiracial Black and white",
            "Ghanaian-American",
        ],
    }
    return (
        f"{system_prompt}\n\n"
        "Generate reusable creator personas from this input JSON. Return JSON only.\n\n"
        f"{json.dumps(context, ensure_ascii=False, indent=2)}"
    )


def persona_diversity_signatures(personas: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [signature for persona in personas if (signature := persona_diversity_signature(persona))]


def persona_diversity_signature(persona: dict[str, Any]) -> dict[str, Any]:
    compact = compact_persona_for_prompt(persona)
    if not compact:
        return {}
    return {
        "display_name": compact.get("display_name"),
        "persona_type": compact.get("persona_type"),
        "role_task": compact.get("role_task"),
        "role": compact.get("role"),
        "demographic": compact.get("demographic"),
        "creator_background": compact.get("creator_background"),
        "recurring_scenes": compact.get("recurring_scenes", []),
        "content_pillars": compact.get("content_pillars", []),
        "memory_symbols": compact.get("memory_symbols", {}),
        "hobbies_interests": compact.get("hobbies_interests", []),
        "props": compact.get("props", []),
        "wardrobe": compact.get("wardrobe"),
        "styling_details": compact.get("styling_details"),
    }


def ensure_persona_lifestyle_is_fresh(
    persona: dict[str, Any],
    used_lifestyle_markers: set[str],
    used_interest_values: set[str],
) -> None:
    repeated_markers = sorted(persona_lifestyle_markers(persona) & used_lifestyle_markers)
    repeated_interests = sorted(persona_interest_values(persona) & used_interest_values)
    if repeated_markers or repeated_interests:
        parts = []
        if repeated_markers:
            parts.append(f"reused lifestyle markers: {', '.join(repeated_markers)}")
        if repeated_interests:
            parts.append(f"reused exact interests: {', '.join(repeated_interests)}")
        raise PersonaLifestyleRepeatError("; ".join(parts))


def persona_lifestyle_markers(persona: dict[str, Any]) -> set[str]:
    text = " ".join(persona_lifestyle_strings(persona)).lower()
    markers = set()
    for marker, pattern in PERSONA_LIFESTYLE_MARKER_PATTERNS:
        if re.search(pattern, text):
            markers.add(marker)
    return markers


def persona_interest_values(persona: dict[str, Any]) -> set[str]:
    values = set()
    for hobby in persona.get("hobbies_interests") or []:
        normalized = normalize_lifestyle_value(hobby)
        if normalized:
            values.add(normalized)
    return values


def persona_lifestyle_strings(persona: dict[str, Any]) -> list[str]:
    strings: list[str] = []
    for key in ("hobbies_interests", "props"):
        value = persona.get(key)
        if isinstance(value, list):
            strings.extend(str(item) for item in value if item)
    for key in ("styling_details", "reference_image_prompt", "veo_identity_string"):
        value = persona.get(key)
        if value:
            strings.append(str(value))
    return strings


def normalize_lifestyle_value(value: Any) -> str:
    text = re.sub(r"[^a-z0-9]+", " ", str(value).lower()).strip()
    return re.sub(r"\s+", " ", text)


def build_edit_prompt(existing: ScriptRecord, instruction: str) -> str:
    resident_prompt = PROMPT_PATH.read_text(encoding="utf-8").strip()
    skill_pack = build_script_agent_skill_pack(
        list(SCRIPT_AGENT_SKILL_ORDER),
        output_contract_path=SCRIPT_EDIT_OUTPUT_CONTRACT_PATH,
    )
    context = {
        "loaded_script_agent_skills": list(SCRIPT_AGENT_SKILL_ORDER),
        "edit_instruction": instruction,
        "existing_script": {
            "topic_plan": existing.topic_plan,
            "script": existing.script,
            "storyboard": existing.storyboard,
            "creator_persona": existing.creator_persona,
            "video_prompt": existing.video_prompt,
            "production_asset_plan": existing.production_asset_plan,
            "risk_check": existing.risk_check,
            "source_breakdown_ids": existing.source_breakdown_ids,
            "source_component_summary": existing.source_component_summary,
        },
        "task": "Return exactly one revised script item using the same schema as one item inside scripts[].",
    }
    return f"{resident_prompt}\n\n{skill_pack}\n\nRevise this script. Return JSON only.\n\n{json.dumps(context, ensure_ascii=False, indent=2)}"


def parse_persona_agent_batch(
    raw_text: str,
    request: PersonaGenerationRequest,
    used_names: set[str] | None = None,
) -> list[dict[str, Any]]:
    try:
        data = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("PERSONA_OUTPUT_NOT_JSON", f"Persona Agent output was not valid JSON: {exc}") from exc
    if isinstance(data, list):
        data = {"personas": data}
    if isinstance(data, dict) and "personas" not in data:
        data = {"personas": data.get("creator_personas") or data.get("creatorPersonas") or [data]}
    personas = data.get("personas") if isinstance(data, dict) else None
    if not isinstance(personas, list):
        raise unprocessable("PERSONA_OUTPUT_NOT_OBJECT", "Persona Agent output must contain a personas array")
    normalized: list[dict[str, Any]] = []
    excluded = set(used_names or set())
    for index, persona in enumerate(personas[: request.persona_count]):
        normalized_persona = normalize_generated_persona(persona, request, index, excluded)
        name = persona_display_name(normalized_persona)
        if name:
            excluded.add(name)
        normalized.append(normalized_persona)
    if len(normalized) < request.persona_count:
        normalized.extend(build_mock_personas(request, excluded, offset=len(normalized))[: request.persona_count - len(normalized)])
    return normalized


def normalize_generated_persona(
    persona: Any,
    request: PersonaGenerationRequest,
    index: int,
    excluded_names: set[str],
) -> dict[str, Any]:
    topic_plan = {
        "title": request.topic_or_brand_context,
        "target_audience": request.target_audience,
        "persona": "Reusable Moras creator persona",
    }
    script = {
        "script_title": request.topic_or_brand_context,
        "persona": "Reusable Moras creator persona",
    }
    normalized = normalize_creator_persona_payload(
        persona if isinstance(persona, dict) else {},
        topic_plan,
        script,
        seed=f"persona-agent|{request.topic_or_brand_context}|{index}",
        variant_index=index,
        excluded_names=excluded_names,
    )
    normalized["veo_identity_string"] = str(normalized.get("veo_identity_string") or veo_identity_string_from_persona(normalized))
    try:
        return CreatorPersonaProfile.model_validate(normalized).model_dump(mode="json")
    except ValidationError as exc:
        raise unprocessable("PERSONA_OUTPUT_SCHEMA_INVALID", str(exc)) from exc


def build_mock_personas(
    request: PersonaGenerationRequest,
    used_names: set[str] | None = None,
    *,
    offset: int = 0,
) -> list[dict[str, Any]]:
    used = set(used_names or set())
    personas: list[dict[str, Any]] = []
    for index in range(offset, offset + request.persona_count):
        seed = f"persona-agent|{request.topic_or_brand_context}|{request.target_audience}|{utc_now()}|{index}|{len(used)}"
        topic_plan = {
            "title": request.topic_or_brand_context or "Reusable Moras creator persona",
            "target_audience": request.target_audience or "Moras creator operators",
            "persona": "Reusable Moras creator persona",
        }
        script = {
            "script_title": request.topic_or_brand_context or "Reusable Moras creator persona",
            "persona": "Reusable Moras creator persona",
        }
        persona = default_creator_persona_payload(
            script,
            topic_plan,
            seed=seed,
            variant_index=index + len(used),
            excluded_names=used,
        )
        apply_mock_persona_lifestyle_variant(persona, index + len(used))
        if request.required_demographic:
            persona["demographic"] = f"{request.required_demographic}; {persona['demographic']}"
            persona["veo_identity_string"] = veo_identity_string_from_persona(persona)
            persona["reference_image_prompt"] = reference_prompt_without_script_terms(persona)
            ensure_digital_human_prompt_assets(persona)
        name = persona_display_name(persona)
        if name:
            used.add(name)
        personas.append(CreatorPersonaProfile.model_validate(persona).model_dump(mode="json"))
    return personas


def apply_mock_persona_lifestyle_variant(persona: dict[str, Any], variant_index: int) -> None:
    variant = MOCK_PERSONA_LIFESTYLE_VARIANTS[variant_index % len(MOCK_PERSONA_LIFESTYLE_VARIANTS)]
    role = variant.get("role", [])
    background = variant.get("creator_background", [])
    if len(role) >= 2:
        persona["role"] = role[0]
        persona.setdefault("localized", {}).setdefault("zh", {})["role"] = role[1]
    if len(background) >= 2:
        persona["creator_background"] = background[0]
        persona.setdefault("localized", {}).setdefault("zh", {})["creator_background"] = background[1]
    persona["hobbies_interests"] = list(variant["hobbies_interests"])
    persona["props"] = list(variant["props"])
    zh = persona.setdefault("localized", {}).setdefault("zh", {})
    zh["hobbies_interests"] = list(variant.get("hobbies_interests_zh", variant["hobbies_interests"]))
    zh["props"] = list(variant.get("props_zh", variant["props"]))
    persona["veo_identity_string"] = veo_identity_string_from_persona(persona)
    zh["veo_identity_string"] = localize_to_chinese(persona["veo_identity_string"])
    persona["reference_image_prompt"] = reference_prompt_without_script_terms(persona)
    zh["reference_image_prompt"] = localize_to_chinese(persona["reference_image_prompt"])
    ensure_digital_human_prompt_assets(persona)


def reference_prompt_without_script_terms(persona: dict[str, Any]) -> str:
    from .persona_defaults import reference_image_prompt_from_persona

    return reference_image_prompt_from_persona(persona)


def parse_script_agent_batch(
    raw_text: str,
    fallback_source_ids: list[str],
    *,
    selected_persona: dict[str, Any] | None = None,
) -> ScriptAgentBatch:
    try:
        data = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("SCRIPT_OUTPUT_NOT_JSON", f"Script Agent output was not valid JSON: {exc}") from exc
    data = unwrap_script_agent_payload(data)
    if isinstance(data, list):
        data = {"scripts": data}
    if isinstance(data, dict) and "scripts" not in data:
        data = {"scripts": [data]}
    if not isinstance(data, dict):
        raise unprocessable("SCRIPT_OUTPUT_NOT_OBJECT", "Script Agent output must be a JSON object")
    normalized_scripts: list[dict[str, Any]] = []
    used_persona_names: set[str] = set()
    for index, item in enumerate(data.get("scripts", [])):
        normalized = normalize_script_item(
            item,
            fallback_source_ids,
            persona_variant_index=index,
            used_persona_names=None if selected_persona else used_persona_names,
            selected_persona=selected_persona,
            auto_fill_localizations=False,
        )
        name = persona_display_name(normalized.get("creator_persona"))
        if name:
            used_persona_names.add(name)
        normalized_scripts.append(normalized)
    data["scripts"] = normalized_scripts
    try:
        return ScriptAgentBatch.model_validate(data)
    except ValidationError as exc:
        raise unprocessable("SCRIPT_OUTPUT_SCHEMA_INVALID", str(exc)) from exc


def parse_script_agent_item(
    raw_text: str,
    fallback_source_ids: list[str],
    *,
    selected_persona: dict[str, Any] | None = None,
) -> ScriptAgentItem:
    try:
        data = json.loads(strip_json_fence(raw_text))
    except json.JSONDecodeError as exc:
        raise unprocessable("SCRIPT_OUTPUT_NOT_JSON", f"Script Agent output was not valid JSON: {exc}") from exc
    data = unwrap_script_agent_payload(data)
    if isinstance(data, dict) and "scripts" in data and isinstance(data["scripts"], list) and data["scripts"]:
        data = data["scripts"][0]
    if not isinstance(data, dict):
        raise unprocessable("SCRIPT_OUTPUT_NOT_OBJECT", "Script Agent output must be a JSON object")
    try:
        return ScriptAgentItem.model_validate(
            normalize_script_item(data, fallback_source_ids, selected_persona=selected_persona, auto_fill_localizations=False)
        )
    except ValidationError as exc:
        raise unprocessable("SCRIPT_OUTPUT_SCHEMA_INVALID", str(exc)) from exc


def unwrap_script_agent_payload(data: Any) -> Any:
    if (
        isinstance(data, list)
        and len(data) == 1
        and isinstance(data[0], dict)
        and isinstance(data[0].get("scripts"), list)
    ):
        return data[0]
    return data


def normalize_script_item(
    item: Any,
    fallback_source_ids: list[str],
    *,
    persona_variant_index: int = 0,
    used_persona_names: set[str] | None = None,
    selected_persona: dict[str, Any] | None = None,
    auto_fill_localizations: bool = True,
) -> dict[str, Any]:
    if not isinstance(item, dict):
        return {}
    normalized = {
        "topic_plan": item.get("topic_plan") or item.get("step_5_idea") or {},
        "script": item.get("script") or item.get("step_6_script") or {},
        "storyboard": item.get("storyboard") or item.get("step_7_storyboard") or [],
        "creator_persona": selected_persona or item.get("creator_persona") or item.get("persona_profile") or item.get("blogger_persona") or {},
        "video_prompt": item.get("video_prompt") or {},
        "production_asset_plan": item.get("production_asset_plan") or item.get("asset_plan") or [],
        "risk_check": item.get("risk_check") or {},
        "source_breakdown_ids": item.get("source_breakdown_ids") or fallback_source_ids,
        "source_component_summary": item.get("source_component_summary") or [],
    }
    if "cta" not in normalized["script"] and "CTA" in normalized["script"]:
        normalized["script"]["cta"] = normalized["script"].pop("CTA")
    normalize_storyboard_field_aliases(normalized["storyboard"])
    normalize_script_agent_type_drift(normalized)
    ensure_script_hook_candidates(normalized["topic_plan"], normalized["script"])
    seed = "|".join(
        [
            str(persona_variant_index),
            str(normalized["topic_plan"].get("title") or ""),
            str(normalized["script"].get("script_title") or ""),
            str(normalized["script"].get("persona") or normalized["topic_plan"].get("persona") or ""),
        ]
    )
    normalized["creator_persona"] = normalize_creator_persona_payload(
        normalized["creator_persona"],
        normalized["topic_plan"],
        normalized["script"],
        seed=seed,
        variant_index=persona_variant_index,
        excluded_names=None if selected_persona else used_persona_names,
    )
    sync_script_item_to_creator_persona(normalized, force=bool(selected_persona))
    repair_script_agent_generation_drift(normalized, persona_variant_index=persona_variant_index)
    repair_storyboard_for_schema(normalized)
    if "step_8_video_prompts" in item and not normalized["video_prompt"]:
        normalized["video_prompt"] = collapse_video_prompts(
            item["step_8_video_prompts"],
            normalized["script"],
            normalized["creator_persona"],
        )
    if not normalized["production_asset_plan"]:
        normalized["production_asset_plan"] = default_production_asset_plan(normalized["storyboard"])
    apply_storyboard_visual_element_specificity(normalized)
    apply_storyboard_timing_for_voiceover(normalized)
    split_long_storyboard_rows(normalized)
    apply_storyboard_timing_for_voiceover(normalized)
    apply_script_spoken_target_duration_floor(normalized)
    if isinstance(normalized["video_prompt"], dict):
        normalized["video_prompt"] = ensure_veo_segments(
            normalized["video_prompt"],
            normalized["script"],
            normalized["storyboard"],
            normalized["production_asset_plan"],
            normalized["creator_persona"],
        )
    if auto_fill_localizations:
        ensure_chinese_localizations(normalized)
    else:
        validate_script_agent_chinese_localizations(normalized)
    repair_publishable_safe_style_drift(normalized)
    return normalized


def normalize_storyboard_field_aliases(storyboard: Any) -> None:
    if not isinstance(storyboard, list):
        return
    for shot in storyboard:
        if not isinstance(shot, dict):
            continue
        for field_name in ("props", "sound_effects", "visual_elements"):
            shot[field_name] = normalize_storyboard_list_field(shot.get(field_name))
        action = shot.pop("action", None)
        if "character_action" not in shot and action is not None:
            shot["character_action"] = action
        duration = shot.get("duration")
        if isinstance(duration, (int, float)):
            shot["duration"] = f"{duration:g}s"
        localized = shot.get("localized")
        zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
        if isinstance(zh, dict):
            zh_action = zh.pop("action", None)
            if "character_action" not in zh and zh_action is not None:
                zh["character_action"] = zh_action
            zh_duration = zh.get("duration")
            if isinstance(zh_duration, (int, float)):
                zh["duration"] = f"{zh_duration:g}秒"
            for field_name in ("props", "sound_effects", "visual_elements"):
                zh[field_name] = normalize_storyboard_list_field(zh.get(field_name))


def normalize_storyboard_list_field(value: Any) -> list[str]:
    placeholder_values = {
        "",
        "n/a",
        "na",
        "none",
        "null",
        "not applicable",
        "无",
        "不适用",
        "没有",
    }
    if isinstance(value, str):
        text = re.sub(r"\s+", " ", value).strip()
        normalized = text.strip(" .。").lower()
        if normalized in placeholder_values:
            return []
        return [text] if text else []
    if isinstance(value, list):
        output: list[str] = []
        for item in value:
            text = compact_text(item, 90).strip()
            normalized = text.strip(" .。").lower()
            if text and normalized not in placeholder_values:
                output.append(text)
        return output
    return []


def normalize_script_agent_type_drift(item: dict[str, Any]) -> None:
    script = item.get("script")
    if isinstance(script, dict):
        for field_name in SCRIPT_TEXT_FIELDS:
            script[field_name] = text_from_script_scalar(script.get(field_name))
        if isinstance(script.get("voiceover"), str):
            script["voiceover"] = split_script_voiceover(script["voiceover"])
        if isinstance(script.get("overlay"), str):
            script["overlay"] = [script["overlay"]]
        localized = script.get("localized")
        zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
        if isinstance(zh, dict):
            for field_name in SCRIPT_TEXT_FIELDS:
                if field_name in zh:
                    zh[field_name] = text_from_script_scalar(zh.get(field_name))
            if isinstance(zh.get("voiceover"), str):
                zh["voiceover"] = split_script_voiceover(zh["voiceover"])
            if isinstance(zh.get("overlay"), str):
                zh["overlay"] = [zh["overlay"]]

    video_prompt = item.get("video_prompt")
    if isinstance(video_prompt, dict):
        notes = video_prompt.get("consistency_notes")
        if isinstance(notes, str):
            video_prompt["consistency_notes"] = [notes]
        localized = video_prompt.get("localized")
        zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
        if isinstance(zh, dict) and isinstance(zh.get("consistency_notes"), str):
            zh["consistency_notes"] = [zh["consistency_notes"]]

    for entry in item.get("production_asset_plan") or []:
        if not isinstance(entry, dict):
            continue
        if isinstance(entry.get("shot_ids"), str):
            entry["shot_ids"] = [entry["shot_ids"]]
        asset_type = str(entry.get("asset_type") or "").strip()
        normalized_layer = normalize_production_asset_layer(entry.get("layer"), asset_type)
        if normalized_layer:
            entry["layer"] = normalized_layer
        entry["moras_asset_category"] = normalize_production_asset_category(
            entry.get("moras_asset_category"),
            asset_type,
        )

    risk_check = item.get("risk_check")
    if isinstance(risk_check, dict):
        forbidden = risk_check.get("forbidden_claims_checked")
        if isinstance(forbidden, bool):
            risk_check["forbidden_claims_checked"] = (
                ["guaranteed income", "guaranteed sales", "fixed earnings"] if forbidden else []
            )
        elif isinstance(forbidden, str):
            risk_check["forbidden_claims_checked"] = [forbidden]
        notes = risk_check.get("compliance_notes")
        if isinstance(notes, str):
            risk_check["compliance_notes"] = [notes]
        localized = risk_check.pop("localized", None)
        zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
        if isinstance(zh, dict):
            zh_notes = first_present(zh.get("compliance_notes"), zh.get("compliance_note"), zh.get("notes"))
            if zh_notes and not risk_check.get("compliance_notes"):
                risk_check["compliance_notes"] = compact_string_list(
                    zh_notes if isinstance(zh_notes, list) else [zh_notes],
                    max_items=4,
                    max_chars=160,
                )
            zh_allowed = zh.get("allowed_for_video_factory")
            if "allowed_for_video_factory" not in risk_check and isinstance(zh_allowed, bool):
                risk_check["allowed_for_video_factory"] = zh_allowed


def repair_script_agent_generation_drift(item: dict[str, Any], *, persona_variant_index: int = 0) -> None:
    repair_publishable_safe_style_drift(item)
    repair_moras_hero_opening(item)
    repair_script_spoken_copy_length(item, persona_variant_index=persona_variant_index)


def repair_publishable_safe_style_drift(item: dict[str, Any]) -> None:
    for section_name in (
        "topic_plan",
        "script",
        "storyboard",
        "production_asset_plan",
        "risk_check",
        "source_component_summary",
        "source_alignment_notes",
        "revision_history",
        "creator_persona",
    ):
        if section_name in item:
            item[section_name] = repair_text_tree_for_safe_style(item[section_name], current_key=section_name)


def repair_named_text_fields_for_safe_style(section: dict[str, Any], field_names: tuple[str, ...]) -> None:
    for field_name in field_names:
        if field_name in section:
            section[field_name] = repair_text_tree_for_safe_style(section[field_name], current_key=field_name)
    localized = section.get("localized")
    zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
    if isinstance(zh, dict):
        for field_name in field_names:
            if field_name in zh:
                zh[field_name] = repair_text_tree_for_safe_style(zh[field_name], current_key=field_name)


SAFE_STYLE_REPAIR_SKIP_KEYS = {
    "sample_requirement",
    "sampleRequirement",
}


def repair_text_tree_for_safe_style(value: Any, *, current_key: str | None = None) -> Any:
    if current_key in SAFE_STYLE_REPAIR_SKIP_KEYS:
        return value
    if isinstance(value, str):
        return repair_safe_style_text(value)
    if isinstance(value, list):
        for index, item in enumerate(value):
            value[index] = repair_text_tree_for_safe_style(item)
        return value
    if isinstance(value, dict):
        for key, item in list(value.items()):
            value[key] = repair_text_tree_for_safe_style(item, current_key=str(key))
        return value
    return value


def repair_safe_style_text(value: str) -> str:
    repaired = value
    for pattern, replacement in SCRIPT_SAFE_STYLE_REPLACEMENTS:
        repaired = re.sub(pattern, replacement, repaired, flags=re.IGNORECASE)
    return compact_text(repaired, 1600)


def repair_moras_hero_opening(item: dict[str, Any]) -> None:
    script = item.get("script")
    if not isinstance(script, dict):
        return
    voiceover = script.get("voiceover") if isinstance(script.get("voiceover"), list) else []
    hook = str(script.get("hook") or "").strip()
    if "moras" in hook.lower():
        replacement = next((line for line in voiceover if "moras" not in str(line).lower()), "")
        script["hook"] = repair_safe_style_text(replacement or "The blank-page loop costs real money.")
        set_localized_zh(script, {"hook": "空白稿这个循环，其实很贵。"})
    if voiceover and "moras" in str(voiceover[0]).lower():
        voiceover[0] = "The blank-page loop costs real money."
        localized = script.get("localized")
        zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
        if isinstance(zh, dict) and isinstance(zh.get("voiceover"), list) and zh["voiceover"]:
            zh["voiceover"][0] = "空白稿这个循环，其实很贵。"


def repair_script_spoken_copy_length(item: dict[str, Any], *, persona_variant_index: int = 0) -> None:
    script = item.get("script")
    if not isinstance(script, dict):
        return
    original_lines = script_voiceover_lines_for_repair(script.get("voiceover"))
    original_zh_lines = script_voiceover_lines_for_repair(localized_zh_from_object(script).get("voiceover"))
    lines: list[str] = []
    zh_lines: list[str] = []
    for index, line in enumerate(original_lines):
        for part in split_script_line_for_repair(repair_safe_style_text(line)):
            if not part:
                continue
            lines.append(part)
            zh_lines.append(script_voiceover_repair_zh(part, index, original_zh_lines))
    lines, zh_lines = limit_moras_mentions_in_voiceover(lines, zh_lines)

    cta = repair_safe_style_text(script.get("cta") or "")
    if not cta or english_word_count(cta) < 5:
        cta = SCRIPT_REPAIR_CTA_EN
    script["cta"] = cta
    localized_script = localized_zh_from_object(script)
    cta_zh = str(localized_script.get("cta") or "").strip()
    if not has_cjk(cta_zh):
        cta_zh = SCRIPT_REPAIR_CTA_ZH

    changed = lines != original_lines or cta != str(script.get("cta") or "")
    if script_voiceover_needs_length_repair(lines, cta):
        changed = True
        for beat_set_offset in range(len(SCRIPT_VOICEOVER_REPAIR_BEAT_SETS)):
            beat_set = SCRIPT_VOICEOVER_REPAIR_BEAT_SETS[
                (persona_variant_index + beat_set_offset) % len(SCRIPT_VOICEOVER_REPAIR_BEAT_SETS)
            ]
            for en_line, zh_line in beat_set:
                if not script_voiceover_needs_length_repair(lines, cta):
                    break
                if "moras" in en_line.lower() and moras_mention_count(lines) >= 2:
                    continue
                if normalized_line_signature(en_line) in {normalized_line_signature(line) for line in lines}:
                    continue
                lines.append(en_line)
                zh_lines.append(zh_line)
            if not script_voiceover_needs_length_repair(lines, cta):
                break

    lines, zh_lines = limit_moras_mentions_in_voiceover(lines, zh_lines)
    if not any("moras" in line.lower() for line in lines):
        insert_index = min(4, len(lines))
        en_line, zh_line = SCRIPT_VOICEOVER_REPAIR_BEAT_SETS[persona_variant_index % len(SCRIPT_VOICEOVER_REPAIR_BEAT_SETS)][4]
        lines.insert(insert_index, en_line)
        zh_lines.insert(insert_index, zh_line)
        changed = True

    if script_voiceover_needs_length_repair(lines, cta):
        for en_line, zh_line in SCRIPT_VOICEOVER_REPAIR_BEAT_SETS[0]:
            if normalized_line_signature(en_line) not in {normalized_line_signature(line) for line in lines}:
                lines.append(en_line)
                zh_lines.append(zh_line)
            if not script_voiceover_needs_length_repair(lines, cta):
                break

    script["voiceover"] = lines
    set_localized_zh(script, {"voiceover": zh_lines, "cta": cta_zh})
    if changed:
        rebuild_storyboard_from_script_spoken_copy(item, cta_zh=cta_zh)


def script_voiceover_lines_for_repair(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(line).strip() for line in value if str(line).strip()]
    if isinstance(value, str):
        return split_script_voiceover(value)
    return []


def split_script_line_for_repair(value: str) -> list[str]:
    text = compact_text(value, 320)
    if not text:
        return []
    if has_cjk(text) or english_word_count(text) <= MAX_SCRIPT_VOICEOVER_ENGLISH_WORDS:
        return [text]
    return [part for part in split_long_english_voiceover_unit(text) if part]


def script_voiceover_repair_zh(line: str, index: int, original_zh_lines: list[str]) -> str:
    if index < len(original_zh_lines):
        candidate = repair_safe_style_text(original_zh_lines[index])
        if has_cjk(candidate):
            return candidate
    for beat_set in SCRIPT_VOICEOVER_REPAIR_BEAT_SETS:
        for en_line, zh_line in beat_set:
            if normalized_line_signature(en_line) == normalized_line_signature(line):
                return zh_line
    localized = localize_to_chinese(line)
    if has_cjk(localized):
        return localized
    return f"创作者补充这一句：{line}"


def script_voiceover_needs_length_repair(lines: list[str], cta: str) -> bool:
    spoken_lines = script_spoken_lines_for_length(lines, cta)
    return (
        len([line for line in lines if line.strip()]) < MIN_SCRIPT_VOICEOVER_LINES
        or sum(english_word_count(line) for line in spoken_lines) < MIN_SCRIPT_VOICEOVER_TOTAL_ENGLISH_WORDS
        or script_voiceover_estimated_duration_sec(spoken_lines) < MIN_SCRIPT_SPOKEN_DURATION_SEC
    )


def moras_mention_count(lines: list[str]) -> int:
    return sum(line.lower().count("moras") for line in lines)


def limit_moras_mentions_in_voiceover(lines: list[str], zh_lines: list[str]) -> tuple[list[str], list[str]]:
    kept_mentions = 0
    repaired_lines: list[str] = []
    repaired_zh_lines: list[str] = []
    for index, line in enumerate(lines):
        mention_count = line.lower().count("moras")
        repaired = line
        if mention_count:
            if kept_mentions >= 3:
                repaired = re.sub(r"\bMoras\b", "the workflow", repaired, flags=re.IGNORECASE)
            elif kept_mentions + mention_count > 3:
                overflow = kept_mentions + mention_count - 3
                for _ in range(overflow):
                    repaired = re.sub(r"\bMoras\b", "the workflow", repaired, count=1, flags=re.IGNORECASE)
            kept_mentions += min(mention_count, max(0, 3 - kept_mentions))
        repaired_lines.append(repaired)
        repaired_zh_lines.append(zh_lines[index] if index < len(zh_lines) else script_voiceover_repair_zh(repaired, index, []))
    return repaired_lines, repaired_zh_lines


def normalized_line_signature(value: str) -> str:
    return re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", str(value).lower()).strip()


def rebuild_storyboard_from_script_spoken_copy(item: dict[str, Any], *, cta_zh: str) -> None:
    script = item.get("script")
    if not isinstance(script, dict):
        return
    script_lines = script_voiceover_lines_for_repair(script.get("voiceover"))
    zh_lines = script_voiceover_lines_for_repair(localized_zh_from_object(script).get("voiceover"))
    spoken_lines = script_spoken_lines_for_length(script_lines, str(script.get("cta") or ""))
    spoken_zh_lines = list(zh_lines)
    if str(script.get("cta") or "").strip():
        spoken_zh_lines.extend(split_script_voiceover(cta_zh))
    row_count = min(8, max(5, math.ceil(len(spoken_lines) / 2)))
    line_groups = distribute_line_indexes(len(spoken_lines), row_count)
    en_templates = mock_storyboard_template_en()
    zh_templates = mock_storyboard_template_zh()
    template_indexes = storyboard_template_indexes(row_count)
    storyboard: list[dict[str, Any]] = []
    for row_index, line_indexes in enumerate(line_groups, start=1):
        template_index = template_indexes[row_index - 1]
        shot = copy.deepcopy(en_templates[template_index])
        zh_template = zh_templates[template_index]
        voiceover = compact_join_text(spoken_lines[line_index] for line_index in line_indexes if line_index < len(spoken_lines))
        zh_voiceover = compact_join_text(
            spoken_zh_lines[line_index] if line_index < len(spoken_zh_lines) else script_voiceover_repair_zh(spoken_lines[line_index], line_index, [])
            for line_index in line_indexes
            if line_index < len(spoken_lines)
        )
        shot["shot_id"] = f"shot_{row_index}"
        shot["voiceover"] = voiceover
        shot["overlay"] = storyboard_overlay_for_template(template_index, localized=False)
        shot["bgm"] = "Light upbeat background rhythm kept under the creator voice."
        shot["sound_effects"] = compact_string_list([shot.get("sound")], max_items=3, max_chars=70)
        shot["subtitle_logic"] = "Use one short caption to name the beat; keep it under six words and synchronized with the voiceover emphasis."
        shot["visual_elements"] = mock_group_visual_elements(row_index, localized=False)
        shot["visual_element_logic"] = "Use the specific proof, workflow, check, or CTA element for this beat; do not add extra product claims."
        set_localized_zh(
            shot,
            {
                "camera": zh_template["camera"],
                "character_action": zh_template["character_action"],
                "facial_expression": zh_template["facial_expression"],
                "background": zh_template["background"],
                "props": zh_template["props"],
                "voiceover": zh_voiceover,
                "overlay": storyboard_overlay_for_template(template_index, localized=True),
                "sound": zh_template["sound"],
                "bgm": "轻快背景音乐保持低音量，不压过口播。",
                "sound_effects": ["点击音", "转场提示音"],
                "subtitle_logic": "每镜只用一句短字幕标记重点，跟随口播重音出现。",
                "visual_elements": mock_group_visual_elements(row_index, localized=True),
                "visual_element_logic": "只使用这一镜对应的证明、工作流、检查或 CTA 元素，不新增商品承诺。",
                "transition": zh_template["transition"],
                "purpose": zh_template["purpose"],
            },
        )
        storyboard.append(shot)
    item["storyboard"] = storyboard


def distribute_line_indexes(line_count: int, row_count: int) -> list[list[int]]:
    groups: list[list[int]] = []
    for row_index in range(row_count):
        start = round(row_index * line_count / row_count)
        end = round((row_index + 1) * line_count / row_count)
        groups.append(list(range(start, max(start + 1, end))))
    return groups


def storyboard_template_indexes(row_count: int) -> list[int]:
    base = [0, 2, 3, 4, 5, 6, 8, 9]
    if row_count >= len(base):
        return base[:row_count]
    if row_count == 5:
        return [0, 2, 3, 6, 9]
    if row_count == 6:
        return [0, 2, 3, 5, 6, 9]
    if row_count == 7:
        return [0, 2, 3, 4, 5, 6, 9]
    return base[:row_count]


def storyboard_overlay_for_template(template_index: int, *, localized: bool) -> str:
    english = {
        0: "5K+ creators",
        2: "Old way",
        3: "Open Moras",
        4: "Choose product",
        5: "Hit Generate",
        6: "Path visible",
        8: "Post smarter",
        9: "Make your own money",
    }
    chinese = {
        0: "5K+ 达人",
        2: "旧办法",
        3: "打开 Moras",
        4: "选商品",
        5: "点击 Generate",
        6: "带货路径可见",
        8: "直接出片",
        9: "赚自己的钱",
    }
    return (chinese if localized else english).get(template_index, "Check first" if not localized else "先检查")


def split_long_storyboard_rows(item: dict[str, Any]) -> None:
    storyboard = item.get("storyboard")
    if not isinstance(storyboard, list):
        return
    expanded: list[Any] = []
    shot_id_replacements: dict[str, list[str]] = {}
    for shot in storyboard:
        if not isinstance(shot, dict):
            expanded.append(shot)
            continue
        duration_sec = storyboard_row_duration_sec(shot)
        if duration_sec is None or duration_sec <= MAX_STORYBOARD_ROW_DURATION_SEC + 0.05:
            expanded.append(shot)
            continue
        old_shot_id = str(shot.get("shot_id") or f"shot_{len(expanded) + 1:02d}")
        voiceover_parts = split_storyboard_voiceover_into_parts(shot.get("voiceover"), min_parts=1)
        localized_zh = localized_zh_from_object(shot)
        zh_voiceover_parts = split_storyboard_voiceover_into_parts(
            localized_zh.get("voiceover") if isinstance(localized_zh, dict) else None,
            min_parts=1,
        )
        required_duration = storyboard_voiceover_min_duration_sec(str(shot.get("voiceover") or ""))
        part_count = max(
            2,
            math.ceil(duration_sec / MAX_STORYBOARD_ROW_DURATION_SEC),
            math.ceil(required_duration / MAX_STORYBOARD_ROW_DURATION_SEC),
            len(voiceover_parts),
            len(zh_voiceover_parts),
        )
        voiceover_parts = split_storyboard_voiceover_into_parts(shot.get("voiceover"), min_parts=part_count)
        zh_voiceover_parts = split_storyboard_voiceover_into_parts(
            localized_zh.get("voiceover") if isinstance(localized_zh, dict) else None,
            min_parts=part_count,
        )
        parsed_range = parse_time_range_seconds(first_present(shot.get("timestamp"), shot.get("time_range"), shot.get("timeRange")))
        split_ids: list[str] = []
        for part_index in range(part_count):
            split_shot = copy.deepcopy(shot)
            split_id = f"{old_shot_id}_part_{part_index + 1}"
            split_shot["shot_id"] = split_id
            split_shot["visual_elements"] = storyboard_split_visual_elements(
                split_shot.get("visual_elements"),
                part_index,
                localized=False,
            )
            split_ids.append(split_id)
            if parsed_range:
                start_sec, end_sec = split_range_part(parsed_range[0], parsed_range[1], part_index, part_count)
                split_shot["timestamp"] = format_time_range(start_sec, end_sec)
                if "time_range" in split_shot:
                    split_shot["time_range"] = split_shot["timestamp"]
                if "timeRange" in split_shot:
                    split_shot["timeRange"] = split_shot["timestamp"]
                split_shot["duration"] = f"{format_seconds(end_sec - start_sec)}s"
            else:
                split_shot["duration"] = f"{format_seconds(duration_sec / part_count)}s"
            if part_index < len(voiceover_parts) and voiceover_parts[part_index]:
                split_shot["voiceover"] = voiceover_parts[part_index]
            localized = split_shot.get("localized")
            split_zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
            if isinstance(split_zh, dict):
                split_zh["duration"] = f"{format_seconds(coerce_seconds(split_shot.get('duration')) or 0)}秒"
                if part_index < len(zh_voiceover_parts) and zh_voiceover_parts[part_index]:
                    split_zh["voiceover"] = zh_voiceover_parts[part_index]
                split_zh["visual_elements"] = storyboard_split_visual_elements(
                    split_zh.get("visual_elements"),
                    part_index,
                    localized=True,
                )
            expanded.append(split_shot)
        shot_id_replacements[old_shot_id] = split_ids
    item["storyboard"] = expanded
    expand_production_asset_plan_shot_ids(item.get("production_asset_plan"), shot_id_replacements)


def storyboard_split_visual_elements(value: Any, part_index: int, *, localized: bool) -> list[str]:
    if isinstance(value, list):
        elements = [str(item).strip() for item in value if str(item).strip()]
    elif str(value or "").strip():
        elements = [str(value).strip()]
    else:
        elements = []
    marker = f"分段 {part_index + 1} 重点" if localized else f"part {part_index + 1} focus"
    return [*elements, marker]


def localized_zh_from_object(value: dict[str, Any]) -> dict[str, Any]:
    localized = value.get("localized")
    zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
    return zh if isinstance(zh, dict) else {}


def split_storyboard_voiceover_into_parts(value: Any, *, min_parts: int) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    units = storyboard_voiceover_units(text)
    parts: list[str] = []
    current: list[str] = []
    for unit in units:
        candidate = compact_join_text([*current, unit])
        if current and (
            english_word_count(candidate) > MAX_STORYBOARD_VOICEOVER_ENGLISH_WORDS
            or sentence_chunk_count(candidate) > MAX_VOICEOVER_SENTENCE_CHUNKS
        ):
            parts.append(compact_join_text(current))
            current = [unit]
        else:
            current.append(unit)
    if current:
        parts.append(compact_join_text(current))
    while len(parts) < min_parts:
        split_index = longest_splittable_voiceover_part(parts)
        if split_index is None:
            break
        before, after = split_voiceover_part(parts[split_index])
        parts[split_index : split_index + 1] = [before, after]
    return [part for part in parts if part]


def storyboard_voiceover_units(text: str) -> list[str]:
    raw_units = [
        unit.strip()
        for unit in re.findall(r"[^.!?\u3002\uff01\uff1f]+(?:\.{3}|[.!?\u3002\uff01\uff1f]+)?", text)
        if unit.strip()
    ] or [text]
    units: list[str] = []
    for unit in raw_units:
        if english_word_count(unit) > MAX_STORYBOARD_VOICEOVER_ENGLISH_WORDS:
            units.extend(split_long_english_voiceover_unit(unit))
        elif storyboard_voiceover_min_duration_sec(unit) > MAX_STORYBOARD_ROW_DURATION_SEC:
            units.extend(split_long_voiceover_unit_by_duration(unit))
        else:
            units.append(unit)
    return units


def split_long_voiceover_unit_by_duration(text: str) -> list[str]:
    required_duration = storyboard_voiceover_min_duration_sec(text)
    if required_duration <= MAX_STORYBOARD_ROW_DURATION_SEC:
        return [text]
    part_count = max(2, math.ceil(required_duration / MAX_STORYBOARD_ROW_DURATION_SEC))
    tokens = text.split()
    if len(tokens) > 1:
        tokens_per_part = math.ceil(len(tokens) / part_count)
        return [
            " ".join(tokens[index : index + tokens_per_part]).strip()
            for index in range(0, len(tokens), tokens_per_part)
            if tokens[index : index + tokens_per_part]
        ]
    chars_per_part = math.ceil(len(text) / part_count)
    return [
        text[index : index + chars_per_part].strip()
        for index in range(0, len(text), chars_per_part)
        if text[index : index + chars_per_part].strip()
    ]


def split_long_english_voiceover_unit(text: str) -> list[str]:
    tokens = text.split()
    word_count = english_word_count(text)
    if word_count <= MAX_STORYBOARD_VOICEOVER_ENGLISH_WORDS or len(tokens) < 2:
        return [text]
    part_count = max(2, math.ceil(word_count / MAX_STORYBOARD_VOICEOVER_ENGLISH_WORDS))
    tokens_per_part = math.ceil(len(tokens) / part_count)
    return [
        " ".join(tokens[index : index + tokens_per_part]).strip()
        for index in range(0, len(tokens), tokens_per_part)
        if tokens[index : index + tokens_per_part]
    ]


def compact_join_text(parts: list[str]) -> str:
    return re.sub(r"\s+", " ", " ".join(part.strip() for part in parts if part.strip())).strip()


def longest_splittable_voiceover_part(parts: list[str]) -> int | None:
    candidates = [
        (index, english_word_count(part), len(part))
        for index, part in enumerate(parts)
        if len(part.split()) > 1 or len(part) > 1
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: (item[1], item[2]))[0]


def split_voiceover_part(text: str) -> tuple[str, str]:
    tokens = text.split()
    if len(tokens) > 1:
        midpoint = max(1, len(tokens) // 2)
        return " ".join(tokens[:midpoint]).strip(), " ".join(tokens[midpoint:]).strip()
    midpoint = max(1, len(text) // 2)
    return text[:midpoint].strip(), text[midpoint:].strip()


def split_range_part(start_sec: float, end_sec: float, part_index: int, part_count: int) -> tuple[float, float]:
    step = (end_sec - start_sec) / part_count
    part_start = round(start_sec + step * part_index, 2)
    part_end = round(start_sec + step * (part_index + 1), 2)
    return part_start, part_end


def expand_production_asset_plan_shot_ids(value: Any, replacements: dict[str, list[str]]) -> None:
    if not replacements or not isinstance(value, list):
        return
    for entry in value:
        if not isinstance(entry, dict):
            continue
        shot_ids = entry.get("shot_ids")
        if not isinstance(shot_ids, list):
            continue
        expanded: list[Any] = []
        for shot_id in shot_ids:
            expanded.extend(replacements.get(str(shot_id), [shot_id]))
        entry["shot_ids"] = expanded


def text_from_script_scalar(value: Any) -> str:
    if isinstance(value, list):
        return compact_text(" ".join(compact_text(item, 240) for item in value if compact_text(item, 240)), 900)
    return compact_text(value, 900)


def split_script_voiceover(value: Any) -> list[str]:
    text = compact_text(value, 1600)
    if not text:
        return []
    pieces = [piece.strip() for piece in re.findall(r"[^.!?。！？]+[.!?。！？]?", text) if piece.strip()]
    return pieces or [text]


def normalize_production_asset_layer(value: Any, asset_type: str) -> str:
    layer = re.sub(r"[-\s]+", "_", str(value or "").strip().lower())
    if layer in PRODUCTION_ASSET_LAYER_ALIASES:
        return PRODUCTION_ASSET_LAYER_ALIASES[layer]
    if any(token in layer for token in ("overlay", "caption", "subtitle", "text", "top", "foreground", "highlight")):
        return "overlay"
    if any(token in layer for token in ("audio", "sound", "music", "sfx")):
        return "audio"
    if any(token in layer for token in ("cutaway", "screen", "recording", "screenshot", "ui")):
        return "cutaway"
    if any(token in layer for token in ("base", "creator", "avatar", "live")):
        return "base_track"
    if asset_type == "sound_design":
        return "audio"
    if asset_type == "post_production_overlay":
        return "overlay"
    if asset_type in REAL_MORAS_ASSET_TYPES:
        return "cutaway"
    if asset_type in {"digital_human_avatar", "live_creator_footage"}:
        return "base_track"
    return str(value or "").strip()


def normalize_production_asset_category(value: Any, asset_type: str) -> str:
    fallback = PRODUCTION_ASSET_FALLBACK_CATEGORIES.get(asset_type, "none")
    text = str(value or "").strip()
    placeholder = text.strip(" .。").lower()
    if placeholder in {"", "n/a", "na", "none", "null", "not_applicable", "not applicable", "无", "不适用", "没有"}:
        return fallback
    normalized = re.sub(r"[-\s]+", "_", text.lower())
    if normalized in MORAS_ASSET_CATEGORIES:
        return normalized
    return text


def repair_storyboard_for_schema(item: dict[str, Any]) -> dict[str, Any]:
    creator_persona = item.get("creator_persona")
    for index, shot in enumerate(item.get("storyboard") or [], start=1):
        if not isinstance(shot, dict):
            continue
        shot["voiceover"] = normalize_storyboard_voiceover(shot.get("voiceover"))
        repair_storyboard_detail_with_localized_zh(
            shot,
            "facial_expression",
            default_storyboard_expression(creator_persona),
            "创作者保持专注、略带担忧，视线跟随商品工作流，手势强调关键步骤。",
        )
        repair_storyboard_detail_with_localized_zh(
            shot,
            "background",
            default_storyboard_background(shot, creator_persona),
            "竖屏创作者工作流场景，画面清楚展示当前步骤、界面状态和相关道具。",
        )
        repair_storyboard_detail_with_localized_zh(
            shot,
            "camera",
            "Vertical medium-close smartphone framing, stable handheld movement, clear face-and-hands composition.",
            "竖屏中近景手机构图，稳定手持移动，清楚呈现脸部、手部和操作重点。",
            minimum_words=3,
            minimum_cjk_chars=6,
        )
        repair_storyboard_detail_with_localized_zh(
            shot,
            "character_action",
            action_with_creator_persona(f"performs the planned beat for shot {index}", creator_persona),
            f"创作者完成第 {index} 镜的计划动作，并用手势或屏幕操作强调当前叙事重点。",
        )
        align_storyboard_contrast_visual(shot)
    return item


def repair_storyboard_detail_with_localized_zh(
    shot: dict[str, Any],
    field_name: str,
    fallback: str,
    zh_fallback: str,
    *,
    minimum_words: int = 8,
    minimum_cjk_chars: int = 12,
) -> None:
    original = shot.get(field_name)
    original_had_detail = has_storyboard_detail(
        str(original or ""),
        minimum_words=minimum_words,
        minimum_cjk_chars=minimum_cjk_chars,
    )
    repaired = ensure_storyboard_detail(
        original,
        fallback,
        minimum_words=minimum_words,
        minimum_cjk_chars=minimum_cjk_chars,
    )
    shot[field_name] = repaired
    if original_had_detail:
        return
    localized = shot.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        shot["localized"] = localized
    zh = localized.get(LOCALIZED_LANGUAGE_KEY)
    if not isinstance(zh, dict):
        zh = {}
        localized[LOCALIZED_LANGUAGE_KEY] = zh
    current_zh = str(zh.get(field_name) or "").strip()
    if not has_cjk(current_zh) or normalized_localization_value(current_zh) == normalized_localization_value(repaired):
        zh[field_name] = zh_fallback


def storyboard_row_duration_sec(shot: dict[str, Any]) -> float | None:
    parsed_range = parse_time_range_seconds(first_present(shot.get("timestamp"), shot.get("time_range"), shot.get("timeRange")))
    if parsed_range:
        return parsed_range[1] - parsed_range[0]
    return coerce_seconds(shot.get("duration"))


def normalize_storyboard_voiceover(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return "Notice the workflow change in this moment."
    return text


def apply_persona_operating_contract_to_mock_script(item: dict[str, Any], selected_persona: dict[str, Any] | None) -> None:
    if not isinstance(selected_persona, dict):
        return
    persona_type = str(selected_persona.get("persona_type") or "").strip()
    role_task = str(selected_persona.get("role_task") or "").strip()
    proof_policy = str(selected_persona.get("proof_policy") or "").strip()
    problem = selected_persona.get("target_problem_profile") if isinstance(selected_persona.get("target_problem_profile"), dict) else {}
    scenes = selected_persona.get("recurring_scenes") if isinstance(selected_persona.get("recurring_scenes"), list) else []
    scene_pair = selected_persona.get("persona_scene_pair") if isinstance(selected_persona.get("persona_scene_pair"), dict) else {}
    primary_scene = str(scene_pair.get("primary_scene") or (scenes[0] if scenes else "")).strip()
    explicit_pains = [str(item).strip() for item in problem.get("explicit_pains", []) if str(item).strip()] if isinstance(problem, dict) else []
    inner_conflict = str(problem.get("inner_conflict") or "").strip() if isinstance(problem, dict) else ""
    desired_state = str(problem.get("desired_state") or "").strip() if isinstance(problem, dict) else ""
    handoff = selected_persona.get("script_agent_handoff") if isinstance(selected_persona.get("script_agent_handoff"), dict) else {}
    forbidden_claims = [str(item).strip() for item in handoff.get("forbidden_claims", []) if str(item).strip()] if isinstance(handoff, dict) else []

    topic_plan = item.get("topic_plan") if isinstance(item.get("topic_plan"), dict) else {}
    script = item.get("script") if isinstance(item.get("script"), dict) else {}
    if persona_type:
        topic_plan["target_audience"] = persona_type
        script["target_audience"] = persona_type
    if role_task:
        topic_plan["content_angle"] = f"{role_task} Use this concept through a creator-native TikTok Shop moment."
    if explicit_pains:
        script["core_pain"] = f"{explicit_pains[0]}. {inner_conflict}".strip()
    if desired_state:
        script["emotional_angle"] = desired_state
    if proof_policy:
        script["proof_insert"] = sanitize_persona_prompt_text(proof_policy)
    compliance_parts = [str(script.get("compliance_note") or "").strip()]
    if forbidden_claims:
        compliance_parts.append(f"Forbidden selected-persona claims: {', '.join(forbidden_claims[:5])}.")
    script["compliance_note"] = " ".join(part for part in compliance_parts if part)
    if primary_scene:
        first_shot = item.get("storyboard", [{}])[0] if isinstance(item.get("storyboard"), list) and item.get("storyboard") else None
        if isinstance(first_shot, dict):
            first_shot["background"] = f"{primary_scene}; {first_shot.get('background', '')}".strip()


def ensure_storyboard_detail(
    value: Any,
    fallback: str,
    *,
    minimum_words: int = 8,
    minimum_cjk_chars: int = 12,
) -> str:
    text = str(value or "").strip()
    if has_storyboard_detail(text, minimum_words=minimum_words, minimum_cjk_chars=minimum_cjk_chars):
        return text
    if text:
        return f"{text}，{fallback}"
    return fallback


def has_storyboard_detail(value: str, *, minimum_words: int, minimum_cjk_chars: int) -> bool:
    text = str(value or "").strip()
    if not text:
        return False
    cjk_chars = re.findall(r"[\u3400-\u9fff]", text)
    if cjk_chars:
        return len(cjk_chars) >= minimum_cjk_chars
    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", text)
    return len(words) >= minimum_words


def default_storyboard_expression(creator_persona: Any) -> str:
    name = persona_display_name(creator_persona) or "The creator"
    return f"{name} stays focused and lightly concerned, with eyes tracking the product workflow and subtle hand-led emphasis."


def default_storyboard_background(shot: dict[str, Any], creator_persona: Any) -> str:
    props = props_text(shot.get("props"))
    name = persona_display_name(creator_persona) or "the creator"
    if props:
        return f"Realistic compact creator desk around {name}, soft daylight, neutral home-office background, {props} visible and arranged for the workflow beat."
    return f"Realistic compact creator desk around {name}, soft daylight, neutral home-office background, laptop, phone, notes, and product page within frame."


def align_storyboard_contrast_visual(shot: dict[str, Any]) -> None:
    voiceover = str(shot.get("voiceover") or "")
    lowered_voiceover = voiceover.lower()
    has_contrast = (
        ("before" in lowered_voiceover and ("now" in lowered_voiceover or "after" in lowered_voiceover))
        or ("以前" in voiceover and ("现在" in voiceover or "之后" in voiceover or "如今" in voiceover))
    )
    if not has_contrast:
        return
    visual_text = " ".join(str(shot.get(key) or "") for key in ("character_action", "background", "camera")).lower()
    if any(term in visual_text for term in ("now", "after", "switch", "comparison", "clean", "moras", "现在", "切换", "对比", "变成", "干净")):
        return
    shot["character_action"] = (
        f"{shot.get('character_action')} The action visibly switches from the old messy workflow to the cleaner current Moras workflow."
    )
    shot["background"] = (
        f"{shot.get('background')} A clear before-and-now comparison is visible between scattered notes and the organized Moras workspace."
    )


def ensure_script_hook_candidates(topic_plan: dict[str, Any], script: dict[str, Any]) -> None:
    candidates = topic_plan.get("hook_candidates")
    if not isinstance(candidates, list):
        candidates = []
    normalized_candidates = [str(candidate).strip() for candidate in candidates if str(candidate).strip()]
    labels = {
        candidate.split("]", 1)[0].strip().lower() + "]"
        for candidate in normalized_candidates
        if candidate.strip().startswith("[") and "]" in candidate
    }
    attention_labels = {
        "[absurd visual]",
        "[curiosity gap]",
        "[psychological trigger]",
        "[relatable weirdness]",
        "[pov]",
        "[open loop]",
        "[mini drama]",
        "[funny overstatement]",
        "[unexpected analogy]",
        "[story opener]",
        "[empathy]",
    }
    if len(normalized_candidates) >= 6 and len(labels) >= 4 and len(labels & attention_labels) >= 4:
        topic_plan["hook_candidates"] = normalized_candidates
        return

    topic_plan["hook_candidates"] = [
        "[Mini Drama] I opened the camera, stared at the product, and closed it again.",
        "[Absurd Visual] My blank phone screen looked like it was judging me.",
        "[Curiosity Gap] The weird part isn't the camera. It's not knowing what the product should prove.",
        "[POV] POV: you found a product at midnight and your brain opened 47 tabs.",
        "[Mini Drama] I had the product. I had the camera. I had absolutely nothing to say.",
        "[Psychological Trigger] The fastest way to waste a day is picking a product you can't explain.",
    ]


def ensure_chinese_localizations(item: dict[str, Any]) -> dict[str, Any]:
    ensure_localized_object(item.get("topic_plan"), LOCALIZED_OBJECT_FIELDS["topic_plan"])
    ensure_localized_object(item.get("script"), LOCALIZED_OBJECT_FIELDS["script"])
    for shot in item.get("storyboard") or []:
        ensure_localized_object(shot, LOCALIZED_OBJECT_FIELDS["storyboard"])
    ensure_localized_object(item.get("creator_persona"), LOCALIZED_OBJECT_FIELDS["creator_persona"])
    video_prompt = item.get("video_prompt")
    ensure_localized_object(video_prompt, LOCALIZED_OBJECT_FIELDS["video_prompt"])
    if isinstance(video_prompt, dict):
        for segment in video_prompt.get("segments") or []:
            ensure_localized_object(segment, LOCALIZED_OBJECT_FIELDS["video_prompt_segments"])
    for entry in item.get("production_asset_plan") or []:
        ensure_localized_object(entry, LOCALIZED_OBJECT_FIELDS["production_asset_plan"])
    return item


SCRIPT_AGENT_REQUIRED_ZH_FIELDS = {
    "topic_plan": [
        "title",
        "target_audience",
        "content_angle",
        "trend_source",
        "template",
        "persona",
        "hook_candidates",
        "cta_candidates",
    ],
    "script": [
        "script_title",
        "target_audience",
        "persona",
        "template",
        "core_pain",
        "emotional_angle",
        "hook",
        "voiceover",
        "visual",
        "overlay",
        "sound_effect",
        "proof_insert",
        "cta",
        "compliance_note",
    ],
    "storyboard": [
        "camera",
        "character_action",
        "facial_expression",
        "background",
        "props",
        "voiceover",
        "overlay",
        "sound",
        "bgm",
        "sound_effects",
        "subtitle_logic",
        "visual_elements",
        "visual_element_logic",
        "transition",
        "purpose",
    ],
    "production_asset_plan": [
        "usage_reason",
        "editor_note",
    ],
}


def validate_script_agent_chinese_localizations(item: dict[str, Any]) -> None:
    validate_required_zh_object(item.get("topic_plan"), "topic_plan", SCRIPT_AGENT_REQUIRED_ZH_FIELDS["topic_plan"])
    validate_required_zh_object(item.get("script"), "script", SCRIPT_AGENT_REQUIRED_ZH_FIELDS["script"])
    for index, shot in enumerate(item.get("storyboard") or [], start=1):
        validate_required_zh_object(shot, f"storyboard[{index}]", SCRIPT_AGENT_REQUIRED_ZH_FIELDS["storyboard"])
    for index, entry in enumerate(item.get("production_asset_plan") or [], start=1):
        validate_required_zh_object(
            entry,
            f"production_asset_plan[{index}]",
            SCRIPT_AGENT_REQUIRED_ZH_FIELDS["production_asset_plan"],
        )


def validate_required_zh_object(value: Any, path: str, field_names: list[str]) -> None:
    if not isinstance(value, dict):
        return
    localized = value.get("localized")
    zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
    if not isinstance(zh, dict):
        raise invalid_script_localization(f"{path}.localized.zh", "is required")
    for field_name in field_names:
        source = value.get(field_name)
        if is_empty_localization_source(source):
            continue
        zh_value = zh.get(field_name)
        field_path = f"{path}.localized.zh.{field_name}"
        if is_empty_localization_source(zh_value):
            raise invalid_script_localization(field_path, "is required when the source field is present")
        if not value_contains_cjk(zh_value):
            raise invalid_script_localization(field_path, "must contain Chinese CJK characters")
        if normalized_localization_value(zh_value) == normalized_localization_value(source):
            raise invalid_script_localization(field_path, "must not be identical to the source field")


def invalid_script_localization(path: str, reason: str) -> Exception:
    return unprocessable("SCRIPT_OUTPUT_SCHEMA_INVALID", f"{path} {reason}")


def is_empty_localization_source(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str):
        return not value.strip()
    if isinstance(value, list):
        return not any(not is_empty_localization_source(item) for item in value)
    if isinstance(value, dict):
        return not any(not is_empty_localization_source(item) for item in value.values())
    return False


def value_contains_cjk(value: Any) -> bool:
    if isinstance(value, str):
        return has_cjk(value)
    if isinstance(value, list):
        return any(value_contains_cjk(item) for item in value)
    if isinstance(value, dict):
        return any(value_contains_cjk(item) for item in value.values())
    return False


def normalized_localization_value(value: Any) -> str:
    if isinstance(value, str):
        return " ".join(value.strip().split())
    if isinstance(value, list):
        return json.dumps([normalized_localization_value(item) for item in value], ensure_ascii=False)
    if isinstance(value, dict):
        normalized = {key: normalized_localization_value(value[key]) for key in sorted(value)}
        return json.dumps(normalized, ensure_ascii=False, sort_keys=True)
    return str(value).strip()


def ensure_localized_object(value: Any, field_names: list[str]) -> None:
    if not isinstance(value, dict):
        return
    localized = value.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        value["localized"] = localized
    zh = localized.get(LOCALIZED_LANGUAGE_KEY)
    if not isinstance(zh, dict):
        zh = {}
        localized[LOCALIZED_LANGUAGE_KEY] = zh
    for field_name in field_names:
        if zh.get(field_name):
            continue
        source = value.get(field_name)
        if isinstance(source, list):
            translated_items = [localize_to_chinese(item) for item in source if item is not None]
            if translated_items:
                zh[field_name] = translated_items
        elif source is not None:
            translated = localize_to_chinese(source)
            if translated:
                zh[field_name] = translated


def localize_to_chinese(value: Any) -> str:
    text = str(value).strip()
    if not text:
        return ""
    if has_cjk(text):
        return text
    exact = EXACT_CHINESE_LOCALIZATIONS.get(text)
    if exact:
        return exact
    if " / " in text:
        parts = [localize_to_chinese(part) for part in text.split(" / ")]
        if any(has_cjk(part) for part in parts):
            return " / ".join(parts)
    translated = text
    for english, chinese in PHRASE_CHINESE_LOCALIZATIONS:
        translated = translated.replace(english, chinese)
    exact_after_phrase = EXACT_CHINESE_LOCALIZATIONS.get(translated)
    if exact_after_phrase:
        return exact_after_phrase
    return translated


def has_cjk(value: str) -> bool:
    return bool(re.search(r"[\u3400-\u9fff]", value))


def default_creator_persona(
    script: dict[str, Any],
    topic_plan: dict[str, Any],
    *,
    variant_index: int | None = None,
    excluded_names: set[str] | None = None,
    seed: str | None = None,
) -> dict[str, Any]:
    seed = seed or "|".join(
        [
            str(topic_plan.get("title") or ""),
            str(script.get("script_title") or ""),
            str(script.get("persona") or topic_plan.get("persona") or ""),
        ]
    )
    return default_creator_persona_payload(
        script,
        topic_plan,
        seed=seed,
        variant_index=variant_index,
        excluded_names=excluded_names,
    )


def normalized_selected_creator_persona(request: ScriptGenerationRequest) -> dict[str, Any] | None:
    persona_hint = normalize_persona_key_style(request.persona_hint) if isinstance(request.persona_hint, dict) else {}
    if not persona_hint:
        return None
    topic_plan = {
        "title": "Selected creator persona",
        "target_audience": "Moras creator operators",
        "persona": creator_persona_label(persona_hint),
    }
    script = {
        "script_title": "Selected creator persona",
        "persona": creator_persona_label(persona_hint),
    }
    persona = normalize_creator_persona_payload(
        persona_hint,
        topic_plan,
        script,
        seed=request.persona_id or persona_display_name(persona_hint),
    )
    return persona


PERSONA_PROMPT_STYLE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\btry it if you are tired of doing it the hard way\.?\s*link is right there\.?", "Save this for the next product."),
    (r"\bMoras workflow generat(?:e|ing|es) (?:a )?video draft in minutes\b", "Moras product selection/Create video workflow"),
    (r"\bgenerat(?:e|ing|es) (?:a )?video draft in minutes\b", "create a video draft to review"),
    (r"\bdoing it the hard way\b", "starting from a blank page"),
    (r"\blink is right there\b", "save this for the next product"),
    (r"\bcheat code\b", "product-to-video workflow"),
    (r"\bcomplete product video drafts?\b", "AI-generated video drafts for review"),
    (r"\bfull video drafts?\b", "AI-generated video drafts for review"),
    (r"\bscript and visuals already mapped out\b", "video draft ready for creator review"),
    (r"\bin minutes\b", "through the approved Generate workflow"),
    (r"\bprove (?:me|her|him|them) wrong\b", "compare it against your own product"),
    (r"\btry it out\b", "save it for the next product"),
    (r"\bgenerates? video drafts without samples\b", "creates video drafts from selected products"),
    (r"\bno[- ]sample testing\b", "product-to-video posting workflow"),
    (r"\bsample[- ]free angle\b", "product-to-video angle"),
    (r"\bwithout samples\b", "from selected products"),
    (r"\bbuy samples\b", "start from zero"),
    (r"\bbuy sample\b", "start from zero"),
    (r"\bsample box\b", "product notes"),
    (r"\bsamples\b", "blank drafts"),
    (r"\bsample\b", "blank draft"),
    (r"\bproduct tests\b", "product promotion videos"),
    (r"\bproduct testing\b", "product promotion"),
    (r"\btesting system\b", "posting system"),
    (r"\btesting routine\b", "posting routine"),
    (r"\btest honestly\b", "promote clearly"),
    (r"\btest which\b", "decide which"),
    (r"\bto test\b", "to promote"),
    (r"\bgenerat(?:e|ing|es) (?:a )?video draft\b", "create a video draft"),
    (r"\bhands you a first draft\b", "gives you a video draft to review"),
    (r"\bprepare a rough first pass as a rough first pass\b", "create a video draft to review"),
    (r"零样品测试", "商品到视频发布流程"),
    (r"无样品", "商品到视频"),
    (r"样品盒", "商品便签"),
    (r"买样品", "从零开始"),
    (r"样品", "商品"),
    (r"测试流程", "发布流程"),
    (r"测试系统", "发布系统"),
    (r"测试", "发布"),
)


def sanitize_persona_prompt_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    cleaned = text
    for pattern, replacement in PERSONA_PROMPT_STYLE_REPLACEMENTS:
        cleaned = re.sub(pattern, replacement, cleaned, flags=re.IGNORECASE)
    return " ".join(cleaned.split()).strip()


def sanitize_compact_persona_prompt_value(value: Any) -> Any:
    if isinstance(value, str):
        return sanitize_persona_prompt_text(value)
    if isinstance(value, list):
        return [item for item in (sanitize_compact_persona_prompt_value(child) for child in value) if item not in ("", [], {})]
    if isinstance(value, dict):
        return {
            key: child
            for key, child in ((key, sanitize_compact_persona_prompt_value(child)) for key, child in value.items())
            if child not in ("", [], {})
        }
    return value


def compact_persona_for_prompt(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    normalized = normalize_persona_key_style(value)
    ensure_digital_human_prompt_assets(normalized)
    field_limits = {
        "persona_id": 80,
        "display_name": 80,
        "persona_type": 60,
        "role_task": 220,
        "audience_callout": 180,
        "proof_policy": 220,
        "role": 120,
        "demographic": 160,
        "creator_background": 220,
        "personality": 140,
        "trust_stance": 180,
        "speech_style": 180,
        "appearance": 220,
        "face_hair_makeup": 220,
        "wardrobe": 220,
        "styling_details": 160,
        "distinctive_marks_or_tattoos": 120,
        "veo_identity_string": 260,
        "reference_image_prompt": 360,
    }
    compact: dict[str, Any] = {}
    for key, max_chars in field_limits.items():
        text = compact_text(normalized.get(key), max_chars)
        if text:
            compact[key] = text
    compact["target_problem_profile"] = compact_persona_object(
        normalized.get("target_problem_profile"),
        {
            "explicit_pains": ("list", 4, 80),
            "inner_conflict": ("text", 180),
            "desired_state": ("text", 180),
        },
    )
    compact["trust_basis"] = compact_persona_object(
        normalized.get("trust_basis"),
        {
            "primary_trust_angle": ("text", 180),
            "usable_proof_assets": ("list", 4, 90),
            "proof_insertion_rule": ("text", 220),
        },
    )
    compact["persona_scene_pair"] = compact_persona_object(
        normalized.get("persona_scene_pair"),
        {
            "primary_scene": ("text", 90),
            "secondary_scenes": ("list", 3, 90),
            "scene_logic": ("text", 180),
        },
    )
    compact["memory_symbols"] = compact_persona_object(
        normalized.get("memory_symbols"),
        {
            "fixed_opening_pattern": ("text", 120),
            "visual_anchor": ("text", 120),
            "recurring_prop": ("text", 100),
            "wardrobe_anchor": ("text", 100),
            "column_name": ("text", 80),
        },
    )
    compact["endorsement_boundary"] = compact_persona_object(
        normalized.get("endorsement_boundary"),
        {
            "allowed_claims": ("list", 4, 90),
            "banned_claims": ("list", 8, 70),
            "experience_rule": ("text", 220),
        },
    )
    compact["persona_quality_score"] = compact_persona_object(
        normalized.get("persona_quality_score"),
        {
            "score": ("raw",),
            "review_notes": ("list", 2, 120),
        },
    )
    compact["script_agent_handoff"] = compact_persona_object(
        normalized.get("script_agent_handoff"),
        {
            "primary_directive": ("text", 220),
            "opening_scene_rules": ("list", 3, 120),
            "hook_rules": ("list", 3, 120),
            "proof_asset_rules": ("list", 3, 130),
            "forbidden_claims": ("list", 8, 70),
            "cta_rule": ("text", 140),
            "compliance_note_rule": ("text", 160),
        },
    )
    compact["digital_human_prompt_assets"] = compact_persona_object(
        normalized.get("digital_human_prompt_assets"),
        {
            "visual_reference_prompt": ("text", 360),
            "avatar_motion_prompt": ("text", 420),
            "voice_style_prompt": ("text", 320),
            "script_delivery_rules": ("list", 5, 150),
            "sample_requirement": ("raw",),
            "synthetic_disclosure_note": ("text", 180),
            "keep_consistent": ("list", 5, 120),
            "avoid": ("list", 5, 120),
        },
    )
    compact["recurring_scenes"] = compact_string_list(normalized.get("recurring_scenes"), max_items=4, max_chars=90)
    compact["content_pillars"] = compact_string_list(normalized.get("content_pillars"), max_items=5, max_chars=80)
    compact["hobbies_interests"] = compact_string_list(normalized.get("hobbies_interests"), max_items=4, max_chars=80)
    compact["props"] = compact_string_list(normalized.get("props"), max_items=4, max_chars=80)
    compact["consistency_rules"] = compact_string_list(normalized.get("consistency_rules"), max_items=4, max_chars=100)
    compact.pop("cta_style", None)
    handoff = compact.get("script_agent_handoff")
    if isinstance(handoff, dict):
        handoff["proof_asset_rules"] = [
            "Show the real Moras product library, product selection/Generate workflow, video output, visible commerce path, and approved creator proof screenshots.",
            "Frame GMV, income, follower, or time numbers as approved proof screenshots/testimonials, never as guaranteed results.",
        ]
        handoff["cta_rule"] = "Use a direct creator-ad CTA such as click the button or click the left-corner button, without promising fixed income."
    sanitized = sanitize_compact_persona_prompt_value(compact)
    return {key: value for key, value in sanitized.items() if value not in (None, "", [], {})}


def compact_persona_object(value: Any, spec: dict[str, tuple[Any, ...]]) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    output: dict[str, Any] = {}
    for key, rule in spec.items():
        mode = rule[0]
        if mode == "text":
            text = compact_text(value.get(key), int(rule[1]))
            if text:
                output[key] = text
        elif mode == "list":
            items = compact_string_list(value.get(key), max_items=int(rule[1]), max_chars=int(rule[2]))
            if items:
                output[key] = items
        elif mode == "raw":
            child = value.get(key)
            if child not in (None, "", [], {}):
                output[key] = child
    return output


def normalize_persona_key_style(value: dict[str, Any]) -> dict[str, Any]:
    aliases = {
        "personaId": "persona_id",
        "displayName": "display_name",
        "personaType": "persona_type",
        "roleTask": "role_task",
        "audienceCallout": "audience_callout",
        "targetProblemProfile": "target_problem_profile",
        "trustBasis": "trust_basis",
        "proofPolicy": "proof_policy",
        "personaScenePair": "persona_scene_pair",
        "recurringScenes": "recurring_scenes",
        "memorySymbols": "memory_symbols",
        "contentPillars": "content_pillars",
        "hookPreferences": "hook_preferences",
        "ctaStyle": "cta_style",
        "endorsementBoundary": "endorsement_boundary",
        "personaQualityScore": "persona_quality_score",
        "scriptAgentHandoff": "script_agent_handoff",
        "creatorBackground": "creator_background",
        "trustStance": "trust_stance",
        "speechStyle": "speech_style",
        "hobbiesInterests": "hobbies_interests",
        "faceHairMakeup": "face_hair_makeup",
        "stylingDetails": "styling_details",
        "distinctiveMarksOrTattoos": "distinctive_marks_or_tattoos",
        "consistencyRules": "consistency_rules",
        "veoIdentityString": "veo_identity_string",
        "referenceImagePrompt": "reference_image_prompt",
        "digitalHumanPromptAssets": "digital_human_prompt_assets",
    }
    normalized: dict[str, Any] = {}
    for key, child in value.items():
        normalized_key = aliases.get(key, key)
        normalized[normalized_key] = child
    return normalized


def apply_creator_persona_instruction(persona: dict[str, Any], instruction: str) -> dict[str, Any]:
    updated = dict(persona)
    instruction = " ".join(str(instruction).split())
    if not instruction:
        return updated
    current_rules = updated.get("consistency_rules")
    rules = [str(item) for item in current_rules] if isinstance(current_rules, list) else []
    edit_rule = f"AI edit note: {instruction[:180]}"
    if edit_rule not in rules:
        rules.append(edit_rule)
    updated["consistency_rules"] = rules[-6:]
    localized = updated.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        updated["localized"] = localized
    zh = localized.get(LOCALIZED_LANGUAGE_KEY)
    if not isinstance(zh, dict):
        zh = {}
        localized[LOCALIZED_LANGUAGE_KEY] = zh
    zh_rules = zh.get("consistency_rules")
    zh_rule_list = [str(item) for item in zh_rules] if isinstance(zh_rules, list) else []
    zh_edit_rule = f"AI 编辑备注：{instruction[:120]}"
    if zh_edit_rule not in zh_rule_list:
        zh_rule_list.append(zh_edit_rule)
    zh["consistency_rules"] = zh_rule_list[-6:]
    return updated


def persona_display_name(creator_persona: Any) -> str:
    if not isinstance(creator_persona, dict):
        return ""
    return str(creator_persona.get("display_name") or "").strip()


def persona_role(creator_persona: Any) -> str:
    if not isinstance(creator_persona, dict):
        return ""
    return str(creator_persona.get("role") or "").strip()


def creator_persona_label(creator_persona: Any) -> str:
    display_name = persona_display_name(creator_persona)
    role = persona_role(creator_persona)
    if display_name and role and display_name.lower() not in role.lower():
        return f"{display_name} - {role}"
    return display_name or role or "Creator"


def creator_persona_label_zh(creator_persona: Any) -> str:
    if not isinstance(creator_persona, dict):
        return "创作者"
    localized = creator_persona.get("localized")
    zh = localized.get("zh") if isinstance(localized, dict) and isinstance(localized.get("zh"), dict) else {}
    display_name = str(zh.get("display_name") or creator_persona.get("display_name") or "").strip()
    role = str(zh.get("role") or creator_persona.get("role") or "").strip()
    if display_name and role and display_name not in role:
        label = f"{display_name} - {role}"
    else:
        label = display_name or role or "创作者"
    if has_cjk(label):
        return label
    if display_name:
        return f"{display_name} - 创作者"
    return "创作者"


def sync_script_item_to_creator_persona(item: dict[str, Any], *, force: bool = False) -> dict[str, Any]:
    creator_persona = item.get("creator_persona")
    label = creator_persona_label(creator_persona)
    zh_label = creator_persona_label_zh(creator_persona)
    for key in ("topic_plan", "script"):
        value = item.get(key)
        if not isinstance(value, dict):
            continue
        if force or persona_field_needs_sync(value.get("persona"), creator_persona):
            value["persona"] = label
        localized = value.get("localized")
        if not isinstance(localized, dict):
            localized = {}
            value["localized"] = localized
        zh = localized.get(LOCALIZED_LANGUAGE_KEY)
        if not isinstance(zh, dict):
            zh = {}
            localized[LOCALIZED_LANGUAGE_KEY] = zh
        if force or persona_field_needs_sync(zh.get("persona"), creator_persona):
            zh["persona"] = zh_label
    for shot in item.get("storyboard") or []:
        if not isinstance(shot, dict):
            continue
        action = first_present(
            shot.get("character_action"),
            shot.get("action"),
            nested_zh_value(shot, "character_action"),
            nested_zh_value(shot, "action"),
            "",
        )
        if force or storyboard_action_needs_sync(str(action), creator_persona):
            shot["character_action"] = action_with_creator_persona(str(action), creator_persona)
        localized = shot.get("localized")
        if not isinstance(localized, dict):
            localized = {}
            shot["localized"] = localized
        zh = localized.get(LOCALIZED_LANGUAGE_KEY)
        if not isinstance(zh, dict):
            zh = {}
            localized[LOCALIZED_LANGUAGE_KEY] = zh
        zh_action = str(zh.get("character_action") or "")
        if force or storyboard_action_needs_sync(zh_action, creator_persona):
            fallback_action = first_present(shot.get("character_action"), shot.get("action"), action)
            zh["character_action"] = (
                action_with_creator_persona(zh_action, creator_persona)
                if zh_action
                else localize_to_chinese(fallback_action)
            )
    return item


def persona_field_needs_sync(value: Any, creator_persona: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    return prompt_contains_stale_identity(text)


def storyboard_action_needs_sync(value: str, creator_persona: Any) -> bool:
    text = str(value or "").strip()
    if not text:
        return True
    display_name = persona_display_name(creator_persona)
    if prompt_contains_stale_identity(text):
        return True
    return bool(display_name and re.search(r"\bcreator\b|创作者", text, re.IGNORECASE) and display_name.lower() not in text.lower())


def prompt_contains_stale_identity(value: str) -> bool:
    lowered = str(value or "").lower()
    stale_terms = [
        "efficiency expert",
        "same young creator",
        "young creator",
        "male creator",
        "female creator",
        "asian creator",
        "asian female",
        "mia chen",
    ]
    if any(term in lowered for term in stale_terms):
        return True
    return any(term in value for term in ["男性创作者", "女性创作者", "亚洲", "米娅"])


def nested_zh_value(value: dict[str, Any], field_name: str) -> Any:
    localized = value.get("localized")
    zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
    if isinstance(zh, dict):
        return zh.get(field_name)
    return None


def action_with_creator_persona(action: str, creator_persona: Any) -> str:
    display_name = persona_display_name(creator_persona) or "The creator"
    cleaned = sanitize_identity_fragment(action)
    cleaned = cleaned.replace("创作者", display_name)
    cleaned = re.sub(r"\bthe creator\b", display_name, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bcreator\b", display_name, cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:，。；：")
    if not cleaned:
        return f"{display_name} works at the creator desk with natural hand movement and a grounded expression."
    if display_name.lower() in cleaned.lower():
        return cleaned
    if has_cjk(cleaned):
        return f"{display_name} performs this beat: {cleaned}"
    return f"{display_name} {cleaned[:1].lower()}{cleaned[1:]}"


def sanitize_identity_fragment(value: str) -> str:
    cleaned = str(value or "")
    cleaned = re.sub(r"一位\s*\d+\s*岁[^，。；;]*(男性|女性|亚洲|亞裔|女创作者|男创作者)[^，。；;]*[，,]?", "", cleaned)
    cleaned = re.sub(r"\b(?:a|an|one)?\s*\d{2}-year-old\s+[^,.;]*(?:male|female|asian)[^,.;]*[,.;]?", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:male|female|asian)\s+creator\b", "creator", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\b(?:young|same young|middle-aged)\s+creator\b", "creator", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bEfficiency Expert\b", "creator", cleaned, flags=re.IGNORECASE)
    for old in ["男性创作者", "女性创作者", "亚洲女性创作者", "亚洲创作者", "亞裔創作者"]:
        cleaned = cleaned.replace(old, "创作者")
    return re.sub(r"\s+", " ", cleaned).strip(" ,.;:，。；：")


def character_lock_from_persona(creator_persona: Any) -> str:
    if not isinstance(creator_persona, dict):
        return "Keep the same creator identity, wardrobe, props, and natural hand movement across every generated clip."
    prompt_assets = digital_human_prompt_assets_for_prompt(creator_persona)
    identity = str(creator_persona.get("veo_identity_string") or "").strip()
    if identity:
        motion = compact_text(prompt_assets.get("avatar_motion_prompt"), 260)
        motion_line = f" Digital-human motion prompt asset: {motion}" if motion else ""
        return f"Use the exact selected creator identity in every generated clip: {identity}.{motion_line}"
    display_name = persona_display_name(creator_persona) or "the creator"
    demographic = str(creator_persona.get("demographic") or "social-commerce creator").strip()
    appearance = str(creator_persona.get("appearance") or "consistent face shape, natural posture, expressive hands").strip()
    face_hair_makeup = str(creator_persona.get("face_hair_makeup") or "natural makeup, consistent hair, detailed facial features").strip()
    wardrobe = str(creator_persona.get("wardrobe") or "creator-native outfit with consistent accessories").strip()
    marks = str(creator_persona.get("distinctive_marks_or_tattoos") or "").strip()
    props = props_text(creator_persona.get("props"))
    marks_line = f" Distinctive details: {marks}." if marks else ""
    props_line = f" {props}." if props else ""
    return (
        f"Use {display_name}, {demographic}, as the only visible creator. "
        f"Appearance continuity: {appearance}. Face, hair, and makeup: {face_hair_makeup}. "
        f"Wardrobe continuity: {wardrobe}.{marks_line}{props_line}"
    )


def digital_human_prompt_assets_for_prompt(creator_persona: Any) -> dict[str, Any]:
    if not isinstance(creator_persona, dict):
        return {}
    normalized = normalize_persona_key_style(creator_persona)
    ensure_digital_human_prompt_assets(normalized)
    assets = normalized.get("digital_human_prompt_assets")
    return dict(assets) if isinstance(assets, dict) else {}


def persona_subject_line(creator_persona: Any, script: dict[str, Any]) -> str:
    if not isinstance(creator_persona, dict):
        return str(script.get("persona") or "a practical social-commerce creator").strip()
    display_name = persona_display_name(creator_persona) or "the creator"
    demographic = str(creator_persona.get("demographic") or "social-commerce creator").strip()
    return f"{display_name}, {demographic}"


def prompt_matches_creator_persona(prompt: str, creator_persona: Any) -> bool:
    display_name = persona_display_name(creator_persona)
    lowered = str(prompt or "").lower()
    if display_name and display_name.lower() not in lowered:
        return False
    stale_terms = [
        "efficiency expert",
        "same young creator",
        "young creator",
        "male creator",
        "female creator",
        "asian creator",
        "asian female",
        "mia chen",
        "男性创作者",
        "女性创作者",
        "亚洲",
        "米娅",
    ]
    return not any(term in lowered or term in prompt for term in stale_terms)


def sync_veo_segment_localized(segment: dict[str, Any]) -> None:
    localized = segment.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        segment["localized"] = localized
    zh = localized.get(LOCALIZED_LANGUAGE_KEY)
    if not isinstance(zh, dict):
        zh = {}
        localized[LOCALIZED_LANGUAGE_KEY] = zh
    zh["veo_prompt"] = str(segment.get("veo_prompt") or "")


def collapse_video_prompts(video_prompts: Any, script: dict[str, Any], creator_persona: dict[str, Any] | None = None) -> dict[str, Any]:
    prompts = video_prompts if isinstance(video_prompts, list) else []
    joined = " ".join(
        str(first_present(prompt.get("veo_prompt"), prompt.get("visual_prompt"), prompt.get("prompt")) or "")
        for prompt in prompts
        if isinstance(prompt, dict)
    ).strip()
    segments = build_veo_segments(script, [], joined, creator_persona=creator_persona)
    return {
        "prompt_title": script.get("script_title") or "Moras short video prompt",
        "aspect_ratio": "vertical 9:16",
        "target_model": "Veo 3.1",
        "veo_model_id": "veo-3.1-generate-001",
        "veo_generation_mode": "text_to_video_9x16",
        "veo_base_duration_sec": 8,
        "character_lock": character_lock_from_persona(creator_persona),
        "scene_lock": "Keep the same realistic creator workspace and lighting continuity.",
        "generation_prompt": joined or "A realistic creator workspace scene, vertical smartphone framing, natural movement, expressive but grounded action, soft daylight, practical product workflow mood.",
        "overlay_exclusion_note": "Overlay text belongs to dedicated editing fields only. Veo prompts are source-footage prompts and should use abstract, non-readable screen shapes instead of captions or UI text.",
        "consistency_notes": ["Maintain vertical 9:16 composition.", "Keep people and scene consistent."],
        "target_duration_sec": DEFAULT_TARGET_DURATION_SEC,
        "veo_generation_duration_sec": round(sum(segment["duration_sec"] for segment in segments), 2),
        "segments": segments,
    }


def ensure_veo_segments(
    video_prompt: dict[str, Any],
    script: dict[str, Any] | None = None,
    storyboard: list[Any] | None = None,
    production_asset_plan: list[Any] | None = None,
    creator_persona: dict[str, Any] | None = None,
) -> dict[str, Any]:
    next_video_prompt = dict(video_prompt)
    next_video_prompt.pop("seedance_generation_duration_sec", None)
    next_video_prompt.pop("seedanceGenerationDurationSec", None)
    next_video_prompt.pop("negative_prompt", None)
    next_video_prompt.pop("negativePrompt", None)
    target_duration_sec = infer_target_duration_sec(next_video_prompt, production_asset_plan or [], storyboard or [])
    expected_ranges = build_generation_ranges(target_duration_sec, production_asset_plan or [])
    existing_segments = normalize_veo_segments(next_video_prompt.get("segments"), target_duration_sec)
    if existing_segments and creator_persona and not all(
        prompt_matches_creator_persona(str(segment.get("veo_prompt") or ""), creator_persona)
        for segment in existing_segments
    ):
        existing_segments = None
    if existing_segments:
        if not veo_segments_match_ranges(existing_segments, expected_ranges):
            existing_segments = remap_veo_segments_to_ranges(existing_segments, expected_ranges, creator_persona)
            if creator_persona and not all(
                prompt_matches_creator_persona(str(segment.get("veo_prompt") or ""), creator_persona)
                for segment in existing_segments
            ):
                existing_segments = None
    if existing_segments:
        for segment in existing_segments:
            sync_veo_segment_localized(segment)
        next_video_prompt["segments"] = existing_segments
    else:
        next_video_prompt["segments"] = build_veo_segments(
            script or {},
            storyboard or [],
            str(next_video_prompt.get("generation_prompt") or ""),
            production_asset_plan or [],
            target_duration_sec,
            creator_persona,
        )
    next_video_prompt["target_model"] = "Veo 3.1"
    next_video_prompt["veo_model_id"] = next_video_prompt.get("veo_model_id") or "veo-3.1-generate-001"
    next_video_prompt["veo_generation_mode"] = next_video_prompt.get("veo_generation_mode") or "text_to_video_9x16"
    next_video_prompt["veo_base_duration_sec"] = 8
    if creator_persona:
        next_video_prompt["character_lock"] = character_lock_from_persona(creator_persona)
    else:
        next_video_prompt["character_lock"] = next_video_prompt.get("character_lock") or character_lock_from_persona(None)
    next_video_prompt["generation_prompt"] = sanitize_video_generation_prompt(
        next_video_prompt.get("generation_prompt"),
        script or {},
        creator_persona,
    )
    next_video_prompt["target_duration_sec"] = target_duration_sec
    next_video_prompt["veo_generation_duration_sec"] = round(
        sum(float(segment["duration_sec"]) for segment in next_video_prompt["segments"]),
        2,
    )
    localized = next_video_prompt.get("localized")
    if isinstance(localized, dict) and isinstance(localized.get(LOCALIZED_LANGUAGE_KEY), dict):
        localized[LOCALIZED_LANGUAGE_KEY].pop("negative_prompt", None)
        localized[LOCALIZED_LANGUAGE_KEY].pop("negativePrompt", None)
    return next_video_prompt


def sanitize_video_generation_prompt(value: Any, script: dict[str, Any], creator_persona: dict[str, Any] | None) -> str:
    cleaned = sanitize_veo_prompt(str(value or ""))
    if not cleaned:
        cleaned = str(script.get("visual") or "")
    cleaned = sanitize_identity_fragment(sanitize_veo_prompt(cleaned))
    if video_generation_prompt_has_forbidden_terms(cleaned):
        cleaned = ""
    if cleaned:
        return cleaned
    subject = persona_subject_line(creator_persona, script)
    return (
        f"Vertical 9:16 realistic creator workspace source footage featuring {subject}, natural face-and-hands movement, "
        "soft daylight, practical product-planning actions, clean desk props, grounded social-commerce tutorial energy, "
        "abstract unreadable screen shapes only, and no readable text inside the generated footage."
    )


def video_generation_prompt_has_forbidden_terms(value: str) -> bool:
    lowered = str(value or "").lower()
    return any(term in lowered for term in ["overlay", "screen recording", "screenshot", "user interface"]) or any(
        term in value for term in ["字幕", "录屏", "截图", "界面"]
    )


def normalize_veo_segments(value: Any, target_duration_sec: float | None = None) -> list[dict[str, Any]] | None:
    if not isinstance(value, list) or not 1 <= len(value) <= MAX_DYNAMIC_VEO_SEGMENTS:
        return None
    segments: list[dict[str, Any]] = []
    for index, segment in enumerate(value, start=1):
        if not isinstance(segment, dict):
            return None
        prompt = (
            first_present(
                segment.get("veo_prompt"),
                segment.get("veoPrompt"),
                segment.get("visual_prompt"),
                segment.get("visualPrompt"),
                segment.get("segment_generation_prompt"),
                segment.get("segmentGenerationPrompt"),
                segment.get("generation_prompt"),
                segment.get("generationPrompt"),
                segment.get("prompt"),
            )
        )
        if not prompt:
            return None
        prompt_text = sanitize_veo_prompt(str(prompt))
        if not is_copyable_veo_prompt(prompt_text):
            return None
        start_sec = coerce_seconds(first_present(segment.get("timeline_start_sec"), segment.get("timelineStartSec")))
        end_sec = coerce_seconds(first_present(segment.get("timeline_end_sec"), segment.get("timelineEndSec")))
        if start_sec is None or end_sec is None:
            parsed_range = parse_time_range_seconds(first_present(segment.get("time_range"), segment.get("timeRange")))
            if parsed_range:
                start_sec, end_sec = parsed_range
        if start_sec is None or end_sec is None or end_sec <= start_sec:
            fallback_start = float((index - 1) * MAX_VEO_SEGMENT_SECONDS)
            fallback_end = min(fallback_start + MAX_VEO_SEGMENT_SECONDS, target_duration_sec or fallback_start + MAX_VEO_SEGMENT_SECONDS)
            start_sec, end_sec = fallback_start, fallback_end
        duration_sec = coerce_seconds(first_present(segment.get("duration_sec"), segment.get("durationSec")))
        if duration_sec is None:
            duration_sec = round(end_sec - start_sec, 2)
        if duration_sec <= 0 or duration_sec > MAX_VEO_SEGMENT_SECONDS + 0.05:
            return None
        if target_duration_sec is not None and end_sec > target_duration_sec + 0.05:
            return None
        normalized_segment = {
            "segment_index": int(segment.get("segment_index") or segment.get("segmentIndex") or index),
            "timeline_start_sec": round(start_sec, 2),
            "timeline_end_sec": round(end_sec, 2),
            "duration_sec": round(duration_sec, 2),
            "time_range": str(first_present(segment.get("time_range"), segment.get("timeRange")) or format_time_range(start_sec, end_sec)),
            "veo_prompt": prompt_text,
            "requires_extension": False,
        }
        if isinstance(segment.get("localized"), dict):
            normalized_segment["localized"] = segment["localized"]
        segments.append(normalized_segment)
    segments.sort(key=lambda item: (float(item["timeline_start_sec"]), float(item["timeline_end_sec"])))
    for index, segment in enumerate(segments, start=1):
        segment["segment_index"] = index
    return segments


def build_veo_segments(
    script: dict[str, Any],
    storyboard: list[Any],
    fallback_generation_prompt: str = "",
    production_asset_plan: list[Any] | None = None,
    target_duration_sec: float | None = None,
    creator_persona: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    target = target_duration_sec or infer_target_duration_sec({}, production_asset_plan or [], storyboard)
    generation_ranges = build_generation_ranges(target, production_asset_plan or [])
    default_prompts = default_veo_prompt_sequence(script, fallback_generation_prompt)
    segments: list[dict[str, Any]] = []
    for index, (start_sec, end_sec) in enumerate(generation_ranges, start=1):
        raw_prompt = veo_prompt_for_range(storyboard, start_sec, end_sec) or default_prompts[(index - 1) % len(default_prompts)]
        prompt = compose_copyable_veo_prompt(raw_prompt, script, fallback_generation_prompt, creator_persona)
        segment = {
            "segment_index": index,
            "timeline_start_sec": round(start_sec, 2),
            "timeline_end_sec": round(end_sec, 2),
            "duration_sec": round(end_sec - start_sec, 2),
            "time_range": format_time_range(start_sec, end_sec),
            "veo_prompt": prompt,
            "requires_extension": False,
        }
        sync_veo_segment_localized(segment)
        segments.append(segment)
    return segments


def first_present(*values: Any) -> Any:
    for value in values:
        if value is not None and value != "":
            return value
    return None


def coerce_seconds(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip().lower().removesuffix("s").strip()
        try:
            return float(text)
        except ValueError:
            return None
    return None


def parse_time_range_seconds(value: Any) -> tuple[float, float] | None:
    if not value:
        return None
    match = re.search(
        r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds|秒)?\s*[-\u2013]\s*"
        r"(\d+(?:\.\d+)?)\s*(?:s|sec|secs|second|seconds|秒)?",
        str(value),
        re.IGNORECASE,
    )
    if not match:
        return None
    start_sec = float(match.group(1))
    end_sec = float(match.group(2))
    if end_sec <= start_sec:
        return None
    return start_sec, end_sec


def format_seconds(value: float) -> str:
    rounded = round(value, 2)
    if rounded.is_integer():
        return str(int(rounded))
    return f"{rounded:g}"


def format_time_range(start_sec: float, end_sec: float) -> str:
    return f"{format_seconds(start_sec)}s-{format_seconds(end_sec)}s"


def storyboard_row_required_duration_sec(shot: dict[str, Any]) -> float:
    return float(storyboard_voiceover_min_duration_sec(str(shot.get("voiceover") or "")))


def apply_storyboard_timing_for_voiceover(item: dict[str, Any]) -> None:
    storyboard = item.get("storyboard")
    if not isinstance(storyboard, list):
        return
    cursor = 0.0
    for index, shot in enumerate(storyboard, start=1):
        if not isinstance(shot, dict):
            continue
        duration = storyboard_row_required_duration_sec(shot)
        start_sec = cursor
        end_sec = round(start_sec + duration, 2)
        shot["shot_id"] = str(shot.get("shot_id") or f"shot_{index}")
        shot["timestamp"] = format_time_range(start_sec, end_sec)
        shot["duration"] = f"{format_seconds(duration)}s"
        localized = shot.get("localized")
        if isinstance(localized, dict):
            zh = localized.get(LOCALIZED_LANGUAGE_KEY)
            if isinstance(zh, dict):
                zh["duration"] = f"{format_seconds(duration)}秒"
        cursor = end_sec
    if isinstance(item.get("video_prompt"), dict):
        item["video_prompt"]["target_duration_sec"] = round(max(25.0, min(50.0, cursor)), 2)
    apply_production_asset_ranges_from_storyboard(item)


def apply_script_spoken_target_duration_floor(item: dict[str, Any]) -> None:
    script = item.get("script")
    video_prompt = item.get("video_prompt")
    if not isinstance(script, dict) or not isinstance(video_prompt, dict):
        return
    voiceover_lines = script_voiceover_lines_for_repair(script.get("voiceover"))
    spoken_lines = script_spoken_lines_for_length(voiceover_lines, str(script.get("cta") or ""))
    if not spoken_lines:
        return
    spoken_duration_sec = script_voiceover_estimated_duration_sec(spoken_lines)
    current = coerce_seconds(video_prompt.get("target_duration_sec"))
    video_prompt["target_duration_sec"] = round(max(current or 0.0, min(50.0, spoken_duration_sec)), 2)


def apply_production_asset_ranges_from_storyboard(item: dict[str, Any]) -> None:
    storyboard = item.get("storyboard")
    plan = item.get("production_asset_plan")
    if not isinstance(storyboard, list) or not isinstance(plan, list):
        return
    ranges_by_shot = {}
    for shot in storyboard:
        if not isinstance(shot, dict):
            continue
        shot_id = str(shot.get("shot_id") or "")
        parsed = parse_time_range_seconds(first_present(shot.get("timestamp"), shot.get("time_range"), shot.get("timeRange")))
        if shot_id and parsed:
            ranges_by_shot[shot_id] = parsed
    for entry in plan:
        if not isinstance(entry, dict):
            continue
        shot_ids = [str(shot_id) for shot_id in entry.get("shot_ids") or [] if str(shot_id).strip()]
        ranges = [ranges_by_shot[shot_id] for shot_id in shot_ids if shot_id in ranges_by_shot]
        if not ranges:
            continue
        start_sec = min(start for start, _ in ranges)
        end_sec = max(end for _, end in ranges)
        entry["time_range"] = format_time_range(start_sec, end_sec)


def visual_elements_need_repair(storyboard: list[Any], *, localized_zh: bool = False) -> bool:
    signatures: dict[str, int] = {}
    for shot in storyboard:
        if not isinstance(shot, dict):
            continue
        visual_elements: Any = shot.get("visual_elements")
        if localized_zh:
            localized = shot.get("localized")
            zh = localized.get(LOCALIZED_LANGUAGE_KEY) if isinstance(localized, dict) else None
            if isinstance(zh, dict):
                visual_elements = zh.get("visual_elements")
        signature = visual_elements_signature(visual_elements)
        if not signature:
            return True
        signatures[signature] = signatures.get(signature, 0) + 1
    return any(count >= 3 for count in signatures.values())


def visual_elements_signature(value: Any) -> str:
    values = value if isinstance(value, list) else [value] if isinstance(value, str) else []
    normalized = sorted({re.sub(r"[\s\W_]+", " ", str(item).lower()).strip() for item in values if str(item or "").strip()})
    return " / ".join(item for item in normalized if item)


def apply_storyboard_visual_element_specificity(item: dict[str, Any]) -> None:
    storyboard = item.get("storyboard")
    if not isinstance(storyboard, list):
        return
    if not (
        visual_elements_need_repair(storyboard)
        or visual_elements_need_repair(storyboard, localized_zh=True)
    ):
        return
    for index, shot in enumerate(storyboard, start=1):
        if not isinstance(shot, dict):
            continue
        shot["visual_elements"] = storyboard_visual_elements_for_index(index, localized=False)
        set_localized_zh(
            shot,
            {"visual_elements": storyboard_visual_elements_for_index(index, localized=True)},
        )


def storyboard_visual_elements_for_index(index: int, *, localized: bool) -> list[str]:
    english = [
        ["creator close-up", "phone foreground", "hook caption"],
        ["approved proof cards", "GMV screenshot", "pop-in number circles"],
        ["crossed-out product note", "old-way desk props", "frustration pause"],
        ["Moras product-library crop", "scroll highlight", "product signal marker"],
        ["selected product close-up", "choice highlight box", "product signal card"],
        ["Generate button zoom", "cursor click ring", "processing state"],
        ["generated video preview", "commerce-path state highlight", "posting entry"],
        ["draft review controls", "text-check marker", "posting-path cursor"],
        ["posting checklist", "product notes", "next-product circle"],
        ["CTA button arrow", "creator pointing gesture", "money caption"],
    ]
    chinese = [
        ["创作者近景", "手机前景", "开场重点字幕"],
        ["已批准证明卡", "GMV 截图", "数字圈注"],
        ["划掉的商品笔记", "旧流程桌面道具", "卡住停顿"],
        ["Moras 商品库裁切", "滚动高亮", "商品信号标记"],
        ["选中商品特写", "选择高亮框", "商品信号卡片"],
        ["Generate 按钮放大", "光标点击圈", "处理中状态"],
        ["生成视频预览", "带货路径状态高亮", "发布入口"],
        ["草稿检查控件", "文字检查标记", "发布路径光标"],
        ["发布清单", "商品便签", "下个商品圈注"],
        ["CTA 按钮箭头", "创作者指向手势", "赚钱重点字幕"],
    ]
    items = chinese if localized else english
    return list(items[(index - 1) % len(items)])


def mock_group_visual_elements(index: int, *, localized: bool) -> list[str]:
    english = [
        ["creator close-up", "phone foreground", "hook caption"],
        ["approved proof cards", "GMV screenshot", "pop-in number circles"],
        ["crossed-out product note", "old-way desk props", "frustration pause"],
        ["Moras product-library crop", "selected product highlight", "product signal marker"],
        ["Generate button zoom", "processing state", "cart output hold"],
        ["draft review controls", "posting checklist", "product notes"],
        ["CTA button arrow", "creator pointing gesture", "money caption"],
        ["final creator close-up", "left-corner button cue", "stylus point"],
    ]
    chinese = [
        ["创作者近景", "手机前景", "开场重点字幕"],
        ["已批准证明卡", "GMV 截图", "数字圈注"],
        ["划掉的商品笔记", "旧流程桌面道具", "卡住停顿"],
        ["Moras 商品库裁切", "选中商品高亮", "商品信号标记"],
        ["Generate 按钮放大", "处理中状态", "带货路径结果停留"],
        ["草稿检查控件", "发布清单", "商品便签"],
        ["CTA 按钮箭头", "创作者指向手势", "赚钱重点字幕"],
        ["结尾创作者近景", "左下角按钮提示", "触控笔指向"],
    ]
    items = chinese if localized else english
    return list(items[(index - 1) % len(items)])


def infer_target_duration_sec(
    video_prompt: dict[str, Any],
    production_asset_plan: list[Any],
    storyboard: list[Any],
) -> float:
    requested = coerce_seconds(first_present(video_prompt.get("target_duration_sec"), video_prompt.get("targetDurationSec")))
    if requested is not None and 25 <= requested <= 50:
        return round(requested, 2)
    inferred_end = 0.0
    for entry in production_asset_plan:
        if isinstance(entry, dict):
            parsed_range = parse_time_range_seconds(first_present(entry.get("time_range"), entry.get("timeRange")))
            if parsed_range:
                inferred_end = max(inferred_end, parsed_range[1])
    for shot in storyboard:
        if isinstance(shot, dict):
            parsed_range = parse_time_range_seconds(first_present(shot.get("timestamp"), shot.get("time_range"), shot.get("timeRange")))
            if parsed_range:
                inferred_end = max(inferred_end, parsed_range[1])
    if inferred_end > 0:
        return round(max(25.0, min(50.0, inferred_end)), 2)
    return DEFAULT_TARGET_DURATION_SEC


def build_generation_ranges(target_duration_sec: float, production_asset_plan: list[Any]) -> list[tuple[float, float]]:
    gaps = subtract_ranges([(0.0, target_duration_sec)], real_moras_cutaway_ranges(production_asset_plan, target_duration_sec))
    ranges: list[tuple[float, float]] = []
    for start_sec, end_sec in gaps:
        cursor = start_sec
        while cursor < end_sec - MIN_VEO_SEGMENT_SECONDS and len(ranges) < MAX_DYNAMIC_VEO_SEGMENTS:
            next_end = min(cursor + MAX_VEO_SEGMENT_SECONDS, end_sec)
            if next_end - cursor >= MIN_VEO_SEGMENT_SECONDS:
                ranges.append((round(cursor, 2), round(next_end, 2)))
            cursor = next_end
    if ranges:
        return ranges
    return [(0.0, min(MAX_VEO_SEGMENT_SECONDS, target_duration_sec))]


def veo_segments_match_ranges(
    segments: list[dict[str, Any]],
    expected_ranges: list[tuple[float, float]],
) -> bool:
    if len(segments) != len(expected_ranges):
        return False
    for segment, (expected_start, expected_end) in zip(segments, expected_ranges, strict=True):
        start_sec = coerce_seconds(segment.get("timeline_start_sec"))
        end_sec = coerce_seconds(segment.get("timeline_end_sec"))
        if start_sec is None or end_sec is None:
            return False
        if abs(start_sec - expected_start) > 0.05 or abs(end_sec - expected_end) > 0.05:
            return False
    return True


def remap_veo_segments_to_ranges(
    segments: list[dict[str, Any]],
    expected_ranges: list[tuple[float, float]],
    creator_persona: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    prompts = [str(segment.get("veo_prompt") or segment.get("visual_prompt") or "") for segment in segments if segment.get("veo_prompt") or segment.get("visual_prompt")]
    if not prompts:
        prompts = default_veo_prompt_sequence({}, "")
    while len(prompts) < len(expected_ranges):
        prompts.append(prompts[-1])
    remapped: list[dict[str, Any]] = []
    for index, (start_sec, end_sec) in enumerate(expected_ranges, start=1):
        prompt = sanitize_veo_prompt(prompts[index - 1])
        if creator_persona and not prompt_matches_creator_persona(prompt, creator_persona):
            prompt = compose_copyable_veo_prompt(prompt, {}, "", creator_persona)
        segment = {
            "segment_index": index,
            "timeline_start_sec": round(start_sec, 2),
            "timeline_end_sec": round(end_sec, 2),
            "duration_sec": round(end_sec - start_sec, 2),
            "time_range": format_time_range(start_sec, end_sec),
            "veo_prompt": prompt,
            "requires_extension": False,
        }
        sync_veo_segment_localized(segment)
        remapped.append(segment)
    return remapped


def real_moras_cutaway_ranges(production_asset_plan: list[Any], target_duration_sec: float) -> list[tuple[float, float]]:
    ranges: list[tuple[float, float]] = []
    for entry in production_asset_plan:
        if not isinstance(entry, dict):
            continue
        asset_type = str(first_present(entry.get("asset_type"), entry.get("assetType")) or "")
        layer = str(entry.get("layer") or "")
        if asset_type not in REAL_MORAS_ASSET_TYPES or layer not in {"base_track", "cutaway"}:
            continue
        parsed_range = parse_time_range_seconds(first_present(entry.get("time_range"), entry.get("timeRange")))
        if not parsed_range:
            continue
        start_sec = max(0.0, min(target_duration_sec, parsed_range[0]))
        end_sec = max(0.0, min(target_duration_sec, parsed_range[1]))
        if end_sec - start_sec >= MIN_VEO_SEGMENT_SECONDS:
            ranges.append((start_sec, end_sec))
    return merge_ranges(ranges)


def merge_ranges(ranges: list[tuple[float, float]]) -> list[tuple[float, float]]:
    merged: list[tuple[float, float]] = []
    for start_sec, end_sec in sorted(ranges):
        if not merged or start_sec > merged[-1][1]:
            merged.append((start_sec, end_sec))
        else:
            previous_start, previous_end = merged[-1]
            merged[-1] = (previous_start, max(previous_end, end_sec))
    return merged


def subtract_ranges(
    base_ranges: list[tuple[float, float]],
    excluded_ranges: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    gaps: list[tuple[float, float]] = []
    excluded = merge_ranges(excluded_ranges)
    for base_start, base_end in base_ranges:
        cursor = base_start
        for excluded_start, excluded_end in excluded:
            if excluded_end <= cursor or excluded_start >= base_end:
                continue
            if excluded_start - cursor >= MIN_VEO_SEGMENT_SECONDS:
                gaps.append((cursor, min(excluded_start, base_end)))
            cursor = max(cursor, excluded_end)
        if base_end - cursor >= MIN_VEO_SEGMENT_SECONDS:
            gaps.append((cursor, base_end))
    return gaps


def sanitize_veo_prompt(prompt: str) -> str:
    cleaned = prompt
    for term in VEO_PROMPT_FORBIDDEN_TERMS:
        cleaned = re.sub(re.escape(term), "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\bscript(?:s|ed|ing)?\b", "content plan", cleaned, flags=re.IGNORECASE)
    cleaned = cleaned.replace("脚本", "内容方案")
    cleaned = cleaned.replace('"', "").replace("“", "").replace("”", "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" ,.;:，。；：")
    if cleaned:
        return cleaned
    return "Realistic creator workspace motion, vertical smartphone framing, natural desk-level action, grounded expression, soft daylight, practical planning rhythm, ambient room tone."


def veo_prompt_for_range(storyboard: list[Any], start_sec: float, end_sec: float) -> str:
    parts: list[str] = []
    for shot in storyboard:
        if not isinstance(shot, dict):
            continue
        shot_range = parse_time_range_seconds(first_present(shot.get("timestamp"), shot.get("time_range"), shot.get("timeRange")))
        if shot_range and (shot_range[1] <= start_sec or shot_range[0] >= end_sec):
            continue
        parts = [
            shot.get("camera"),
            shot.get("character_action"),
            shot.get("facial_expression"),
            shot.get("background"),
            props_text(shot.get("props")),
            shot.get("transition"),
        ]
        prompt = ", ".join(str(part).strip() for part in parts if str(part or "").strip())
        if prompt:
            return prompt
    return ""


def props_text(value: Any) -> str:
    if isinstance(value, list):
        return "Props: " + ", ".join(str(item).strip() for item in value if str(item).strip())
    if value:
        return f"Props: {value}"
    return ""


def default_veo_prompt_sequence(script: dict[str, Any], fallback_generation_prompt: str) -> list[str]:
    core_action = str(script.get("visual") or fallback_generation_prompt).strip()
    if not core_action:
        core_action = "realistic creator desk workflow with phone, laptop, product research, and planning actions"
    return [
        f"Opening block: vertical smartphone framing, creator notices a product-selection problem, close-up hands with phone and laptop, focused pause, quick practical movement, {core_action}.",
        "Middle block: creator compares product planning steps through physical gestures, over-the-shoulder desk view, close-up hand taps, organized workflow rhythm, natural daylight, grounded creator energy.",
        "Closing block: creator reaches the visual resolution by reviewing a prepared workflow result, relaxed posture, confident nod, then continues with a calm usable ending that can also be trimmed cleanly, phone and laptop in frame, clean vertical composition.",
    ]


def compose_copyable_veo_prompt(
    raw_prompt: str,
    script: dict[str, Any],
    fallback_generation_prompt: str,
    creator_persona: dict[str, Any] | None = None,
) -> str:
    subject = persona_subject_line(creator_persona, script)
    identity = str((creator_persona or {}).get("veo_identity_string") or "").strip() if isinstance(creator_persona, dict) else ""
    core_visual = sanitize_identity_fragment(
        sanitize_veo_prompt(raw_prompt or fallback_generation_prompt or str(script.get("visual") or ""))
    )
    if not core_visual:
        core_visual = "realistic creator desk workflow with phone, laptop, product research notes, natural hand movement, and a grounded expression"
    appearance = ""
    wardrobe = ""
    prompt_assets = digital_human_prompt_assets_for_prompt(creator_persona)
    avatar_motion = compact_text(sanitize_veo_prompt(str(prompt_assets.get("avatar_motion_prompt") or "")), 360)
    voice_style = compact_text(sanitize_veo_prompt(str(prompt_assets.get("voice_style_prompt") or "")), 280)
    delivery_rules = compact_string_list(prompt_assets.get("script_delivery_rules"), max_items=2, max_chars=120)
    delivery_rules_text = "; ".join(sanitize_veo_prompt(rule) for rule in delivery_rules if sanitize_veo_prompt(rule))
    if isinstance(creator_persona, dict):
        appearance = (
            f" Appearance continuity: {creator_persona.get('appearance')}. "
            f"Face, hair, and makeup: {creator_persona.get('face_hair_makeup')}."
        )
        wardrobe = f" Wardrobe and props: {creator_persona.get('wardrobe')}; {props_text(creator_persona.get('props'))}."
    identity_line = f" Exact identity string: {identity}." if identity else ""
    prompt_asset_line = f" Digital-human prompt asset motion: {avatar_motion}." if avatar_motion else ""
    spoken_delivery_line = ""
    if voice_style:
        spoken_delivery_line = f" Spoken delivery direction from Persona Agent: {voice_style}."
    if delivery_rules_text:
        spoken_delivery_line = f"{spoken_delivery_line} Delivery rules: {delivery_rules_text}."
    return (
        "Generate one 8-second vertical 9:16 Veo 3.1 source clip. "
        f"Subject: {subject}, the same person throughout the clip, natural skin texture, realistic hand movement, grounded creator energy."
        f"{identity_line}"
        f"{appearance}{wardrobe}{prompt_asset_line} "
        f"Action and expression: {core_visual}; keep the action as one continuous moment, not a montage. "
        "Scene: compact creator home office desk with a laptop, phone, sticky notes, and clean product-planning props; any screens are soft, non-readable background shapes. "
        "Camera: smartphone-style vertical medium close-up with a subtle handheld push-in, stable framing, shallow depth of field, clear face-and-hands composition. "
        "Lighting and style: realistic high-fidelity social video, soft side daylight, warm neutral color grade, natural shadows, practical creator-workflow mood. "
        f"Audio and ambiance: quiet room tone, soft desk sounds, gentle upbeat background rhythm, natural spoken narration energy.{spoken_delivery_line} "
        "Use synthetic media direction only, with clean footage, abstract unreadable screen shapes, and plain non-branded background details."
    )


def is_copyable_veo_prompt(prompt: str) -> bool:
    words = re.findall(r"[A-Za-z0-9]+(?:'[A-Za-z0-9]+)?", prompt)
    cjk_chars = re.findall(r"[\u3400-\u9fff]", prompt)
    if len(words) < 45 and len(cjk_chars) < 80:
        return False
    lowered = prompt.lower()
    groups = {
        "subject": ["subject", "creator", "person", "人物", "创作者"],
        "action": ["action", "gesture", "expression", "movement", "动作", "表情"],
        "camera": ["camera", "shot", "vertical", "framing", "镜头", "竖屏"],
        "lighting": ["lighting", "light", "realistic", "cinematic", "光", "真实"],
        "audio": ["audio", "ambiance", "sound", "room tone", "声音", "环境声"],
    }
    return all(any(term in lowered or term in prompt for term in terms) for terms in groups.values())


def compact_breakdown(record: Any) -> dict[str, Any]:
    source_video = record.source_video or {}
    classification = record.classification or {}
    decomposition = record.decomposition or {}
    structure_protocol = record.structure_protocol or {}
    script_agent_bridge = record.script_agent_bridge or {}
    reference_storyboard = getattr(record, "reference_storyboard", None) or fallback_reference_storyboard(decomposition)
    return {
        "id": record.id,
        "source_video": {
            "title": compact_text(source_video.get("title"), 100),
            "platform": source_video.get("platform"),
            "duration_seconds": source_video.get("duration_seconds"),
            "content_summary": compact_text(source_video.get("content_summary"), 120),
        },
        "classification": compact_classification(classification),
        "decomposition": compact_decomposition(decomposition),
        "structure_protocol": compact_structure_protocol(structure_protocol),
        "script_agent_bridge": compact_script_agent_bridge(script_agent_bridge),
        "reference_storyboard": compact_reference_storyboard(reference_storyboard),
    }


def compact_classification(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "hook_type": compact_text(value.get("hook_type"), 70),
        "emotion_factors": compact_string_list(value.get("emotion_factors"), max_items=3, max_chars=70),
        "persona_factors": compact_string_list(value.get("persona_factors"), max_items=3, max_chars=70),
        "scene_factors": compact_string_list(value.get("scene_factors"), max_items=3, max_chars=70),
        "pain_factors": compact_string_list(value.get("pain_factors"), max_items=2, max_chars=80),
        "itch_factors": compact_string_list(value.get("itch_factors"), max_items=2, max_chars=80),
        "value_factors": compact_string_list(value.get("value_factors"), max_items=2, max_chars=80),
        "proof_factors": compact_string_list(value.get("proof_factors"), max_items=2, max_chars=80),
        "cta_factors": compact_string_list(value.get("cta_factors"), max_items=3, max_chars=70),
        "structure_factors": compact_string_list(value.get("structure_factors"), max_items=3, max_chars=70),
        "audience_segments": compact_string_list(value.get("audience_segments"), max_items=3, max_chars=70),
        "general_templates": compact_string_list(value.get("general_templates"), max_items=3, max_chars=70),
        "vertical_templates": compact_string_list(value.get("vertical_templates"), max_items=3, max_chars=70),
        "factor_reasoning": compact_text(value.get("factor_reasoning"), 100),
        "evidence": compact_string_list(value.get("evidence"), max_items=2, max_chars=80),
    }


def compact_decomposition(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "one_sentence_summary": compact_text(value.get("one_sentence_summary"), 120),
        "hook": compact_text(value.get("hook"), 160),
        "narrative_structure": compact_string_list(value.get("narrative_structure"), max_items=2, max_chars=110),
        "segments": [
            compact_segment(segment)
            for segment in as_dict_list(value.get("segments"))[:2]
        ],
        "key_takeaways": compact_string_list(value.get("key_takeaways"), max_items=2, max_chars=100),
        "visual_language": compact_text(value.get("visual_language"), 100),
        "audio_language": compact_text(value.get("audio_language"), 90),
        "interaction_or_cta": compact_text(value.get("interaction_or_cta"), 90),
        "performance_logic": compact_text(value.get("performance_logic"), 100),
    }


def compact_segment(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "start_second": value.get("start_second"),
        "end_second": value.get("end_second"),
        "role": compact_text(value.get("role"), 60),
        "content": compact_text(value.get("content"), 90),
        "technique": compact_text(value.get("technique"), 90),
    }


def compact_structure_protocol(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "core_pattern": compact_text(value.get("core_pattern"), 100),
        "timeline_slots": [
            {
                "slot_id": compact_text(slot.get("slot_id"), 60),
                "name": compact_text(slot.get("name"), 70),
                "role": compact_text(slot.get("role"), 70),
                "required_assets": compact_string_list(slot.get("required_assets"), max_items=2, max_chars=60),
                "transfer_rule": compact_text(slot.get("transfer_rule"), 80),
            }
            for slot in as_dict_list(value.get("timeline_slots"))[:2]
        ],
        "reuse_rules": compact_string_list(value.get("reuse_rules"), max_items=3, max_chars=80),
        "risk_flags": compact_string_list(value.get("risk_flags"), max_items=2, max_chars=80),
    }


def compact_script_agent_bridge(value: dict[str, Any]) -> dict[str, Any]:
    return {
        "reusable_pattern": compact_text(value.get("reusable_pattern"), 100),
        "script_agent_instructions": compact_string_list(value.get("script_agent_instructions"), max_items=3, max_chars=90),
        "variables_to_collect": compact_string_list(value.get("variables_to_collect"), max_items=4, max_chars=60),
        "do_not_copy": compact_string_list(value.get("do_not_copy"), max_items=4, max_chars=60),
        "adaptation_notes": compact_string_list(value.get("adaptation_notes"), max_items=3, max_chars=80),
    }


def compact_reference_storyboard(value: list[dict[str, Any]]) -> list[dict[str, Any]]:
    shots = as_dict_list(value)
    if len(shots) > 3:
        shots = [shots[0], shots[len(shots) // 2], shots[-1]]
    return [
        {
            "shot_id": compact_text(shot.get("shot_id"), 40),
            "timestamp": compact_text(shot.get("timestamp"), 30),
            "duration": compact_text(shot.get("duration"), 30),
            "camera": compact_text(shot.get("camera"), 36),
            "character_action": compact_text(shot.get("character_action"), 45),
            "facial_expression": compact_text(shot.get("facial_expression"), 30),
            "background": compact_text(shot.get("background"), 36),
            "props": compact_string_list(shot.get("props"), max_items=3, max_chars=24),
            "voiceover": compact_text(shot.get("voiceover"), 45),
            "overlay": compact_text(shot.get("overlay"), 32),
            "sound": compact_text(shot.get("sound"), 30),
            "bgm": compact_text(shot.get("bgm"), 25),
            "sound_effects": compact_string_list(shot.get("sound_effects"), max_items=3, max_chars=24),
            "subtitle_logic": compact_text(shot.get("subtitle_logic"), 40),
            "visual_elements": compact_string_list(shot.get("visual_elements"), max_items=4, max_chars=26),
            "visual_element_logic": compact_text(shot.get("visual_element_logic"), 45),
            "transition": compact_text(shot.get("transition"), 30),
            "purpose": compact_text(shot.get("purpose"), 40),
            "localized": compact_reference_storyboard_localized(shot.get("localized")),
        }
        for shot in shots
    ]


def compact_reference_storyboard_localized(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    zh = value.get("zh")
    if not isinstance(zh, dict):
        return {}
    return {
        "zh": {
            "camera": compact_text(zh.get("camera"), 35),
        }
    }


def fallback_reference_storyboard(decomposition: dict[str, Any]) -> list[dict[str, Any]]:
    fallback: list[dict[str, Any]] = []
    for index, segment in enumerate(as_dict_list(decomposition.get("segments")), start=1):
        start = segment.get("start_second")
        end = segment.get("end_second")
        timestamp = f"{start}s-{end}s" if start is not None and end is not None else f"segment_{index}"
        fallback.append(
            {
                "shot_id": f"shot_{index}",
                "timestamp": timestamp,
                "duration": timestamp,
                "camera": compact_text(decomposition.get("visual_language"), 100) or "Source segment visual language was not separately returned.",
                "character_action": compact_text(segment.get("content"), 140) or "Source segment action was not separately returned.",
                "facial_expression": "Source segment facial expression was not separately returned.",
                "background": compact_text(segment.get("role"), 100) or "Source segment background was not separately returned.",
                "props": [],
                "voiceover": "Source teardown did not return a unified storyboard voiceover field.",
                "overlay": "",
                "sound": compact_text(decomposition.get("audio_language"), 90) or "Source audio detail was not separately returned.",
                "bgm": "",
                "sound_effects": [],
                "subtitle_logic": "Legacy teardown did not return shot-level subtitle placement logic.",
                "visual_elements": [],
                "visual_element_logic": "Legacy teardown did not return shot-level visual element logic.",
                "transition": compact_text(segment.get("technique"), 100) or "Source transition detail was not separately returned.",
                "purpose": compact_text(segment.get("role"), 100) or "Mapped from legacy decomposition segment.",
                "localized": {},
            }
        )
    return fallback


def default_moras_assets() -> dict[str, Any]:
    reference_skeletons = load_reference_skeletons()
    return {
        "positioning": "Persona-led social growth video agent for TikTok Shop creators, sellers, and MCNs.",
        "safe_values": [
            "减少选品试错",
            "更快生成带货路径清晰的视频",
            "不用从零写脚本",
            "把 Moras 选品转成带货路径清晰的视频",
            "用反馈改进内容决策",
        ],
        "proof_assets_allowed": [
            "Moras workflow screen recording",
            "product selection to commerce-path video before/after",
            "approved creator handle / GMV / income proof screenshots",
            "time saved workflow comparison",
            "product selection logic",
            "published content feedback without income guarantees",
        ],
        "approved_asset_types": [
            "real_moras_screen_recording",
            "real_moras_screenshot",
            "moras_product_workflow",
            "ai_generated_broll",
            "digital_human_avatar",
            "live_creator_footage",
            "post_production_overlay",
            "sound_design",
        ],
        "moras_asset_categories": [
            "workflow_screen_recording",
            "product_card_to_video_draft_before_after",
            "product_to_script_before_after",
            "time_saved_comparison",
            "product_selection_logic",
            "published_content_feedback",
            "approved_feature_screenshot",
        ],
        "reference_skeleton_scope_note": compact_text(reference_skeletons.get("scope_note"), 140),
        "reference_teardown_skeletons": compact_reference_teardown_skeletons(
            reference_skeletons.get("reference_teardown_skeletons")
        ),
        "cross_reference_rules_for_script_agent": compact_string_list(
            reference_skeletons.get("cross_reference_rules_for_script_agent"),
            max_items=3,
            max_chars=90,
        ),
        "minimum_reference_prompt_rules": compact_string_list(
            reference_skeletons.get("minimum_prompt_rules_to_add"),
            max_items=3,
            max_chars=90,
        ),
        "forbidden_claims": [
            "guaranteed income",
            "passive income guaranteed",
            "make $10K easily",
            "automatic money",
            "AI guarantees sales",
            "platform bypass",
            "fixed settlement timing",
        ],
    }


def compact_reference_teardown_skeletons(value: Any) -> list[dict[str, Any]]:
    skeletons: list[dict[str, Any]] = []
    for skeleton in as_dict_list(value)[:4]:
        persona_pattern = skeleton.get("persona_pattern") if isinstance(skeleton.get("persona_pattern"), dict) else {}
        skeletons.append(
            {
                "reference_id": compact_text(skeleton.get("reference_id"), 80),
                "duration_sec": skeleton.get("duration_sec"),
                "persona_pattern": {
                    "archetype": compact_text(persona_pattern.get("archetype"), 70),
                    "setting": compact_text(persona_pattern.get("setting"), 80),
                    "trust_stance": compact_text(persona_pattern.get("trust_stance"), 80),
                },
                "social_distribution_pattern": compact_text(skeleton.get("social_distribution_pattern"), 90),
                "timeline_asset_slots": [
                    {
                        "slot_id": compact_text(slot.get("slot_id"), 70),
                        "time_range": compact_text(slot.get("time_range"), 40),
                        "narrative_phase": compact_text(slot.get("narrative_phase"), 70),
                        "material_type": compact_text(slot.get("material_type"), 70),
                        "layer": compact_text(slot.get("layer"), 70),
                        "script_agent_learning": compact_text(slot.get("script_agent_learning"), 90),
                    }
                    for slot in as_dict_list(skeleton.get("timeline_asset_slots"))[:1]
                ],
            }
        )
    return skeletons


def as_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def compact_string_list(value: Any, *, max_items: int, max_chars: int = 140) -> list[str]:
    if not isinstance(value, list):
        return []
    output: list[str] = []
    for item in value:
        text = compact_text(item, max_chars)
        if text:
            output.append(text)
        if len(output) >= max_items:
            break
    return output


def compact_text(value: Any, max_chars: int) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1].rstrip() + "…"


def load_reference_skeletons() -> dict[str, Any]:
    if not REFERENCE_SKELETONS_PATH.exists():
        return {}
    try:
        data = json.loads(REFERENCE_SKELETONS_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}
    if not isinstance(data, dict):
        return {}
    skeletons = data.get("reference_teardown_skeletons")
    if not isinstance(skeletons, list):
        data["reference_teardown_skeletons"] = []
    return data


def default_production_asset_plan(storyboard: list[Any]) -> list[dict[str, Any]]:
    shot_ids = [
        str(shot.get("shot_id") or f"shot_{index}")
        for index, shot in enumerate(storyboard[:3], start=1)
        if isinstance(shot, dict)
    ]
    first_shot = shot_ids[0] if shot_ids else "shot_1"
    second_shot = shot_ids[1] if len(shot_ids) > 1 else first_shot
    third_shot = shot_ids[2] if len(shot_ids) > 2 else second_shot
    return [
        {
            "plan_id": "asset_1",
            "time_range": "0s-9s",
            "shot_ids": [first_shot],
            "narrative_phase": "Hook",
            "asset_type": "digital_human_avatar",
            "moras_asset_category": "none",
            "layer": "base_track",
            "usage_reason": "Use the selected persona's digital-human prompt asset to establish trust and make the hook feel native to short-form social video.",
            "editor_note": "Generate or bind persona-led base footage from the prompt asset; spoken delivery comes from the persona voice direction and script lines.",
        },
        {
            "plan_id": "asset_2",
            "time_range": "9s-25s",
            "shot_ids": [second_shot],
            "narrative_phase": "Solution / Proof",
            "asset_type": "real_moras_screen_recording",
            "moras_asset_category": "workflow_screen_recording",
            "layer": "cutaway",
            "usage_reason": "Use real Moras workflow footage when the script explains selected-product-to-ready-video efficiency.",
            "editor_note": "Cut away from the base track to approved Moras screen recording; show product library, Generate, ready-with-cart video, and posting entry.",
        },
        {
            "plan_id": "asset_3",
            "time_range": "25s-38s",
            "shot_ids": [third_shot],
            "narrative_phase": "CTA / Resolution",
            "asset_type": "post_production_overlay",
            "moras_asset_category": "none",
            "layer": "overlay",
            "usage_reason": "Use editing overlays for CTA, arrows, highlights, and final reminder without contaminating Veo source-footage prompts.",
            "editor_note": "Add the CTA and highlights in editing; keep the ending flexible for a 35-45s cut.",
        },
    ]


MOCK_SCRIPT_VARIANTS: list[dict[str, Any]] = [
    {
        "title": "5K Creator Wake-Up Call",
        "title_zh": "5K 达人紧急提醒",
        "audience": "5K+ TikTok Shop Creator",
        "audience_zh": "5K+ TikTok Shop 达人",
        "content_angle": "Open with an urgent callout to 5K+ TikTok Shop creators and move quickly into proof and Generate workflow.",
        "content_angle_zh": "用 5K+ TikTok Shop 达人的紧急点名开场，快速进入证明和 Generate 流程。",
        "core_pain": "Affiliate creators work every day while top creators already see what converts and what to promote.",
        "core_pain_zh": "带货达人每天都在苦做内容，而头部达人已经知道什么在转化、该推什么。",
        "emotional_angle": "Urgency from discovering the missing advantage.",
        "emotional_angle_zh": "发现缺失优势后的紧迫感。",
        "hook": "Girl, if you're a 5K+ TikTok Shop creator, listen up.",
        "hook_zh": "如果你是 5K+ TikTok Shop 达人，听我说。",
        "bridge": "Top creators see what sells before the rest of us guess.",
        "bridge_zh": "头部达人在我们瞎猜前，就已经看到什么卖得动。",
        "check_line": "Here's proof from creator handles and GMV screenshots.",
        "check_line_zh": "这里有达人 handle 和 GMV 截图作证明。",
        "moras_line": "Now I open Moras and choose a product.",
        "moras_line_zh": "现在我打开 Moras，选一个商品。",
        "payoff": "Moras makes the video and shows the commerce path.",
        "payoff_zh": "Moras 会做出视频，并展示带货路径。",
        "opportunity": "That gives me more videos I can actually post.",
        "opportunity_zh": "这样我能多做几条真正可以发布的视频。",
        "cta": "If you're a 5K+ TikTok Shop creator, click the button. Make your own money.",
        "cta_zh": "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。",
        "overlay_en": ["5K+ creators", "Hit Generate", "Path visible"],
        "overlay_zh": ["5K+ 达人", "点击 Generate", "带货路径可见"],
        "hook_candidates": [
            "[Direct Callout] Girl, if you're a 5K+ TikTok Shop creator, listen up.",
            "[Curiosity Gap] Why are top creators winning while you're still guessing?",
            "[Open Loop] The unfair part is they already know what is converting.",
            "[Psychological Trigger] Guessing gets expensive when every product looks urgent.",
            "[POV] POV: you have 5K followers and still don't know what to promote.",
            "[Empathy] If TikTok Shop feels like work without money, this is for you.",
        ],
        "hook_candidates_zh": [
            "[直接点名] 如果你是 5K+ TikTok Shop 达人，听我说。",
            "[好奇缺口] 为什么头部达人赢了，而你还在猜？",
            "[开放循环] 不公平的是，他们已经知道什么在转化。",
            "[心理触发] 当每个商品都很急，瞎猜会变得很贵。",
            "[POV] POV：你有 5K 粉丝，却还不知道该推什么。",
            "[共情] 如果 TikTok Shop 只有工作没有钱，这条是给你的。",
        ],
        "source_summary": ["5K creator hook", "GMV proof screenshots", "Generate workflow", "Click-button CTA"],
    },
    {
        "title": "This App Needs to Be Exposed",
        "title_zh": "这个 App 应该被曝光",
        "audience": "Under-monetized TikTok Shop Creator",
        "audience_zh": "还没赚到钱的 TikTok Shop 达人",
        "content_angle": "Use a whispery exposed-app hook, then show proof clips before the Moras Generate workflow.",
        "content_angle_zh": "用压低声音的爆料式开头，再展示证明切片和 Moras Generate 流程。",
        "core_pain": "Creators are still digging for products, writing scripts, and guessing manually while others move faster.",
        "core_pain_zh": "很多达人还在手动找品、写脚本和瞎猜，而别人已经跑得更快。",
        "emotional_angle": "The feeling of finding a tool nobody is talking about.",
        "emotional_angle_zh": "发现一个没人公开讲的工具时的爆料感。",
        "hook": "I'm sorry, but this app needs to be exposed.",
        "hook_zh": "不好意思，但这个 App 真的该被曝光。",
        "bridge": "Creators are using it to skip the slowest TikTok Shop steps.",
        "bridge_zh": "有达人正在用它跳过 TikTok Shop 最慢的步骤。",
        "check_line": "Most people still dig for products, write scripts, and guess.",
        "check_line_zh": "大多数人还在找品、写脚本、瞎猜。",
        "moras_line": "In Moras, I choose a product.",
        "moras_line_zh": "在 Moras 里，我选一个商品。",
        "payoff": "Moras makes the video and shows the commerce path.",
        "payoff_zh": "Moras 会做出视频，并展示带货路径。",
        "opportunity": "That's the part that used to eat my whole night.",
        "opportunity_zh": "这正是以前会吃掉我一整晚的部分。",
        "cta": "If you're a 5K+ TikTok Shop creator, click the button. Make your own money.",
        "cta_zh": "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。",
        "overlay_en": ["This app exposed", "Here's proof", "Path visible"],
        "overlay_zh": ["这个 App 曝光", "这里有证明", "带货路径可见"],
        "hook_candidates": [
            "[Open Loop] I'm sorry, but this app needs to be exposed.",
            "[Curiosity Gap] Nobody is talking about the tool creators are quietly using.",
            "[Empathy] If TikTok Shop still feels manual, this is probably for you.",
            "[Mini Drama] I found the app, opened it, and stopped rewriting the same product script.",
            "[Psychological Trigger] The exhausting part is not filming. It is guessing what works.",
            "[Direct Callout] If you have TikTok Shop access and no real money yet, watch this.",
        ],
        "hook_candidates_zh": [
            "[开放循环] 不好意思，但这个 App 真的该被曝光。",
            "[好奇缺口] 没人在讲这个达人悄悄用的工具。",
            "[共情] 如果 TikTok Shop 对你来说还全是手动，这条可能适合你。",
            "[小剧场] 我找到这个 App，打开后，就不用重写同一个商品脚本了。",
            "[心理触发] 累人的不是拍摄，而是一直猜什么有效。",
            "[直接点名] 如果你有 TikTok Shop 账号但还没赚到真钱，看这个。",
        ],
        "source_summary": ["Exposed-app hook", "Creator proof clips", "Niche-product Generate", "Left-corner CTA"],
    },
    {
        "title": "Midnight Product Posting Flow",
        "title_zh": "午夜商品发布流程",
        "audience": "Side-hustle Creator",
        "audience_zh": "副业型创作者",
        "content_angle": "Turn late-night product excitement into a calmer product-to-video posting flow.",
        "content_angle_zh": "把深夜选品的兴奋感转成更清楚的商品到视频发布流程。",
        "core_pain": "A promising product can still fail when the creator guesses manually instead of using current product proof.",
        "core_pain_zh": "一个看似有潜力的商品，如果还靠手动猜测而不是当前证明，也可能跑不起来。",
        "emotional_angle": "Manual exhaustion turning into a clear product-to-video workflow.",
        "emotional_angle_zh": "从手动疲惫转为清晰的商品到视频流程。",
        "hook": "Most creators are still doing every TikTok Shop step manually.",
        "hook_zh": "大多数达人还在手动做 TikTok Shop 的每一步。",
        "bridge": "Product digging, script writing, and guessing what sells gets exhausting.",
        "bridge_zh": "找品、写脚本、猜什么卖得动，真的很耗人。",
        "check_line": "The proof is in creator screenshots, not magic promises.",
        "check_line_zh": "证明来自达人截图，不是魔法承诺。",
        "moras_line": "I choose a product in Moras.",
        "moras_line_zh": "我在 Moras 选一个商品。",
        "payoff": "Moras makes the video and shows the commerce path.",
        "payoff_zh": "Moras 会做出视频，并展示带货路径。",
        "opportunity": "Now I can post while the product window is still warm.",
        "opportunity_zh": "现在我能在商品窗口还热的时候发布视频。",
        "cta": "If you're a 5K+ TikTok Shop creator, click the button. Make your own money.",
        "cta_zh": "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。",
        "overlay_en": ["Manual workflow", "Generate video", "Path visible"],
        "overlay_zh": ["手动流程", "生成视频", "带货路径可见"],
        "hook_candidates": [
            "[POV] POV: your TikTok Shop workflow still has 47 manual steps.",
            "[Funny Overstatement] My product list was moving faster than my actual posting flow.",
            "[Curiosity Gap] The product was not the problem. The manual workflow was.",
            "[Psychological Trigger] Guessing what converts gets exhausting when every product looks urgent.",
            "[Open Loop] One Generate click changed the whole product-to-posting path.",
            "[Before/After] Before, I guessed for hours. Now I start with proof.",
        ],
        "hook_candidates_zh": [
            "[POV] POV：你的 TikTok Shop 流程还有 47 个手动步骤。",
            "[夸张幽默] 我的商品列表跑得比我的发布流程还快。",
            "[好奇缺口] 有问题的不是商品，而是手动流程。",
            "[心理触发] 当每个商品都很急，猜什么转化真的很累。",
            "[开放循环] 一次 Generate 点击改变了商品到发布的路径。",
            "[前后对比] 以前我猜几个小时，现在先看证明。",
        ],
        "source_summary": ["Manual workflow hook", "Creator proof screenshots", "Generate-to-commerce-path video", "Click-button CTA"],
    },
]

MOCK_EXTRA_SCRIPT_AXES = [
    ("5K Creator Product Library", "5K 达人爆品库", "5K+ Creator", "5K+ 达人", "If you have 5K followers and still do TikTok Shop manually, watch this.", "如果你有 5K 粉丝还在手动做 TikTok Shop，看这个。", "5K creator callout", "Product library proof"),
    ("Proof Screenshot Reveal", "证明截图爆出", "Proof-Led Creator", "证明导向达人", "I'm not asking you to believe me. Look at the creator proof first.", "我不是让你信我，先看达人证明。", "Proof reveal hook", "GMV screenshot proof"),
    ("Generate Button Moment", "Generate 按钮瞬间", "Workflow Creator", "流程型达人", "The moment I hit Generate is where the manual workflow gets lighter.", "我点击 Generate 的那一刻，手动流程就轻了。", "Generate click hook", "Path visible hold"),
    ("Commerce Path Hold", "带货路径可见停留", "TikTok Shop Affiliate", "TikTok Shop 联盟达人", "The important part is not a script. Moras shows the commerce path too.", "重点不是脚本，Moras 也会展示带货路径。", "Commerce-path hook", "Commerce path hold"),
    ("Top Creator Advantage", "头部达人优势", "Ambitious Affiliate", "有增长目标的联盟达人", "Top creators are not guessing every product from zero.", "头部达人不是每个商品都从零开始猜。", "Top-creator proof hook", "Current converting products"),
    ("Manual Workflow Killer", "干掉手动流程", "Solo Affiliate Creator", "单人联盟达人", "Most creators are still doing the money work by hand.", "大多数达人还在手动做最该赚钱的环节。", "Manual workflow hook", "One-click publish path"),
    ("Left-Corner CTA", "左下角 CTA", "Action-Oriented Creator", "行动型达人", "If you're a TikTok Shop creator, the button is the next step.", "如果你是 TikTok Shop 达人，下一步就是点按钮。", "Click-button hook", "Direct CTA"),
]


def mock_script_variant(index: int) -> dict[str, Any]:
    if index < len(MOCK_SCRIPT_VARIANTS):
        return dict(MOCK_SCRIPT_VARIANTS[index])
    (
        title,
        title_zh,
        audience,
        audience_zh,
        hook,
        hook_zh,
        summary_1,
        summary_2,
    ) = MOCK_EXTRA_SCRIPT_AXES[(index - len(MOCK_SCRIPT_VARIANTS)) % len(MOCK_EXTRA_SCRIPT_AXES)]
    return {
        "title": title,
        "title_zh": title_zh,
        "audience": audience,
        "audience_zh": audience_zh,
        "content_angle": f"Open with the specific creator tension behind {title.lower()}, then show the Moras product-library to Generate to completed product-video output flow.",
        "content_angle_zh": f"从「{title_zh}」背后的达人张力开场，再展示 Moras 爆品库到 Generate 到带货路径结果的流程。",
        "core_pain": f"The creator wants TikTok Shop money, but manual product digging, script writing, and guessing slow down {summary_2.lower()}.",
        "core_pain_zh": f"达人想赚 TikTok Shop 的钱，但手动找品、写脚本和猜测会拖慢「{summary_2}」。",
        "emotional_angle": "Urgency from seeing that the manual workflow is the real blocker.",
        "emotional_angle_zh": "意识到手动流程才是真正阻碍后的紧迫感。",
        "hook": hook,
        "hook_zh": hook_zh,
        "bridge": "The tiring part is digging, scripting, and guessing what actually converts.",
        "bridge_zh": "真正累的是找品、写稿、猜什么真的会转化。",
        "check_line": "Use approved proof screenshots, not a made-up income promise.",
        "check_line_zh": "用已批准的证明截图，而不是编一个收入承诺。",
        "moras_line": "I choose a product in Moras.",
        "moras_line_zh": "我在 Moras 选一个商品。",
        "payoff": "Moras makes the video and shows the commerce path.",
        "payoff_zh": "Moras 会做出视频，并展示带货路径。",
        "opportunity": "That gives me another video before the day disappears.",
        "opportunity_zh": "这样一天过去前，我还能多做一条视频。",
        "cta": "If you're a 5K+ TikTok Shop creator, click the button. Make your own money.",
        "cta_zh": "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。",
        "overlay_en": [summary_1, summary_2, "Make your own money"],
        "overlay_zh": [title_zh, "带货路径可见", "赚自己的钱"],
        "hook_candidates": [
            f"[Psychological Trigger] {hook}",
            "[Curiosity Gap] The product was not confusing. The manual workflow was.",
            "[Open Loop] This one Generate click shows the finished video.",
            "[POV] POV: the product looks good, but the posting workflow still feels heavy.",
            "[Unexpected Analogy] Manual TikTok Shop work is like a checkout line; if it stalls, people leave.",
            "[Empathy] If you keep rewriting the same opener, the workflow is taking money time.",
        ],
        "hook_candidates_zh": [
            f"[心理触发] {hook_zh}",
            "[好奇缺口] 不是商品让人困惑，而是手动流程太重。",
            "[开放循环] 一次 Generate 点击会展示完成的视频。",
            "[POV] POV：商品看起来不错，但发布流程还是很重。",
            "[意外类比] 手动 TikTok Shop 流程就像结账队伍，一卡住人就走了。",
            "[共情] 如果你一直重写同一个开头，流程正在吃掉赚钱时间。",
        ],
        "source_summary": [summary_1, summary_2, "Generate-to-post CTA", "Moras selected-product workflow scene"],
    }


def mock_script_voiceover_lines(variant: dict[str, Any]) -> list[str]:
    return [
        str(variant["hook"]),
        str(variant["bridge"]),
        str(variant["check_line"]),
        str(variant.get("old_way", "The old way burns time before I even post.")),
        "That delay costs me another posting window.",
        "So I stop guessing and protect the posting window.",
        str(variant["moras_line"]),
        "I choose the product I want to promote.",
        str(variant.get("generate_line", "Then I hit Generate.")),
        "Moras makes the video for that product.",
        "The commerce path is visible so the post can sell.",
        "I watch it like a real shopper would.",
        str(variant.get("check_result", "I check it before I post.")),
        str(variant["opportunity"]),
    ]


def mock_script_voiceover_lines_zh(variant: dict[str, Any]) -> list[str]:
    return [
        str(variant["hook_zh"]),
        str(variant["bridge_zh"]),
        str(variant["check_line_zh"]),
        str(variant.get("old_way_zh", "旧办法会在发布前耗掉很多时间。")),
        "这个延迟会让我错过一次发布时间。",
        "所以我停止瞎猜，也保住发布时间。",
        str(variant["moras_line_zh"]),
        "我选择想推广的商品。",
        str(variant.get("generate_line_zh", "然后我点击 Generate。")),
        "Moras 会为这个商品做出视频。",
        "它会展示带货路径，让内容可以卖货。",
        "我会像真实买家一样看一遍。",
        str(variant.get("check_result_zh", "我会先检查，再决定发布。")),
        str(variant["opportunity_zh"]),
    ]


def ensure_mock_storyboard_rows(item: dict[str, Any], row_count: int) -> None:
    while len(item["storyboard"]) < row_count:
        row_index = len(item["storyboard"]) + 1
        start = (row_index - 1) * 4
        template = copy.deepcopy(item["storyboard"][-1])
        template.update(
            {
                "shot_id": f"shot_{row_index}",
                "timestamp": f"{start}s-{start + 4}s",
                "duration": "4s",
                "voiceover": "I check the next step before I post.",
                "overlay": "Check first",
            }
        )
        item["storyboard"].append(template)


def mock_storyboard_template_en() -> list[dict[str, Any]]:
    return [
        {
            "camera": "Vertical creator close-up, slightly handheld, with the phone held near the lens like a breaking-news reveal.",
            "character_action": "The creator leans in and delivers the creator callout with urgent eye contact.",
            "facial_expression": "A controlled I-need-to-show-you-this expression, not a polished product demo smile.",
            "background": "Creator bedroom or desk setup with a phone, laptop, and one visible product package.",
            "props": ["phone", "laptop", "product box"],
            "overlay": "5K+ creators",
            "sound": "Fast whoosh into a low, urgent beat.",
            "transition": "Hard cut on the last word.",
            "purpose": "Land the creator-specific hook before the app appears.",
        },
        {
            "camera": "Fast proof montage with cropped creator handle pages and approved GMV or income screenshots bouncing onto screen.",
            "character_action": "Proof cards stack and snap into place around the screen.",
            "facial_expression": "No face shown; the proof assets carry the beat.",
            "background": "Darkened edit background with high-contrast green or gold proof numbers.",
            "props": ["creator handle screenshot", "GMV screenshot", "income proof card"],
            "overlay": "Proof first",
            "sound": "Three fast pop sounds synced to proof inserts.",
            "transition": "Screenshot stack wipes into a creator desk shot.",
            "purpose": "Use approved creator proof without promising a fixed outcome.",
        },
        {
            "camera": "Desk close-up; the creator crosses out a messy product note and pauses.",
            "character_action": "The creator taps the crossed-out note, then points to the screen as the old process stalls.",
            "facial_expression": "Frustrated but conversational, like explaining a mistake to a friend.",
            "background": "Messy creator desk with notes, product packaging, phone, and laptop browser tabs.",
            "props": ["sticky notes", "phone", "product packaging", "laptop"],
            "overlay": "Old way",
            "sound": "Pencil scratch and short pause.",
            "transition": "Desk note wipes into Moras screen recording.",
            "purpose": "Make the old manual cost visible before the Moras workflow.",
        },
        {
            "camera": "Full-screen Moras screen recording; cursor opens the app and pauses on the product library.",
            "character_action": "The cursor enters Moras and scrolls products that are picking up.",
            "facial_expression": "No face shown; optional digital-human window stays small in the corner.",
            "background": "Moras product-library UI with approved sales or product signals visible.",
            "props": ["Moras capture", "product library", "product filters"],
            "overlay": "Open Moras",
            "sound": "Scroll tick and click sound.",
            "transition": "Quick zoom toward the chosen product.",
            "purpose": "Show that Moras starts from product discovery, not pasted product data.",
        },
        {
            "camera": "Moras screen recording tight crop on a selected product and its detail area.",
            "character_action": "The cursor chooses one product and pauses long enough for the selection state to read.",
            "facial_expression": "No face shown; the selection state carries the beat.",
            "background": "Moras product detail and selection UI with product signal cards.",
            "props": ["Moras capture", "selected product", "product signals"],
            "overlay": "Choose product",
            "sound": "Clean tap sound.",
            "transition": "Snap zoom from selection to the Generate button.",
            "purpose": "Make the product-selection step separate and easy to follow.",
        },
        {
            "camera": "Moras screen recording tight crop on the Generate button.",
            "character_action": "The cursor taps Generate, waits one beat, and a processing state appears.",
            "facial_expression": "No face shown; the button click is the action.",
            "background": "Same Moras workflow view moving from selection to generation.",
            "props": ["Moras capture", "Generate button", "processing state"],
            "overlay": "Hit Generate",
            "sound": "Click followed by a short success tone.",
            "transition": "Processing state cuts to completed output.",
            "purpose": "Make the one-click Generate value visible and concrete.",
        },
        {
            "camera": "Screen recording holds on the completed video, commerce path, and posting entry.",
            "character_action": "The cursor hovers over the generated video and commerce path state without rushing.",
            "facial_expression": "No face shown; the visible completion state is the point.",
            "background": "Moras completed-output state with commerce path and posting entry visible if approved.",
            "props": ["generated video", "commerce path", "posting entry"],
            "overlay": "Path visible",
            "sound": "Beat drops out briefly so the output is readable.",
            "transition": "Output hold cuts to a quick check view.",
            "purpose": "Show the generated video and commerce path as the main product value.",
        },
        {
            "camera": "Moras Posts or draft review view with check/edit controls visible.",
            "character_action": "The cursor checks the output, pauses on text review, then moves toward the posting entry.",
            "facial_expression": "No face shown; the review controls make this feel operational.",
            "background": "Moras Drafts or Posts workflow with pre-check or edit controls visible if approved.",
            "props": ["draft review", "text check", "posting entry"],
            "overlay": "Check first",
            "sound": "Soft confirmation tap.",
            "transition": "Review view wipes back to creator desk.",
            "purpose": "Show the creator still checks the output instead of blindly trusting it.",
        },
        {
            "camera": "Creator desk medium close-up with notes now organized into a short posting checklist.",
            "character_action": "The creator circles the next product to promote and moves the product notes beside the phone.",
            "facial_expression": "Relieved, practical, and still grounded.",
            "background": "Same creator desk with Moras screen blurred in the background.",
            "props": ["posting checklist", "product notes", "phone"],
            "overlay": "Post smarter",
            "sound": "Paper slide and light beat pickup.",
            "transition": "Push into creator face for CTA.",
            "purpose": "Translate Moras into a better posting routine, not a guaranteed result.",
        },
        {
            "camera": "Vertical creator close-up, background blurred, face larger in frame for the final CTA.",
            "character_action": "The creator points toward the button and finishes with one direct line.",
            "facial_expression": "Confident, urgent, and straightforward.",
            "background": "Blurred Moras output or creator desk with no extra explanatory text.",
            "props": ["phone", "CTA button direction"],
            "overlay": "Make your own money",
            "sound": "Short final click and music stop.",
            "transition": "Final freeze on the pointing gesture.",
            "purpose": "Close with the direct TikTok Shop creator CTA.",
        },
    ]


def mock_storyboard_template_zh() -> list[dict[str, Any]]:
    return [
        {
            "camera": "真人或数字人竖屏近景，手机靠近镜头，像刚发现一个必须马上说的东西。",
            "character_action": "创作者前倾看镜头，用紧迫语气点名目标达人。",
            "facial_expression": "像压不住要爆料，但仍保持可信克制。",
            "background": "创作者卧室或桌面场景，有手机、电脑和一个商品包装。",
            "props": ["手机", "电脑", "商品盒"],
            "sound": "快速 whoosh 进入低音量紧迫节奏。",
            "transition": "在最后一个词上硬切。",
            "purpose": "先让目标达人感到这条内容和自己直接相关。",
        },
        {
            "camera": "快速证明蒙太奇，裁切达人 handle 页和已批准 GMV / 收入截图并弹入画面。",
            "character_action": "证明卡片围绕屏幕快速叠放，不新增虚假个人收入。",
            "facial_expression": "不露脸，由证明素材承担这一拍。",
            "background": "暗色剪辑背景，绿色或金色大数字突出。",
            "props": ["达人 handle 截图", "GMV 截图", "收入证明卡"],
            "sound": "三次短促弹出音，对齐证明卡片。",
            "transition": "截图堆叠擦拭切入创作者桌面。",
            "purpose": "用已批准达人证明建立可信度，但不写成固定收益承诺。",
        },
        {
            "camera": "桌面近景，创作者划掉一条混乱的商品笔记后停顿。",
            "character_action": "创作者点一下被划掉的笔记，再指向屏幕，表现旧流程卡住。",
            "facial_expression": "有点烦，但像在和朋友讲一个踩过的坑。",
            "background": "凌乱创作者桌面，有便签、商品包装、手机和电脑页面。",
            "props": ["便签", "手机", "商品包装", "电脑"],
            "sound": "笔划纸面的声音后短暂停顿。",
            "transition": "便签擦拭切入 Moras 录屏。",
            "purpose": "在 Moras 出现前，把旧办法的成本先演出来。",
        },
        {
            "camera": "Moras 全屏录屏，光标打开 app 并在商品库停留一秒。",
            "character_action": "光标进入 Moras，快速浏览正在起量的商品。",
            "facial_expression": "不露脸；可在角落保留小数字人窗口。",
            "background": "Moras 商品库 UI，展示已批准的商品和销量信号。",
            "props": ["Moras 录屏", "商品库", "商品筛选器"],
            "sound": "滚动 tick 声和点击声。",
            "transition": "快速放大到被选中的商品。",
            "purpose": "说明 Moras 从商品发现开始，不是粘贴商品数据。",
        },
        {
            "camera": "Moras 录屏特写，裁到被选中的商品和商品详情区域。",
            "character_action": "光标选中一个商品，并停留到观众能看懂选择状态。",
            "facial_expression": "不露脸，由选择状态承担这一拍。",
            "background": "Moras 商品详情和选择 UI，带商品信号卡片。",
            "props": ["Moras 录屏", "已选商品", "商品信号"],
            "sound": "清晰点击声。",
            "transition": "从选择状态快速推到 Generate 按钮。",
            "purpose": "把选商品单独拆出来，让流程更容易听懂。",
        },
        {
            "camera": "Moras 录屏特写，裁到 Generate 按钮。",
            "character_action": "光标点击 Generate，停顿一拍，出现处理中状态。",
            "facial_expression": "不露脸，按钮点击就是动作重点。",
            "background": "同一 Moras 工作流，从选择进入生成。",
            "props": ["Moras 录屏", "Generate 按钮", "处理中状态"],
            "sound": "点击声后接短促成功提示音。",
            "transition": "处理中状态切到完成结果。",
            "purpose": "让一键 Generate 的卖点被观众看见。",
        },
        {
            "camera": "录屏停在生成视频、带货路径和发布入口。",
            "character_action": "光标悬停在生成视频和带货路径状态，不急着切走。",
            "facial_expression": "不露脸，生成完成状态就是画面重点。",
            "background": "Moras 完成态界面，展示生成视频、带货路径和发布入口。",
            "props": ["生成视频", "带货路径", "发布入口"],
            "sound": "音乐短暂留白，让结果界面可读。",
            "transition": "完成态切到检查界面。",
            "purpose": "把生成视频和带货路径状态作为主价值点。",
        },
        {
            "camera": "Moras Posts 或草稿检查界面，能看到检查和编辑控件。",
            "character_action": "光标检查输出，停在文字检查处，再移动到发布入口。",
            "facial_expression": "不露脸，由检查控件体现这是实际操作。",
            "background": "Moras Drafts 或 Posts 流程，展示可批准的 pre-check 或编辑控件。",
            "props": ["草稿检查", "文字检查", "发布入口"],
            "sound": "轻柔确认点击声。",
            "transition": "检查界面擦回创作者桌面。",
            "purpose": "说明创作者仍会检查结果，而不是盲信工具。",
        },
        {
            "camera": "创作者桌面中近景，笔记整理成一张短发布清单。",
            "character_action": "创作者圈出下一个要推广的商品，把商品便签放到手机旁边。",
            "facial_expression": "放松、实际，仍然有落地感。",
            "background": "同一创作者桌面，背景里虚化显示 Moras 界面。",
            "props": ["发布清单", "商品便签", "手机"],
            "sound": "纸张滑动声，节奏轻轻抬起。",
            "transition": "推进到创作者大脸 CTA。",
            "purpose": "把 Moras 落到更好的发布节奏，而不是保证结果。",
        },
        {
            "camera": "竖屏创作者近景，背景虚化，人物脸部更大用于收束 CTA。",
            "character_action": "创作者指向按钮，并用一句话结束。",
            "facial_expression": "自信、紧迫、直接。",
            "background": "虚化的 Moras 完成态或创作者桌面，不加多余说明文字。",
            "props": ["手机", "CTA 按钮方向"],
            "sound": "最后一个点击音后音乐停住。",
            "transition": "定格在指向按钮的动作。",
            "purpose": "用直接 TikTok Shop 达人 CTA 收尾。",
        },
    ]


def build_mock_script_batch(request: ScriptGenerationRequest, source_records: list[Any]) -> ScriptAgentBatch:
    source_ids = [record.id for record in source_records]
    selected_persona = normalized_selected_creator_persona(request)
    items = [
        build_mock_script_item(
            index=index,
            script_type=request.script_type,
            source_ids=source_ids,
            selected_persona=selected_persona,
        )
        for index in range(request.script_count)
    ]
    return ScriptAgentBatch(scripts=items)


def set_localized_zh(target: dict[str, Any], values: dict[str, Any]) -> None:
    localized = target.get("localized")
    if not isinstance(localized, dict):
        localized = {}
        target["localized"] = localized
    zh = localized.get(LOCALIZED_LANGUAGE_KEY)
    if not isinstance(zh, dict):
        zh = {}
        localized[LOCALIZED_LANGUAGE_KEY] = zh
    zh.update({key: value for key, value in values.items() if value is not None})


def apply_mock_language_contract(item: dict[str, Any], variant: dict[str, Any]) -> None:
    item["source_component_summary"] = list(variant["source_summary"])
    title_zh = str(variant["title_zh"])
    script_voiceover_en = mock_script_voiceover_lines(variant)
    script_voiceover_zh = mock_script_voiceover_lines_zh(variant)
    set_localized_zh(item["topic_plan"], {
        "title": title_zh,
        "target_audience": variant["audience_zh"],
        "content_angle": variant["content_angle_zh"],
        "trend_source": "来自社媒视频拆解库的 Hook、结构和视觉节奏因子。",
        "template": localize_to_chinese(item["topic_plan"].get("template")),
        "persona": "实用型创作者朋友",
        "hook_candidates": variant["hook_candidates_zh"],
        "cta_candidates": [variant["cta_zh"], "如果你是 5K+ TikTok Shop 达人，点击按钮，赚自己的钱。"],
        "recommended_platform": "TikTok / Reels / Shorts",
    })
    item["topic_plan"]["trend_source"] = "Hook, structure, and visual pacing factors from the social video teardown library."

    item["script"]["voiceover"] = script_voiceover_en
    set_localized_zh(item["script"], {
        "script_title": title_zh,
        "target_audience": variant["audience_zh"],
        "persona": "实用型创作者朋友",
        "template": localize_to_chinese(item["script"].get("template")),
        "core_pain": variant["core_pain_zh"],
        "emotional_angle": variant["emotional_angle_zh"],
        "hook": variant["hook_zh"],
        "voiceover": script_voiceover_zh,
        "visual": "真人或数字人口播、达人证明截图、真实 Moras 商品库录屏，以及点击 Generate 后带货路径可见的视频。",
        "overlay": variant["overlay_zh"],
        "sound_effect": "轻快点击声，步骤切换时使用短促提示音。",
        "proof_insert": "展示已批准的达人 handle / GMV / 收入证明截图，再展示选中商品、点击 Generate、视频带货路径可见；不要写成固定收益承诺。",
        "cta": variant["cta_zh"],
        "compliance_note": "可以展示已批准达人结果证明，但不能承诺所有人都会获得固定销量或收入。",
    })
    item["script"]["overlay"] = list(variant["overlay_en"])
    item["script"]["sound_effect"] = "Light click sounds with short confirmation tones during step changes."

    english_storyboard = [
        {
            "camera": "Vertical creator close-up, slightly handheld, with the phone held near the lens like a breaking-news reveal.",
            "character_action": "The creator leans in and delivers the 5K+ TikTok Shop callout with urgent eye contact.",
            "facial_expression": "A controlled I-need-to-show-you-this expression, not a polished product demo smile.",
            "background": "Creator bedroom or desk setup with a phone, laptop, and one visible product package.",
            "props": ["phone", "laptop", "product box"],
            "overlay": "5K+ creators",
            "sound": "Fast whoosh into a low, urgent beat.",
            "transition": "Hard cut on the word proof.",
            "purpose": "Land the creator-specific hook before the app appears.",
        },
        {
            "camera": "Fast proof montage with cropped creator handle pages and approved GMV or income screenshots bouncing onto screen.",
            "character_action": "No character action; proof cards stack and snap into place around the screen.",
            "facial_expression": "No face shown; the proof assets carry the beat.",
            "background": "Darkened edit background with high-contrast green or gold proof numbers.",
            "props": ["creator handle screenshot", "GMV screenshot", "income proof card"],
            "overlay": "Here's proof",
            "sound": "Three fast pop sounds synced to proof inserts.",
            "transition": "Screenshot stack wipes into the Moras screen recording.",
            "purpose": "Use approved creator proof without turning it into a fixed-income outcome claim.",
        },
        {
            "camera": "Full-screen Moras screen recording; cursor opens the app and pauses on the product library.",
            "character_action": "The cursor browses the product library, scrolls products that are picking up, and lands on one selected product.",
            "facial_expression": "No face shown; optional digital-human window stays small in the corner.",
            "background": "Moras product-library UI with sales/product signals visible if approved.",
            "props": ["Moras capture", "product library", "product filters", "selected product"],
            "overlay": "Pick your product",
            "sound": "Scroll tick and click sound.",
            "transition": "Quick zoom toward the Generate button.",
            "purpose": "Show that Moras starts from product discovery, not pasted product data.",
        },
        {
            "camera": "Moras screen recording tight crop on the selected product and Generate button.",
            "character_action": "The cursor taps Generate, waits one beat, and the generated video appears.",
            "facial_expression": "No face shown; digital-human corner window subtly enlarges during the voiceover line.",
            "background": "Same Moras workflow view, now moving from selection to completed product-video output.",
            "props": ["Moras capture", "Generate button", "generated video", "commerce path"],
            "overlay": "Hit Generate",
            "sound": "Clean click followed by a short success tone.",
            "transition": "Hold on the completed output for one full second.",
            "purpose": "Make the one-click Generate value visible and concrete.",
        },
        {
            "camera": "Screen recording holds on the completed video, commerce path, and posting entry.",
            "character_action": "The cursor hovers over the output/video output and then the publish or posting entry without rushing.",
            "facial_expression": "No face shown; the visible completion state is the point.",
            "background": "Moras completed-output state with commerce path and posting entry visible if approved.",
            "props": ["generated video", "commerce path", "posting entry"],
            "overlay": "Path visible",
            "sound": "Beat drops out briefly so the output is readable.",
            "transition": "Blurred output becomes money-proof typography.",
            "purpose": "Show the generated video and commerce path as the main product value.",
        },
        {
            "camera": "Dark result-reinforcement card with large green or gold proof numbers and subtle shake.",
            "character_action": "Approved proof numbers jump in one by one; no fake personal earnings are added.",
            "facial_expression": "No face shown; typography and proof assets carry the result beat.",
            "background": "Dark background derived from blurred Moras output.",
            "props": ["proof numbers", "creator proof cards", "GMV screenshot"],
            "overlay": "Not luck. Workflow.",
            "sound": "Money-card hits with a restrained bass accent.",
            "transition": "Push into creator face for CTA.",
            "purpose": "Reinforce observed creator results without promising the viewer a fixed result.",
        },
        {
            "camera": "Vertical creator close-up, background blurred, face larger in frame for the final CTA.",
            "character_action": "The creator points toward the left-corner button and finishes with one direct line.",
            "facial_expression": "Confident, urgent, and straightforward.",
            "background": "Blurred Moras output or creator desk, with no extra explanatory text.",
            "props": ["phone", "CTA button direction"],
            "overlay": "Make your own money",
            "sound": "Short final click and music stop.",
            "transition": "Final freeze on the pointing gesture.",
            "purpose": "Close with the direct TikTok Shop creator CTA.",
        },
    ]
    english_storyboard = mock_storyboard_template_en()
    for shot_index, shot in enumerate(english_storyboard, start=1):
        shot["bgm"] = "Light upbeat background rhythm kept under the creator voice."
        shot["sound_effects"] = compact_string_list([shot.get("sound")], max_items=3, max_chars=70)
        shot["subtitle_logic"] = "Use one short caption to name the beat; keep it under six words and synchronized with the voiceover emphasis."
        shot["visual_elements"] = compact_string_list([*shot.get("props", []), shot.get("overlay")], max_items=8, max_chars=60)
        shot["visual_element_logic"] = (
            "Add only the visual element that proves this beat: hook emphasis in the opening, workflow proof in the middle, "
            "and CTA reinforcement near the ending."
        )
    storyboard_voiceover_en = list(item["script"]["voiceover"]) + [variant["cta"]]
    storyboard_voiceover_zh = script_voiceover_zh + [variant["cta_zh"]]
    storyboard_overlay_zh = [
        "5K+ 达人",
        "先看证明",
        "旧办法",
        "打开 Moras",
        "选商品",
        "点击 Generate",
        "带货路径可见",
        "先检查",
        "直接出片",
        "赚自己的钱",
    ]
    storyboard_overlay_en = [
        "5K+ creators",
        "Proof first",
        "Old way",
        "Open Moras",
        "Choose product",
        "Hit Generate",
        "Path visible",
        "Check first",
        "Post smarter",
        "Make your own money",
    ]
    storyboard_groups = [
        {"template": 0, "lines": [0], "overlay_en": "5K+ creators", "overlay_zh": "5K+ 达人"},
        {"template": 1, "lines": [1, 2], "overlay_en": "Proof first", "overlay_zh": "先看证明"},
        {"template": 2, "lines": [3, 4], "overlay_en": "Old way", "overlay_zh": "旧办法"},
        {"template": 3, "lines": [5, 6], "overlay_en": "Open Moras", "overlay_zh": "打开 Moras"},
        {"template": 6, "lines": [7, 8], "overlay_en": "Hit Generate", "overlay_zh": "点击 Generate"},
        {"template": 7, "lines": [9, 10], "overlay_en": "Path visible", "overlay_zh": "带货路径可见"},
        {"template": 8, "lines": [11, 12], "overlay_en": "Check first", "overlay_zh": "先检查"},
        {"template": 9, "lines": [13], "overlay_en": "Make your own money", "overlay_zh": "赚自己的钱"},
    ]
    zh_storyboard = [
        {
            "camera": "真人或数字人竖屏近景，手机靠近镜头，像刚发现一个必须马上说的东西。",
            "character_action": "创作者前倾看镜头，用紧迫语气点名 5K+ TikTok Shop 达人。",
            "facial_expression": "像压不住要爆料，但仍保持可信克制。",
            "background": "创作者卧室或桌面场景，有手机、电脑和一个商品包装。",
            "props": ["手机", "电脑", "商品盒"],
            "sound": "快速 whoosh 进入低音量紧迫节奏。",
            "transition": "在 proof 这个词上硬切。",
            "purpose": "先让目标达人感到这条内容和自己直接相关。",
        },
        {
            "camera": "快速证明蒙太奇，裁切达人 handle 页和已批准 GMV / 收入截图并弹跳进入画面。",
            "character_action": "不出现人物动作，证明卡片围绕屏幕快速叠放。",
            "facial_expression": "不露脸，由证明素材承担这一拍。",
            "background": "暗色剪辑背景，绿色或金色的大数字突出。",
            "props": ["达人 handle 截图", "GMV 截图", "收入证明卡"],
            "sound": "三次短促弹出音，对齐证明卡片。",
            "transition": "截图堆叠擦拭切入 Moras 录屏。",
            "purpose": "用已批准达人证明建立可信度，但不写成固定收益承诺。",
        },
        {
            "camera": "Moras 全屏录屏，光标打开 app 并在商品库停留一秒。",
            "character_action": "光标浏览商品库，快速滚动正在起量的商品，并停在一张选中商品。",
            "facial_expression": "不露脸；可在右下角放小数字人窗口。",
            "background": "Moras 商品库 UI，展示已批准的商品和销量信号。",
            "props": ["Moras 录屏", "商品库", "商品筛选器", "已选商品"],
            "sound": "滚动 tick 声和点击声。",
            "transition": "快速放大到 Generate 按钮。",
            "purpose": "说明 Moras 从商品发现开始，不是粘贴商品数据。",
        },
        {
            "camera": "Moras 录屏特写，裁到已选商品和 Generate 按钮。",
            "character_action": "光标点击 Generate，停顿一拍，然后出现生成的视频。",
            "facial_expression": "不露脸；数字人口播窗口在说话时略微放大。",
            "background": "同一 Moras 工作流，从选品进入生成结果。",
            "props": ["Moras 录屏", "Generate 按钮", "生成视频", "带货路径"],
            "sound": "清晰点击声后接短促成功提示音。",
            "transition": "在完成结果上停留整整一秒。",
            "purpose": "让一键 Generate 的卖点被观众看见。",
        },
        {
            "camera": "录屏停在生成视频、带货路径和发布入口。",
            "character_action": "光标悬停在带货路径状态和发布入口，不急着切走。",
            "facial_expression": "不露脸，生成完成状态就是画面重点。",
            "background": "Moras 完成态界面，展示生成视频、带货路径和发布入口。",
            "props": ["生成视频", "带货路径", "发布入口"],
            "sound": "音乐短暂留白，让结果界面可读。",
            "transition": "虚化结果界面后切到金额证明大字。",
            "purpose": "把生成视频和带货路径状态作为主价值点。",
        },
        {
            "camera": "暗色结果强化卡，大号绿色或金色证明数字逐个弹出。",
            "character_action": "只展示已批准证明数字，不新增虚假的个人收入。",
            "facial_expression": "不露脸，由字体和证明截图承担结果强化。",
            "background": "由 Moras 完成态虚化形成的暗色背景。",
            "props": ["证明数字", "达人证明卡", "GMV 截图"],
            "sound": "数字落下时配克制低频音效。",
            "transition": "推进到创作者大脸 CTA。",
            "purpose": "强化达人结果证明，同时避免固定收益承诺。",
        },
        {
            "camera": "竖屏创作者近景，背景虚化，人物脸部更大用于收束 CTA。",
            "character_action": "创作者指向左下角按钮，并用一句话结束。",
            "facial_expression": "自信、紧迫、直接。",
            "background": "虚化的 Moras 完成态或创作者桌面，不加多余说明文字。",
            "props": ["手机", "CTA 按钮方向"],
            "sound": "最后一个点击音后音乐停住。",
            "transition": "定格在指向按钮的动作。",
            "purpose": "用直接 TikTok Shop 达人 CTA 收尾。",
        },
    ]
    zh_storyboard = mock_storyboard_template_zh()
    ensure_mock_storyboard_rows(item, len(storyboard_groups))
    item["storyboard"] = item["storyboard"][: len(storyboard_groups)]
    for shot_index, (shot, group) in enumerate(zip(item["storyboard"], storyboard_groups, strict=True), start=1):
        template_index = int(group["template"])
        english = english_storyboard[template_index]
        zh_fields = zh_storyboard[template_index]
        line_indexes = list(group["lines"])
        zh_voiceover = " ".join(storyboard_voiceover_zh[line_index] for line_index in line_indexes)
        shot.update(english)
        shot["shot_id"] = f"shot_{shot_index}"
        shot["voiceover"] = " ".join(storyboard_voiceover_en[line_index] for line_index in line_indexes)
        shot["overlay"] = str(group["overlay_en"])
        shot["visual_elements"] = mock_group_visual_elements(shot_index, localized=False)
        if shot_index == 4:
            shot["camera"] = "Full-screen Moras screen recording moving from product library scroll to a selected product hold."
            shot["character_action"] = "The cursor opens Moras, scans the product library, and stops on the product the creator wants to promote."
            shot["background"] = "Moras product-library UI with visible product signals, filters, and a clear selected product state."
            shot["props"] = ["Moras capture", "product library", "selected product", "product signals"]
            shot["purpose"] = "Show product discovery and selection as one continuous Moras UI action."
        if shot_index == 5:
            shot["camera"] = "Continuous Moras screen recording from the Generate button to the completed video and commerce-path state."
            shot["character_action"] = "The cursor taps Generate, waits through processing, then holds on the generated video with the commerce-path state visible."
            shot["background"] = "Moras workflow UI moving from selected product to generated video output and posting path."
            shot["props"] = ["Generate button", "processing state", "generated video", "commerce path"]
            shot["purpose"] = "Show the Generate-to-video-with-cart value without pretending it guarantees sales."
        if shot_index == 6:
            shot["camera"] = "Moras review view pulls back to the creator desk where the posting checklist is visible."
            shot["character_action"] = "The cursor checks the output, then the creator circles the next product to promote."
            shot["background"] = "Moras Drafts or Posts review controls beside a practical creator desk with posting notes."
            shot["props"] = ["draft review", "posting checklist", "product notes", "phone"]
            shot["purpose"] = "Connect checking the output to posting more product videos without promising a fixed result."
        set_localized_zh(shot, {
            "duration": shot.get("duration"),
            "camera": zh_fields["camera"],
            "character_action": zh_fields["character_action"],
            "facial_expression": zh_fields["facial_expression"],
            "background": zh_fields["background"],
            "props": zh_fields["props"],
            "voiceover": zh_voiceover,
            "overlay": str(group["overlay_zh"]),
            "sound": zh_fields["sound"],
            "bgm": "轻快背景音乐保持低音量，不压过口播。",
            "sound_effects": ["点击音", "转场提示音"],
            "subtitle_logic": "每镜只用一句短字幕标记重点，跟随口播重音出现。",
            "visual_elements": mock_group_visual_elements(shot_index, localized=True),
            "visual_element_logic": "开头加紧迫点名，中段加证明和录屏，结尾加点击按钮 CTA。",
            "transition": zh_fields["transition"],
            "purpose": zh_fields["purpose"],
        })
        if shot_index == 4:
            set_localized_zh(shot, {
                "camera": "Moras 全屏录屏，从商品库滚动连续移动到选中商品停留。",
                "character_action": "光标打开 Moras，浏览商品库，并停在创作者想推广的商品上。",
                "background": "Moras 商品库 UI，能看到商品信号、筛选器和清楚的选中状态。",
                "props": ["Moras 录屏", "商品库", "已选商品", "商品信号"],
                "purpose": "把商品发现和选中商品作为一段连续 Moras UI 动作展示。",
            })
        if shot_index == 5:
            set_localized_zh(shot, {
                "camera": "连续 Moras 录屏，从 Generate 按钮推进到生成视频和带货路径状态。",
                "character_action": "光标点击 Generate，等待处理中状态，然后停在生成视频和带货路径状态。",
                "background": "Moras 工作流 UI，从已选商品进入生成视频结果和发布路径。",
                "props": ["Generate 按钮", "处理中状态", "生成视频", "带货路径"],
                "purpose": "展示 Generate 到完成视频和带货路径的价值，但不暗示保证出单。",
            })
        if shot_index == 6:
            set_localized_zh(shot, {
                "camera": "Moras 检查界面拉回创作者桌面，发布清单清楚可见。",
                "character_action": "光标检查输出后，创作者圈出下一个想推广的商品。",
                "background": "Moras Drafts 或 Posts 检查控件旁边是实用型创作者桌面和发布笔记。",
                "props": ["草稿检查", "发布清单", "商品便签", "手机"],
                "purpose": "把检查输出和继续发布商品视频连接起来，同时不承诺固定结果。",
            })

    apply_storyboard_visual_element_specificity(item)
    apply_storyboard_timing_for_voiceover(item)

    asset_zh = [
        ("用真人或数字人口播建立紧迫感，开头直接点名 5K+ TikTok Shop 达人。", "保留人物口播，后期叠加短字幕，不在 Veo 提示词里写字幕。"),
        ("脚本讲 Moras 工作流时必须切真实录屏，重点展示商品库、选品、Generate、带货路径和发布入口。", "剪入已批准 Moras 工作流录屏，先展示达人证明截图，再展示选品到带货路径结果。"),
        ("CTA、金额证明大字、箭头和按钮提示应由剪辑层完成，保持投放素材可控。", "在真实录屏和 base track 上加 proof 数字和点击按钮提示；成片可按 35-45s 节奏裁切。"),
    ]
    asset_en = [
        ("Use avatar or live creator footage to establish urgency and call out 5K+ TikTok Shop creators directly.", "Keep creator footage as the base visual track; add short captions only in post-production, not inside Veo prompts."),
        ("Cut to real Moras workflow footage when the script explains product library, product selection, Generate, completed product-video output, and publish entry.", "Insert approved creator proof screenshots first, then approved Moras workflow capture from product selection to completed product-video output."),
        ("Keep CTA, proof-number typography, arrows, highlights, and button prompts in the editing layer so the final asset remains controllable.", "Add proof numbers and click-button prompts over the real capture and base track; trim the final piece to the 35-45s pacing range."),
    ]
    asset_ranges = [
        ("0s-12s", ["shot_1", "shot_2", "shot_3"]),
        ("12s-32s", ["shot_4", "shot_5", "shot_6"]),
        ("32s-44s", ["shot_7", "shot_8"]),
    ]
    for entry, (zh_reason, zh_note), (en_reason, en_note), (time_range, shot_ids) in zip(
        item["production_asset_plan"],
        asset_zh,
        asset_en,
        asset_ranges,
        strict=False,
    ):
        entry["time_range"] = time_range
        entry["shot_ids"] = shot_ids
        set_localized_zh(entry, {"usage_reason": zh_reason, "editor_note": zh_note, "narrative_phase": entry.get("narrative_phase")})
        entry["usage_reason"] = en_reason
        entry["editor_note"] = en_note
    apply_production_asset_ranges_from_storyboard(item)


def build_mock_script_item(
    index: int,
    script_type: str,
    source_ids: list[str],
    selected_persona: dict[str, Any] | None = None,
) -> ScriptAgentItem:
    variant = mock_script_variant(index)
    templates = ["Beginner Trap", "Product-to-Video Workflow", "Faceless Creator"]
    template = templates[index % len(templates)] if script_type == "all" else script_type
    title = str(variant["title"])
    audience = str(variant["audience"])
    item = {
        "topic_plan": {
            "title": title,
            "target_audience": audience,
            "content_angle": variant["content_angle"],
            "trend_source": "来自社媒视频拆解库的 Hook、结构和视觉节奏因子。",
            "template": template,
            "persona": "Practical creator friend",
            "hook_candidates": variant["hook_candidates"],
            "cta_candidates": [variant["cta"], "If you're a 5K+ TikTok Shop creator, click the button. Make your own money."],
            "recommended_platform": "TikTok / Reels / Shorts",
            "moras_relevance_score": 86,
            "risk_score": 18,
        },
        "script": {
            "script_title": title,
            "target_audience": audience,
            "persona": "Practical creator friend",
            "template": template,
            "core_pain": variant["core_pain"],
            "emotional_angle": variant["emotional_angle"],
            "hook": variant["hook"],
            "voiceover": mock_script_voiceover_lines(variant),
            "visual": "A live or digital-human hook, approved creator proof screenshots, real Moras product-library recording, and a product video output with the commerce path visible.",
            "overlay": variant["overlay_en"],
            "sound_effect": "Light click sounds with short confirmation tones during step changes.",
            "proof_insert": "Show approved creator handle / GMV / income proof screenshots, then show product selection, Generate, and the product video output with the commerce path visible; do not present it as a fixed-income outcome.",
            "cta": variant["cta"],
            "compliance_note": "Allowed proof numbers must be framed as approved creator results or screenshots, not fixed sales or income outcomes.",
            "version": "v1",
        },
        "storyboard": [
            {
                "shot_id": "shot_1",
                "timestamp": "0s-4s",
                "duration": "4s",
                "camera": "手机竖屏近景，镜头轻微手持推进到手机屏幕。",
                "character_action": "创作者打开相机，看着桌上的商品停住，然后没有录制就把相机关掉。",
                "facial_expression": "有点尴尬地停顿，像意识到卡住的不是相机。",
                "background": "真实桌面工作区，手机旁边摆着打开的笔记本电脑和便签。",
                "props": ["手机", "商品盒", "笔记本电脑", "便签"],
                "voiceover": "I opened the camera, stared at the product, and closed it again.",
                "overlay": "Camera closed again",
                "sound": "相机点击声后留一个安静停顿。",
                "transition": "快速推近到手机屏幕。",
                "purpose": "从真实创作者卡住的瞬间开场，而不是产品卖点开场。",
            },
            {
                "shot_id": "shot_2",
                "timestamp": "4s-9s",
                "duration": "5s",
                "camera": "桌面俯拍切到便签近景，镜头沿着三条粗糙笔记下移。",
                "character_action": "创作者写下角度、证明点和第一镜，把一句别扭开头划掉。",
                "facial_expression": "不露脸，仅保留手部动作。",
                "background": "同一张桌面上有手机商品页、便签和笔，旁边电脑保持待机。",
                "props": ["手机", "便签", "笔"],
                "voiceover": "That's usually my sign that I picked a product before I knew the angle.",
                "overlay": "Angle first",
                "sound": "轻微写字声和纸张滑动声。",
                "transition": "便签文字擦拭切到 Moras 录屏。",
                "purpose": "让软件出现前先有一个人的小动作和真实卡点。",
            },
            {
                "shot_id": "shot_3",
                "timestamp": "9s-14s",
                "duration": "5s",
                "camera": "Moras 工作流录屏，光标从商品库选择商品并进入 Generate 流程。",
                "character_action": "光标选中一个商品，点击 Generate，并停在加了带货路径的视频上。",
                "facial_expression": "不露脸，画面重点放在光标和界面状态变化。",
                "background": "Moras 工作流界面显示已选商品和加带货路径的视频区域。",
                "props": ["Moras 录屏", "商品", "Generate", "带货路径"],
                "voiceover": "I choose the product in Moras and hit Generate.",
                "overlay": "选商品 -> Generate",
                "sound": "清晰点击声和轻提示音。",
                "transition": "局部放大到 Generate 按钮和完成态。",
                "purpose": "用真实 Moras 录屏承接解决方案。",
            },
            {
                "shot_id": "shot_4",
                "timestamp": "14s-20s",
                "duration": "6s",
                "camera": "Moras 录屏继续推进，镜头裁切到视频草稿预览和 Drafts/Posts 检查控件。",
                "character_action": "光标从生成草稿移动到文字编辑和片段拆分控件，最后停在可检查的视频输出上。",
                "facial_expression": "不露脸，重点展示界面反馈和生成完成状态。",
                "background": "Moras 工作流界面保持同一账号和同一商品流程。",
                "props": ["Moras 录屏", "视频草稿预览", "编辑文字", "拆分片段"],
                "voiceover": "Then I check the video before I lose the whole evening.",
                "overlay": "先看是否值得迭代",
                "sound": "完成提示音。",
                "transition": "录屏末尾切回桌面俯拍。",
                "purpose": "证明 Moras 能连接商品选择、视频草稿生成和后续检查控件。",
            },
            {
                "shot_id": "shot_5",
                "timestamp": "20s-25s",
                "duration": "5s",
                "camera": "桌面俯拍，镜头从电脑屏幕拉回创作者手边便签。",
                "character_action": "创作者在便签上勾选解释成本、素材空间、一眼能懂三个判断点。",
                "facial_expression": "不露脸，手部动作变得放松且确认。",
                "background": "同一桌面工作区，电脑上仍停留在 Moras 工作流结果页。",
                "props": ["电脑", "便签", "笔", "手机"],
                "voiceover": "At least I'm not inventing the opener from a blank phone screen.",
                "overlay": "低成本出片",
                "sound": "笔尖划过纸面的轻声。",
                "transition": "手部勾选切到人物收束镜头。",
                "purpose": "把产品价值落到减少试错。",
            },
            {
                "shot_id": "shot_6",
                "timestamp": "25s-32s",
                "duration": "7s",
                "camera": "手机竖屏中近景，镜头稳定对准创作者和桌面。",
                "character_action": "创作者把手机放到桌上，拿起便签对镜头展示三个判断点。",
                "facial_expression": "轻松、确认感，语气像给朋友提醒。",
                "background": "自然光桌面工作区，电脑和手机保持在画面边缘。",
                "props": ["手机", "便签", "笔记本电脑"],
                "voiceover": "I still check the product myself, but I don't start from a blank page.",
                "overlay": "下次选品前先过一遍",
                "sound": "轻快背景节奏继续。",
                "transition": "便签抬起后定格。",
                "purpose": "将建议变成可保存的行动步骤。",
            },
            {
                "shot_id": "shot_7",
                "timestamp": "32s-38s",
                "duration": "6s",
                "camera": "手机竖屏近景，镜头轻微推近到保存动作。",
                "character_action": "创作者用手指向屏幕下方保存位置，然后把便签放回电脑旁。",
                "facial_expression": "温和微笑，带有鼓励感。",
                "background": "同一桌面工作区，Moras 结果页在电脑屏幕上虚化显示。",
                "props": ["手机", "便签", "电脑屏幕"],
                "voiceover": "Save this for the next product.",
                "overlay": "保存这三个判断点",
                "sound": "保存提示音。",
                "transition": "最后定格在保存动作。",
                "purpose": "完成保存 CTA 并结束视频。",
            },
        ],
        "video_prompt": {
            "prompt_title": f"{title} 视觉生成提示",
            "aspect_ratio": "vertical 9:16",
            "target_model": "Veo 3.1",
            "veo_model_id": "veo-3.1-generate-001",
            "veo_generation_mode": "text_to_video_9x16",
            "veo_base_duration_sec": 8,
            "character_lock": "Same young creator hands and casual workspace presence across all shots, neutral hoodie, natural skin tone, realistic hand movement.",
            "scene_lock": "Same compact creator desk with laptop, phone, sticky notes, daylight from side window, practical home-office mood.",
            "generation_prompt": "Vertical smartphone video in a realistic creator desk setup, close-up hand interaction with a phone and laptop, focused workflow mood, natural daylight, subtle handheld movement, clear product research and planning actions, expressive pause and relief through body language, practical home-office environment.",
            "overlay_exclusion_note": "Overlay lines are stored in dedicated editing fields only; they must be added in editing, not generated inside Veo source-footage prompts.",
            "consistency_notes": ["Keep the same desk layout and lighting.", "Keep vertical 9:16 framing.", "Use abstract, unreadable screen shapes for any device displays."],
            "target_duration_sec": 38,
            "segments": [],
        },
        "production_asset_plan": [
            {
                "plan_id": "asset_1",
                "time_range": "0s-9s",
                "shot_ids": ["shot_1", "shot_2"],
                "narrative_phase": "Hook",
                "asset_type": "digital_human_avatar",
                "moras_asset_category": "none",
                "layer": "base_track",
                "usage_reason": "使用 Persona 数字人提示词资产保留手机随拍的创作者感，让开头像一个人正在卡住。",
                "editor_note": "用人设视觉与声音表达提示词生成或绑定基础画面；字幕只在后期叠加，不写进 Veo 提示词。",
            },
            {
                "plan_id": "asset_2",
                "time_range": "9s-25s",
                "shot_ids": ["shot_3", "shot_4", "shot_5"],
                "narrative_phase": "Solution / Proof",
                "asset_type": "real_moras_screen_recording",
                "moras_asset_category": "workflow_screen_recording",
                "layer": "cutaway",
                "usage_reason": "脚本讲 Moras 工作流时必须切真实录屏，避免只靠 AI 画面空泛表达。",
                "editor_note": "剪入已批准 Moras 工作流录屏，重点展示商品选择、Create video / Custom Create、视频草稿和编辑检查路径。",
            },
            {
                "plan_id": "asset_3",
                "time_range": "25s-38s",
                "shot_ids": ["shot_6", "shot_7"],
                "narrative_phase": "CTA / Resolution",
                "asset_type": "post_production_overlay",
                "moras_asset_category": "none",
                "layer": "overlay",
                "usage_reason": "CTA、箭头、高亮和步骤标题应由剪辑层完成，保持投放素材可控。",
                "editor_note": "在真实录屏和 base track 上加步骤高亮；成片可按 35-45s 节奏裁切。",
            },
        ],
        "risk_check": {
            "risk_level": "low",
            "forbidden_claims_checked": ["guaranteed income", "guaranteed sales", "platform bypass", "fixed settlement"],
            "compliance_notes": ["未承诺收入或销量。", "只表达效率、出片和工作流价值。"],
            "allowed_for_video_factory": True,
        },
        "source_breakdown_ids": source_ids,
        "source_component_summary": variant["source_summary"],
    }
    apply_mock_language_contract(item, variant)
    apply_persona_operating_contract_to_mock_script(item, selected_persona)
    item["creator_persona"] = selected_persona or default_creator_persona(item["script"], item["topic_plan"], variant_index=index)
    sync_script_item_to_creator_persona(item, force=bool(selected_persona))
    item["video_prompt"] = ensure_veo_segments(
        item["video_prompt"],
        item["script"],
        item["storyboard"],
        item["production_asset_plan"],
        item["creator_persona"],
    )
    ensure_chinese_localizations(item)
    repair_publishable_safe_style_drift(item)
    return ScriptAgentItem.model_validate(item)


def build_mock_edited_script(existing: ScriptRecord, instruction: str) -> ScriptAgentItem:
    creator_persona = normalize_creator_persona_payload(
        existing.creator_persona,
        existing.topic_plan,
        existing.script,
        seed=existing.id,
    )
    item = {
        "topic_plan": {**existing.topic_plan, "content_angle": f"{existing.topic_plan.get('content_angle', '')} 修改方向：{instruction}"},
        "script": {
            **existing.script,
            "script_title": f"{existing.script.get('script_title', existing.topic_plan.get('title', '脚本'))}（已修改）",
            "hook": f"{existing.script.get('hook', '')} 修改后更聚焦：{instruction}",
            "compliance_note": "修改后仍只表达效率、出片和工作流价值，不承诺销量或收入。",
            "version": "v2",
        },
        "storyboard": existing.storyboard,
        "creator_persona": creator_persona,
        "video_prompt": existing.video_prompt,
        "production_asset_plan": existing.production_asset_plan or default_production_asset_plan(existing.storyboard),
        "risk_check": {**existing.risk_check, "risk_level": "low", "allowed_for_video_factory": True},
        "source_breakdown_ids": existing.source_breakdown_ids,
        "source_component_summary": existing.source_component_summary,
    }
    item["topic_plan"].pop("localized", None)
    item["script"].pop("localized", None)
    ensure_script_hook_candidates(item["topic_plan"], item["script"])
    sync_script_item_to_creator_persona(item)
    apply_storyboard_visual_element_specificity(item)
    apply_storyboard_timing_for_voiceover(item)
    item["video_prompt"] = ensure_veo_segments(
        item["video_prompt"],
        item["script"],
        item["storyboard"],
        item["production_asset_plan"],
        item["creator_persona"],
    )
    ensure_chinese_localizations(item)
    return ScriptAgentItem.model_validate(item)
