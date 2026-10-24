#Requires -Version 7.0
<#
  scripts/publish-public.ps1 - the one way this repository reaches GitHub.

  The working repository and the public repository do not share history. The
  public one is published from a clone with the vendored third-party skill
  packs and the internal working files stripped out of every commit, so a
  plain "git push" from this checkout would either be rejected or, worse,
  publish them. This script does the clone -> filter -> push sequence, and
  stops - loudly - at the first precondition it cannot prove.

  It never touches the working repository: the clone, the filter and the push
  all happen in a separate directory.

  The strip list is $StripPaths below; docs/guides/publishing.md explains why
  each entry is there and what to verify after a publish.

  Usage:
    pwsh -File scripts/publish-public.ps1 -DryRun   # preconditions only; nothing is cloned or pushed
    pwsh -File scripts/publish-public.ps1           # clone, filter, push
#>
[CmdletBinding()]
param(
  # Public repository, owner/name.
  [ValidatePattern('^[^/\s]+/[^/\s]+$')]
  [string]$Repo = 'ahmadmhmdsy/vibe',

  # Working-repository root; defaults to the parent of scripts/.
  [string]$Source = (Split-Path -Parent $PSScriptRoot),

  # Where the filtered clone is written; defaults to a fresh directory under
  # the system temp directory. An existing path is refused, never deleted.
  [string]$Destination,

  # Run every precondition and print the plan, then stop.
  [switch]$DryRun
)

$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
Set-StrictMode -Version Latest

# Stripped from every published commit. Product code, docs, rules and the
# state documents stay; nothing else belongs here.
$StripPaths = @('.agents', '.superpowers', 'archive', 'skills-lock.json')

function Stop-Publish {
  param([string]$Message, [string]$Hint)
  Write-Host ''
  Write-Host "publish-public: $Message" -ForegroundColor Red
  if ($Hint) { Write-Host "               $Hint" -ForegroundColor Yellow }
  Write-Host ''
  exit 1
}

function Write-Step {
  param([string]$Message)
  Write-Host "==> $Message" -ForegroundColor Cyan
}

# ---------------------------------------------------------------- preconditions

if (-not (Get-Command git -ErrorAction SilentlyContinue)) {
  Stop-Publish 'git is not on PATH.' 'Install Git and reopen the terminal.'
}
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
  Stop-Publish 'gh (GitHub CLI) is not on PATH.' 'Install it from https://cli.github.com and run gh auth login.'
}
if (-not (Get-Command git-filter-repo -ErrorAction SilentlyContinue)) {
  Stop-Publish 'git-filter-repo is not on PATH.' 'Install it: uv tool install git-filter-repo'
}

$resolved = Resolve-Path -LiteralPath $Source -ErrorAction SilentlyContinue
if (-not $resolved) {
  Stop-Publish "the source directory '$Source' does not exist." 'Pass -Source <repository root>.'
}
$Source = $resolved.Path
if (-not (Test-Path -LiteralPath (Join-Path $Source '.git'))) {
  Stop-Publish "'$Source' is not a git working tree." 'Pass -Source <repository root>.'
}

$dirty = @(git -C $Source status --porcelain=v1)
if ($LASTEXITCODE -ne 0) {
  Stop-Publish "git status failed in '$Source'." 'Fix git first; nothing was cloned or pushed.'
}
if ($dirty.Count -gt 0) {
  $preview = ($dirty | Select-Object -First 12 | ForEach-Object { "                 $_" }) -join [Environment]::NewLine
  Stop-Publish ("the working tree is not clean, so the public copy would not match any commit:" + [Environment]::NewLine + $preview) 'Commit the work, then run again. This script does not stash, reset or choose for you.'
}

$branch = (git -C $Source rev-parse --abbrev-ref HEAD | Out-String).Trim()
if ($branch -ne 'master') {
  Stop-Publish "the working tree is on '$branch', not 'master'." 'Switch to master before publishing: git switch master'
}

gh auth status *> $null
if ($LASTEXITCODE -ne 0) {
  Stop-Publish 'the GitHub CLI is not authenticated.' 'Run: gh auth login'
}

$view = gh repo view $Repo --json name,visibility 2>&1 | Out-String
if ($LASTEXITCODE -ne 0) {
  Stop-Publish "GitHub repository '$Repo' is not reachable - it does not exist, or gh cannot see it." "Create it first and re-run: gh repo create $Repo --public"
}
$visibility = ($view | ConvertFrom-Json).visibility
if ($visibility -ne 'PUBLIC') {
  Stop-Publish "'$Repo' is $($visibility.ToLower()) - this script publishes the public mirror." 'Make the repository public, or pass the intended -Repo.'
}

