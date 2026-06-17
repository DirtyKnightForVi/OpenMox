"""
ConfigDAO — unified data access layer for static configuration.

Covers:
  - Agent templates (Agent_Sets/)
  - Global Skill library (Skills/)
  - Agent instances (.Agents/{id}/)
  - Project config (.Project/)
  - momo identity (.Project/momo.yaml)

Global data accessed via class methods (no project context).
Project data accessed via instance methods (bound to project_root).
"""

import shutil
import yaml
from pathlib import Path
from typing import Optional

from .models import (
    TemplateSummary, TemplateConfig,
    AgentSummary, AgentConfig,
    SkillSummary, SkillConfig, SkillSources,
)

# ── Paths (relative to backend/) ──────────────────────

TEMPLATES_DIR = Path("Agent_Sets")
SKILLS_DIR = Path("Skills")
PROJECT_TEMPLATES_DIR = Path("Project_Templates")


class ConfigDAO:
    """Unified config data access."""

    def __init__(self, project_root: str | Path):
        self.root = Path(project_root)
        self.agents_dir = self.root / ".Agents"
        self.project_dir = self.root / ".Project"

    # ═══════════════════════════════════════════════════
    # Global: Agent Templates
    # ═══════════════════════════════════════════════════

    @staticmethod
    def list_templates() -> list[TemplateSummary]:
        if not TEMPLATES_DIR.exists():
            return []
        result = []
        for d in sorted(TEMPLATES_DIR.iterdir()):
            if not d.is_dir():
                continue
            yaml_file = d / "agent.yaml"
            if not yaml_file.exists():
                continue
            data = ConfigDAO._read_yaml(yaml_file)
            result.append(TemplateSummary(
                id=d.name,
                name=data.get("name", d.name),
                avatar=data.get("avatar", "🤖"),
                description=data.get("description", ""),
                skills_count=len(data.get("skills", [])),
            ))
        return result

    @staticmethod
    def get_template(template_id: str) -> Optional[TemplateConfig]:
        yaml_file = TEMPLATES_DIR / template_id / "agent.yaml"
        if not yaml_file.exists():
            return None
        data = ConfigDAO._read_yaml(yaml_file)
        return TemplateConfig(
            id=template_id,
            name=data.get("name", template_id),
            avatar=data.get("avatar", "🤖"),
            description=data.get("description", ""),
            skills_count=len(data.get("skills", [])),
            system=data.get("system", ""),
            rules=data.get("rules", []),
            skills=data.get("skills", []),
        )

    @staticmethod
    def get_template_skills(template_id: str) -> list[str]:
        t = ConfigDAO.get_template(template_id)
        return t.skills if t else []

    # ═══════════════════════════════════════════════════
    # Global: Skill Library
    # ═══════════════════════════════════════════════════

    @staticmethod
    def list_global_skills() -> list[SkillSummary]:
        if not SKILLS_DIR.exists():
            return []
        result = []
        for d in sorted(SKILLS_DIR.iterdir()):
            if not d.is_dir():
                continue
            md = d / "SKILL.md"
            if not md.exists():
                continue
            name, desc = ConfigDAO._parse_skill_frontmatter(md)
            result.append(SkillSummary(name=name or d.name, description=desc or ""))
        return result

    @staticmethod
    def get_skill(skill_name: str) -> Optional[SkillConfig]:
        md = SKILLS_DIR / skill_name / "SKILL.md"
        if not md.exists():
            return None
        name, desc = ConfigDAO._parse_skill_frontmatter(md)
        body = md.read_text(encoding="utf-8")
        return SkillConfig(name=name or skill_name, description=desc or "", body=body)

    @staticmethod
    def install_skill(skill_name: str, target_dir: str | Path) -> bool:
        src = SKILLS_DIR / skill_name
        if not (src / "SKILL.md").exists():
            return False
        dst = Path(target_dir) / skill_name
        shutil.copytree(src, dst, dirs_exist_ok=True)
        return True

    # ═══════════════════════════════════════════════════
    # Project: Agent Instances
    # ═══════════════════════════════════════════════════

    def list_agents(self) -> list[AgentSummary]:
        if not self.agents_dir.exists():
            return []
        momo_id = self.get_momo_id()
        result = []
        for d in sorted(self.agents_dir.iterdir()):
            if not d.is_dir():
                continue
            yaml_file = d / "agent.yaml"
            if not yaml_file.exists():
                continue
            data = self._read_yaml(yaml_file)
            result.append(AgentSummary(
                id=d.name,
                name=data.get("name", d.name),
                avatar=data.get("avatar", "🤖"),
                description=data.get("description", ""),
                template=data.get("template", d.name),
                is_momo=(d.name == momo_id),
                capabilities=data.get("capabilities", []),
            ))
        return result

    def get_agent(self, agent_id: str) -> Optional[AgentConfig]:
        yaml_file = self.agents_dir / agent_id / "agent.yaml"
        if not yaml_file.exists():
            return None
        data = self._read_yaml(yaml_file)
        return AgentConfig(
            id=agent_id,
            name=data.get("name", agent_id),
            avatar=data.get("avatar", "🤖"),
            description=data.get("description", ""),
            template=data.get("template", agent_id),
            is_momo=self.is_momo(agent_id),
            system=data.get("system", ""),
            rules=data.get("rules", []),
            skills=data.get("skills", []),
            capabilities=data.get("capabilities", []),
            shendu_prompt=data.get("shendu_prompt", ""),
        )

    def get_agent_system_prompt(self, agent_id: str) -> str:
        cfg = self.get_agent(agent_id)
        return cfg.system if cfg else ""

    def create_agent(
        self,
        *,
        agent_id: str,
        template_id: str,
        name: Optional[str] = None,
        avatar: Optional[str] = None,
        description: Optional[str] = None,
        system_override: Optional[str] = None,
    ) -> AgentConfig:
        """Create an agent instance from a template."""
        tmpl = ConfigDAO.get_template(template_id)
        if not tmpl:
            raise ValueError(f"Template not found: {template_id}")

        # Build config
        config = {
            "name": name or tmpl.name,
            "avatar": avatar or tmpl.avatar,
            "description": description or tmpl.description,
            "system": system_override or tmpl.system,
            "rules": tmpl.rules,
            "skills": tmpl.skills,
            "template": template_id,
        }

        # Save agent.yaml
        agent_dir = self.agents_dir / agent_id
        agent_dir.mkdir(parents=True, exist_ok=True)
        self._write_yaml(agent_dir / "agent.yaml", config)

        # Scaffold
        (agent_dir / "MEMORY.md").write_text(
            f"# {config['name']} 独有记忆\n\n", encoding="utf-8"
        )
        (agent_dir / "rules").mkdir(exist_ok=True)
        (agent_dir / "skills").mkdir(exist_ok=True)

        # Install skills from template
        for skill_name in tmpl.skills:
            ConfigDAO.install_skill(skill_name, str(agent_dir / "skills"))

        # Auto-set as momo if first agent
        is_first = (self.get_momo_id() is None)
        if is_first:
            self.set_momo(agent_id)

        return AgentConfig(
            id=agent_id,
            name=config["name"],
            avatar=config["avatar"],
            description=config["description"],
            template=template_id,
            is_momo=self.is_momo(agent_id),
            system=config["system"],
            rules=tmpl.rules,
            skills=tmpl.skills,
        )

    def delete_agent(self, agent_id: str) -> bool:
        agent_dir = self.agents_dir / agent_id
        if agent_dir.exists():
            shutil.rmtree(agent_dir)
            # Clear momo if this was momo
            if self.is_momo(agent_id):
                self._clear_momo()
            return True
        return False

    def get_agent_skills(self, agent_id: str) -> SkillSources:
        own = []
        own_dir = self.agents_dir / agent_id / "skills"
        if own_dir.exists():
            own = [d.name for d in own_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

        project = []
        proj_dir = self.project_dir / "skills"
        if proj_dir.exists():
            project = [d.name for d in proj_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()]

        return SkillSources(own=own, project=project)

    def get_skill_dirs(self, agent_id: str) -> list[str]:
        """Return skill directory paths for Toolkit registration."""
        dirs = []
        own = self.agents_dir / agent_id / "skills"
        if own.exists() and any(own.iterdir()):
            dirs.append(str(own))
        proj = self.project_dir / "skills"
        if proj.exists() and any(proj.iterdir()):
            dirs.append(str(proj))
        return dirs

    # ═══════════════════════════════════════════════════
    # Project: momo Identity
    # ═══════════════════════════════════════════════════

    def get_momo_id(self) -> Optional[str]:
        yaml_file = self.project_dir / "momo.yaml"
        if not yaml_file.exists():
            return None
        data = self._read_yaml(yaml_file)
        return data.get("momo_agent_id")

    def set_momo(self, agent_id: str) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.project_dir / "momo.yaml", {"momo_agent_id": agent_id})

    def is_momo(self, agent_id: str) -> bool:
        return agent_id == self.get_momo_id()

    def _clear_momo(self) -> None:
        momo_file = self.project_dir / "momo.yaml"
        if momo_file.exists():
            momo_file.unlink()

    # ═══════════════════════════════════════════════════
    # Project: Team configuration (.Project/team.yaml)
    # ═══════════════════════════════════════════════════

    def read_team_yaml(self) -> dict | None:
        """Read .Project/team.yaml, return None if missing."""
        f = self.project_dir / "team.yaml"
        if not f.exists():
            return None
        return self._read_yaml(f)

    def write_team_yaml(self, leader: str, member_ids: list[str]) -> None:
        """Write .Project/team.yaml with leader + member list."""
        self.project_dir.mkdir(parents=True, exist_ok=True)
        self._write_yaml(self.project_dir / "team.yaml", {
            "leader": leader,
            "members": member_ids,
        })

    def add_team_member(self, agent_id: str) -> None:
        """Append an agent to the team member list."""
        data = self.read_team_yaml() or {}
        members: list[str] = list(data.get("members", []))
        if agent_id not in members:
            members.append(agent_id)
            leader = data.get("leader") or self.get_momo_id() or ""
            self.write_team_yaml(leader, members)

    def remove_team_member(self, agent_id: str) -> None:
        """Remove an agent from the team member list."""
        data = self.read_team_yaml() or {}
        members: list[str] = list(data.get("members", []))
        if agent_id in members:
            members.remove(agent_id)
            leader = data.get("leader") or self.get_momo_id() or ""
            self.write_team_yaml(leader, members)

    def get_team_leader(self) -> str | None:
        """Return the team leader agent_id from team.yaml, or None."""
        data = self.read_team_yaml()
        return data.get("leader") if data else None

    # ═══════════════════════════════════════════════════
    # Project: Config
    # ═══════════════════════════════════════════════════

    def get_project_skills(self) -> list[str]:
        d = self.project_dir / "skills"
        if not d.exists():
            return []
        return [x.name for x in d.iterdir() if x.is_dir() and (x / "SKILL.md").exists()]

    def get_project_rules(self) -> list[str]:
        d = self.project_dir / "rules"
        if not d.exists():
            return []
        return sorted(f.name for f in d.glob("*.md"))

    def get_project_memo(self) -> str:
        f = self.project_dir / "PROJECT_MEMO.md"
        if f.exists():
            return f.read_text(encoding="utf-8")
        return ""

    def write_project_memo(self, content: str) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        (self.project_dir / "PROJECT_MEMO.md").write_text(content, encoding="utf-8")

    def get_onboarding_context(self) -> str:
        """Return project background for injection into system_prompt."""
        parts = []
        rules_dir = self.project_dir / "rules"
        if rules_dir.exists():
            for f in sorted(rules_dir.glob("*.md")):
                parts.append(f.read_text(encoding="utf-8"))
        agents_md = self.root / "AGENTS.md"
        if agents_md.exists():
            parts.append(agents_md.read_text(encoding="utf-8"))
        return "\n\n".join(parts) if parts else ""

    # ═══════════════════════════════════════════════════
    # Lifecycle
    # ═══════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════
    # Global: Project Templates
    # ═══════════════════════════════════════════════════

    @staticmethod
    def list_project_templates() -> list[dict]:
        """List available project templates from Project_Templates/."""
        if not PROJECT_TEMPLATES_DIR.exists():
            return []
        result = []
        for f in sorted(PROJECT_TEMPLATES_DIR.glob("*.yaml")):
            data = ConfigDAO._read_yaml(f)
            result.append({
                "id": f.stem,
                "name": data.get("name", f.stem),
                "description": data.get("description", ""),
                "agents": data.get("agents", []),
            })
        return result

    @staticmethod
    def get_project_template(template_id: str) -> dict | None:
        """Return a single project template, or None."""
        f = PROJECT_TEMPLATES_DIR / f"{template_id}.yaml"
        if not f.exists():
            return None
        data = ConfigDAO._read_yaml(f)
        return {
            "id": template_id,
            "name": data.get("name", template_id),
            "description": data.get("description", ""),
            "agents": data.get("agents", []),
        }

    @staticmethod
    def init_project(project_root: str | Path) -> None:
        root = Path(project_root)
        root.mkdir(parents=True, exist_ok=True)
        for d in [".Agents", ".Project", ".Project/rules", ".Project/skills"]:
            (root / d).mkdir(parents=True, exist_ok=True)

    # ═══════════════════════════════════════════════════
    # Helpers
    # ═══════════════════════════════════════════════════

    @staticmethod
    def _read_yaml(path: Path) -> dict:
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = yaml.safe_load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    @staticmethod
    def _write_yaml(path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, default_flow_style=False)

    @staticmethod
    def _parse_skill_frontmatter(md_path: Path) -> tuple[Optional[str], Optional[str]]:
        """Extract name and description from SKILL.md frontmatter."""
        try:
            text = md_path.read_text(encoding="utf-8")
        except Exception:
            return None, None
        # Simple frontmatter parser: look for --- delimited block at start
        if text.startswith("---"):
            end = text.find("---", 3)
            if end > 0:
                fm_text = text[3:end].strip()
                name = None
                desc = None
                for line in fm_text.split("\n"):
                    if ":" in line:
                        key, _, val = line.partition(":")
                        key = key.strip()
                        val = val.strip().strip('"').strip("'")
                        if key == "name":
                            name = val
                        elif key == "description":
                            desc = val
                return name, desc
        return None, None
