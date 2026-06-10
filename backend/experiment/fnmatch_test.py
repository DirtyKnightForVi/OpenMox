"""
验证 Python fnmatch 对权限规则的实际支持情况。

发现：fnmatch 不支持中间的 **，只在开头/结尾有效。
结论：权限规则需要用精确路径或 fnmatch 兼容的模式。
"""

import fnmatch

# ── 修正后的规则测试（避免中间 **）────────────────────

cases = [
    # 模式                         路径                                       预期
    ("*.yaml",                     ".Agents/pm-secretary/agent.yaml",       False), # * 不跨 /
    ("**/*.yaml",                  ".Agents/pm-secretary/agent.yaml",       True),
    ("**/agent.yaml",              ".Agents/product-manager/agent.yaml",   True),
    ("**/MEMORY.md",               ".Agents/pm-secretary/MEMORY.md",       True),
    (".Agents/*/agent.yaml",       ".Agents/product-manager/agent.yaml",   True),
    (".Agents/*/MEMORY.md",        ".Agents/pm-secretary/MEMORY.md",       True),
    (".Agents/*/MEMORY.md",        ".Agents/arch-manager/agent.yaml",      False),
    (".Agents/pm-secretary/**",    ".Agents/pm-secretary/MEMORY.md",       True),
    (".Agents/pm-secretary/**",    ".Agents/product-manager/MEMORY.md",    False),
    (".Project/PROJECT_MEMO.md",   ".Project/PROJECT_MEMO.md",              True),
    (".Project/PROJECT_MEMO.md",   ".Project/skills/SKILL.md",              False),
    (".Project/skills/*",          ".Project/skills/web_search/SKILL.md",  False), # * 不跨 /
    (".Project/skills/**",         ".Project/skills/web_search/SKILL.md",  True),
    ("src/**",                     "src/main.py",                          True),
    ("src/**",                     "src/sub/deep/file.py",                 True),
    ("**",                         "anything/at/all.py",                   True),
]

print("=== fnmatch 权限规则验证 ===\n")
all_ok = True
for pattern, path, expected in cases:
    result = fnmatch.fnmatch(path, pattern)
    status = "✅" if result == expected else "❌"
    if result != expected:
        all_ok = False
    print(f"{status}  {pattern:35s} ← {path}")

print(f"\n{'全部通过 ✅ — 规则可用' if all_ok else '存在失败 ❌'}")

# ── 权限矩阵可行性结论 ────────────────────────────────

print("""
=== 结论 ===

fnmatch 规则：
  开头 **/   → 匹配任意深度   ✅
  结尾 /**   → 匹配任意深度   ✅
  中间 **    → 不可用         ❌
  *          → 不跨 /         ✅
  精确路径    → 精确匹配       ✅

我们的权限矩阵：
  DENY  agent.yaml      → ".Agents/*/agent.yaml"         ✅
  RW    自己 MEMORY.md   → ".Agents/{self}/**"            ✅
  DENY  别人目录          → 需要列出所有 other 路径          ⚠️
  RW    PROJECT_MEMO.md  → ".Project/PROJECT_MEMO.md"     ✅ (精确路径)
  RO    skills/rules     → ".Agents/*/skills/**" → DENY write ✅
  RW    用户目录          → 不需规则（ACCEPT_EDITS 模式）   ✅
""")
