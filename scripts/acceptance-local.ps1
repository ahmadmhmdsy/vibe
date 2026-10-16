#Requires -Version 7.0
<#
  scripts/acceptance-local.ps1 - the local acceptance run (R5-T10, run in R7).

  Prints one labeled line per criterion and appends everything to
  artifacts/acceptance-local.txt. Labels are the repository vocabulary:
  PASS / FAIL / SKIPPED / BLOCKED.

  Two rules this script keeps, because the temptation is real:
    1. It skips honestly. Steps 3, 4 and the transcript half of 5 need a
       configured provider. With none, they print SKIPPED with the reason
       instead of inventing a loop that never ran.
    2. It never touches the real workspace. Every server it starts gets
       VIBE_WORKSPACE_DIR pointing under the temp directory, and step 2
       asserts that is where /health says the data lives. Step 6 queries the
       temp database directly, so "it landed here" is measured, not assumed.

  Usage:
    pwsh -File scripts/acceptance-local.ps1
    pwsh -File scripts/acceptance-local.ps1 -FullE2E

  -FullE2E asks the agent for the smallest complete app and records the preview
  URL, which spends the user's provider credits. Without it, step 3 asks for a
  single file - also a paid call, but a tiny one.
#>
[CmdletBinding()]
param(
  [int]$Port = 7411,
  [int]$NoProviderPort = 7412,
  [switch]$FullE2E,
  [string]$Workspace = (Join-Path $env:TEMP 'vibe-acceptance'),
  [string]$NoProviderWorkspace = (Join-Path $env:TEMP 'vibe-acceptance-noprovider')
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'

$repo = Split-Path -Parent $PSScriptRoot
$python = Join-Path $repo 'services\vibe\.venv\Scripts\python.exe'
if (-not (Test-Path $python)) { $python = 'python' }
$artifactDir = Join-Path $repo 'artifacts'
if (-not (Test-Path $artifactDir)) { New-Item -ItemType Directory -Path $artifactDir | Out-Null }
$artifact = Join-Path $artifactDir 'acceptance-local.txt'

$script:Failures = 0
$script:Skips = 0
$script:Blocked = 0
$script:Server = $null
$script:Server2 = $null

# [Console]::Out, not Write-Output: a helper called inside a value-returning
# function must not add its text to that function's return value (see the note
# in scripts/release-check.ps1 - that mistake made every step look green).
function Say([string]$text) {
  [Console]::Out.WriteLine($text)
  Add-Content -LiteralPath $artifact -Value $text -Encoding UTF8
}

function Mark([string]$label, [string]$name, [string]$detail) {
  switch ($label) {
    'FAIL'    { $script:Failures++ }
    'BLOCKED' { $script:Blocked++ }
    'SKIPPED' { $script:Skips++ }
  }
  Say ('{0}  {1} :: {2}' -f $label.PadRight(7), $name, $detail)
}

function Http([string]$method, [string]$url, [string]$json, [int]$maxTime = 120) {
  $tmpOut = [System.IO.Path]::GetTempFileName()
  $tmpJson = $null
  $curlArgs = @('-s', '-o', $tmpOut, '-w', '%{http_code}', '-X', $method, '--max-time', "$maxTime", $url)
  if ($json) {
    $tmpJson = [System.IO.Path]::GetTempFileName()
    [System.IO.File]::WriteAllText($tmpJson, $json, (New-Object System.Text.UTF8Encoding($false)))
    $curlArgs += @('-H', 'Content-Type: application/json', '--data-binary', "@$tmpJson")
  }
  $code = (& curl.exe @curlArgs | Select-Object -Last 1)
  $body = ''
  if (Test-Path $tmpOut) { $body = Get-Content -LiteralPath $tmpOut -Raw -ErrorAction SilentlyContinue }
  Remove-Item -LiteralPath $tmpOut -Force -ErrorAction SilentlyContinue
  if ($tmpJson) { Remove-Item -LiteralPath $tmpJson -Force -ErrorAction SilentlyContinue }
  $status = 0
  if ($code) { $status = [int]$code }
  return @{ status = $status; body = $body }
}

# ConvertFrom-Json does not unroll a top-level JSON array through the pipeline under
# Windows PowerShell 5.1, so '@($body | ConvertFrom-Json)' nests it one level and
# '$list[0].id' then yields an array of ids joined by spaces. This enumerates the items
# so that '@(Get-JsonList $body)' is flat on both 5.1 and 7.
function Get-JsonList([string]$body) {
  try { $parsed = $body | ConvertFrom-Json } catch { return }
  foreach ($item in @($parsed)) {
    if ($item -is [System.Array]) { foreach ($inner in $item) { $inner } } else { $item }
  }
}

function Get-Descendants([int]$parent) {
  $found = @()
  if ($parent -le 0) { return $found }
  $queue = @($parent)
  while ($queue.Count -gt 0) {
    $current = $queue[0]
    if ($queue.Count -gt 1) { $queue = $queue[1..($queue.Count - 1)] } else { $queue = @() }
    $kids = @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$current" -ErrorAction SilentlyContinue |
              Select-Object -ExpandProperty ProcessId)
    foreach ($kid in $kids) { $found += $kid; $queue += $kid }
  }
  return $found
}

