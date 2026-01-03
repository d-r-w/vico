from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from tools.tool_definitions import get_tool_definitions


@dataclass(frozen=True)
class AgentProfile:
    """Policy + prompt bundle for a specific agent persona."""

    agent_id: str
    description: str
    allowed_tool_names: Set[str]


def _fingerprint_toolset(tool_names: Iterable[str]) -> str:
    joined = ",".join(sorted(set(tool_names)))
    if not joined:
        return "none"
    return hashlib.sha1(joined.encode("utf-8")).hexdigest()[:8]


def filter_tool_definitions(allowed_tool_names: Iterable[str]) -> List[Dict[str, Any]]:
    allowed = set(allowed_tool_names)
    if not allowed:
        return []
    tools = get_tool_definitions()
    filtered: List[Dict[str, Any]] = []
    for tool in tools:
        function = tool.get("function") or {}
        name = function.get("name")
        if isinstance(name, str) and name in allowed:
            filtered.append(tool)
    return filtered


def build_tool_usage_prompt(*, allowed_tool_definitions: Sequence[Dict[str, Any]]) -> str:
    if not allowed_tool_definitions:
        return (
            "You do not have access to any tools.\n"
            "Do not output <tool_call> blocks.\n"
            "Answer using only the conversation context."
        )

    lines: List[str] = [
        "You have access to a limited set of tools. Use them only when they materially improve correctness.",
        "",
        "Tool calling format (exact):",
        "<tool_call>{\"name\": \"tool_name\", \"arguments\": {\"arg\": \"value\"}}</tool_call>",
        "",
        "Rules:",
        "- Call tools sequentially; do not batch multiple <tool_call> blocks in one message.",
        "- Use simple, minimal arguments that match the tool schema.",
        "- After receiving <tool_call_results>, continue the task; do not repeat the same call without a new reason.",
        "",
        "Available tools:",
    ]

    for tool in allowed_tool_definitions:
        function = tool.get("function") or {}
        name = function.get("name", "")
        description = function.get("description", "")
        if isinstance(name, str) and name:
            desc = description if isinstance(description, str) else ""
            lines.append(f"- {name}: {desc}".rstrip())

    return "\n".join(lines).strip()


def get_agent_profile(agent_id: Optional[str], *, is_agent: bool) -> AgentProfile:
    resolved = (agent_id or "").strip()
    if not resolved:
        resolved = "chat" if not is_agent else "orchestrator"

    profiles: Dict[str, AgentProfile] = {
        # No-tool profile for standard chat.
        "chat": AgentProfile(
            agent_id="chat",
            description="No tools; pure chat.",
            allowed_tool_names=set(),
        ),
        # Specialized agents (the orchestrator should see these as tools).
        "general": AgentProfile(
            agent_id="general",
            description="General assistant with memory search and offline research tools (no writes, no shell).",
            allowed_tool_names={"search_memories", "perform_research", "get_full_topic_details"},
        ),
        # Memory write-enabled agent.
        "memory_manager": AgentProfile(
            agent_id="memory_manager",
            description="Memory maintenance (search + save + edit).",
            allowed_tool_names={"search_memories", "save_memory", "edit_memory"},
        ),
        # Shell-enabled agent (dangerous; keep intentionally separate).
        "dev_shell": AgentProfile(
            agent_id="dev_shell",
            description="Developer shell access via terminal_command only.",
            allowed_tool_names={"terminal_command"},
        ),
        # Orchestrator sees specialized agents as "tools" and delegates into them.
        "orchestrator": AgentProfile(
            agent_id="orchestrator",
            description="Orchestrator agent. Delegates work to specialized agents (which have real tool access).",
            allowed_tool_names={"general", "memory_manager", "dev_shell"},
        ),
    }

    profile = profiles.get(resolved)
    if profile is None:
        # Unknown agent_id: fail closed to a safe default rather than silently granting more power.
        profile = profiles["orchestrator" if is_agent else "chat"]

    return profile


def get_specialized_agent_profiles() -> List[AgentProfile]:
    """Profiles that should be exposed to the orchestrator as callable agent-tools."""
    return [
        get_agent_profile("general", is_agent=True),
        get_agent_profile("memory_manager", is_agent=True),
        get_agent_profile("dev_shell", is_agent=True),
    ]


def build_agent_profile_tool_definitions(agent_profiles: Sequence[AgentProfile]) -> List[Dict[str, Any]]:
    """Create tool schemas representing agent profiles (not raw tools)."""
    definitions: List[Dict[str, Any]] = []
    for profile in agent_profiles:
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": profile.agent_id,
                    "description": profile.description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "What you want this specialized agent to do.",
                            }
                        },
                        "required": ["task"],
                    },
                },
            }
        )
    return definitions


def get_agent_cache_suffix(profile: AgentProfile) -> str:
    """Stable suffix to prevent prompt-cache cross-contamination between agent policies."""
    return f"{profile.agent_id}__{_fingerprint_toolset(profile.allowed_tool_names)}"


