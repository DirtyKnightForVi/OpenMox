"""Experiment: verify fnmatch behaviour with different path prefixes.

Background: AgentScope's Write/Edit/Read/Glob/Grep tools use fnmatch.fnmatch()
to match permission rule_content against tool input paths.  If an LLM passes
"./.Agents/pm/agent.yaml" (e.g. after a Glob result) instead of
".Agents/pm/agent.yaml", the original rule won't match.

Run: cd backend && python3 experiment/path_normalize_test.py
"""

import fnmatch
import sys


def test():
    rules = [
        ".Agents/*/agent.yaml",
        ".Agents/*/skills/**",
        ".Agents/*/rules/**",
        ".Agents/pm-secretary/**",
        ".Project/PROJECT_MEMO.md",
    ]

    paths = [
        # Canonical relative (what we designed for)
        ".Agents/pm-secretary/agent.yaml",
        ".Agents/pm-secretary/skills/web_search/SKILL.md",
        ".Agents/pm-secretary/rules/code-style.md",
        ".Agents/pm-secretary/MEMORY.md",
        ".Project/PROJECT_MEMO.md",
        # Prefixed with ./ (what LLM often emits after glob)
        "./.Agents/pm-secretary/agent.yaml",
        "./.Agents/pm-secretary/skills/web_search/SKILL.md",
        "./.Agents/pm-secretary/rules/code-style.md",
        "./.Agents/pm-secretary/MEMORY.md",
        "./.Project/PROJECT_MEMO.md",
        # User files (should NOT match agent protection rules)
        "src/main.py",
        "docs/README.md",
    ]

    all_pass = True
    for rule in rules:
        for path in paths:
            matched = fnmatch.fnmatch(path, rule)
            # This path SHOULD match this rule
            should = _should_match(rule, path)
            status = "✅" if matched == should else "❌"
            if matched != should:
                all_pass = False
            print(f"{status}  rule={rule:50s}  path={path:50s}  match={matched}")

    print()
    if all_pass:
        print("All checks passed ✅")
    else:
        print("FAILURES DETECTED — ./ prefix paths need additional rules ❌")
        sys.exit(1)


def _should_match(rule: str, path: str) -> bool:
    """Whether path *should* match rule semantically."""
    # Strip ./ prefix for comparison
    normalized = path.removeprefix("./")
    return fnmatch.fnmatch(normalized, rule)


if __name__ == "__main__":
    test()
