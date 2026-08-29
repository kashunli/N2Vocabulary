[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "Run this script from inside the N2Vocabulary Git repository."
}

$hooksDirectory = Join-Path $repoRoot ".githooks"
$preCommitHook = Join-Path $hooksDirectory "pre-commit"
if (-not (Test-Path -LiteralPath $preCommitHook -PathType Leaf)) {
    throw "Expected versioned pre-commit hook was not found at $preCommitHook."
}

Set-Location $repoRoot
git config core.hooksPath .githooks

Write-Host "Installed the repository pre-commit hook." -ForegroundColor Green
Write-Host "Git will now run the relevant frontend and/or Rust checks before each commit."
Write-Host "Run .\tools\verify.ps1 -Scope All to run the complete gate manually."
