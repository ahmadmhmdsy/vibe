#Requires -Version 7.0
<#
  scripts/release-check.ps1 - the one command a maintainer runs before handing
  a build to a user (R5-T10).

  Runs, in order, stopping at the first failure:
    backend    ruff check .        pytest -q
    frontend   eslint              prettier --check    tsc    vitest    vite build
    doctor     python -m vibe doctor

  Writes every command line and its output to artifacts/release-check.txt, and
  exits non-zero at the first failed step - a release check that kept going
  after a red step would hide the first cause behind the noise of the rest.

  Usage:
    pwsh -File scripts/release-check.ps1
    pwsh -File scripts/release-check.ps1 -SkipFrontend
#>
[CmdletBinding()]
param([switch]$SkipFrontend, [int]$StepTimeoutSec = 900)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $repo 'services\vibe'
$frontend = Join-Path $repo 'apps\vibe'
$python = Join-Path $backend '.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$artifactDir = Join-Path $repo 'artifacts'
if (-not (Test-Path $artifactDir)) { New-Item -ItemType Directory -Path $artifactDir | Out-Null }
$artifact = Join-Path $artifactDir 'release-check.txt'
$script:stepTimeout = $StepTimeoutSec

$pnpmCmd = Get-Command pnpm.cmd -ErrorAction SilentlyContinue
if (-not $pnpmCmd) { $pnpmCmd = Get-Command pnpm -ErrorAction SilentlyContinue }
$pnpm = if ($pnpmCmd) { $pnpmCmd.Source } else { 'pnpm' }

# [Console]::Out rather than Write-Output on purpose: Write-Output writes to the
# pipeline, so a helper called inside a value-returning function would add its
# text to that function's return value. That is not a style preference - the
# first version of this script checked "if (Step ...)" and every call returned a
# non-empty array of log lines, which is always truthy, so it reported PASS for
# a pytest run that had died during collection.
function Say([string]$text) {
  [Console]::Out.WriteLine($text)
  Add-Content -LiteralPath $artifact -Value $text -Encoding UTF8
}

# Start-Process -Wait -PassThru and $proc.ExitCode, not $LASTEXITCODE: reading
# the automatic variable after a pipeline proved unreliable here (it reported 0
# for a pytest that exited 2), and a release check whose exit code is guessed is
# worse than no release check.
function Invoke-Capture([string]$file, [string[]]$cmdArgs, [string]$workdir) {
  $stdout = [System.IO.Path]::GetTempFileName()
  $stderr = [System.IO.Path]::GetTempFileName()
  $clock = [System.Diagnostics.Stopwatch]::StartNew()
  # No -Wait on purpose. -Wait also waits for the redirected pipes to reach EOF,
  # and a grandchild that inherited them keeps them open: the backend suite leaks
  # a vite dev server, so -Wait turned a green 41s pytest step into a 24 minute
  # hang (see artifacts/release-check.txt, "backend pytest (exit 0, 1443.2s)").
  # Waiting on the process object is bounded and does not depend on the pipes.
  $proc = Start-Process -FilePath $file -ArgumentList $cmdArgs -WorkingDirectory $workdir -PassThru -NoNewWindow -RedirectStandardOutput $stdout -RedirectStandardError $stderr
  $timedOut = -not $proc.WaitForExit($script:stepTimeout * 1000)
  if (-not $timedOut) { $proc.WaitForExit() }
  $clock.Stop()
  if ($timedOut) {
    foreach ($kid in (@(Get-Kids -parent $proc.Id) | Sort-Object -Descending)) { Stop-Process -Id $kid -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
    Start-Sleep -Seconds 1
  }
  # The output readers write as data arrives; give them a moment to flush.
  Start-Sleep -Milliseconds 400
  $out = ''
  if (Test-Path $stdout) { $out = (Get-Content -LiteralPath $stdout -Raw -ErrorAction SilentlyContinue) }
  $err = ''
  if (Test-Path $stderr) { $err = (Get-Content -LiteralPath $stderr -Raw -ErrorAction SilentlyContinue) }
  Remove-Item -LiteralPath $stdout, $stderr -Force -ErrorAction SilentlyContinue
  $code = $proc.ExitCode
  $note = ''
  if ($timedOut) {
    $code = 124
    $note = '[release-check] step exceeded ' + $script:stepTimeout + 's and its process tree was stopped' + [Environment]::NewLine
  }
  return @{ code = $code; text = ($note + $out + [Environment]::NewLine + $err); seconds = [Math]::Round($clock.Elapsed.TotalSeconds, 1) }
}

# Every process below $parent, so a timed-out step can be stopped as a tree
# rather than leaving its children behind.
function Get-Kids([int]$parent) {
  $all = @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)
  $kids = @()
  $queue = @($parent)
  while ($queue.Count -gt 0) {
    $cur = $queue[0]
    if ($queue.Count -gt 1) { $queue = $queue[1..($queue.Count - 1)] } else { $queue = @() }
    foreach ($p in $all) {
      if ($p.ParentProcessId -eq $cur) { $kids += $p.ProcessId; $queue += $p.ProcessId }
    }
  }
  return $kids
}

