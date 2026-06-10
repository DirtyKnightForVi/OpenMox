"""
OpenMoxRedisStorage — RedisStorage subclass that bridges agent CRUD to ConfigDAO (YAML).

Agent configuration (system_prompt, skills, rules, etc.) lives in YAML files
managed by ConfigDAO — human-editable and git-friendly. All other runtime
state (sessions, credentials, schedules, messages, teams) uses RedisStorage
natively via AgentScope's standard Redis backend.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from agentscope.app.storage import RedisStorage, AgentRecord, AgentData
from agentscope.agent import ContextConfig, ReActConfig

from ..dao.config_dao import ConfigDAO

if TYPE_CHECKING:
    from redis.asyncio import ConnectionPool

# ── Shared sentinel user_id ─────────────────────────
_USER_ID = "openmox"


class OpenMoxRedisStorage(RedisStorage):
    """RedisStorage with agent CRUD delegated to ConfigDAO (YAML files).

    All RedisStorage methods work natively (Redis-backed) EXCEPT:
      - upsert_agent / list_agents / get_agent / delete_agent
    which are overridden to delegate to ConfigDAO.
    """

    def __init__(
        self,
        project_root: str | Path = ".",
        *args,
        **kwargs,
    ) -> None:
        """Store project_root for ConfigDAO bridge.

        Args:
            project_root: Path to the project directory containing
                          .Agents/ and .Project/.
            *args, **kwargs: Forwarded to RedisStorage.__init__.
        """
        super().__init__(*args, **kwargs)
        self._project_root = Path(project_root).resolve()
        self._dao: ConfigDAO | None = None

    async def __aenter__(self):
        """Enter Redis context, then init ConfigDAO."""
        result = await super().__aenter__()
        self._dao = ConfigDAO(self._project_root)
        return result

    # ═══════════════════════════════════════════════════
    # Agent CRUD — bridged to ConfigDAO (YAML)
    # ═══════════════════════════════════════════════════

    def _ensure_dao(self) -> ConfigDAO:
        if self._dao is None:
            self._dao = ConfigDAO(self._project_root)
        return self._dao

    def _agent_to_record(self, cfg) -> AgentRecord:
        """Convert ConfigDAO AgentConfig → AgentScope AgentRecord."""
        from agentscope.app.storage import AgentRecord, AgentData
        return AgentRecord(
            id=cfg.id,   # MUST match agent_id so RedisStorage.get_agent can find it
            user_id=_USER_ID,
            source="user",
            data=AgentData(
                name=cfg.name,
                system_prompt=cfg.system if hasattr(cfg, 'system') else "",
                context_config=ContextConfig(),
                react_config=ReActConfig(),
            ),
        )

    async def upsert_agent(
        self, user_id: str, agent_record: AgentRecord,
    ) -> str:
        """Create or return existing agent via ConfigDAO."""
        dao = self._ensure_dao()
        existing = dao.get_agent(agent_record.id)
        if existing:
            return existing.id
        cfg = dao.create_agent(
            agent_id=agent_record.id,
            template_id=agent_record.data.name,
            name=agent_record.data.name,
            description="",
            system_override=agent_record.data.system_prompt,
        )
        return cfg.id

    async def list_agents(self, user_id: str) -> list[AgentRecord]:
        """List all agent instances in the project."""
        dao = self._ensure_dao()
        records: list[AgentRecord] = []
        for summary in dao.list_agents():
            cfg = dao.get_agent(summary.id)
            if cfg:
                records.append(self._agent_to_record(cfg))
        return records

    async def get_agent(
        self, user_id: str, agent_id: str,
    ) -> AgentRecord | None:
        """Get a single agent by id.

        Checks Redis first (where :meth:`ensure_agent_from_path` writes
        project-scoped agents), then falls back to the local ConfigDAO
        (``.Agents/`` YAML).
        """
        if not agent_id:
            return None
        # 1. Try Redis — project-scoped agents live here.
        record = await RedisStorage.get_agent(self, user_id, agent_id)
        if record is not None:
            return record
        # 2. Fallback: local ConfigDAO for onboarded agents.
        dao = self._ensure_dao()
        cfg = dao.get_agent(agent_id)
        if not cfg:
            return None
        return self._agent_to_record(cfg)

    async def delete_agent(self, user_id: str, agent_id: str) -> bool:
        """Delete agent directory via ConfigDAO."""
        dao = self._ensure_dao()
        return dao.delete_agent(agent_id)

    async def ensure_agent_from_path(
        self, user_id: str, agent_id: str, project_path: str,
    ) -> bool:
        """Look up an agent from a project directory and register it in Redis.

        The singleton storage is initialised with a fixed ``project_root``
        (the monorepo root).  When a WebSocket chat handler needs to run
        an agent from a **different** project, it calls this method first
        to sync the agent into Redis — otherwise
        :meth:`ChatService._run_impl` won't find it.

        Uses :class:`ConfigDAO` with ``project_path``, builds an
        ``AgentRecord``, and stores it directly in Redis (bypassing the
        ConfigDAO-backed :meth:`upsert_agent` override).

        Args:
            user_id: Always ``"openmox"``.
            agent_id: e.g. ``"momo"``.
            project_path: Absolute path to the project root.

        Returns:
            ``True`` if the agent was found and registered.
        """
        from ..dao import ConfigDAO
        dao = ConfigDAO(project_path)
        cfg = dao.get_agent(agent_id)
        if not cfg:
            return False
        record = self._agent_to_record(cfg)
        # Store directly in Redis — skip OpenMoxRedisStorage.upsert_agent
        # which would delegate back to the wrong ConfigDAO.
        await RedisStorage.upsert_agent(self, user_id, record)
        return True

    # ═══════════════════════════════════════════════════
    # Credential — built from environment (DeepSeek)
    # ═══════════════════════════════════════════════════

    async def get_credential(
        self, user_id: str, credential_id: str,
    ) -> "CredentialRecord | None":
        """Return DeepSeek credential from environment.

        Ignores credential_id — all callers use "default".
        Falls back to Client.__init__ signature: api_key + base_url
        so CredentialFactory.from_dict() can resolve the correct
        OpenAICredential class.
        """
        from ..core.settings import get_settings
        from agentscope.app.storage import CredentialRecord
        s = get_settings()
        if not s.deepseek_api_key:
            return None
        return CredentialRecord(
            user_id=user_id if user_id else "openmox",
            data={
                "type": "deepseek_credential",
                "api_key": s.deepseek_api_key,
                "base_url": s.deepseek_base_url,
            },
        )

    async def list_credentials(
        self, user_id: str,
    ) -> list["CredentialRecord"]:
        cred = await self.get_credential(user_id, "default")
        return [cred] if cred else []

    async def upsert_credential(
        self, user_id: str, credential_data,
    ) -> str:
        # Read-only: credentials come from env vars.
        return "default"

    async def delete_credential(
        self, user_id: str, credential_id: str,
    ) -> bool:
        return False  # Read-only

