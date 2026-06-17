"""Data models for ConfigDAO."""

from dataclasses import dataclass, field


@dataclass
class TemplateSummary:
    id: str
    name: str
    avatar: str
    description: str
    skills_count: int = 0


@dataclass
class TemplateConfig(TemplateSummary):
    system: str = ""
    rules: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)


@dataclass
class AgentSummary:
    id: str
    name: str
    avatar: str
    description: str
    template: str = ""
    is_momo: bool = False
    capabilities: list[str] = field(default_factory=list)


@dataclass
class AgentConfig(AgentSummary):
    system: str = ""
    rules: list[str] = field(default_factory=list)
    skills: list[str] = field(default_factory=list)
    capabilities: list[str] = field(default_factory=list)
    shendu_prompt: str = ""


@dataclass
class SkillSummary:
    name: str
    description: str


@dataclass
class SkillConfig(SkillSummary):
    body: str = ""


@dataclass
class SkillSources:
    own: list[str] = field(default_factory=list)
    project: list[str] = field(default_factory=list)


# ── Dashboard task model ──────────────────────────────


@dataclass
class TaskItem:
    """A single task in the project DAG dashboard.

    Mirrors the YAML schema in .Project/DASHBOARD.yaml.
    """
    id: str
    title: str
    description: str = ""
    phase: str = ""                          # research | development | review | delivery
    owner: str = ""                          # agent_id responsible
    status: str = "pending"                  # pending | in_progress | done | blocked
    depends_on: list[str] = field(default_factory=list)  # task IDs that must complete first
    window_id: str | None = None             # None = project-level (all windows visible)
    created_by: str = ""
    created_at: str = ""
    completed_at: str = ""
    output: str = ""
    blocked_reason: str = ""
    communication_budget: int = 3            # max peer-to-peer TeamSay calls for this task
