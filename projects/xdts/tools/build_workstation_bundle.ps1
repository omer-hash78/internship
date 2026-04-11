$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$bundleRoot = Join-Path $projectRoot "dist\xdts-workstation"

if (Test-Path -LiteralPath $bundleRoot) {
    Remove-Item -LiteralPath $bundleRoot -Recurse -Force
}

$directories = @(
    $bundleRoot,
    (Join-Path $bundleRoot "deploy"),
    (Join-Path $bundleRoot "docs\review"),
    (Join-Path $bundleRoot "docs\rollout")
)

foreach ($directory in $directories) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$rootFiles = @(
    "auth.py",
    "database.py",
    "gui.py",
    "logger.py",
    "main.py",
    "services.py"
)

foreach ($file in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination (Join-Path $bundleRoot $file)
}

$deployFiles = @(
    "launch_xdts.cmd",
    "initialize_admin.cmd",
    "verify_audit.cmd",
    "xdts_runtime.template.cmd"
)

foreach ($file in $deployFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot "deploy\$file") -Destination (Join-Path $bundleRoot "deploy\$file")
}

$docFiles = @(
    "docs\review\implementation_plan_03_status.md",
    "docs\review\xdts_gui_smoke_checklist.md",
    "docs\rollout\xdts_admin_guide.md",
    "docs\rollout\xdts_operator_failure_guide.md",
    "docs\rollout\xdts_release_notes_first_release.md",
    "docs\rollout\xdts_rollout_plan.md",
    "docs\rollout\xdts_user_guide.md"
)

foreach ($file in $docFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination (Join-Path $bundleRoot $file)
}

New-Item -ItemType Directory -Path (Join-Path $bundleRoot "logs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundleRoot "backups") -Force | Out-Null

Write-Output "Workstation bundle created at: $bundleRoot"
