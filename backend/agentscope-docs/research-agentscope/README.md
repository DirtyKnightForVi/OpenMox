# AgentScope 深度研究报告集

三次递进式研究，全部以 Markdown 撰写，图使用 Mermaid 语法。

## 目录

```
research-agentscope/
├── README.md                      ← 本索引
├── 00-previous/                   ← 历史研究（多智能体调用 Demo）
├── 01-version-diff/               ← 第一轮：2.0.0 vs 2.0.1 差异
│   ├── report.md                  ← 主报告
│   ├── findings.md                ← 详细发现
│   └── sources/                   ← 原始提取源文件
├── 02-team-critique/              ← 第二轮：Team Mode 源码级批判
│   ├── report.md
│   ├── findings.md
│   └── sources/
└── 03-comprehensive/              ← 第三轮：融合你的设计哲学的理想架构
    ├── report.md
    ├── findings.md
    └── sources/
```

## 研究递进逻辑

| 轮次 | 入口问题 | 关键发现 |
|------|---------|---------|
| **01** | v2.0.0 和 v2.0.1 有什么差别？ | Agent Team 是 2.0.1 headline 特性；25 commits/251 文件/14 贡献者 |
| **02** | Team Mode 好坏？与你的需求缺口？ | 原始设计 #1422（共享队列）被简化为 Leader 驱动；基础设施好但 API 层断层 |
| **03** | 融合"Leader=人类代理, Worker=平权peer"的理想架构？ | 3 个洞察 + P0~P3 路线图；P0 只需 1 天 |

## 关键结论

- **03** 是最终结论，融合了前两轮的所有分析
- 底层基础设施（MessageBus、Redis 存储、InboxMiddleware）对拓扑中立，可完整复用
- 核心改动在工具层和 API 层，P0（Worker 平权 + 层级控制）只需 1 天
