[CmdletBinding()]
param(
    [ValidateSet("Changed", "Frontend", "Rust", "All")]
    [string]$Scope = "Changed"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = (git rev-parse --show-toplevel).Trim()
if (-not $repoRoot) {
    throw "Run this script from inside the N2Vocabulary Git repository."
}

Set-Location $repoRoot
$frontendDirectory = Join-Path $repoRoot "wordService\frontend"
$generatedFrontendDirectory = "wordService/static/react-rail"

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Label,

        [Parameter(Mandatory = $true)]
        [string]$FilePath,

        [Parameter(Mandatory = $false)]
        [string[]]$Arguments = @(),

        [Parameter(Mandatory = $false)]
        [string]$WorkingDirectory = $repoRoot
    )

    Write-Host "`n==> $Label" -ForegroundColor Cyan
    Push-Location $WorkingDirectory
    try {
        & $FilePath @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Label failed with exit code $LASTEXITCODE."
        }
    }
    finally {
        Pop-Location
    }
}

function Get-StagedPath {
    @(
        git diff --cached --name-only --diff-filter=ACMR
    )
}

function Test-FrontendChange {
    param([string]$Path)

    return $Path -like "wordService/frontend/*" -or
        $Path -like "$generatedFrontendDirectory/*"
}

function Test-RustChange {
    param([string]$Path)

    return $Path -match '^wordService/(src|tests|benches|examples)/.*\.rs$' -or
        $Path -match '^wordService/(Cargo\.toml|Cargo\.lock|build\.rs|rust-toolchain.*)$' -or
        $Path -like "wordService/.cargo/*"
}

function Assert-GeneratedFrontendIsClean {
    $unstagedGeneratedPaths = @(
        git diff --name-only -- $generatedFrontendDirectory
    )

    if ($unstagedGeneratedPaths.Count -gt 0) {
        $paths = $unstagedGeneratedPaths -join ", "
        throw @"
The generated frontend assets already have unstaged changes: $paths

The verifier will not overwrite them. Stage the rebuilt assets, or inspect and
resolve those changes first, then run the verifier again.
"@
    }
}

function Invoke-FrontendVerification {
    Assert-GeneratedFrontendIsClean

    Invoke-CheckedCommand `
        -Label "Install locked frontend dependencies" `
        -FilePath "pnpm" `
        -Arguments @("install", "--frozen-lockfile") `
        -WorkingDirectory $frontendDirectory

    Invoke-CheckedCommand `
        -Label "Run frontend tests" `
        -FilePath "pnpm" `
        -Arguments @("test") `
        -WorkingDirectory $frontendDirectory

    Invoke-CheckedCommand `
        -Label "Type-check frontend" `
        -FilePath "pnpm" `
        -Arguments @("typecheck") `
        -WorkingDirectory $frontendDirectory

    Invoke-CheckedCommand `
        -Label "Build frontend" `
        -FilePath "pnpm" `
        -Arguments @("build") `
        -WorkingDirectory $frontendDirectory

    $unstagedGeneratedPaths = @(
        git diff --name-only -- $generatedFrontendDirectory
    )
    if ($unstagedGeneratedPaths.Count -gt 0) {
        $paths = $unstagedGeneratedPaths -join ", "
        throw @"
The frontend build changed generated assets that are not staged: $paths

Review the generated output and stage it with the corresponding frontend
source change. This is the same stale-asset protection used by CI.
"@
    }
}

function Invoke-RustVerification {
    Invoke-CheckedCommand `
        -Label "Check Rust formatting" `
        -FilePath "cargo" `
        -Arguments @("fmt", "--manifest-path", "wordService/Cargo.toml", "--all", "--", "--check")

    Invoke-CheckedCommand `
        -Label "Run strict Rust Clippy" `
        -FilePath "cargo" `
        -Arguments @("clippy", "--manifest-path", "wordService/Cargo.toml", "--all-targets", "--all-features", "--", "-D", "warnings")

    Invoke-CheckedCommand `
        -Label "Run Rust tests" `
        -FilePath "cargo" `
        -Arguments @("test", "--manifest-path", "wordService/Cargo.toml")
}

$runFrontend = $false
$runRust = $false

switch ($Scope) {
    "Frontend" {
        $runFrontend = $true
    }
    "Rust" {
        $runRust = $true
    }
    "All" {
        $runFrontend = $true
        $runRust = $true
    }
    "Changed" {
        $stagedPaths = @(Get-StagedPath)
        $runFrontend = @($stagedPaths | Where-Object { Test-FrontendChange $_ }).Count -gt 0
        $runRust = @($stagedPaths | Where-Object { Test-RustChange $_ }).Count -gt 0

        if ($stagedPaths.Count -eq 0) {
            Write-Host "No staged files found; nothing to verify for -Scope Changed." -ForegroundColor Yellow
        }
    }
}

if (-not $runFrontend -and -not $runRust) {
    Write-Host "No frontend or Rust checks selected." -ForegroundColor Yellow
    exit 0
}

if ($runFrontend) {
    Invoke-FrontendVerification
}

if ($runRust) {
    Invoke-RustVerification
}

Write-Host "`nVerification passed for scope: $Scope" -ForegroundColor Green
