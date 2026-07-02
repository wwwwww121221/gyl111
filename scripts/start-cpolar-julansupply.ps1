$cpolarExe = "C:\Program Files\cpolar\cpolar.exe"
$args = @("http", "-region=cn_vip", "-subdomain=JulanSupply", "80")

if (-not (Test-Path -LiteralPath $cpolarExe)) {
    Write-Error "cpolar executable not found: $cpolarExe"
    exit 1
}

$running = Get-CimInstance Win32_Process -ErrorAction SilentlyContinue |
    Where-Object {
        $_.Name -eq "cpolar.exe" -and
        $_.CommandLine -and
        $_.CommandLine -like "*-subdomain=JulanSupply*" -and
        $_.CommandLine -like "* 80*"
    }

if ($running) {
    Write-Output "JulanSupply cpolar tunnel is already running."
    exit 0
}

Start-Process -FilePath $cpolarExe -ArgumentList $args -WindowStyle Hidden
Write-Output "Started JulanSupply cpolar tunnel."
