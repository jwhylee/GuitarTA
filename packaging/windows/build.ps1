$ErrorActionPreference = "Stop"
$env:PYTHONIOENCODING = "utf-8"
$env:PYTHONUTF8 = "1"
$env:PYTHONLEGACYWINDOWSSTDIO = "0"

[Console]::InputEncoding = [System.Text.Encoding]::UTF8
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$OutputEncoding = [System.Text.Encoding]::UTF8
chcp 65001 | Out-Null

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "../..")
$distDir = Join-Path $PSScriptRoot "dist"
$zipPath = Join-Path $distDir "GuitarTA-windows.zip"
$windowsBuildDir = Join-Path $repoRoot "build/windows"

Push-Location $repoRoot
try {
    flet build windows . --product GuitarTA --bundle-id com.guitarta.app --yes

    if (-not (Test-Path $windowsBuildDir)) {
        throw "Windows build output was not created: $windowsBuildDir"
    }

    New-Item -ItemType Directory -Force $distDir | Out-Null
    if (Test-Path $zipPath) {
        Remove-Item $zipPath -Force
    }
    Compress-Archive -Path (Join-Path $windowsBuildDir "*") -DestinationPath $zipPath -Force
}
finally {
    Pop-Location
}
