# =============================================================================
# reset_migrations.ps1 - Rebuild migrations and database from scratch
# =============================================================================
# All output is ASCII-only to avoid PowerShell encoding problems on Windows.
#
# Run:
#   powershell -ExecutionPolicy Bypass -File .\reset_migrations.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$root = "D:\Casset.ir\casset-django"
Set-Location $root

$apps = @(
    "accounts", "core", "tracks", "uploads", "plays",
    "interactions", "playlists", "explore", "moderation",
    "billing", "notifications"
)

Write-Host ""
Write-Host "=== 1/6  Backup ===" -ForegroundColor Cyan
$stamp = Get-Date -Format "yyyyMMdd_HHmmss"
if (Test-Path "db.sqlite3") {
    Copy-Item "db.sqlite3" "db.sqlite3.backup_$stamp"
    Write-Host "  Saved: db.sqlite3.backup_$stamp" -ForegroundColor Green
} else {
    Write-Host "  No database to back up." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=== 2/6  Sanity check (imports must work first) ===" -ForegroundColor Cyan
python manage.py check
if ($LASTEXITCODE -ne 0) {
    Write-Host "  'manage.py check' failed. Fix the import/config error above." -ForegroundColor Red
    Write-Host "  Nothing was deleted. Your database is untouched." -ForegroundColor Yellow
    exit 1
}
Write-Host "  Imports OK." -ForegroundColor Green

Write-Host ""
Write-Host "=== 3/6  Remove old migrations ===" -ForegroundColor Cyan
$removed = 0
foreach ($app in $apps) {
    $migDir = Join-Path $root "$app\migrations"
    if (Test-Path $migDir) {
        Get-ChildItem -Path $migDir -Filter "*.py" |
            Where-Object { $_.Name -ne "__init__.py" } |
            ForEach-Object { Remove-Item $_.FullName -Force; $removed++ }
        $pyc = Join-Path $migDir "__pycache__"
        if (Test-Path $pyc) { Remove-Item $pyc -Recurse -Force }
    }
}
Write-Host "  Removed $removed migration files." -ForegroundColor Green

Write-Host ""
Write-Host "=== 4/6  Delete current database ===" -ForegroundColor Cyan
if (Test-Path "db.sqlite3") {
    Remove-Item "db.sqlite3" -Force
    Write-Host "  db.sqlite3 deleted (backup exists)." -ForegroundColor Green
}

Write-Host ""
Write-Host "=== 5/6  Generate fresh migrations ===" -ForegroundColor Cyan
python manage.py makemigrations $apps
if ($LASTEXITCODE -ne 0) {
    Write-Host "  makemigrations failed. Stopped." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== 6/6  Apply migrations ===" -ForegroundColor Cyan
python manage.py migrate
if ($LASTEXITCODE -ne 0) {
    Write-Host "  migrate failed. Stopped." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=== Verify ===" -ForegroundColor Cyan
python manage.py makemigrations --check --dry-run
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Models and database are in sync." -ForegroundColor Green
} else {
    Write-Host "  Warning: models still differ from migrations." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host " Done." -ForegroundColor Green
Write-Host " Next:" -ForegroundColor Cyan
Write-Host "   python manage.py createsuperuser"
Write-Host "   python manage.py test"
Write-Host "=============================================" -ForegroundColor Cyan
Write-Host ""
