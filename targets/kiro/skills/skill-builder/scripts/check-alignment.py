#!/usr/bin/env python3
"""List agent tool sets and prompt domains for alignment checking."""
import argparse
import glob
import json
import os
import re


def scan_agents(agents_dir):
    """Return {agent_name: [tool_names]} from agent JSON configs."""
    results = {}
    for path in sorted(glob.glob(os.path.join(agents_dir, "*.json"))):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path) as f:
                data = json.load(f)
            tools = []
            for t in data.get("tools", []):
                if isinstance(t, str):
                    tools.append(t)
                elif isinstance(t, dict) and "name" in t:
                    tools.append(t["name"])
            results[name] = tools
        except (json.JSONDecodeError, OSError):
            results[name] = ["<parse error>"]
    return results


def scan_prompts(prompts_dir):
    """Return {prompt_name: first_heading_or_line} from prompt .md files."""
    results = {}
    for path in sorted(glob.glob(os.path.join(prompts_dir, "*.md"))):
        name = os.path.splitext(os.path.basename(path))[0]
        try:
            with open(path) as f:
                for line in f:
                    line = line.strip()
                    if line:
                        # Strip leading # for headings
                        results[name] = re.sub(r'^#+\s*', '', line)
                        break
                else:
                    results[name] = "<empty>"
        except OSError:
            results[name] = "<read error>"
    return results


def main():
    parser = argparse.ArgumentParser(
        description="List agent tool sets and prompt domains.")
    parser.add_argument("--agents-dir",
                        default=os.path.expanduser("~/.kiro/agents"),
                        help="Path to agents directory")
    parser.add_argument("--prompts-dir",
                        default=os.path.expanduser("~/.kiro/prompts"),
                        help="Path to prompts directory")
    args = parser.parse_args()

    agents = scan_agents(args.agents_dir)
    prompts = scan_prompts(args.prompts_dir)

    if agents:
        print("Agents:")
        for name, tools in agents.items():
            print(f"  {name}: {', '.join(tools) if tools else '<no tools>'}")
    else:
        print("Agents: none found")

    if prompts:
        print("\nPrompts:")
        for name, domain in prompts.items():
            print(f"  {name}: {domain}")
    else:
        print("\nPrompts: none found")


if __name__ == "__main__":
    main()
