from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set

from tools.tool_definitions import get_tool_definitions, perform_research_tool_name

AGENT_GENERAL = "general"
AGENT_MEMORY_MANAGER = "memory_manager"
AGENT_SHELL_OPERATOR = "shell_operator"
AGENT_ORCHESTRATOR = "orchestrator"

TOOL_SEARCH_MEMORIES = "search_memories"
TOOL_PERFORM_RESEARCH = "perform_research"
TOOL_GET_FULL_TOPIC_DETAILS = "get_full_topic_details"
TOOL_SAVE_MEMORY = "save_memory"
TOOL_EDIT_MEMORY = "edit_memory"
TOOL_TERMINAL_COMMAND = "terminal_command"

TOOL_USAGE_NO_TOOLS = (
    "You do not have access to any tools.\n"
    "Do not output <tool_call> blocks.\n"
    "Answer using only the conversation context."
)

@dataclass(frozen=True)
class AgentProfile:
    agent_id: str
    description: str
    allowed_tool_names: Set[str]
    system_instructions: Optional[str] = None


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


def build_tool_usage_prompt(
    *, 
    allowed_tool_definitions: Sequence[Dict[str, Any]],
    is_subagent: bool = False
) -> str:
    if not allowed_tool_definitions:
        return TOOL_USAGE_NO_TOOLS

    lines: List[str] = []

    if is_subagent:
        # Subagent prompt - show available tools
        lines.extend([
            "",
            "Available tools:",
        ])
    else:
        # Orchestrator prompt - show available subagents
        lines.extend([
            "You are an agent orchestrator with access to subagents. Delegate to these agents to materially improve response quality.",
            "",
            "Rules:",
            "- Call subagents sequentially; do not batch multiple <tool_call> blocks in one message.",
            "- Subagents do not persist context between calls; each call is a new context. It is vital to provide the subagent with sufficient context to complete the task.",
            "- Use simple, minimal arguments that match the tool schema.",
            "- After receiving <tool_call_results> (the subagent response), continue the task; do not repeat the same call without a new reason.",
            "",
            "Available subagents:",
        ])

    for tool in allowed_tool_definitions:
        function = tool.get("function") or {}
        name = function.get("name", "")
        description = function.get("description", "")
        if isinstance(name, str) and name:
            desc = description if isinstance(description, str) else ""
            lines.append(f"- {name}: {desc}".rstrip())

    return "\n".join(lines).strip()


def get_agent_profile(agent_id: Optional[str]) -> AgentProfile:
    profiles: Dict[str, AgentProfile] = {
        AGENT_GENERAL: AgentProfile(
            agent_id=AGENT_GENERAL,
            description="General assistant with memory search and offline research tools (no writes, no shell).",
            allowed_tool_names={
                TOOL_SEARCH_MEMORIES,
                TOOL_PERFORM_RESEARCH,
                TOOL_GET_FULL_TOPIC_DETAILS,
            },
            system_instructions=(
                f"Always cite the article ID when providing information from `{perform_research_tool_name}`. Only include information that can be found within the article. If the article does not contain the information, do not include it in your response."
            )
        ),
        AGENT_MEMORY_MANAGER: AgentProfile(
            agent_id=AGENT_MEMORY_MANAGER,
            description="Memory maintenance agent.",
            allowed_tool_names={
                TOOL_SEARCH_MEMORIES,
                TOOL_SAVE_MEMORY,
                TOOL_EDIT_MEMORY,
            },
        ),
        AGENT_SHELL_OPERATOR: AgentProfile(
            agent_id=AGENT_SHELL_OPERATOR,
            description="Agent with access to a macos zsh shell environment. Can read web resources. Requested task can be an agentic goal - request minimal output to prevent context window bloat.",
            allowed_tool_names={TOOL_TERMINAL_COMMAND},
            system_instructions=(
                "You are operating in a macOS zsh environment. Strive to do more than just running commands, complete the task as fully as possible. You have the ability to read web resources using curl -L.\n"
                "When finished, output a concise final result intended to be consumed by the parent assistant."
            ),
        ),
        AGENT_ORCHESTRATOR: AgentProfile(
            agent_id=AGENT_ORCHESTRATOR,
            description="Orchestrator agent. Delegates work and reasoning to specialized agents (which have real tool access). Continuously negotiates with available agents on the user's behalf to fully and successfully complete the task.",
            allowed_tool_names={AGENT_GENERAL, AGENT_MEMORY_MANAGER, AGENT_SHELL_OPERATOR},
        ),
    }
    
    resolved = (agent_id or "").strip()

    profile = profiles.get(resolved)
    if profile is None:
        profile = profiles[AGENT_ORCHESTRATOR]

    return profile

def get_specialized_agent_profiles() -> List[AgentProfile]:
    return [
        get_agent_profile(AGENT_GENERAL),
        get_agent_profile(AGENT_MEMORY_MANAGER),
        get_agent_profile(AGENT_SHELL_OPERATOR),
    ]

def build_agent_profile_tool_definitions(agent_profiles: Sequence[AgentProfile]) -> List[Dict[str, Any]]:
    definitions: List[Dict[str, Any]] = []
    for profile in agent_profiles:
        tool_list = ", ".join(f"`{tool}`" for tool in sorted(profile.allowed_tool_names)) if profile.allowed_tool_names else "none"
        description = f"{profile.description} Agent Tools: {tool_list}"
        definitions.append(
            {
                "type": "function",
                "function": {
                    "name": profile.agent_id,
                    "description": description,
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "detailed_task": {
                                "type": "string",
                                "description": "A detailed explanation of the end-to-end task you want this specialized agent to do (in plain english) - continuously negotiate with available agents on the user's behalf to fully and successfully complete the task.",
                            }
                        },
                        "required": ["detailed_task"],
                    },
                },
            }
        )
    return definitions


def get_agent_cache_suffix(profile: AgentProfile) -> str:
    """Stable suffix to prevent prompt-cache cross-contamination between agent policies."""
    return f"{profile.agent_id}__{_fingerprint_toolset(profile.allowed_tool_names)}"
