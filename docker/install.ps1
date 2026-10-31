# LADO's Docker installer for Windows, in PowerShell (5.1 or 7), with no administrator
# rights:
#
#   irm https://github.com/ladohq/lado/releases/latest/download/install.ps1 | iex
#
# LADO runs in Ubuntu inside WSL 2, with Docker Desktop's Docker: this script checks Docker
# Desktop (starting it when it is not running), finds Ubuntu in WSL (offering to install
# it), checks that Docker answers there, then runs its release's install.sh in Ubuntu, which
# asks its questions here and opens LADO in Windows' browser. Running it again updates LADO.
# The switches -Yes, -Phone and -NoPhone are install.sh's --yes, --phone and --no-phone:
#
#   & ([scriptblock]::Create((irm https://github.com/ladohq/lado/releases/latest/download/install.ps1))) -Yes
#
# The guide: https://github.com/ladohq/lado/blob/main/docs/install.md#docker-on-windows. The release
# stamps its version below (scripts/stamp_installers.py); the repository's copy has none.
param([switch]$Yes, [switch]$Phone, [switch]$NoPhone)

Set-StrictMode -Version 2.0
$ErrorActionPreference = 'Stop'

$LadoVersion = ''

$Desktop = 'https://www.docker.com/products/docker-desktop/'
$Again = 'irm https://github.com/ladohq/lado/releases/latest/download/install.ps1 | iex'
$Arrow = [char]0x2192
$script:ExitCode = 0
$script:Output = @()

function Stop-Install([string]$Message) {
    throw "lado install: $Message"
}

# Runs a program quietly: its output in $script:Output, whether it succeeded. Its stderr is
# dropped with 'Continue', since Windows PowerShell 5.1 turns a redirected native stderr
# line into an error, which 'Stop' would throw.
function Test-Native([string]$Exe, [string[]]$Arguments) {
    $old = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    try {
        $script:Output = @(& $Exe @Arguments 2>$null)
        return ($LASTEXITCODE -eq 0)
    } finally {
        $ErrorActionPreference = $old
    }
}

function Assert-Docker {
    if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
        Stop-Install "Docker Desktop is not installed: get it from $Desktop, start it, then run this again"
    }
    if (Test-Native 'docker' @('info')) { return }
    $Exe = Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'
    if (-not (Test-Path $Exe)) {
        Stop-Install "Docker does not answer and Docker Desktop is not found: install it from $Desktop, start it, then run this again"
    }
    Write-Host 'Waiting for Docker Desktop to start (up to 2 minutes)...'
    Start-Process $Exe
    $deadline = (Get-Date).AddSeconds(120)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 2
        if (Test-Native 'docker' @('info')) { return }
    }
    Stop-Install 'Docker Desktop did not answer in 2 minutes: start it from the Start menu, wait until it runs, then run this again'
}

# The WSL distribution LADO runs in: the first Ubuntu, never Docker Desktop's own.
function Find-Ubuntu {
    if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
        Stop-Install 'WSL is missing, and Docker Desktop needs WSL 2: run wsl --install in an administrator PowerShell, restart, then run this again'
    }
    # wsl -l -q answers in UTF-16, with NULs between the characters otherwise.
    $encoding = [Console]::OutputEncoding
    [Console]::OutputEncoding = [System.Text.Encoding]::Unicode
    try {
        $listed = Test-Native 'wsl.exe' @('-l', '-q')
    } finally {
        [Console]::OutputEncoding = $encoding
    }
    if (-not $listed) {
        Stop-Install 'WSL does not answer, and Docker Desktop needs WSL 2: run wsl --install in an administrator PowerShell, restart, then run this again'
    }
    $names = @($script:Output | ForEach-Object { ([string]$_ -replace "`0", '').Trim() })
    $found = @($names | Where-Object { $_ -notlike 'docker-desktop*' -and $_ -like 'Ubuntu*' })
    if ($found.Count -gt 0) { return $found[0] }
    return $null
}

function Install-Ubuntu {
    Write-Host 'LADO runs in Ubuntu inside WSL, which this computer does not have yet.'
    Write-Host 'wsl --install -d Ubuntu installs it; it may ask for administrator rights and a restart.'
    $answer = 'n'
    if (-not $Yes) { $answer = Read-Host 'Install Ubuntu now? [y/N]' }
    if ($answer -notmatch '^[yY]') {
        Stop-Install "LADO needs Ubuntu in WSL: install it (wsl --install -d Ubuntu), open it once, then run this again: $Again"
    }
    & wsl.exe --install -d Ubuntu
    Write-Host ''
    Write-Host 'When Ubuntu is installed (after a restart, if Windows asks for one), open Ubuntu from the Start menu once, make its user, then run the same command again:'
    Write-Host "  $Again"
}

function Install-Lado {
    if (-not $LadoVersion) {
        Stop-Install "this install.ps1 carries no version: take the release's (https://github.com/ladohq/lado/releases/latest/download/install.ps1)"
    }
    Assert-Docker
    $Distro = Find-Ubuntu
    if (-not $Distro) {
        Install-Ubuntu
        return
    }
    if (-not (Test-Native 'wsl.exe' @('-d', $Distro, '--', 'docker', 'version', '--format', '{{.Server.Version}}'))) {
        Stop-Install "Docker does not answer in $Distro`: in Docker Desktop turn on Settings $Arrow Resources $Arrow WSL integration for $Distro, apply, then run this again"
    }
    $Flags = @()
    if ($Yes) { $Flags += '--yes' }
    if ($Phone) { $Flags += '--phone' }
    if ($NoPhone) { $Flags += '--no-phone' }
    $Url = "https://github.com/ladohq/lado/releases/download/v$LadoVersion/install.sh"
    $Line = "curl -fsSL '$Url' | sh -s -- $($Flags -join ' ')"
    Write-Host "Installing LADO $LadoVersion in $Distro..."
    # Not captured: install.sh asks its questions on this console.
    & wsl.exe -d $Distro --cd '~' -- sh -c $Line
    $script:ExitCode = $LASTEXITCODE
}

try {
    Install-Lado
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    $script:ExitCode = 1
}
$global:LASTEXITCODE = $script:ExitCode
# Under irm | iex an exit would close this PowerShell window: only a file run exits.
if ($PSCommandPath) { exit $script:ExitCode }
