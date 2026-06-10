"""
Permission rule builder — generates AgentScope PermissionRules from the
four-layer file access model.

Rules (fnmatch-compatible, no middle **):
  1. .Agents/*/agent.yaml      → DENY write/edit for all
  2. .Agents/*/skills/**        → DENY write/edit for all
  3. .Agents/*/rules/**         → DENY write/edit for all
  4. .Agents/{self}/**          → ALLOW write
  5. .Agents/{other}/**         → DENY write
  6. .Project/PROJECT_MEMO.md   → momo ALLOW, others DENY
  7. .Project/skills/**         → DENY write for all
  8. .Project/rules/**          → DENY write for all

User content (src/, docs/, etc.) is unrestricted — agents can read/write freely.

Path normalization: each rule_content is emitted in two variants —
  - original  (".Agents/*/agent.yaml")
  - ./-prefixed ("./.Agents/*/agent.yaml")
This covers LLMs that prepend "./" to paths, which is common when they use
the Glob tool first and receive "./.Agents/..." style paths back.
"""

from agentscope.permission import PermissionRule, PermissionBehavior


# Tools that modify files (need path-based rules)
# Names must match AgentScope's built-in tool names exactly
_WRITE_TOOLS = ("Write", "Edit")
_READ_TOOLS = ("Read", "Glob", "Grep")


def _expand_path_variants(rules: list[PermissionRule]) -> list[PermissionRule]:
    """For each path-based rule, add a './'-prefixed copy.

    fnmatch matches the full string, so ".Agents/*/agent.yaml" won't match
    "./.Agents/pm/agent.yaml".  This helper ensures both variants exist.
    Rules with rule_content=None (tool-name-level) are left unchanged.
    """
    expanded: list[PermissionRule] = []
    for rule in rules:
        expanded.append(rule)
        if rule.rule_content and not rule.rule_content.startswith("./"):
            expanded.append(PermissionRule(
                tool_name=rule.tool_name,
                rule_content=f"./{rule.rule_content}",
                behavior=rule.behavior,
                source=f"{rule.source}_dotprefix",
            ))
    return expanded


def build_permission_rules(
    agent_id: str,
    all_agent_ids: list[str],
    is_momo: bool = False,
) -> list[PermissionRule]:
    """Generate the permission rule set for one agent.

    Args:
        agent_id: This agent's ID.
        all_agent_ids: All agent IDs in the project.
        is_momo: Whether this agent is the project's momo.

    Returns:
        List of PermissionRule ready for injection into PermissionContext.
    """
    rules: list[PermissionRule] = []

    # ── 1. agent.yaml → everyone DENY ──────────────────
    for tool in _WRITE_TOOLS:
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=".Agents/*/agent.yaml",
            behavior=PermissionBehavior.DENY,
            source="protect_agent_config",
        ))

    # ── 2. Own skills/rules → RO (DENY write) ──────────
    for tool in _WRITE_TOOLS:
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=f".Agents/{agent_id}/skills/**",
            behavior=PermissionBehavior.DENY,
            source="protect_own_skills",
        ))
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=f".Agents/{agent_id}/rules/**",
            behavior=PermissionBehavior.DENY,
            source="protect_own_rules",
        ))

    # ── 3. Other agents' skills/rules → DENY write ─────
    for other in all_agent_ids:
        if other == agent_id:
            continue
        for tool in _WRITE_TOOLS:
            rules.append(PermissionRule(
                tool_name=tool,
                rule_content=f".Agents/{other}/skills/**",
                behavior=PermissionBehavior.DENY,
                source="protect_other_skills",
            ))
            rules.append(PermissionRule(
                tool_name=tool,
                rule_content=f".Agents/{other}/rules/**",
                behavior=PermissionBehavior.DENY,
                source="protect_other_rules",
            ))

    # ── 4. Own workspace → ALLOW write ─────────────────
    for tool in _WRITE_TOOLS:
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=f".Agents/{agent_id}/**",
            behavior=PermissionBehavior.ALLOW,
            source="self_workspace",
        ))

    # ── 5. Other agents' workspace → DENY write ────────
    for other in all_agent_ids:
        if other == agent_id:
            continue
        for tool in _WRITE_TOOLS:
            rules.append(PermissionRule(
                tool_name=tool,
                rule_content=f".Agents/{other}/**",
                behavior=PermissionBehavior.DENY,
                source="other_workspace",
            ))

    # ── 6. PROJECT_MEMO.md → momo ALLOW, others DENY ───
    for tool in _WRITE_TOOLS:
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=".Project/PROJECT_MEMO.md",
            behavior=PermissionBehavior.ALLOW if is_momo else PermissionBehavior.DENY,
            source="project_memo",
        ))

    # ── 7. Project skills/rules → DENY write ───────────
    for tool in _WRITE_TOOLS:
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=".Project/skills/**",
            behavior=PermissionBehavior.DENY,
            source="protect_project_skills",
        ))
        rules.append(PermissionRule(
            tool_name=tool,
            rule_content=".Project/rules/**",
            behavior=PermissionBehavior.DENY,
            source="protect_project_rules",
        ))

    return _expand_path_variants(rules)
