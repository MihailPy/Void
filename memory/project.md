# Project Memory

## Current Version
Void v0.3

## Implemented
- Agent Loop
- Structured JSON output
- Short-term memory
- Medium-term memory
- Self-tools
- Planning
- request_capability
- Skill System
- Capability System

## Skills
- summarize_file
- find_text
- project_report

## Known Problems
- Local model sometimes returns invalid JSON
- Long JSON fields can be truncated

## Decisions
- Self-tools must be pure functions
- Built-in tools are required for filesystem/network access
- Always check existing tools before creating new ones

## Next Tasks
- FastAPI backend
- Web UI
- Browser automation capability
- Improve JSON retry
