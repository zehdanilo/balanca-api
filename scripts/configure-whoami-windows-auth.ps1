param(
    [string]$SiteName = "balanca-api",
    [string]$WhoamiPath = "whoami"
)

$ErrorActionPreference = "Stop"

$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw "Execute este script em um PowerShell aberto como Administrador."
}

Import-Module WebAdministration

$site = Get-Website -Name $SiteName -ErrorAction Stop
$appHost = Join-Path $env:windir "System32\inetsrv\config\applicationHost.config"
$backup = "$appHost.balanca-auth-{0:yyyyMMddHHmmss}.bak" -f (Get-Date)
Copy-Item -LiteralPath $appHost -Destination $backup -Force

$rootLocation = $SiteName
$whoamiLocation = "$SiteName/$WhoamiPath"

# Mantem a API publica no site inteiro. Com Anonymous ligado no site,
# o IIS so vai exigir Windows Authentication no caminho configurado abaixo.
Set-WebConfigurationProperty `
    -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Location $rootLocation `
    -Filter "system.webServer/security/authentication/anonymousAuthentication" `
    -Name enabled `
    -Value $true

Set-WebConfigurationProperty `
    -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Location $rootLocation `
    -Filter "system.webServer/security/authentication/windowsAuthentication" `
    -Name enabled `
    -Value $true

# Forca Windows Authentication somente no endpoint usado pela tela para identificar o operador.
Set-WebConfigurationProperty `
    -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Location $whoamiLocation `
    -Filter "system.webServer/security/authentication/anonymousAuthentication" `
    -Name enabled `
    -Value $false

Set-WebConfigurationProperty `
    -PSPath "MACHINE/WEBROOT/APPHOST" `
    -Location $whoamiLocation `
    -Filter "system.webServer/security/authentication/windowsAuthentication" `
    -Name enabled `
    -Value $true

Restart-WebItem "IIS:\Sites\$SiteName"

Write-Host "Configurado com sucesso."
Write-Host "Backup: $backup"
Write-Host "Site '$SiteName': Anonymous=True, Windows=True"
Write-Host "Caminho '$whoamiLocation': Anonymous=False, Windows=True"
Write-Host "Depois valide no navegador: /whoami deve aparecer no log do IIS com cs-username preenchido."
