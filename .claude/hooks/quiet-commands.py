#!/usr/bin/env python3
"""PreToolUse hook: refuse Bash commands that would dump unbounded output into the conversation.

Every token in the conversation is re-read on each later turn, so one page or log
dump keeps costing for the rest of the session. The hook blocks the usual culprits
and tells the agent how to retry. Exit code 2 blocks the call and shows stderr.
"""
import json
import re
import sys

BOUNDED = re.compile(r"\|\s*(head|tail|cut|grep|egrep|awk|sed|jq|wc|sort|uniq|python3?|node)\b|\s>\s*\S|\s>>\s*\S|-o\s+\S|--output\s+\S|\s-I\b|--head\b|-w\s+['\"]")


def segments(command):
    """Split on ;, && and newlines so each command is judged with its own pipe."""
    return [part for part in re.split(r"\n|;|&&|\|\|", command) if part.strip()]


def check(command):
    for part in segments(command):
        if re.search(r"(^|\s)curl\s", part) and not BOUNDED.search(part):
            return "curl prints the whole response. Add `-o /dev/null -w '%{http_code}\\n'`, `-I`, or pipe to `head -c 2000` / `grep -o`."
        if re.search(r"\bgh run view\b.*--log", part) and not BOUNDED.search(part):
            return "Log dumps are huge. Pipe `gh run view --log-failed` through `grep -E 'FAILED|Error|assert' | head -20`."
        if re.search(r"\bgh api\b", part) and "graphql" not in part and not re.search(r"(-q|--jq)\s", part) and not BOUNDED.search(part):
            return "Add `-q '<jq filter>'` or pipe `gh api` to `head -c 2000`."
        if re.search(r"\bjournalctl\b", part) and not re.search(r"(-n\s*\d+|--lines)", part) and not BOUNDED.search(part):
            return "Add `-n 30` or pipe journalctl to `tail -30` / `grep`."
    return None


def main():
    try:
        data = json.load(sys.stdin)
    except ValueError:
        return 0
    if data.get("tool_name") != "Bash":
        return 0
    reason = check((data.get("tool_input") or {}).get("command") or "")
    if reason:
        print("Blocked by .claude/hooks/quiet-commands.py: " + reason, file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
