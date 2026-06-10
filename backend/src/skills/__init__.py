"""
SkillLibrary — thin wrapper over ConfigDAO for global skill management.

Usage:
    lib = SkillLibrary()
    lib.list_all()           → ["web_search", ...]
    lib.install("web_search", ".Agents/pm-secretary/skills")
"""

from pathlib import Path

from ..dao.config_dao import ConfigDAO


class SkillLibrary:
    """Global Skills library (backend/Skills/)."""

    def __init__(self, library_path: str = "Skills"):
        self.path = Path(library_path)

    def list_all(self) -> list[str]:
        """List all available skill names."""
        return ConfigDAO.list_global_skills()

    def install(self, skill_name: str, target_dir: str | Path) -> bool:
        """Copy a skill from the global library to a target directory."""
        return ConfigDAO.install_skill(skill_name, str(target_dir))