$sourcePrefix = $Source.TrimEnd('\', '/') + [System.IO.Path]::DirectorySeparatorChar
if ($Destination) {
  $Destination = [System.IO.Path]::GetFullPath($Destination)
  if (Test-Path -LiteralPath $Destination) {
    Stop-Publish "the destination '$Destination' already exists." 'Pass a path that does not exist - this script never deletes a directory.'
  }
} else {
  $Destination = Join-Path ([System.IO.Path]::GetTempPath()) ('vibe-public-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
  if (Test-Path -LiteralPath $Destination) {
    Stop-Publish "the destination '$Destination' already exists." 'Wait a second and re-run, or pass -Destination <new path>.'
  }
}
if ($Destination.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase) -or $Destination -eq $Source) {
  Stop-Publish 'the destination is inside the working repository.' 'Choose a path outside it - a clone inside the tree would appear as untracked work.'
}

# ------------------------------------------------------------------- the plan

$filterCommand = 'git filter-repo --force --invert-paths' + (($StripPaths | ForEach-Object { " --path $_" }) -join '')

Write-Step 'preconditions satisfied'
Write-Host "    source       $Source (branch master, clean)"
Write-Host "    target       https://github.com/$Repo (public)"
Write-Host "    clone        $Destination"
Write-Host "    filter       $filterCommand"
Write-Host '    push         git push -u origin master'

if ($DryRun) {
  Write-Host ''
  Write-Step 'dry run: nothing was cloned, filtered or pushed.'
  exit 0
}

# ------------------------------------------------------------------- the work

Write-Step "cloning $Source -> $Destination"
git clone --no-hardlinks $Source $Destination
if ($LASTEXITCODE -ne 0) {
  Stop-Publish 'git clone failed.' 'Nothing was pushed. Inspect the output above and retry with a new -Destination.'
}

Push-Location -LiteralPath $Destination
try {
  Write-Step 'stripping the publish exclusions from every commit'
  $filterArgs = @('filter-repo', '--force', '--invert-paths')
  foreach ($path in $StripPaths) { $filterArgs += @('--path', $path) }
  & git @filterArgs
  if ($LASTEXITCODE -ne 0) {
    Stop-Publish 'git filter-repo failed.' "Nothing was pushed. The partial clone is at $Destination."
  }

  # Paranoid check: a filter that silently matched nothing must not reach push.
  $objects = @(git -C $Destination rev-list --objects --all |
    ForEach-Object { $parts = $_ -split ' ', 2; if ($parts.Count -eq 2) { $parts[1] } })
  $leaked = @()
  foreach ($path in $StripPaths) {
    if ($objects | Where-Object { $_ -eq $path -or $_ -like "$path/*" }) { $leaked += $path }
  }
  if ($leaked.Count -gt 0) {
    Stop-Publish ("the filtered history still contains: " + ($leaked -join ', ')) 'Stop: do not push. Inspect the clone and the strip list.'
  }

  git remote add origin "https://github.com/$Repo.git"
  if ($LASTEXITCODE -ne 0) {
    Stop-Publish "could not add 'origin' to the clone." "Nothing was pushed. The clone is at $Destination."
  }

  Write-Step "pushing master to https://github.com/$Repo"
  git push -u origin master
  if ($LASTEXITCODE -ne 0) {
    Stop-Publish 'git push failed.' 'If it was rejected as non-fast-forward, the public history moved: re-run from a clean master. Never force-push.'
  }

  $commits = (git -C $Destination rev-list --count origin/master | Out-String).Trim()
  $files = @(git -C $Destination ls-tree -r --name-only origin/master).Count
  $head = (git -C $Destination rev-parse --short origin/master | Out-String).Trim()

  Write-Host ''
  Write-Step "published: $commits commits, $files files at $head"
  Write-Host ''
  Write-Host 'Verify the result (each command answers as the comment says):'
  Write-Host ''
  $checks = @(
    "gh repo view $Repo --json visibility,defaultBranchRef,url",
    "git -C '$Destination' ls-tree -r --name-only origin/master | Select-String '^(\.agents|\.superpowers|archive|skills-lock)'   # nothing",
    "git -C '$Destination' ls-tree -r --name-only origin/master | Select-String '(^|/)[.]env$'   # nothing",
    "gh run list --repo $Repo --limit 1   # success",
    "Invoke-WebRequest 'https://raw.githubusercontent.com/$Repo/master/docs/assets/hero.png' -Method Head   # 200"
  )
  foreach ($check in $checks) { Write-Host "  $check" }
  Write-Host ''
  Write-Host "The filtered clone is kept at $Destination for inspection; delete it when you are done."
}
finally {
  Pop-Location
}
