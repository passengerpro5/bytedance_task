# 任务3页面设计指导：新内容与素材输入

## 目标

任务3要在页面2完成样例视频拆解之后，进入“新内容与素材输入”流程。系统需要支持用户输入新的主题、商品卖点或用户素材，并识别这些内容是否足以支撑页面2中得到的目标视频结构。

这个阶段的关键不是直接生成新视频，而是回答三个问题：

1. 用户给了什么新内容和素材？
2. 这些内容和素材能否匹配样例视频拆解出的结构槽位？
3. 如果不能，缺哪些素材，用户是否要补全或修改？

## 页面数量建议

建议任务3拆成 3 个分页面：

1. 页面3：新内容与素材输入
2. 页面3.1：素材识别与缺口分析结果
3. 页面3.2：素材补全与修改

页面3负责输入，页面3.1负责展示识别结果和缺口，页面3.2负责让用户补充、替换、重排素材。这样既符合任务3，也能自然衔接任务5和任务6。

## 页面3：新内容与素材输入

### 页面定位

页面3是任务3的主入口，从页面2进入。它接收用户的新主题、商品卖点、文案、图片、视频等内容，并带着页面2的样例结构进入素材适配分析。

### 入口

页面2中增加“进入新内容输入”按钮。点击后进入页面3。

### 主要区域

1. 样例结构摘要区
   - 展示页面2已经拆解出的结构信息。
   - 包括估算镜头段数、拆解方法、核心步骤、已有脚本/节奏/包装摘要。
   - 只做摘要，不铺满全部拆解结果。

2. 新内容输入区
   - 主题输入：如新品、活动、种草主题。
   - 商品卖点输入：支持多条卖点。
   - 用户文案输入：可粘贴已有文案。
   - 素材上传：至少支持图片或视频，后续可支持多文件。
   - 可选补充信息：目标人群、风格、平台、时长。

3. 操作按钮区
   - 返回上一步：返回页面2。
   - 开始分析：进入页面3.1。
   - 分析设置：进入页面3设置页。

### 按钮逻辑

1. 返回上一步
   - `setCurrentPage('analysis')`
   - 保留页面3输入草稿。

2. 开始分析
   - 保存当前输入为 `Task3InputDraft`。
   - 调用素材识别分析逻辑。
   - 分析完成后进入页面3.1。
   - 如果分析耗时较长，可先进入页面3.1并显示处理中状态。

3. 分析设置
   - 进入页面3设置页。
   - 设置结构参考页面2.1。

## 页面3设置页：分析设置

### 页面编号建议

建议命名为页面3.0 或 页面3设置。为了和页面2.1保持一致，也可以叫页面3.2之前的“页面3设置”。如果需要严格编号，推荐：

- 页面3：输入页
- 页面3.0：分析设置页
- 页面3.1：分析结果页
- 页面3.2：补全修改页

如果希望页面编号更简单，也可以把设置页作为页面3的抽屉或子面板，不单独编号。

### 设置内容

分析设置用于配置任务3的识别目标和步骤，建议包括：

1. 识别目标内容
   - 商品/品牌识别
   - 人物/场景识别
   - 卖点覆盖识别
   - 素材槽位匹配
   - 缺口识别

2. 分析输入模式
   - 结构化分析：使用文字输入、素材元信息、图片识别、视频抽帧识别。
   - 直接多模态分析：如果用户配置了支持图像/视频理解的模型，可直接分析素材。

3. 步骤配置
   - 每个步骤可配置名称、目标、prompt、skill。
   - 每个步骤可选择使用：
     - 文本交互模型
     - 图片识别模型
     - 视频识别模型
   - 支持导入 JSON、导出 JSON。

### 本地保存

参考页面2.1，使用 `localStorage` 保存：

```text
hot-engine-task3-analysis-settings
```

JSON 建议结构：

```json
{
  "version": 1,
  "targetMode": "material-fit",
  "inputMode": "structured",
  "steps": [
    {
      "id": "material-inventory",
      "name": "素材盘点",
      "modelType": "image-recognition",
      "skillKey": "material-inventory.md",
      "prompt": "识别用户素材中包含的商品、人物、场景和可用片段。"
    },
    {
      "id": "slot-matching",
      "name": "结构槽位匹配",
      "modelType": "chat",
      "skillKey": "slot-matching.md",
      "prompt": "根据样例视频结构，判断当前素材可以覆盖哪些结构槽位。"
    },
    {
      "id": "gap-detection",
      "name": "素材缺口识别",
      "modelType": "chat",
      "skillKey": "gap-detection.md",
      "prompt": "识别缺失的开头吸引镜头、商品特写、使用过程、对比镜头和CTA镜头。"
    }
  ]
}
```

## 页面3.1：素材识别与缺口分析结果

### 页面定位

页面3.1展示“新内容与素材是否足以支撑目标视频结构”的判断结果。

### 输入来源

1. 页面2拆解出的样例结构。
2. 页面3用户输入的新主题、卖点、文案、素材。
3. 页面3分析设置。

### 展示内容

1. 输入内容摘要
   - 新主题
   - 商品卖点
   - 文案摘要
   - 上传素材数量和类型

2. 已识别素材信息
   - 图片素材：商品、场景、人物、文字、包装元素。
   - 视频素材：估算镜头段数、片段时长、可用画面类型。
   - 文案素材：卖点、行动引导、核心表达。

