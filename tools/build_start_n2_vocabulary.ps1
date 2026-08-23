param(
    [switch]$RegenerateIcon,
    # Local iteration can reuse an already verified frontend install. Release
    # builds keep installation enabled so a clean checkout is always tested.
    [switch]$SkipInstall
)

$ErrorActionPreference = 'Stop'

# Build both processes in release mode. The launcher remains a separate
# executable so the WordService can still be run and diagnosed independently.
# Use a dedicated Cargo target directory: Windows keeps a running .exe locked,
# so rebuilding must not require stopping a currently usable WordService.
$repoRoot = Split-Path -Parent $PSScriptRoot
$manifestPath = Join-Path $repoRoot 'wordService\Cargo.toml'
$buildTargetDirectory = Join-Path $repoRoot 'wordService\target\launcher-release'
$releaseDirectory = Join-Path $buildTargetDirectory 'release'
$launcherSource = Join-Path $releaseDirectory 'start_n2_vocabulary.exe'
$launcherDestination = Join-Path $repoRoot 'Start N2 Vocabulary.exe'
$iconGenerator = Join-Path $repoRoot 'tools\generate_n2_vocabulary_icon.py'
$iconPath = Join-Path $repoRoot 'wordService\assets\n2-vocabulary.ico'
$frontendDirectory = Join-Path $repoRoot 'wordService\frontend'

function Invoke-CheckedCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    Write-Host "==> $Label"
    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE"
    }
}

Push-Location $repoRoot
try {
    Push-Location $frontendDirectory
    try {
        if (-not $SkipInstall) {
            Invoke-CheckedCommand 'Install frontend dependencies' { corepack pnpm install --frozen-lockfile }
        }
        Invoke-CheckedCommand 'Run frontend tests' { pnpm test }
        Invoke-CheckedCommand 'Type-check frontend' { pnpm typecheck }
        Invoke-CheckedCommand 'Build frontend assets' { pnpm build }
    }
    finally {
        Pop-Location
    }

    Invoke-CheckedCommand 'Check Rust formatting' {
        cargo fmt --manifest-path $manifestPath --all -- --check
    }
    Invoke-CheckedCommand 'Run strict Rust linting' {
        cargo clippy --manifest-path $manifestPath --all-targets -- -D warnings
    }
    Invoke-CheckedCommand 'Run Rust tests' { cargo test --manifest-path $manifestPath }

    if ($RegenerateIcon -or -not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
        & python $iconGenerator
        if ($LASTEXITCODE -ne 0) {
            throw "Icon generation failed with exit code $LASTEXITCODE"
        }
    }

    if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
        throw "The Windows icon was not found at $iconPath"
    }

    Invoke-CheckedCommand 'Build WordService and launcher' {
        cargo build --release --target-dir $buildTargetDirectory --manifest-path $manifestPath --bin n2-word-service-rust --bin start_n2_vocabulary
    }
}
finally {
    Pop-Location
}

if (-not (Test-Path -LiteralPath $launcherSource -PathType Leaf)) {
    throw "Cargo completed but the launcher was not found at $launcherSource"
}

# Put the friendly, double-clickable name at the project root. The launcher
# resolves the freshly built service from wordService\target\launcher-release\release,
# so no database or media files are copied or overwritten by this step.
Copy-Item -LiteralPath $launcherSource -Destination $launcherDestination -Force
Write-Host "Created $launcherDestination"
