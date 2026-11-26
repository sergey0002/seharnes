# Export next steps

Target: `/home/newuser/projects/seharnes`
Profile: `developer`
Mode: `update`

1. Fill secrets: `.cursor/mcp.env` and `.codex/mcp.env` (created from the example).
2. Verify the harness: `python3 .agents/skills/harness-router/children/harness-core/scripts/harness_cli.py doctor`.
3. Re-run view sync after any canon edit:
   `bash .agents/skills/harness-router/children/environment-sync/scripts/sync-agent-views.sh --local-only`
4. Configure MCP, ports and indexes:
   `python3 .agents/skills/harness-router/children/project-setup/scripts/onboard-project.py --root . --check`
5. Fill `.doc/architecture/index.md` and project documentation with the project-doc skill.
6. Remove `EXPORT_NEXT_STEPS.md` when the target is configured.
