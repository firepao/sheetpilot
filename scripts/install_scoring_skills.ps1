$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false)
$OutputEncoding = [System.Text.UTF8Encoding]::new($false)

$sourceRoot = "D:\bitexcel\SheetPilot\skills"
$installations = @(
    @{
        Name = "sheetpilot-run-review"
        TargetRoot = "C:\Users\nine\.codex\skills"
    },
    @{
        Name = "sheetpilot-run-scorer"
        TargetRoot = "C:\Users\nine\.codex\skills"
    },
    @{
        Name = "sheetpilot-excel-agent"
        TargetRoot = "C:\Users\nine\bit-Agent\skills"
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