function Start-Backend([int]$port, [string]$ws, [switch]$NoKeys) {
  if (-not (Test-Path $ws)) { New-Item -ItemType Directory -Path $ws -Force | Out-Null }
  $env:VIBE_WORKSPACE_DIR = $ws
  $env:VIBE_PORT = "$port"
  $env:VIBE_MODE = 'prod'
  $env:VIBE_HOST = '127.0.0.1'
  if ($NoKeys) {
    $env:OPENAI_API_KEY = ''
    $env:ANTHROPIC_API_KEY = ''
    $env:OPENCODE_API_KEY = ''
  } else {
    Remove-Item Env:OPENAI_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:ANTHROPIC_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:OPENCODE_API_KEY -ErrorAction SilentlyContinue
  }
  $outLog = Join-Path $env:TEMP "vibe-acc-$port.out.log"
  $errLog = Join-Path $env:TEMP "vibe-acc-$port.err.log"
  # Keep one previous generation. Start-Process truncates the redirect target,
  # so the restart in step 5 would otherwise erase the shutdown log of the
  # instance that just stopped - the log that says whether the app stopped its
  # dev servers.
  foreach ($logFile in @($outLog, $errLog)) {
    if (Test-Path $logFile) { Move-Item -LiteralPath $logFile -Destination ($logFile -replace '[.]log$', '.prev.log') -Force -ErrorAction SilentlyContinue }
  }
  $proc = Start-Process -FilePath $python -ArgumentList @('-m', 'vibe', 'serve') -WorkingDirectory $repo -PassThru -WindowStyle Hidden -RedirectStandardOutput $outLog -RedirectStandardError $errLog
  $deadline = (Get-Date).AddSeconds(60)
  while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) {
      $tail = (Get-Content -LiteralPath $errLog -Raw -ErrorAction SilentlyContinue)
      return @{ proc = $proc; ok = $false; why = "server exited early (exit $($proc.ExitCode)): $tail" }
    }
    $health = Http 'GET' "http://127.0.0.1:$port/health" $null 10
    if ($health.status -eq 200) { return @{ proc = $proc; ok = $true; why = '' } }
    Start-Sleep -Milliseconds 400
  }
  return @{ proc = $proc; ok = $false; why = 'health did not answer within 60s' }
}

function Stop-Backend($proc) {
  if ($null -eq $proc) { return }
  try {
    if (-not $proc.HasExited) {
      Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
      $proc.WaitForExit(10000) | Out-Null
    }
  } catch { }
}

function Wait-Exit($proc, [int]$seconds) {
  if ($null -eq $proc) { return $true }
  $deadline = (Get-Date).AddSeconds($seconds)
  while ((Get-Date) -lt $deadline) {
    if ($proc.HasExited) { return $true }
    Start-Sleep -Milliseconds 300
  }
  return $proc.HasExited
}

# agent-browser spawns a browser and can leave it holding the inherited pipe
# handle, so "& agent-browser ... | Out-Null" can hang forever - it did, for
# over ten minutes, on this script's first real run. Start-Process with file
# redirection plus WaitForExit(timeout) keeps the acceptance run bounded.
function Invoke-Browser([string]$exe, [string[]]$cmdArgs, [int]$timeoutSec = 75) {
  $outFile = [System.IO.Path]::GetTempFileName()
  $errFile = [System.IO.Path]::GetTempFileName()
  $proc = Start-Process -FilePath $exe -ArgumentList $cmdArgs -PassThru -WindowStyle Hidden -RedirectStandardOutput $outFile -RedirectStandardError $errFile
  $exited = $proc.WaitForExit($timeoutSec * 1000)
  if (-not $exited) {
    foreach ($kid in (@(Get-Descendants -parent $proc.Id) | Sort-Object -Descending)) { Stop-Process -Id $kid -Force -ErrorAction SilentlyContinue }
    Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue
  }
  $text = ((Get-Content -LiteralPath $outFile -Raw -ErrorAction SilentlyContinue) + ' ' + (Get-Content -LiteralPath $errFile -Raw -ErrorAction SilentlyContinue))
  Remove-Item -LiteralPath $outFile, $errFile -Force -ErrorAction SilentlyContinue
  return @{ ok = $exited; text = $text.Trim() }
}