function Step([string]$name, [string]$file, [string[]]$cmdArgs, [string]$workdir) {
  Say ''
  Say ('$ ' + $file + ' ' + ($cmdArgs -join ' '))
  Say ('  (' + $workdir + ')')
  $result = Invoke-Capture $file $cmdArgs $workdir
  # The caller reads the code through this variable rather than the return
  # value: Step returns a boolean, and "if (Step ...)" on a returned exit code
  # would read 0 as success and 2 as failure by accident.
  $script:lastCode = $result.code
  foreach ($line in ($result.text -split "[\r\n]+")) {
    if ($line.Trim()) { Say ('    ' + $line.TrimEnd()) }
  }
  if ($result.code -eq 0) {
    Say ('  PASS  ' + $name + '  (exit 0, ' + $result.seconds + 's)')
    return $true
  }
  Say ('  FAIL  ' + $name + '  (exit ' + $result.code + ', ' + $result.seconds + 's)')
  return $false
}

Say ('=== release-check.ps1  ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ===')
Say ('repo:       ' + $repo)
Say ('python:     ' + $python)
Say ('pnpm:       ' + $pnpm)
Say ('engine:     ' + $PSVersionTable.PSVersion.ToString())
Say ('frontend:   ' + $(if ($SkipFrontend) { 'SKIPPED by -SkipFrontend' } else { 'included' }))

$steps = @(
  @{ name = 'backend ruff';      file = $python; args = @('-m', 'ruff', 'check', '.'); cwd = $backend }
  @{ name = 'backend pytest';    file = $python; args = @('-m', 'pytest', '-q');       cwd = $backend }
)
if (-not $SkipFrontend) {
  $steps += @{ name = 'frontend eslint';       file = $pnpm; args = @('run', 'lint');         cwd = $frontend }
  $steps += @{ name = 'frontend prettier';     file = $pnpm; args = @('run', 'format:check'); cwd = $frontend }
  $steps += @{ name = 'frontend typecheck';    file = $pnpm; args = @('run', 'typecheck');    cwd = $frontend }
  $steps += @{ name = 'frontend vitest';       file = $pnpm; args = @('run', 'test');         cwd = $frontend }
  $steps += @{ name = 'frontend vite build';   file = $pnpm; args = @('run', 'build');        cwd = $frontend }
}
$steps += @{ name = 'doctor'; file = $python; args = @('-m', 'vibe', 'doctor'); cwd = $repo }

$failed = $null
$passed = 0
$codes = @()
$script:lastCode = $null
foreach ($step in $steps) {
  $ok = Step $step.name $step.file $step.args $step.cwd
  $codes += ($step.name + '=' + $script:lastCode)
  if ($ok) { $passed++ }
  else { $failed = $step.name; break }
}

Say ''
Say ('step exit codes: ' + ($codes -join ', '))
if ($null -eq $failed) {
  Say ('RESULT: PASS - ' + $passed + '/' + $steps.Count + ' step(s) green, every step exited 0')
  exit 0
}
Say ('RESULT: FAIL - ' + $passed + '/' + $steps.Count + ' step(s) green; the first failing step was ' + $failed + ' (exit ' + $script:lastCode + ')')
exit 1
