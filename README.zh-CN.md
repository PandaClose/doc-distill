# doc-distill

[English](README.md) | **简体中文**

**把任何文档资产蒸馏成手册型 Agent Skill + RAG 语料。**

一本书、一套文档站、一个 GitHub 仓库、一个 llms.txt 清单——一条命令变成两层产物：

1. **手册型 skill**：`SKILL.md`（何时使用 + 章节地图 + 蒸馏成果）+ `references/full/`（按需加载的原文分块），放进 `~/.agents/skills/` 即可在 Claude Code / ZCode / Codex 等 Agent Skills 兼容运行时中使用；
2. **RAG 语料**：零依赖 JSONL / Markdown 包，每行带 `id / text / metadata`，可直接进任意 embedding 与向量库管线。

```bash
doc-distill run 我的书.epub -o out/
# out/
# ├── <slug>/               ← 手册型 skill（含章节地图 + 原文分块 + 三节蒸馏占位）
# ├── <slug>-rag/chunks.jsonl
# └── <slug>-rag/full.md
```

## 设计哲学

**零核心依赖、零 API key、零 Docker。** 提取与导出由本地确定性 Python 完成；蒸馏这一步交给你的宿主 agent（Claude Code / ZCode…）按内置规格执行——你已经在为此付费的模型就是蒸馏引擎，不需要再配任何 API。

架构上，一切穿过一个**统一中间表示（IR）**：

```
输入(书/网站/repo/…) → 提取器(插件) → IR(chunks+outline+meta) → 蒸馏(宿主agent,可选) → 导出器(插件)
```

源 × 蒸馏 × 导出互不耦合，增量并入（fold-in）只对 IR 做合并。

## 支持的输入

| 输入 | 依赖 | 说明 |
|---|---|---|
| Markdown / 纯文本 / RST / AsciiDoc | 无 | 含 setext 标题、围栏代码块 |
| HTML（文件/URL） | 无（可选 `[web]` 提质） | 内置零依赖 HTML→MD 转换器 |
| EPUB / DOCX | 无 | stdlib 解析 zip+XML 容器 |
| PDF | `[pdf]`（pypdf） | 技术书推荐 `[pdf-pro]`（docling，保留表格/代码结构） |
| RTF | `[rtf]` | |
| MOBI / AZW / AZW3 | 系统安装 [Calibre](https://calibre-ebook.com) | 调用 `ebook-convert` |
| 文档站 | 无 | 同域 BFS 爬取（默认 20 页/深度 2）；**先探测 `/llms.txt`，有则直接用** |
| GitHub 仓库 | 无（不需要 git） | codeload tarball；文档全量、代码截为概览 |
| 本地文档目录 / glob | 无 | 一次并入同一册 |

扫描版 PDF 需先 OCR：`ocrmypdf in.pdf out.pdf`。

## 安装

```bash
# PyPI（发布后）
pipx install doc-distill[all]        # 或 uv tool install

# 从源码
git clone https://github.com/PandaClose/doc-distill.git && cd doc-distill
pip install -e .[all]
```

## 用法

```bash
doc-distill detect <输入...>            # 识别源类型
doc-distill run <输入...> -o out/       # 一条龙：提取 → IR → 导出（无蒸馏，立即可用）
doc-distill extract <输入...> -o ir/    # 只建 IR（供宿主 agent 蒸馏）
doc-distill export ir/ --targets skill-manual,rag-jsonl -o out/
doc-distill extract <新材料> -o ir/ --append   # 增量并入
doc-distill validate out/<slug> --strict       # 质检（蒸馏占位未补全则失败）
```

### 作为 skill 使用（推荐）

把本仓库根目录注册为 skill（它本身就是一份 SKILL.md 蒸馏规格）：

```bash
npx skills add PandaClose/doc-distill       # 或手动克隆到 ~/.agents/skills/doc-distill
```

之后在 Claude Code / ZCode 里直接说「把 xx.pdf 做成 skill」，宿主 agent 会按 `SKILL.md` +
`references/distill-spec.md` 的规格完成「提取 → 通读 → 蒸馏 → 校验」全流程。

**两种用法的关系**：`run` 命令的产物是「索引 + 全文查阅型」skill，即刻可用；宿主 agent
补全三节蒸馏占位（核心框架 / 高频模式与技巧 / 决策速查）后升级为完整手册——
`validate --strict` 通过即代表蒸馏完成。

## RAG 语料格式

`chunks.jsonl` 每行一个 JSON：

```json
{"id": "0012", "text": "……", "metadata": {"source": "…", "section": "第3章 > 3.2", "title": "…", "tokens": 487, "type": "epub", "asset": "书名"}}
```

语义分块保证：代码块完整不切、段落边界对齐、约 512 tokens + 50 重叠。向量库导出（faiss/chroma 等）在路线图 M4。

## 路线图

- [x] **M1** 统一 IR + 本地 7 格式 + skill-manual/router + rag-jsonl/markdown + skill 形态
- [x] **M2** 文档站 / llms.txt / GitHub 适配器 + 源自动探测
- [ ] **M3** API 蒸馏引擎（CI / 无宿主场景，可选）+ 输出一致性校验强化
- [ ] **M4** 视频转录 / Notion / Confluence / 向量库 extras

## 与两个前身的关系

本项目合并了 [book-to-skill](https://github.com/virgiliojr94/book-to-skill)（提取/蒸馏分离架构、
手册规格、可选依赖哲学）与 [Skill_Seekers](https://github.com/yusufkaraaslan/Skill_Seekers)
（多源适配器、语义分块、多导出目标），详见 [NOTICE.md](NOTICE.md)。两者均 MIT。

## 免责声明

本工具不包含、不分发任何受版权保护的内容；蒸馏产物属个人学习用途的衍生笔记，请勿重新分发。