# $env:TEMP can be the 8.3 short form (C:\Users\AHMADM~1\...). The backend
# reports the long form, so comparing the two as raw strings says "not
# isolated" about a workspace that is in fact the right one. GetFullPath
# expands the short components.
function Normalize-Path([string]$path) {
  if (-not $path) { return '' }
  try { return ([System.IO.Path]::GetFullPath($path)).TrimEnd('\') } catch { return $path.TrimEnd('\') }
}

function Db-Scalar([string]$db, [string]$sql, [string]$sid) {
  $code = @'
import sqlite3, sys
con = sqlite3.connect(sys.argv[1])
try:
    print(con.execute(sys.argv[2], (sys.argv[3],)).fetchone()[0])
except Exception as exc:
    print("ERR " + str(exc))
'@
  $out = & $python -c $code $db $sql $sid 2>&1 | Out-String
  return $out.Trim()
}

Say ''
Say ('=== acceptance-local.ps1  ' + (Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ===')
Say ("repo:                  " + $repo)
Say ("interpreter:           " + $python)
Say ("workspace under test:  " + $Workspace + " (existed before: " + (Test-Path $Workspace) + ")")
Say ("provider-free run:     " + $NoProviderWorkspace)
Say ("engine:                " + $PSVersionTable.PSVersion.ToString())
Say ''

if (-not (Get-Command curl.exe -ErrorAction SilentlyContinue)) {
  Mark 'BLOCKED' 'acceptance run' 'curl.exe is not on PATH; the script speaks HTTP through it rather than through version-specific PowerShell cmdlets'
  exit 2
}

$base = "http://127.0.0.1:$Port"
$sid = $null
$providerId = $null
$modelId = $null
$step3 = 'SKIPPED'
$e2eUrl = $null

try {
  # ---------------------------------------------------------------- step 1
  $env:VIBE_WORKSPACE_DIR = $Workspace
  # Start-Process for the exit code: $LASTEXITCODE after a pipeline is not
  # dependable, and step 1's whole point is the doctor's exit code.
  $docOutFile = [System.IO.Path]::GetTempFileName()
  $docErrFile = [System.IO.Path]::GetTempFileName()
  $docProc = Start-Process -FilePath $python -ArgumentList @('-m', 'vibe', 'doctor') -WorkingDirectory $repo -PassThru -Wait -NoNewWindow -RedirectStandardOutput $docOutFile -RedirectStandardError $docErrFile
  $doctorOut = ((Get-Content -LiteralPath $docOutFile -Raw -ErrorAction SilentlyContinue) + [Environment]::NewLine + (Get-Content -LiteralPath $docErrFile -Raw -ErrorAction SilentlyContinue))
  $doctorCode = $docProc.ExitCode
  Remove-Item -LiteralPath $docOutFile, $docErrFile -Force -ErrorAction SilentlyContinue
  foreach ($line in ($doctorOut -split "[\r\n]+")) { if ($line.Trim()) { Say ('    doctor | ' + $line.Trim()) } }
  $hardFail = @($doctorOut -split "[\r\n]+" | Where-Object { $_ -match '^(FAIL|ERROR)' }).Count
  $warn = @($doctorOut -split "[\r\n]+" | Where-Object { $_ -match '^WARN' }).Count
  if ($doctorCode -eq 0 -and $hardFail -eq 0) {
    Mark 'PASS' 'step 1 doctor on this machine' "exit 0; $hardFail blocking problem(s), $warn warning(s) (a warning is a missing provider key or browser and does not block)"
  } else {
    Mark 'FAIL' 'step 1 doctor on this machine' "exit $doctorCode; $hardFail blocking problem(s) - see the doctor lines above"
  }

  # ---------------------------------------------------------------- step 2
  $started = Start-Backend -port $Port -ws $Workspace
  $script:Server = $started.proc
  if (-not $started.ok) {
    Mark 'FAIL' 'step 2 start the app and serve the SPA' ("could not start: " + $started.why)
  } else {
    $health = Http 'GET' "$base/health" $null 20
    $reported = ''
    try { $reported = ($health.body | ConvertFrom-Json).workspace_dir } catch { }
    $sameWorkspace = ((Normalize-Path $reported) -eq (Normalize-Path $Workspace))
    $shell = Http 'GET' "$base/" $null 20
    $hasRoot = ($shell.body -match 'id="root"')
    if ($health.status -eq 200 -and $shell.status -eq 200 -and $hasRoot -and $sameWorkspace) {
      Mark 'PASS' 'step 2 start the app and serve the SPA' "/health 200, workspace_dir=$reported (isolated from the real workspace), GET / 200 with the SPA shell on the same port $Port"
    } else {
      Mark 'FAIL' 'step 2 start the app and serve the SPA' "/health=$($health.status); workspace_dir='$reported' isolated=$sameWorkspace; GET /=$($shell.status); shell marker present=$hasRoot"
    }
  }

  # ---------------------------------------------------------------- step 3
  $catalog = Http 'GET' "$base/catalog" $null 30
  $providers = @()
  $providers = @(Get-JsonList $catalog.body)
  $configured = @($providers | Where-Object { $_.key_configured })
  if ($configured.Count -eq 0) {
    Mark 'SKIPPED' 'step 3 agent builds a file' 'no provider key is configured (GET /catalog reports key_configured=false for every provider), so no run can be produced honestly'
  } else {
    $preferred = @($configured | Where-Object { $_.id -eq 'opencode-go' })
    if ($preferred.Count -eq 0) { $preferred = $configured }
    $providerId = $preferred[0].id
    $models = @($preferred[0].models)
    $free = @($models | Where-Object { $_.id -match 'free' })
    if ($free.Count -gt 0) { $modelId = $free[0].id } else { $modelId = $models[0].id }

    $createJson = @{ model = @{ provider_id = $providerId; model_id = $modelId } } | ConvertTo-Json -Compress
    $create = Http 'POST' "$base/sessions" $createJson 60
    try { $sid = ($create.body | ConvertFrom-Json).id } catch { }
    if ($create.status -ne 201 -or -not $sid) {
      Mark 'FAIL' 'step 3 agent builds a file' "POST /sessions returned $($create.status): $($create.body)"
    } else {
      if ($FullE2E) {
        $prompt = 'Build a minimal Vite + React + TypeScript app in this workspace: package.json with a dev script, index.html, and src/main.tsx that renders an h1 saying Hello from Vibe. Install what it needs and make it run.'
      } else {
        $prompt = 'Create a file named hello.txt whose content is exactly: hello from vibe. Use the write tool, then tell me the path.'
      }
      $msgJson = @{ content = $prompt; attachments = @() } | ConvertTo-Json -Compress
      $sent = Http 'POST' "$base/sessions/$sid/messages" $msgJson 2400
      $filesRaw = Http 'GET' "$base/sessions/$sid/files" $null 60
      $files = @()
      $files = @(Get-JsonList $filesRaw.body)
      $answer = ''
      try { $answer = ($sent.body | ConvertFrom-Json).content } catch { }
      $answerHead = ($answer -replace '[\r\n]+', ' ')
      if ($answerHead.Length -gt 300) { $answerHead = $answerHead.Substring(0, 300) + '...' }
      if ($sent.status -eq 200 -and $files.Count -gt 0) {
        $step3 = 'PASS'
        $first = $files | Select-Object -First 1
        Mark 'PASS' 'step 3 agent builds a file' "provider=$providerId model=$modelId; run returned 200; $($files.Count) file(s) in the workspace, first: $first"
        Say ("    step 3 | session id: " + $sid)
        Say ("    step 3 | files: " + (($files | Select-Object -First 12) -join ', '))
        Say ("    step 3 | agent said: " + $answerHead)
      } elseif ($sent.status -eq 200) {
        Mark 'FAIL' 'step 3 agent builds a file' "the run answered 200 but produced no file (session $sid); agent said: $answerHead"
      } else {
        $sentHead = ($sent.body -replace '[\r\n]+', ' ')
        Mark 'FAIL' 'step 3 agent builds a file' "POST messages returned $($sent.status): $sentHead"
      }

      if ($FullE2E -and $step3 -eq 'PASS') {
        $run = Http 'POST' "$base/sessions/$sid/preview/run" '{}' 300
        try { $e2eUrl = ($run.body | ConvertFrom-Json).url } catch { }
        if ($e2eUrl) {
          $ok = $false
          for ($i = 0; $i -lt 30; $i++) {
            $probe = Http 'GET' $e2eUrl $null 15
            if ($probe.status -eq 200 -and $probe.body -match 'id="root"') { $ok = $true; break }
            Start-Sleep -Seconds 2
          }
          if ($ok) { Mark 'PASS' 'step 3b preview serves the built app' "GET $e2eUrl -> 200 with the app shell" }
          else { Mark 'FAIL' 'step 3b preview serves the built app' "GET $e2eUrl never returned 200 with an app shell within 60s" }
        } else {
          $runHead = ($run.body -replace '[\r\n]+', ' ')
          Mark 'FAIL' 'step 3b preview serves the built app' "POST preview/run returned $($run.status): $runHead"
        }
      }
    }
  }

  # ---------------------------------------------------------------- step 4
  if ($configured.Count -eq 0 -or -not $providerId) {
    Mark 'SKIPPED' 'step 4 abort stops a run' 'no provider configured, so no run can be started to abort; the registry path is covered by tests/test_run_registry.py'
  } else {
    $create2Json = @{ model = @{ provider_id = $providerId; model_id = $modelId } } | ConvertTo-Json -Compress
    $create2 = Http 'POST' "$base/sessions" $create2Json 60
    $sid2 = $null
    try { $sid2 = ($create2.body | ConvertFrom-Json).id } catch { }
    if (-not $sid2) {
      Mark 'FAIL' 'step 4 abort stops a run' "could not create a session to abort: $($create2.status) $($create2.body)"
    } else {
      # A prompt the model cannot finish instantly: the abort has to arrive
      # while the run is still in flight, and "say hello" is over before the
      # first poll can land.
      $abortMsg = @{ content = 'Write a file named big.txt containing the numbers 1 to 300, one per line, using the write tool. Then reply done.'; attachments = @() } | ConvertTo-Json -Compress
      $jsonFile = [System.IO.Path]::GetTempFileName()
      [System.IO.File]::WriteAllText($jsonFile, $abortMsg, (New-Object System.Text.UTF8Encoding($false)))
      $runOut = [System.IO.Path]::GetTempFileName()
      # The status is read from curl's own header dump. Capturing the child's
      # stdout through Start-Process -RedirectStandardOutput corrupted this very
      # invocation: the run body never reached the app (400 validation_failed)
      # and the captured code file held two codes ("000{...}400"). Nothing here
      # depends on the child's stdout any more.
      $headOut = [System.IO.Path]::GetTempFileName()
      # Snapshot the backend's descendants before the run. Step 3 leaves a dev
      # server behind, which is a legitimate long-lived child; counting it as a
      # leak from the abort would be a false FAIL. Only the delta is step 4's.
      $serverPid = 0
      if ($script:Server) { $serverPid = $script:Server.Id }
      $beforeKids = @{}
      foreach ($kid in @(Get-Descendants -parent $serverPid)) { $beforeKids[[int]$kid] = $true }
      $bg = Start-Process -FilePath 'curl.exe' -WorkingDirectory $repo -PassThru -WindowStyle Hidden -ArgumentList @(
        # Start-Process joins -ArgumentList with spaces and the child re-splits
        # them, so 'Content-Type: application/json' arrived as two tokens
        # ("Content-Type:" plus a bogus extra URL) and the request carried no
        # JSON content type: the app's request-validation handler answered 400
        # validation_failed and the route never ran, which is why step 4 could
        # only ever be SKIPPED. Keep the header one token - no space after the
        # colon. Proven by an argv probe; see hardening-final-checks.txt.
        '-s', '-o', $runOut, '-D', $headOut, '-X', 'POST', '--max-time', '180',
        '-H', 'Content-Type:application/json', '--data-binary', "@$jsonFile", "$base/sessions/$sid2/messages")
      # Poll instead of sleeping a fixed 3s: a fast model can answer before one
      # delayed abort arrives, and aborted=false then says nothing about whether
      # abort works. Keep asking while the run is still in flight.
      $abortedFlag = $false
      $abortStatus = 0
      for ($i = 0; $i -lt 120; $i++) {
        Start-Sleep -Milliseconds 250
        if ($bg.HasExited) { break }
        $abort = Http 'POST' "$base/sessions/$sid2/abort" '{}' 30
        $abortStatus = $abort.status
        try { $abortedFlag = [bool](($abort.body | ConvertFrom-Json).aborted) } catch { }
        if ($abortedFlag) { break }
      }
      $stopped = Wait-Exit $bg 120
      $runCode = 'not captured'
      $headRaw = Get-Content -LiteralPath $headOut -Raw -ErrorAction SilentlyContinue
      if ($headRaw) {
        $codes = [regex]::Matches($headRaw, 'HTTP/\d[.]\d (\d{3})')
        if ($codes.Count -gt 0) { $runCode = $codes[$codes.Count - 1].Groups[1].Value }
      }
      Start-Sleep -Seconds 2
      $newKids = @()
      foreach ($kid in @(Get-Descendants -parent $serverPid)) {
        if (-not $beforeKids.ContainsKey([int]$kid)) { $newKids += $kid }
      }
      $newKidDetail = @()
      foreach ($kid in $newKids) {
        $info = Get-CimInstance Win32_Process -Filter "ProcessId=$kid" -ErrorAction SilentlyContinue
        if ($info) {
          $cl = $info.CommandLine
          if ($cl -and $cl.Length -gt 90) { $cl = $cl.Substring(0, 90) + '...' }
          $newKidDetail += ($info.Name + ':' + $kid + ' [' + $cl + ']')
        } else {
          $newKidDetail += ('pid:' + $kid + ' [already exited]')
        }
      }
      Remove-Item -LiteralPath $jsonFile -Force -ErrorAction SilentlyContinue
      Remove-Item -LiteralPath $runOut -Force -ErrorAction SilentlyContinue
      Remove-Item -LiteralPath $headOut -Force -ErrorAction SilentlyContinue
      if ($abortedFlag -and $stopped -and $newKidDetail.Count -eq 0) {
        Mark 'PASS' 'step 4 abort stops a run' "POST /abort -> aborted=true; the in-flight run returned within 120s (the run answered HTTP $runCode); no child process appeared under the backend pid $serverPid between the baseline and the abort"
      } elseif ($abortedFlag -and $stopped) {
        Mark 'FAIL' 'step 4 abort stops a run' "the abort landed (aborted=true, run returned) but left $($newKidDetail.Count) new child process(es) under the backend: $($newKidDetail -join '; ')"
      } elseif ($stopped -and -not $abortedFlag) {
        Mark 'SKIPPED' 'step 4 abort stops a run' "the run finished before any abort landed (the run answered HTTP $runCode; the last POST /abort answered $abortStatus with aborted=false), so there was nothing in flight to stop; the in-flight path is covered by tests/test_run_registry.py"
      } else {
        Mark 'FAIL' 'step 4 abort stops a run' "aborted=$abortedFlag; run returned=$stopped; run HTTP=$runCode; new children: $($newKidDetail -join '; ')"
      }
    }
  }

  # ---------------------------------------------------------------- step 5
  if (-not $sid) {
    Mark 'SKIPPED' 'step 5 restart keeps the transcript' 'no session was created in step 3 (no provider), so there is nothing whose survival could be asserted'
  } else {
    $beforeRaw = Http 'GET' "$base/sessions/$sid/messages" $null 30
    $beforeMessages = @()
    $beforeMessages = @(Get-JsonList $beforeRaw.body)
    $shutdown = Http 'POST' "$base/admin/shutdown" '{}' 30
    $exited = Wait-Exit $script:Server 30
    if (-not $exited) { Stop-Backend $script:Server }
    $restarted = Start-Backend -port $Port -ws $Workspace
    $script:Server = $restarted.proc
    if (-not $restarted.ok) {
      Mark 'FAIL' 'step 5 restart keeps the transcript' "the app did not come back: $($restarted.why)"
    } else {
      $row = Http 'GET' "$base/sessions/$sid" $null 30
      $afterRaw = Http 'GET' "$base/sessions/$sid/messages" $null 30
      $afterMessages = @()
      $afterMessages = @(Get-JsonList $afterRaw.body)
      $usage = Http 'GET' "$base/sessions/$sid/usage" $null 30
      $tokens = 0
      try { $tokens = [int](($usage.body | ConvertFrom-Json).total_tokens) } catch { }
      if ($row.status -eq 200 -and $afterMessages.Count -gt 0 -and $afterMessages.Count -ge $beforeMessages.Count -and $usage.status -eq 200 -and $tokens -gt 0) {
        Mark 'PASS' 'step 5 restart keeps the transcript' "graceful POST /admin/shutdown stopped the server (exited=$exited); after restart the row is 200, $($afterMessages.Count) message(s) survived and usage reports $tokens token(s)"
      } else {
        Mark 'FAIL' 'step 5 restart keeps the transcript' "row=$($row.status) messages before=$($beforeMessages.Count) after=$($afterMessages.Count) usage=$($usage.status) tokens=$tokens"
      }
    }
  }

  # ---------------------------------------------------------------- step 6
  if (-not $sid) {
    Mark 'SKIPPED' 'step 6a delete moves the workspace to .trash' 'no session exists to delete'
  } else {
    # The preview from step 3b is a process this script started, and the app's
    # own stop endpoint is the first way to end it. A restart (step 5) forgets
    # the registry entry, so that call can be a no-op while the process lives on
    # - a finding in itself - and the script then stops what it started rather
    # than letting an orphan decide the delete verdict.
    $previewPort = 0
    if ($e2eUrl) { try { $previewPort = [int](([uri]$e2eUrl).Port) } catch { } }
    $holderBefore = @()
    if ($previewPort -gt 0) {
      $holderBefore = @(Get-NetTCPConnection -LocalPort $previewPort -State Listen -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique)
    }
    $holderLabels = @()
    foreach ($op in $holderBefore) {
      $info = Get-CimInstance Win32_Process -Filter "ProcessId=$op" -ErrorAction SilentlyContinue
      if ($info) { $holderLabels += ($info.Name + ':' + $op) } else { $holderLabels += ('pid:' + $op) }
    }
    $stop = Http 'POST' "$base/sessions/$sid/preview/stop" '{}' 60
    Start-Sleep -Seconds 2
    $killed = @()
    foreach ($op in $holderBefore) {
      if (-not (Get-Process -Id $op -ErrorAction SilentlyContinue)) { continue }
      foreach ($kid in (@(Get-Descendants -parent $op) | Sort-Object -Descending)) { Stop-Process -Id $kid -Force -ErrorAction SilentlyContinue }
      Stop-Process -Id $op -Force -ErrorAction SilentlyContinue
      $killed += ('pid:' + $op)
    }
    if ($killed.Count -gt 0) { Start-Sleep -Seconds 2 }
    $stopNote = "POST preview/stop -> $($stop.status)"
    if ($holderLabels.Count -gt 0) { $stopNote += "; preview port $previewPort was held by $($holderLabels -join ',')" }
    if ($killed.Count -gt 0) { $stopNote += "; those process(es) were still listening after the stop call (a restart forgets the dev-server registry entry), so the script stopped the tree it had started" }
    $del = Http 'DELETE' "$base/sessions/$sid" $null 60
    $trash = @(Get-ChildItem -Path (Join-Path $Workspace '.trash') -Filter "$sid-*" -ErrorAction SilentlyContinue)
    $after = Http 'GET' "$base/sessions/$sid" $null 30
    $db = Join-Path $Workspace 'sessions.db'
    $rows = 'no database'
    if (Test-Path $db) { $rows = Db-Scalar $db 'SELECT COUNT(*) FROM sessions WHERE id = ?' $sid }
    # Who is holding the directory open? On Windows a dev server still running
    # under the session workspace makes the move-aside fail, and the status code
    # alone would not say so. This diagnostic used to report "none seen" while a
    # live node process whose command line named the session held the workspace,
    # which is exactly the evidence the failure needs -- so it now matches the
    # session id as well as the absolute path, and no longer filters by image
    # name (a browser or a python can hold the directory just as well).
    $holders = @()
    $sessionWs = Join-Path $Workspace $sid
    foreach ($proc in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
      $named = $proc.CommandLine -like ('*' + $sessionWs + '*') -or $proc.CommandLine -like ('*' + $sid + '*')
      if ($proc.CommandLine -and $named) {
        $holders += ($proc.Name + ':' + $proc.ProcessId)
      }
    }
    if ($del.status -eq 204 -and $trash.Count -ge 1 -and $after.status -eq 404 -and $rows -eq '0') {
      Mark 'PASS' 'step 6a delete moves the workspace to .trash' "$stopNote; DELETE -> 204; .trash/$($trash[0].Name) exists; GET the deleted session -> 404; rows in the temp sessions.db = $rows"
    } else {
      $delHead = ($del.body -replace '[
]+', ' ')
      if ($delHead.Length -gt 160) { $delHead = $delHead.Substring(0, 160) + '...' }
      $holderNote = 'none seen'
      if ($holders.Count -gt 0) { $holderNote = (($holders -join ',') + ' - started by the agent run in step 3; the app did not stop them') }
      Mark 'FAIL' 'step 6a delete moves the workspace to .trash' "$stopNote; DELETE=$($del.status) body=$delHead trash entries=$($trash.Count) GET=$($after.status) db rows=$rows; processes still holding the session workspace: $holderNote"
    }
  }

  # ---------------------------------------------------------------- step 6b
  # Delete while something holds the workspace open. Deterministic: the script
  # opens a file inside the session workspace and keeps the handle, which is the
  # exact mechanism that made the directory rename fail (WinError 32/5). The app
  # must retry, then answer a named 409 workspace_busy and leave the session
  # intact - never a 500, and never a half-torn-down session.
  $model6b = @{ provider_id = 'openai'; model_id = 'gpt-4o' }
  if ($providerId -and $modelId) { $model6b = @{ provider_id = $providerId; model_id = $modelId } }
  $create3 = Http 'POST' "$base/sessions" (@{ model = $model6b } | ConvertTo-Json -Compress) 60
  $sid3 = $null
  try { $sid3 = ($create3.body | ConvertFrom-Json).id } catch { }
  if (-not $sid3) {
    Mark 'FAIL' 'step 6b delete while the workspace is locked' "could not create a session to lock: $($create3.status) $($create3.body)"
  } else {
    $sessionWs3 = Join-Path $Workspace $sid3
    if (-not (Test-Path $sessionWs3)) { New-Item -ItemType Directory -Path $sessionWs3 -Force | Out-Null }
    $lockPath = Join-Path $sessionWs3 'locked.txt'
    $stream = $null
    try {
      $stream = [System.IO.File]::Open($lockPath, [System.IO.FileMode]::Create, [System.IO.FileAccess]::ReadWrite, [System.IO.FileShare]::None)
      $stream.WriteByte(65)
      $stream.Flush()
      $delLocked = Http 'DELETE' "$base/sessions/$sid3" $null 60
      $lockedCode = ''
      try { $lockedCode = ($delLocked.body | ConvertFrom-Json).error.code } catch { }
      $rowLocked = Http 'GET' "$base/sessions/$sid3" $null 30
      $trashLocked = @(Get-ChildItem -Path (Join-Path $Workspace '.trash') -Filter "$sid3-*" -ErrorAction SilentlyContinue)
    } finally {
      if ($stream) { $stream.Close() }
    }
    Remove-Item -LiteralPath $lockPath -Force -ErrorAction SilentlyContinue
    Start-Sleep -Milliseconds 500
    $delFree = Http 'DELETE' "$base/sessions/$sid3" $null 60
    $trashFree = @(Get-ChildItem -Path (Join-Path $Workspace '.trash') -Filter "$sid3-*" -ErrorAction SilentlyContinue)
    $afterFree = Http 'GET' "$base/sessions/$sid3" $null 30
    $busyOk = ($delLocked.status -eq 409 -and $lockedCode -eq 'workspace_busy' -and $rowLocked.status -eq 200 -and $trashLocked.Count -eq 0)
    $freeOk = ($delFree.status -eq 204 -and $trashFree.Count -ge 1 -and $afterFree.status -eq 404)
    if ($busyOk -and $freeOk) {
      Mark 'PASS' 'step 6b delete while the workspace is locked' "with an open handle inside the workspace: DELETE -> 409 code=$lockedCode, session still 200, .trash untouched; after the handle closed: DELETE -> 204 and .trash/$($trashFree[0].Name) exists"
    } elseif (-not $busyOk) {
      Mark 'FAIL' 'step 6b delete while the workspace is locked' "with an open handle inside the workspace: DELETE=$($delLocked.status) code=$lockedCode (expected 409 workspace_busy), session GET=$($rowLocked.status) (expected 200), trash entries=$($trashLocked.Count) (expected 0); after the handle closed: DELETE=$($delFree.status)"
    } else {
      Mark 'FAIL' 'step 6b delete while the workspace is locked' "the locked case answered 409 workspace_busy correctly, but the delete after the handle closed gave DELETE=$($delFree.status) trash entries=$($trashFree.Count) GET=$($afterFree.status)"
    }
  }
} catch {
  Mark 'BLOCKED' 'acceptance run' ("the script itself stopped: " + $_.Exception.Message)
} finally {
  # ---------------------------------------------------------------- step 7
  # In the finally block on purpose: the provider-free first run is worth
  # checking even when an earlier step failed, and it uses its own workspace
  # and port so it cannot disturb the session above.
  try {
    if (-not (Test-Path $NoProviderWorkspace)) { New-Item -ItemType Directory -Path $NoProviderWorkspace -Force | Out-Null }
    $started2 = Start-Backend -port $NoProviderPort -ws $NoProviderWorkspace -NoKeys
    $script:Server2 = $started2.proc
    $base2 = "http://127.0.0.1:$NoProviderPort"
    if (-not $started2.ok) {
      Mark 'FAIL' 'step 7 first run without a provider' ("the provider-free instance did not start: " + $started2.why)
    } else {
      $cat2 = Http 'GET' "$base2/catalog" $null 30
      $prov2 = @()
      $prov2 = @(Get-JsonList $cat2.body)
      $anyKey = @($prov2 | Where-Object { $_.key_configured }).Count
      $shell2 = Http 'GET' "$base2/" $null 20
      $apiOk = ($cat2.status -eq 200 -and $anyKey -eq 0 -and $shell2.status -eq 200)
      $browser = Get-Command agent-browser -ErrorAction SilentlyContinue
      if (-not $apiOk) {
        Mark 'FAIL' 'step 7 first run without a provider' "GET /catalog=$($cat2.status) with $anyKey configured provider(s); GET /=$($shell2.status)"
      } elseif (-not $browser) {
        Mark 'PASS' 'step 7 first run without a provider' "GET /catalog 200 with 0 configured providers and the SPA shell served; the DOM half is SKIPPED (agent-browser is not on PATH, so the .first-run panel was not rendered here)"
      } else {
        # agent-browser is a .ps1 shim on Windows, so it needs an interpreter.
        $browserExe = $browser.Source
        $browserPrefix = @()
        if ($browserExe -match '[.](ps1|cmd|bat)$') { $browserPrefix = @('-NoProfile', '-File', $browserExe); $browserExe = 'pwsh' }
        $open = Invoke-Browser $browserExe ($browserPrefix + @('open', "$base2/"))
        $visible = ''
        $text = ''
        $browserNote = ''
        if (-not $open.ok) {
          $browserNote = 'agent-browser open did not return within 75s and was killed, so the DOM half was not evaluated (a tooling limit, not a verdict on the panel)'
        } else {
          $vis = Invoke-Browser $browserExe ($browserPrefix + @('is', 'visible', '.first-run'))
          $visible = $vis.text
          $txt = Invoke-Browser $browserExe ($browserPrefix + @('get', 'text', '.first-run'))
          $text = $txt.text
          $null = Invoke-Browser $browserExe ($browserPrefix + @('close', '--all')) 30
        }
        $head = ($text -replace '[\r\n]+', ' ')
        if ($head.Length -gt 160) { $head = $head.Substring(0, 160) + '...' }
        if ($browserNote) {
          Mark 'SKIPPED' 'step 7 first run without a provider' "GET /catalog 200 with 0 configured providers and the SPA shell served; $browserNote"
        } elseif ($visible -match 'true') {
          Mark 'PASS' 'step 7 first run without a provider' "GET /catalog 200 with 0 configured providers; the rendered SPA shows .first-run (visible=$visible): $head"
        } else {
          Mark 'FAIL' 'step 7 first run without a provider' "the API half is fine (0 configured providers) but .first-run is not visible in the rendered SPA (visible=$visible)"
        }
      }
    }
  } catch {
    Mark 'BLOCKED' 'step 7 first run without a provider' ("could not be evaluated: " + $_.Exception.Message)
  }

  Say ''
  Say ('--- cleanup ' + (Get-Date -Format 'HH:mm:ss') + ' ---')
  Stop-Backend $script:Server
  Stop-Backend $script:Server2
  $env:VIBE_WORKSPACE_DIR = ''
  # The app can leave a dev server (pnpm -> cmd -> node) behind at shutdown: it
  # terminates the shell it spawned, sees that shell exit, and never reaches its
  # own tree-kill fallback. The orphan then holds the session workspace open.
  # This script started those processes, so it stops them - and reports it,
  # because having to is a finding rather than housekeeping.
  $swept = @()
  foreach ($proc in @(Get-CimInstance Win32_Process -ErrorAction SilentlyContinue)) {
    if (-not $proc.CommandLine) { continue }
    if ($proc.ProcessId -eq $PID) { continue }
    if ($proc.Name -notmatch '^(node|cmd|pnpm)[.]exe$') { continue }
    $hit = $false
    foreach ($ws in @($Workspace, $NoProviderWorkspace)) {
      if ($proc.CommandLine -like ('*' + $ws + '*')) { $hit = $true }
    }
    if ($hit) {
      Stop-Process -Id $proc.ProcessId -Force -ErrorAction SilentlyContinue
      $swept += ($proc.Name + ':' + $proc.ProcessId)
    }
  }
  if ($swept.Count -gt 0) {
    Say ("cleanup | stopped " + $swept.Count + " process(es) still serving the acceptance workspace after the app shut down: " + ($swept -join ', '))
    Say "cleanup | the app left them behind (it terminates the spawned shell and never reaches its tree-kill fallback); see the step 6 line above"
  }
  $stoppedIds = @()
  foreach ($p in @($script:Server, $script:Server2)) { if ($p) { $stoppedIds += $p.Id } }
  Say ("stopped the backend pid(s): " + ($stoppedIds -join ', '))
  Start-Sleep -Milliseconds 800
  $left = @(Get-NetTCPConnection -LocalPort $Port, $NoProviderPort -State Listen -ErrorAction SilentlyContinue)
  if ($left.Count -eq 0) {
    Say "ports $Port and $NoProviderPort are free again"
  } else {
    Say ("WARNING: still listening on " + (($left | Select-Object -ExpandProperty LocalPort) -join ', '))
    $script:Failures++
  }

  Say ''
  Say ("summary: " + $script:Failures + " FAIL/BLOCKED, " + $script:Skips + " SKIPPED")
  Say ("e2e: provider=" + $providerId + " model=" + $modelId + " session=" + $sid + " preview=" + $e2eUrl)
  if ($script:Failures -eq 0) { Say 'RESULT: PASS' } else { Say 'RESULT: FAIL' }
}

if ($script:Failures -gt 0) { exit 1 }
exit 0
