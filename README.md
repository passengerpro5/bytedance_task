# 社媒视频生产 Agent

社媒视频生产 Agent 是一个面向短视频创意生产的全栈工具。它把参考视频拆解、创意资产沉淀、脚本生成、导演计划、素材绑定和本地视频草稿输出放在同一个工作台里，适合用于从爆款样例到可执行生产方案的快速迭代。

## 核心功能

- 视频拆解：支持视频链接和本地视频上传，后端会导入视频并调用可切换的模型 provider 生成结构化拆解结果。
- 爆款结构提取：沉淀开头钩子、叙事节奏、关键镜头、视觉元素、CTA、风险点和可复用创意因子。
- 脚本编辑部：基于拆解结果生成多版社媒短视频脚本，输出 hook、voiceover、CTA、分镜、视觉动作和视频 prompt。
- 人设资产：生成并保存可复用创作者人设，保证同一脚本包内的人设、口播风格、镜头动作和视频 prompt 一致。
- 创意仓库：把参考视频中的 hook、结构、场景、证明素材、镜头模板和脚本 brief 组织成可检索的生产资产。
- 视频工厂：把已通过校验的脚本转成导演计划，拆分真实素材、AI 视频素材、字幕、音频、剪辑和 QA 任务。
- 素材绑定与审核：支持上传真实录屏、截图和外部生成视频片段，按 asset_ref / clip_id 绑定到导演计划中。
- 本地草稿输出：在素材满足条件时，后端可通过 FFmpeg 生成 9:16 本地视频草稿，并记录字幕、音频和 QA 摘要等产物。
- Markdown 导出：拆解结果和生产过程可导出为 Markdown，方便提交、复盘和二次编辑。

## 功能架构

```text
frontend/
  React + Vite 工作台
  - 视频拆解页
  - 脚本编辑部
  - 创意仓库
  - 视频工厂

backend/
  FastAPI 服务
  - 视频导入与下载
  - 模型 provider 路由
  - 拆解 / 脚本 / 人设 / 导演计划服务
  - SQLite 本地持久化
  - 素材上传与审核
  - FFmpeg 草稿渲染
```

运行态数据默认写入 `backend/data/` 和 `backend/uploads/`。这些目录只用于本地调试，不应提交到 Git。

## Agent 协作框架

```text
Reference Video
  -> Video Teardown Agent
  -> Creative Library
  -> Persona Agent
  -> Voiceover Expert
  -> Script Agent
  -> Director Agent
  -> Asset Binding / QA
  -> Local Render Draft
```

- Video Teardown Agent：读取参考视频，输出结构化拆解，抽取可复用的创意资产。
- Creative Library：承接拆解产物，把 hook、结构、镜头、场景、CTA 和风险规则整理成下游可用资产。
- Persona Agent：为脚本生成前确定创作者身份、表达方式、可信证明边界和视觉身份约束。
- Voiceover Expert：先生成口播基础稿，后复核 hook、voiceover、CTA 和分镜口播时长。
- Script Agent：把拆解资产、人设约束和口播基础稿组合成完整脚本包，包括分镜、提示词、生产素材计划和风险检查。
- Director Agent：把脚本包拆成可执行导演计划，安排真实素材、外部视频片段、字幕、音频、剪辑和 QA 任务。
- Asset Binding / QA：人工上传或审核素材后，系统检查素材状态、语义匹配、时长和画幅。
- Local Render Draft：在素材齐备后生成本地草稿视频，作为最终交付前的检查版本。

## 本地运行

后端：

```bash
cd backend
python3 -m venv .venv
. .venv/bin/activate
pip install -e ".[dev]"
uvicorn app.main:app --reload --port 8766
```

前端：

```bash
cd frontend
npm install
npm run dev
```

默认前端地址是 `http://127.0.0.1:8022`，默认后端地址是 `http://127.0.0.1:8766`。

## 配置

复制后端示例配置：

```bash
cp backend/.env.example backend/.env
```

默认 provider 是 `mock`，不需要外部密钥即可跑通基础流程。需要接入真实模型时，只在本地 `.env` 中填写密钥；`.env`、本地数据库、上传素材和构建产物已被 `.gitignore` 排除。

## 验证

后端：

```bash
cd backend
python -m py_compile app/*.py smoke_test.py
pytest -q
```

前端：

```bash
cd frontend
npm test -- --run
npm run build
```
