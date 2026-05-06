param(
    [string]$SiteName = "balanca-api",
    [string]$WhoamiPath = "whoami"
)

$ErrorActionPreference = "Continue"
$LogPath = Join-Path (Split-Path -Parent $PSScriptRoot) "iis-auth-appcmd.log"
$AppCmd = Join-Path $env:windir "System32\inetsrv\appcmd.exe"
$TargetPath = "$SiteName/$WhoamiPath"

function Log($Message) {
    $Message | Tee-Object -FilePath $LogPath -Append
}

if (Test-Path -LiteralPath $LogPath) {
    Remove-Item -LiteralPath $LogPath -Force
}

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este script em um PowerShell aberto como Administrador."
}

Log "=== Applying auth to $TargetPath ==="
& $AppCmd set config $TargetPath -section:system.webServer/security/authentication/anonymousAuthentication /enabled:false /commit:apphost 2>&1 | Tee-Object -FilePath $LogPath -Append
& $AppCmd set config $TargetPath -section:system.webServer/security/authentication/windowsAuthentication /enabled:true /commit:apphost 2>&1 | Tee-Object -FilePath $LogPath -Append

Log "=== Root anonymous ==="
& $AppCmd list config $SiteName -section:system.webServer/security/authentication/anonymousAuthentication 2>&1 | Tee-Object -FilePath $LogPath -Append
Log "=== Root windows ==="
& $AppCmd list config $SiteName -section:system.webServer/security/authentication/windowsAuthentication 2>&1 | Tee-Object -FilePath $LogPath -Append
Log "=== Whoami anonymous ==="
& $AppCmd list config $TargetPath -section:system.webServer/security/authentication/anonymousAuthentication 2>&1 | Tee-Object -FilePath $LogPath -Append
Log "=== Whoami windows ==="
& $AppCmd list config $TargetPath -section:system.webServer/security/authentication/windowsAuthentication 2>&1 | Tee-Object -FilePath $LogPath -Append

Log "=== Recycle site ==="
& $AppCmd stop site /site.name:$SiteName 2>&1 | Tee-Object -FilePath $LogPath -Append
Start-Sleep -Seconds 2
& $AppCmd start site /site.name:$SiteName 2>&1 | Tee-Object -FilePath $LogPath -Append

Log "=== Done ==="
