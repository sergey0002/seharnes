# Shared agent kit root: .codex (Codex) first, .codex fallback.
function Get-AgentKitDir {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)
    if ($env:AGENT_KIT_DIR) {
        return (Join-Path $RepoRoot $env:AGENT_KIT_DIR.TrimStart('/', '\'))
    }
    foreach ($name in @('.codex', '.codex')) {
        $dir = Join-Path $RepoRoot $name
        if (Test-Path (Join-Path $dir 'mcp.env.example')) { return $dir }
        if (Test-Path (Join-Path $dir 'config.toml')) { return $dir }
        if (Test-Path (Join-Path $dir 'mcp.json')) { return $dir }
    }
    return (Join-Path $RepoRoot '.codex')
}

function Get-GototaskConfigPath {
    param([Parameter(Mandatory = $true)][string]$RepoRoot)
    $kitConfig = Join-Path (Get-AgentKitDir $RepoRoot) 'skills/task-router/children/gototask/config.json'
    if (Test-Path $kitConfig) { return $kitConfig }
    Join-Path $RepoRoot '.agents/skills/task-router/children/gototask/config.json'
}
