param(
    [switch]$RegenerateIcon
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

Push-Location $repoRoot
try {
    if ($RegenerateIcon -or -not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
        & python $iconGenerator
        if ($LASTEXITCODE -ne 0) {
            throw "Icon generation failed with exit code $LASTEXITCODE"
        }
    }

    if (-not (Test-Path -LiteralPath $iconPath -PathType Leaf)) {
        throw "The Windows icon was not found at $iconPath"
    }

    & cargo build --release --target-dir $buildTargetDirectory --manifest-path $manifestPath --bin n2-word-service-rust --bin start_n2_vocabulary
    if ($LASTEXITCODE -ne 0) {
        throw "Cargo failed with exit code $LASTEXITCODE"
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
