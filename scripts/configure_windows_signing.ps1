$ErrorActionPreference = 'Stop'
if (-not $env:WINDOWS_CERTIFICATE -or -not $env:WINDOWS_CERTIFICATE_PASSWORD) {
    throw 'Windows Authenticode certificate and password are required for production builds.'
}
$certificateBytes = [Convert]::FromBase64String($env:WINDOWS_CERTIFICATE)
$certificate = New-Object System.Security.Cryptography.X509Certificates.X509Certificate2
$certificate.Import($certificateBytes, $env:WINDOWS_CERTIFICATE_PASSWORD, 'PersistKeySet')
$store = New-Object System.Security.Cryptography.X509Certificates.X509Store('My', 'CurrentUser')
$store.Open('ReadWrite')
try { $store.Add($certificate) } finally { $store.Close() }
$configuration = Get-Content 'src-tauri/tauri.conf.json' -Raw | ConvertFrom-Json
$configuration.bundle.windows | Add-Member -NotePropertyName certificateThumbprint -NotePropertyValue $certificate.Thumbprint -Force
$configuration.bundle.windows | Add-Member -NotePropertyName digestAlgorithm -NotePropertyValue 'sha256' -Force
$configuration.bundle.windows | Add-Member -NotePropertyName timestampUrl -NotePropertyValue 'http://timestamp.digicert.com' -Force
$configuration | ConvertTo-Json -Depth 30 | Set-Content 'src-tauri/tauri.conf.json' -Encoding utf8
