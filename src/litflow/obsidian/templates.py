from __future__ import annotations

from litflow.obsidian.frontmatter import build_frontmatter


def render_literature_note(paper: dict, today: str) -> str:
    title = paper.get("title") or "论文题目"
    return f"""{build_frontmatter(paper, today)}

# {title}

## 1. 一句话结论

> 待补充。

## 2. 研究背景

> 待补充。

## 3. 研究 Gap

> 待补充。

## 4. 核心创新点

> 待补充。

## 5. 数据来源与算例规模

> 待补充。

## 6. 模型与方法分类

- 方法类型：
- 模型类型：
- 求解方式：
- 静态/动态：
- 单目标/多目标：

## 7. 目标函数与约束

> 待补充。

## 8. 实验设置与结果

> 待补充。

## 9. 局限性

> 待补充。

## 10. 与我的研究的关系

> 待补充。

## 11. 我的粗读批注

> 待补充。

## 12. 可引用证据

> 待补充。

## 13. 关联文献

> 待补充。
"""

