$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$sourceRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\skills")).Path
$codexSkillsRoot = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME "skills" } else { Join-Path $HOME ".codex\skills" }
$bitAgentSkillsRoot = if ($env:BITAGENT_SKILLS_ROOT) { $env:BITAGENT_SKILLS_ROOT } else { Join-Path $HOME "bit-Agent\skills" }
$installations = @(
    @{
        Name = "sheetpilot-run-review"
        TargetRoot = $codexSkillsRoot
    },
    @{
        Name = "sheetpilot-run-scorer"
        TargetRoot = $codexSkillsRoot
    },
    @{
        Name = "sheetpilot-excel-agent"
        TargetRoot = $bitAgentSkillsRoot
    }
)

foreach ($installation in $installations) {
    $skillName = $installation.Name
    $targetRoot = $installation.TargetRoot
    $source = Join-Path $sourceRoot $skillName
    $target = Join-Path $targetRoot $skillName

    if (-not (Test-Path -LiteralPath (Join-Path $source "SKILL.md") -PathType Leaf)) {
        throw "Source skill is incomplete. Missing: $source\SKILL.md"
    }

    if (Test-Path -LiteralPath $target) {
        Remove-Item -LiteralPath $target -Recurse -Force
    }

    New-Item -ItemType Directory -Path $targetRoot -Force | Out-Null
    Copy-Item -LiteralPath $source -Destination $targetRoot -Recurse -Force
    Write-Host "Installed: $skillName -> $targetRoot"
}

foreach ($installation in $installations) {
    $skillName = $installation.Name
    $targetRoot = $installation.TargetRoot
    $installed = Join-Path $targetRoot "$skillName\SKILL.md"
    if (-not (Test-Path -LiteralPath $installed -PathType Leaf)) {
        throw "Installation verification failed: $installed"
    }
}

Write-Host "SheetPilot skill installation completed."
Write-Host "Restart the Codex task and BitAgent session to load the updated skills."
