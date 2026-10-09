# NOTICE

doc-distill 的设计与部分实现受益于以下两个 MIT 项目，特此致谢：

## book-to-skill

- 仓库：<https://github.com/virgiliojr94/book-to-skill>
- 许可：MIT
- 借鉴内容：「提取与蒸馏分离」架构、手册型 skill 产物规格（SKILL.md + chapters + glossary +
  patterns + cheatsheet）、可选依赖（extras）按格式拆分与运行时检测引导的依赖哲学、
  「结构而非摘要」的蒸馏理念（见 `references/distill-spec.md`）。

## Skill_Seekers

- 仓库：<https://github.com/yusufkaraaslan/Skill_Seekers>
- 许可：MIT
- 借鉴内容：多源适配器思路（文档站爬取 / llms.txt / GitHub 仓库 / 视频）、语义分块规则
  （代码块完整性、段落边界、chunk size 与 overlap、元数据注入，见 `src/doc_distill/chunker.py`）、
  多导出目标（skill 格式 + RAG 语料格式）的产品矩阵设计。

两者均按 MIT 许可授权使用。本项目衍生内容同样以 MIT 许可发布。
本工具不包含也不分发任何受版权保护的书籍内容；请仅将蒸馏产物用于个人学习用途，勿重新分发。
