$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$projectRoot = Split-Path -Parent $scriptDir
$bundleRoot = Join-Path $projectRoot "dist\xdts-workstation"

if (Test-Path -LiteralPath $bundleRoot) {
    Remove-Item -LiteralPath $bundleRoot -Recurse -Force
}

$directories = @(
    $bundleRoot,
    (Join-Path $bundleRoot "core"),
    (Join-Path $bundleRoot "deploy"),
    (Join-Path $bundleRoot "docs\review"),
    (Join-Path $bundleRoot "docs\user"),
    (Join-Path $bundleRoot "docs\operations"),
    (Join-Path $bundleRoot "services"),
    (Join-Path $bundleRoot "ui")
)

foreach ($directory in $directories) {
    New-Item -ItemType Directory -Path $directory -Force | Out-Null
}

$rootFiles = @(
    "main.py"
)

foreach ($file in $rootFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination (Join-Path $bundleRoot $file)
}

$packageFiles = @(
    "core\__init__.py",
    "core\auth.py",
    "core\config.py",
    "core\database.py",
    "core\logger.py",
    "services\__init__.py",
    "services\admin.py",
    "services\auth.py",
    "services\documents.py",
    "services\models.py",
    "services\reporting.py",
    "services\support.py",
    "ui\__init__.py",
    "ui\gui.py",
    "ui\gui_dialogs.py"
)

foreach ($file in $packageFiles) {
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
    "docs\review\xdts_first_release_handoff.md",
    "docs\review\xdts_system_walkthrough.md",
    "docs\user\xdts_admin_guide.md",
    "docs\user\xdts_user_guide.md",
    "docs\operations\xdts_operator_failure_guide.md",
    "docs\operations\xdts_release_notes_first_release.md",
    "docs\operations\xdts_rollout_plan.md",
    "docs\operations\xdts_deployment_guide.md"
)

foreach ($file in $docFiles) {
    Copy-Item -LiteralPath (Join-Path $projectRoot $file) -Destination (Join-Path $bundleRoot $file)
}

New-Item -ItemType Directory -Path (Join-Path $bundleRoot "logs") -Force | Out-Null
New-Item -ItemType Directory -Path (Join-Path $bundleRoot "backups") -Force | Out-Null

Write-Output "Workstation bundle created at: $bundleRoot"
