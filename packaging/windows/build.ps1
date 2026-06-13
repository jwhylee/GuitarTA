$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$distDir = Join-Path $PSScriptRoot "dist"
$zipPath = Join-Path $distDir "GuitarTA-windows.zip"

Push-Location $repoRoot
try {
    flet build windows . --product GuitarTA --bundle-id com.guitarta.app --yes

    New-Item -ItemType Directory -Force $distDir | Out-Null
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    Compress-Archive -Path "build/windows/*" -DestinationPath $zipPath -Force
}
finally {
    Pop-Location
}
