$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if (-not (Get-Command gh -ErrorAction SilentlyContinue)) {
    throw 'GitHub CLI is needed for this optional helper. You can use GitHub Desktop instead. See INSTALL_WINDOWS.md.'
}
$repo = Read-Host 'New private repository name (for example ClipifyAI-copy)'
if ($repo -notmatch '^[a-zA-Z0-9][a-zA-Z0-9._-]*$') { throw 'Use letters, numbers, dots, dashes or underscores.' }
if (-not (Test-Path '.git')) {
    git init -b main
    if ($LASTEXITCODE -ne 0) { throw 'Git initialization failed.' }
}
# Explicit source allowlist keeps local videos and transcripts out of GitHub.
$items = @('app','Tests/*.py','docs','Assets/*.png','clipify.py','check_setup.py','install_missing.py',
'install_into_existing.py','install_into_existing.bat','install_dependencies.bat','run_clipify.bat',
'setup_visual_ai.py','setup_visual_ai.bat','README.md','INSTALL_WINDOWS.md','requirements.txt',
'.gitignore','publish_github.ps1','publish_github.bat')
foreach ($item in $items) { git add -- $item }
git diff --cached --quiet
if ($LASTEXITCODE -eq 1) {
    git commit -m 'Build local Clipify AI desktop application'
    if ($LASTEXITCODE -ne 0) { throw 'Commit failed. Set your Git name and email using GitHub Desktop.' }
}
gh repo create $repo --private --source . --remote share --push
if ($LASTEXITCODE -ne 0) { throw 'Publishing failed. Existing local files were preserved. Check gh auth login.' }
gh repo view --web
