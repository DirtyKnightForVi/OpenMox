# EvoTraders 多智能体交易系统

- **URL:** https://github.com/agentscope-ai/agentscope-samples/tree/main/evotraders
- **Website:** http://trading.evoagents.cn/
- **Retrieved:** 2025-01-XX

---

## 简介

EvoTraders是一个开源的金融交易智能体框架，通过多智能体协作和记忆系统，构建能够在真实市场中持续学习和进化的交易系统。

**6个角色的交易团队：**
- 4个专业分析师（基本面、技术、情绪、估值）
- 投资组合经理 (Portfolio Manager)
- 风险管理师 (Risk Manager)

## 核心架构

```
evotraders/
├── backend/
│   ├── agents/           # Agent定义
│   ├── core/            # 核心逻辑（pipeline, scheduler）
│   ├── services/        # 服务（gateway, market, storage）
│   ├── tools/           # 分析工具
│   └── main.py          # 入口
├── frontend/            # Web界面
└── config/              # 配置文件
```

## backend/main.py 核心代码

```python
# -*- coding: utf-8 -*-
"""
Main Entry Point
Supports: backtest, live, mock modes
"""
import argparse
import asyncio
import logging
import os
from contextlib import AsyncExitStack
from pathlib import Path
import loguru

from dotenv import load_dotenv

from backend.agents import AnalystAgent, PMAgent, RiskAgent
from backend.config.constants import ANALYST_TYPES
from backend.config.env_config import get_env_float, get_env_int, get_env_list
from backend.core.pipeline import TradingPipeline
from backend.core.scheduler import BacktestScheduler, Scheduler
from backend.utils.settlement import SettlementCoordinator
from backend.llm.models import get_agent_formatter, get_agent_model
from backend.services.gateway import Gateway
from backend.services.market import MarketService
from backend.services.storage import StorageService

load_dotenv()

# ... 省略其他代码 ...

def create_agents(
    config_name: str,
    initial_cash: float,
    margin_requirement: float,
    enable_long_term_memory: bool = False,
):
    """Create all agents for the system

    Returns:
        tuple: (analysts, risk_manager, portfolio_manager, long_term_memories)
    """
    analysts = []
    long_term_memories = []

    for analyst_type in ANALYST_TYPES:
        model = get_agent_model(analyst_type)
        formatter = get_agent_formatter(analyst_type)
        toolkit = create_toolkit(analyst_type)

        long_term_memory = None
        if enable_long_term_memory:
            long_term_memory = create_long_term_memory(
                analyst_type,
                config_name,
            )
            if long_term_memory:
                long_term_memories.append(long_term_memory)

        analyst = AnalystAgent(
            analyst_type=analyst_type,
            toolkit=toolkit,
            model=model,
            formatter=formatter,
            agent_id=analyst_type,
            config={"config_name": config_name},
            long_term_memory=long_term_memory,
        )
        analysts.append(analyst)

    # 创建风险管理Agent
    risk_long_term_memory = None
    if enable_long_term_memory:
        risk_long_term_memory = create_long_term_memory(
            "risk_manager",
            config_name,
        )

    risk_manager = RiskAgent(
        model=get_agent_model("risk_manager"),
        formatter=get_agent_formatter("risk_manager"),
        name="risk_manager",
        config={"config_name": config_name},
        long_term_memory=risk_long_term_memory,
    )

    # 创建投资组合管理Agent
    pm_long_term_memory = None
    if enable_long_term_memory:
        pm_long_term_memory = create_long_term_memory(
            "portfolio_manager",
            config_name,
        )

    portfolio_manager = PMAgent(
        name="portfolio_manager",
        model=get_agent_model("portfolio_manager"),
        formatter=get_agent_formatter("portfolio_manager"),
        initial_cash=initial_cash,
        margin_requirement=margin_requirement,
        config={"config_name": config_name},
        long_term_memory=pm_long_term_memory,
    )

    return analysts, risk_manager, portfolio_manager, long_term_memories

def create_long_term_memory(agent_name: str, config_name: str):
    """Create ReMeTaskLongTermMemory for an agent"""
    from agentscope.memory import ReMeTaskLongTermMemory
    from agentscope.model import DashScopeChatModel
    from agentscope.embedding import DashScopeTextEmbedding

    api_key = os.getenv("MEMORY_API_KEY")
    if not api_key:
        return None

    memory_dir = str(Path(config_name) / "memory")

    return ReMeTaskLongTermMemory(
        agent_name=agent_name,
        user_name=agent_name,
        model=DashScopeChatModel(
            model_name=os.getenv("MEMORY_MODEL_NAME", "qwen3-max"),
            api_key=api_key,
            stream=False,
        ),
        embedding_model=DashScopeTextEmbedding(
            model_name=os.getenv("MEMORY_EMBEDDING_MODEL", "text-embedding-v4"),
            api_key=api_key,
            dimensions=1024,
        ),
        **{
            "vector_store.default.backend": "local",
            "vector_store.default.params.store_dir": memory_dir,
        },
    )
```

## 核心特性

1. **多智能体协作交易** - 6个角色的团队协作，模拟真实交易团队
2. **持续学习与进化** - 基于ReMe记忆框架，每次交易后反思总结
3. **长期投资方法论** - 形成独特的投资风格，而非一次性随机推理
4. **长期记忆 (LTS)** - 每个Agent有独立的持久化记忆
5. **TradingPipeline** - 交易工作流管道
6. **回测支持** - 支持回测、实盘、模拟三种模式
