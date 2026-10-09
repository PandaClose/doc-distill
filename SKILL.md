---
name: doc-distill
description: "书籍/文档资产 → Agent Skill + RAG 语料的元技能（doc-distill）。仅当用户明确提出『转化成 skill』类指令时才可触发：消息必须同时包含（1）具体对象（某本书/文档/PDF/URL）和（2）明确的转化动词短语，例如『将《xxx》这本书转化成 skill』『把这个 PDF 做成 skill』『帮我把这套文档蒸馏成 skill 知识库』。仅仅出现书名或文件名、询问书中内容、讨论 skill 或蒸馏概念、要求总结或阅读某文档、或单纯提到 doc-distill，均不构成触发条件——不要触发本 skill。"
---

# doc-distill：文档资产 → 手册 Skill + RAG 语料

**核心原则：结构而非摘要。** 产物不是读书笔记，而是一套可导航、可引用、按需加载的知识结构。

## 架构（为什么这样做）

```
输入 → 提取（Python，确定性）→ 统一 IR（chunks/ + outline + source.json）
     → 蒸馏（你，宿主 agent，按 references/distill-spec.md）
     → 导出（Python）→ 手册 skill + RAG 语料
```

提取与导出交给 CLI（零依赖、无 API key、无 Docker）；**蒸馏由你完成**——这是质量所在，也是默认路径完全不需要 API 的原因。

## 前置：确认 CLI 可用

优先用已安装的命令：

```bash
doc-distill --version                    # 已 pip/uvx 安装
PYTHONPATH=src python3 -m doc_distill --version   # 本仓库开发态
uvx doc-distill[all] --version           # 临时运行
```

重格式需要可选依赖，缺什么装什么（每格式一个 extra）：`[pdf]`（pypdf）、`[pdf-pro]`（docling，技术书推荐）、`[rtf]`、`[web]`（trafilatura）、`[all]`。EPUB/DOCX/HTML/Markdown/纯文本零依赖。扫描版 PDF 先让用户 OCR（`ocrmypdf in.pdf out.pdf`）。MOBI/AZW 需要系统安装 Calibre。

## 工作流

### 模式 1：快速（索引 + 全文查阅型，零蒸馏）

用户说「快速做一下 / 只要能查就行」时：

```bash
doc-distill run <输入...> -o <输出目录> --targets skill-manual,rag-jsonl,rag-markdown
doc-distill validate <输出目录>/<slug>
```

产物立即可用（章节地图 + references/full/ 按需读原文）。向用户说明：三个蒸馏占位节尚未补全，随时可以让我补全。

### 模式 2：完整蒸馏（默认推荐）

1. **探测**：`doc-distill detect <输入...>` 确认源类型；不可读的格式先解决依赖。
2. **提取**：`doc-distill extract <输入...> -o <ir-dir>`。文档站优先探测 `https://<host>/llms.txt`（存在则传该 URL，质量最高、最快）。
3. **通读 IR**：读 `<ir-dir>/source.json` 和 `outline.json` 建立全书地图；然后**通读 chunks/**（或按 `references/full/` 分组文件），边读边积累：命名框架、原则、技巧、反模式、作者口吻。
4. **蒸馏**：按 `references/distill-spec.md` 的规格与模板，补全 skill 的三节占位（核心框架 / 高频模式与技巧 / 决策速查），需要时增删调整章节地图的「主题」描述。
5. **校验**：`doc-distill validate <skill-dir> --strict`，修复全部问题。
6. **交付**：告诉用户产物路径与安装方式（`~/.agents/skills/` 全局；`<项目>/.agents/skills/` 项目级）。

### 模式 3：增量并入（fold-in）

用户提供新材料要并入已有产物时：

```bash
doc-distill extract <新材料...> -o <已有 ir-dir> --append
doc-distill export <已有 ir-dir> --targets skill-manual,rag-jsonl -o <原输出目录>
```

然后更新 SKILL.md：新增章节进地图、检查三节蒸馏内容是否需要修订、重跑 validate --strict。

## 各类源的要点

详见 `references/source-routing.md`。速记：

- **书（PDF/EPUB）**：技术书优先装 `[pdf-pro]`；提取后先抽查目录结构是否完整（章节数对得上原书目录吗）。
- **文档站**：先试 llms.txt；否则 website 模式（默认 20 页/深度 2，可用 `--max-pages` 调大）。
- **GitHub 仓库**：README 与 docs/ 优先，代码文件截为概览；蒸馏时聚焦架构、关键流程、API 面。
- **多个输入**：一次传多个路径/glob，自动并入同一 IR，形成一册。

## 硬性要求

1. **不得虚构**：蒸馏只允许重组书中/资料中的内容；原资料没有的，宁缺毋滥。
2. **保留作者精确性**：「5 Whys」不能写成「多问几次为什么」；专有名词、公式、代码原样保留。
3. **回答带出处**：生成 skill 的使用规则里要求引用内容块 [id]。
4. **产物自检**：任何交付前必须跑 `validate --strict` 并全绿。
5. **版权口径**：产物是个人学习用途的衍生笔记，提醒用户不要重新分发受版权保护作品的蒸馏产物。

## RAG 语料

`rag-jsonl` 每行 `{"id","text","metadata"}`，可直接进任意 embedding/向量库管线；`rag-markdown` 是整册打包。语义分块已保证：代码块完整、段落对齐、~512 tokens + 50 重叠。用户要接入 LangChain/LlamaIndex 时，读 JSONL 构造 Document 即可（M4 会内置更多向量库格式）。
