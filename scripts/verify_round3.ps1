[CmdletBinding()]
param(
    [switch]$SkipBackend,
    [switch]$SkipFrontend,
    [switch]$SkipE2E,
    [switch]$SkipAndroid,
    [switch]$SkipCodeGraph
)

$ErrorActionPreference = "Stop"

$RepoRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$BackendDir = Join-Path $RepoRoot "backend"
$FrontendDir = Join-Path $RepoRoot "frontend"
$AndroidDir = Join-Path $RepoRoot "android"
$PytestTmp = Join-Path $RepoRoot ".pytest-tmp"
$BackendPytestTmp = Join-Path $PytestTmp "backend-basetemp"
$GradleHome = Join-Path $RepoRoot ".gradle-ascii"
$DefaultJavaHome = "C:\Program Files\Android\Android Studio\jbr"

function Invoke-Round3Step {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][scriptblock]$Script
    )

    Write-Host ""
    Write-Host "==> $Name" -ForegroundColor Cyan
    $startedAt = Get-Date
    & $Script
    $duration = [int]((Get-Date) - $startedAt).TotalSeconds
    Write-Host "OK: $Name (${duration}s)" -ForegroundColor Green
}

function Test-CommandAvailable {
    param([Parameter(Mandatory = $true)][string]$Name)
    return [bool](Get-Command $Name -ErrorAction SilentlyContinue)
}

function Invoke-NativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Command failed with exit code ${LASTEXITCODE}: $FilePath $($Arguments -join ' ')"
    }
}

New-Item -ItemType Directory -Force -Path $PytestTmp | Out-Null
New-Item -ItemType Directory -Force -Path $GradleHome | Out-Null

$env:TMP = (Resolve-Path $PytestTmp).Path
$env:TEMP = (Resolve-Path $PytestTmp).Path

if (-not $SkipBackend) {
    Invoke-Round3Step "Backend full pytest" {
        Push-Location $BackendDir
        try {
            Invoke-NativeCommand "python" "-m" "pytest" "-q" "--basetemp" $BackendPytestTmp
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipFrontend) {
    Invoke-Round3Step "Frontend production build" {
        Push-Location $FrontendDir
        try {
            Invoke-NativeCommand "npm.cmd" "run" "build"
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipE2E) {
    Invoke-Round3Step "Web round3 Playwright smoke" {
        Push-Location $FrontendDir
        try {
            Invoke-NativeCommand "npx.cmd" "playwright" "install" "chromium"
            Invoke-NativeCommand "npm.cmd" "run" "test:e2e:round3"
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipAndroid) {
    Invoke-Round3Step "Android unit tests and debug build" {
        if (Test-Path $DefaultJavaHome) {
            $env:JAVA_HOME = $DefaultJavaHome
        }
        if (-not $env:JAVA_HOME) {
            throw "JAVA_HOME is not set and Android Studio JBR was not found at $DefaultJavaHome"
        }
        $env:GRADLE_USER_HOME = (Resolve-Path $GradleHome).Path
        $env:Path = "$env:JAVA_HOME\bin;$env:Path"

        Push-Location $AndroidDir
        try {
            Invoke-NativeCommand ".\gradlew.bat" ":app:testDebugUnitTest" ":app:assembleDebug" "--no-daemon"
        }
        finally {
            Pop-Location
        }
    }
}

if (-not $SkipCodeGraph) {
    Invoke-Round3Step "CodeGraph status if available" {
        if (Test-CommandAvailable "codegraph") {
            Push-Location $RepoRoot
            try {
                Invoke-NativeCommand "codegraph" "sync" "."
                Invoke-NativeCommand "codegraph" "status" "."
            }
            finally {
                Pop-Location
            }
        }
        else {
            Write-Host "SKIP: codegraph command not found in PATH" -ForegroundColor Yellow
        }
    }
}

Write-Host ""
Write-Host "Round3 verification finished." -ForegroundColor Green
