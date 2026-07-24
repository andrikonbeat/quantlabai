"""Agent CLI command handlers.

Implements: agent memory inspect, agent memory query.
"""

from __future__ import annotations

import argparse
import sys
import yaml
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ──────────────────────────────────────────────────────────────────────────────
# Output formatting
# ──────────────────────────────────────────────────────────────────────────────

def print_json(data: dict | list, pretty: bool = True) -> None:
    """Print JSON to stdout."""
    import json
    if pretty:
        print(json.dumps(data, indent=2, default=str))
    else:
        print(json.dumps(data, default=str))


def print_human(message: str, *, error: bool = False) -> None:
    """Print human-readable message."""
    if error:
        print(message, file=sys.stderr)
    else:
        print(message)


def print_error(message: str) -> None:
    """Print error message to stderr."""
    print(f"Error: {message}", file=sys.stderr)


def print_table(headers: list[str], rows: list[list[str]]) -> None:
    """Print table to stdout."""
    if not rows:
        print_human("(no data)")
        return

    # Calculate column widths
    col_widths = []
    for i in range(len(headers)):
        max_width = len(str(headers[i]))
        for row in rows:
            if i < len(row):
                max_width = max(max_width, len(str(row[i])))
        col_widths.append(max_width + 2)  # padding

    # Print header
    header_str = "".join(str(h).ljust(w) for h, w in zip(headers, col_widths))
    print_human(header_str)
    print_human("-" * len(header_str))

    # Print rows
    for row in rows:
        row_str = "".join(
            (str(cell) if i < len(row) else "").ljust(w)
            for i, (cell, w) in enumerate(zip(row, col_widths))
        )
        print_human(row_str)


# ──────────────────────────────────────────────────────────────────────────────
# Agent Memory Commands
# ──────────────────────────────────────────────────────────────────────────────

async def cmd_agent_memory_inspect(args: argparse.Namespace) -> int:
    """Inspect agent memory for a specific agent and campaign."""
    from quantlab.agents.memory import AgentMemoryManager
    
    try:
        memory_manager = AgentMemoryManager(
            knowledge_root=args.knowledge_root
        )
        
        # Load memory from Knowledge Lake
        memory = await memory_manager.load_memory(args.agent, args.campaign_id)
        
        if memory is None:
            print_human(f"No memory found for agent '{args.agent}' in campaign '{args.campaign_id}'")
            return 1
            
        if args.json:
            print_json(memory)
        else:
            print_human(f"Agent Memory: {args.agent}")
            print_human(f"Campaign: {args.campaign_id}")
            print_human("-" * 40)
            
            if isinstance(memory, list):
                for i, decision in enumerate(memory, 1):
                    print_human(f"Decision {i}:")
                    print_human(f"  Timestamp: {decision.get('timestamp', 'unknown')}")
                    print_human(f"  Type: {decision.get('type', 'unknown')}")
                    print_human(f"  Data: {yaml.dump(decision.get('data', {}), default_flow_style=False)}")
                    print_human("")
            elif isinstance(memory, dict):
                print_human(yaml.dump(memory, default_flow_style=False))
            else:
                print_human(str(memory))
                
        return 0
        
    except Exception as e:
        print_error(f"Failed to inspect agent memory: {e}")
        return 1


async def cmd_agent_memory_query(args: argparse.Namespace) -> int:
    """Query agent memory across agents and campaigns."""
    from quantlab.agents.memory import AgentMemoryManager
    
    try:
        memory_manager = AgentMemoryManager(
            knowledge_root=args.knowledge_root
        )
        
        # Query cross-agent memory
        results = await memory_manager.query_cross_agent(args.pattern)
        
        if not results:
            print_human(f"No memories found matching pattern: '{args.pattern}'")
            return 0
            
        if args.json:
            print_json(results)
        else:
            print_human(f"Agent Memory Query Results for pattern: '{args.pattern}'")
            print_human("=" * 60)
            
            total_matches = 0
            for agent_name, memories in results.items():
                print_human(f"\nAgent: {agent_name} ({len(memories)} matches)")
                print_human("-" * 40)
                
                for i, memory in enumerate(memories, 1):
                    print_human(f"  Match {i}:")
                    print_human(f"    Campaign: {memory.get('campaign_id', 'unknown')}")
                    print_human(f"    Timestamp: {memory.get('timestamp', 'unknown')}")
                    print_human(f"    Type: {memory.get('type', 'unknown')}")
                    
                    # Show a preview of the data
                    data = memory.get('data', {})
                    if isinstance(data, dict) and data:
                        preview = str(data)[:100]
                        if len(str(data)) > 100:
                            preview += "..."
                        print_human(f"    Data Preview: {preview}")
                    else:
                        print_human(f"    Data: {data}")
                    print_human("")
                    
                    total_matches += 1
            
            print_human(f"Total matches: {total_matches}")
                
        return 0
        
    except Exception as e:
        print_error(f"Failed to query agent memory: {e}")
        return 1


async def cmd_agent_memory(args: argparse.Namespace) -> int:
    """Handle agent memory subcommands."""
    # This function is just a dispatcher - the actual work is done in the subcommand functions
    print_error("Agent memory subcommand required. Use 'inspect' or 'query'.")
    return 1


def add_agent_subparser(subparsers: argparse._SubParsersAction) -> None:
    """Add agent subcommands to main parser."""
    p_agent = subparsers.add_parser("agent", help="Agent management and querying")
    agent_sub = p_agent.add_subparsers(dest="agent_cmd", required=True)

    # agent memory
    p_memory = agent_sub.add_parser("memory", help="Query and inspect agent memory")
    memory_sub = p_memory.add_subparsers(dest="memory_cmd", required=True)

    # agent memory inspect
    p_inspect = memory_sub.add_parser("inspect", help="Inspect memory for specific agent/campaign")
    p_inspect.add_argument("agent", help="Agent name (e.g., research-agent, builder-agent)")
    p_inspect.add_argument("campaign_id", help="Campaign ID")
    p_inspect.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_inspect.add_argument("--json", action="store_true", help="Output as JSON")
    p_inspect.set_defaults(func=cmd_agent_memory_inspect)

    # agent memory query
    p_query = memory_sub.add_parser("query", help="Query memory across agents/campaigns")
    p_query.add_argument("pattern", help="Text pattern to search for (case-insensitive)")
    p_query.add_argument("--agent", help="Filter by agent name")
    p_query.add_argument("--campaign", help="Filter by campaign ID")
    p_query.add_argument("--knowledge-root", default="knowledge", help="Knowledge Lake root path")
    p_query.add_argument("--json", action="store_true", help="Output as JSON")
    p_query.set_defaults(func=cmd_agent_memory_query)


def dispatch_agent(args: argparse.Namespace) -> int:
    """Dispatch agent subcommand using async runner."""
    import asyncio

    func = getattr(args, "func", None)
    if func is None:
        print_error("Agent subcommand required. Use 'agent memory inspect' or 'agent memory query'.")
        return 1

    return asyncio.run(func(args))