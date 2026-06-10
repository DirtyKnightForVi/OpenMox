"""
MentionRouter — parse @agentId mentions from message text.

Example:
    "@product-manager @arch-manager 分析这个需求"
    → mentioned = ["product-manager", "arch-manager"]
    → clean_msg = "分析这个需求"
"""

import re
from typing import Tuple

# Matches @agent-id where agent-id is alphanumeric + hyphens/underscores
_MENTION_RE = re.compile(r"@([a-z0-9_-]+)", re.IGNORECASE)


class MentionRouter:
    """Parse @mentions from user messages."""

    def parse(self, text: str) -> Tuple[list[str], str]:
        """Extract @agentId mentions and return (mentioned_ids, clean_text).

        Args:
            text: The raw user message, e.g. "@pm @dev 分析需求"

        Returns:
            (mentioned, clean_msg) where mentioned is a deduplicated,
            order-preserving list of agent IDs, and clean_msg has all
            @mentions stripped.
        """
        if not text:
            return [], ""

        mentioned = list(dict.fromkeys(_MENTION_RE.findall(text)))
        clean = _MENTION_RE.sub("", text).strip()
        # If stripping removed everything, keep original
        if not clean and mentioned:
            clean = text.strip()
        return mentioned, clean


# Convenience singleton
_router: MentionRouter | None = None


def get_router() -> MentionRouter:
    global _router
    if _router is None:
        _router = MentionRouter()
    return _router
