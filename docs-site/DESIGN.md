# 设计记录

- 读者：复现项目的开发者与评审，首要任务是理解设备边界并跑通实验。
- 概念：把 TurboVLA 的动作块时间线变成可操作的文档示例；调节请求期间执行步数，观察裁剪、替换、融合与 hold。
- 专属内容：Orin Nano 8GB、Thor 128GB、全模型在 Thor、两视角、256px、8维状态、12×7动作、R=4、B=3、单请求、LIBERO、墙钟视频。
- 论证：概览解释分工；部署给出可执行命令；调度解释代码；完整性连接入口与测试；验证明确测量口径。
- 采用 VitePress 官方文档主题（MIT），保留其侧边栏、搜索和移动端目录。
- Taste Skill：公开仓库 `Leonxlnx/taste-skill`，`skills/taste-skill/SKILL.md`。Direction `product-performs`，seed `122050552`。
- 用户约束优先：白底、近黑文字、浅蓝色；固定左侧目录，凝练技术文档。因此不采用该营销页方向的全屏暗色 hero、客户 logo、四图下限、八处动画要求。没有虚构客户、成绩或资源占用。
- 主色 #285b8e，底色 #ffffff，面板 #f2f7fc；系统字体支持本地中文，代码用等宽字体。标题左对齐、无渐变、无装饰阴影。
- 动态用于操作反馈与手动播放的调度 GIF；默认静态，支持 reduced-motion。时间线每格不代表实测毫秒，Sync 与异步轴语义在图下注明。
- 实拍来源为用户项目设备照片，经 DDS 清理后展示并保留原图入口。框架与流水线先由 DDS 生成，再通过可编辑 PPT 原生对象重建为纯色图；无外部设备照片或占位图。

## 浏览器审查记录

ROUND 1
Seen in one second: 双设备内存与职责形成页面主视觉。
Idea: 把项目实际动作时间线变为可操作的说明。
Live thing: Sync / Blend / Async 切换与延迟步数滑块。
Layout words by section: intro=文档 / devices=双列 / scheduling=时间线 / proof=表格。
Top three problems: 手机标题出现单字落行；通信标签偏小；导航细线多余。已缩短标题、增大标签并去除细线。

ROUND 2
Scores: design 7 · usability 8 · creativity 7 · content 8 → overall 7.4（按技术文档用途评估，不是营销网站评分）。
Exceptions: `few-pictures`、`still-page` 与用户的凝练技术说明用途冲突，因此不添加无关图片和持续动画；`eyebrow` 将设备间真实传输标签误判为营销小标题，保留其语义。代码等宽字体允许系统回退；VitePress 导航与正文具有更多字号，不强行压成营销页五档字号。无视频：本页用于说明调度，不展示未测的任务录像。
Remaining limit: 手机完整时间线需横向滚动，已提供可聚焦容器与明确说明；静态表格/正文仍可完整阅读。

ROUND 3（实物部署与媒体修订）
新增真实设备双列照片、原图入口、纯色框架/流水线图、可编辑 PPT 下载及手动播放 GIF。桌面照片并排、手机单列，不裁切设备。GIF 默认为静态图，播放、停止和模式切换均可键盘操作；完整流水线保留横向滚动，避免把文字缩到不可读。根路径与子路径检查覆盖新增资源与播放器。
