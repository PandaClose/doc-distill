# 源路由指南（source-routing）

按源类型选择提取策略与蒸馏侧重。

## 判定顺序

1. 输入是 URL？
   - `github.com/<owner>/<repo>` → GitHub 仓库
   - 以 `llms.txt` 结尾 → llms.txt 清单（文档站的最优路径）
   - 以 `.md/.txt/.html/.pdf` 等结尾 → 单个远程文件
   - 其他 → 文档站爬取（website）
2. 输入是本地路径 → 按扩展名路由；目录 → docs_dir（含 `.git` 则按仓库处理）
3. 多个输入 / glob → 全部并入同一 IR，形成一册

## 各源要点

### 书籍（PDF / EPUB / MOBI）

- 技术书（代码/表格/公式多）优先 `pip install 'doc-distill[pdf-pro]'` 用 docling，保留结构。
- 纯文本书用默认 `[pdf]`（pypdf）即可；标题识别基于「第X章 / Chapter N / 数字编号」模式，提取后**抽查章节数是否与原书目录一致**，缺章时改用 pdf-pro 重提。
- 扫描版无文本层：让用户先 `ocrmypdf in.pdf out.pdf`。
- MOBI/AZW：需系统 Calibre（`ebook-convert` 在 PATH）。
- 蒸馏侧重：框架、原则、反模式；代码书增加惯用法与示例。

### 文档站（website / llms.txt）

- **先试 `https://<host>/llms.txt`**：存在则直接传该 URL——清单式抓取，最准最快。
- 无 llms.txt 用 website 模式：同域 BFS，默认 20 页、深度 2。大站用 `--max-pages 50 --max-depth 3`；抓完检查覆盖面（导航栏主要栏目是否都在）。
- SPA 站点（JS 渲染）抓不到内容时：如实告知用户，建议找 llms.txt、导出的 markdown 镜像或本地文档目录。
- 蒸馏侧重：API 面、任务导向的 how-to、配置参考；决策表从 FAQ/troubleshooting 提炼。

### GitHub 仓库

- 远程仓库无需 git：走 codeload tarball。本地路径也行。
- 文档文件全量收；代码文件截为 400 行概览（IR 中标注截断）。
- 蒸馏侧重：架构与数据流（读 README、docs/、入口文件）、关键模块职责、安装/使用面、代码惯例。
- 不要试图把整个代码库逐行蒸馏——产物是「理解与使用该仓库」的手册，不是代码镜像。

### 文本 / Markdown / HTML / RTF / DOCX

- 零依赖直读（RTF 需 `[rtf]` extra；DOCX 走 stdlib 解析）。
- 多个同主题文档：一次传入，chunker 自动按各文档标题分层；蒸馏时跨文档去重、合并同名主题。

## 上限与礼貌

- 远程单资源 64 MB 上限；仓库 800 文件、单文件 512 KB 上限（超出自动截断并提示）。
- 爬取串行 + 0.5s 延迟，尊重站点；用户要求更快时提醒对方是别人家的服务器。
- 版权口径：一切产物默认个人学习用途，不重新分发。