3. 结构槽位匹配
   - 开头 hook 是否有素材支撑。
   - 商品特写是否有素材支撑。
   - 使用过程是否有素材支撑。
   - 对比镜头是否有素材支撑。
   - 结尾 CTA 是否有素材支撑。

4. 素材缺口提示
   - 如果存在缺口，列出缺口名称、影响程度和建议补全方式。
   - 如果没有缺口，显示：
     ```text
     内容完整无缺口
     ```

5. 操作区
   - 返回输入：回到页面3。
   - 补全或修改素材：进入页面3.2。
   - 继续生成方案：后续进入任务4页面。

### 重要交互要求

不管有没有缺口，都允许用户进入页面3.2进行素材缺口补全或素材修改。

原因：

1. 用户可能想主动替换素材。
2. 用户可能想强化某个卖点。
3. 即使系统判断无缺口，也可能存在风格或表达偏好问题。

## 页面3.2：素材补全与修改

### 页面定位

页面3.2用于处理任务5和任务6的前置工作：用户可以根据页面3.1的缺口识别结果，对素材进行补充、替换、重排或文本补全。

### 功能模块

1. 缺口列表
   - 显示页面3.1识别出的缺口。
   - 每个缺口展示影响程度、关联结构槽位、建议补全方式。

2. 素材补全方式
   - 上传新素材。
   - 修改文案/字幕。
   - 使用标题条/卖点卡片补足。
   - 重排已有素材。
   - 标记为忽略。
   - 后续可扩展 AIGC 生成补全。

3. 素材修改区
   - 修改主题。
   - 修改卖点顺序。
   - 替换或删除上传素材。
   - 给素材打标签，如开头、中段、结尾、商品特写、使用过程。

4. 重新分析
   - 修改后可重新进入页面3.1。
   - 重新分析时保留历史结果对比。

## 推荐数据结构

### Task3InputDraft

```ts
type Task3InputDraft = {
  id: string
  topic: string
  sellingPoints: string[]
  copyText?: string
  targetAudience?: string
  platform?: string
  stylePreference?: string
  materials: Array<{
    id: string
    type: "image" | "video" | "text"
    name: string
    url?: string
    text?: string
    tags?: string[]
  }>
  sourceAnalysisVideoIds: string[]
  createdAt: string
  updatedAt: string
}
```

### Task3AnalysisResult

```ts
type Task3AnalysisResult = {
  id: string
  inputId: string
  status: "pending" | "analyzing" | "ready" | "failed"
  materialInventory: Array<{
    materialId: string
    detectedObjects?: string[]
    detectedScenes?: string[]
    detectedText?: string[]
    usableForSlots?: string[]
    confidence?: number
  }>
  slotMatches: Array<{
    slotId: string
    slotName: string
    requiredMaterial: string
    matchedMaterialIds: string[]
    status: "covered" | "partial" | "missing"
    reason: string
  }>
  gaps: Array<{
    id: string
    slotId: string
    name: string
    severity: "low" | "medium" | "high"
    reason: string
    suggestedFixes: string[]
  }>
  summary: string
  createdAt: string
}
```

## 后端实现建议

### 存储

首版仍可使用本地 JSON 文件：

```text
backend_data/task3_inputs.json
backend_data/task3_analysis.json
backend_data/task3_materials/
```

如果后续多人使用或数据量变大，再迁移到 SQLite。

### API 建议

```text
POST /api/task3/inputs
GET /api/task3/inputs/{input_id}
PUT /api/task3/inputs/{input_id}
POST /api/task3/inputs/{input_id}/materials
POST /api/task3/inputs/{input_id}/analyze
GET /api/task3/analysis/{analysis_id}
PUT /api/task3/analysis/{analysis_id}/gaps
```

### 分析流程

1. 收集页面2样例结构。
2. 收集页面3新内容和素材。
3. 对图片调用图片识别/OCR。
4. 对视频调用基础解析、镜头段检测、抽帧识别和语音识别。
5. 对文案调用文本模型提取卖点和CTA。
6. 统一进行结构槽位匹配。
7. 输出素材缺口。
8. 写入 `Task3AnalysisResult`。

## 前端实现建议

### 页面流转

```text
页面2
  ↓ 进入新内容输入
页面3
  ├─ 返回上一步 → 页面2
  ├─ 分析设置 → 页面3设置页
  └─ 开始分析 → 页面3.1

页面3.1
  ├─ 返回输入 → 页面3
  ├─ 补全或修改素材 → 页面3.2
  └─ 继续生成方案 → 任务4页面

页面3.2
  ├─ 返回分析结果 → 页面3.1
  └─ 重新分析 → 页面3.1
```

### 页面3首版最小闭环

建议第一版先实现：

1. 主题输入。
2. 卖点多行输入。
3. 文案输入。
4. 图片/视频素材上传。
5. 页面3.1展示素材盘点、槽位匹配和缺口。
6. 页面3.2允许修改文案、补充素材、标记缺口处理方式。

这样就能覆盖任务3，并为任务5、任务6打基础。

## 验收标准

1. 页面2可以进入页面3。
2. 页面3有返回上一步、开始分析、分析设置三个按钮。
3. 页面3能输入主题、商品卖点或素材至少一种。
4. 点击开始分析后进入页面3.1。
5. 页面3.1能展示识别出的已有素材信息。
6. 页面3.1能展示素材缺口；无缺口时显示“内容完整无缺口”。
7. 不管是否有缺口，用户都能进入页面3.2进行补全或修改。
8. 页面3设置支持配置分析目标和步骤，并能本地保存、导入和导出。
