$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This build must run on Windows.' }
python -c "from pathlib import Path; from follower.license_core import load_public_key; load_public_key(Path('follower/assets/license-public.pem').read_bytes()); print('Public key verified')"
if ($LASTEXITCODE -ne 0) { throw 'Missing or invalid production public key.' }
python -m unittest discover -s tests -v
if ($LASTEXITCODE -ne 0) { throw 'Tests failed.' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name MouseFollower --add-data "follower/assets:follower/assets" --exclude-module admin client_main.py
if ($LASTEXITCODE -ne 0) { throw 'Client build failed.' }
python -m PyInstaller --noconfirm --clean --onefile --windowed --name LicenseIssuer --exclude-module cv2 --exclude-module numpy --exclude-module mss --exclude-module PIL issuer_main.py
if ($LASTEXITCODE -ne 0) { throw 'Issuer build failed.' }
foreach ($exe in @('MouseFollower.exe','LicenseIssuer.exe')) {
    $process = Start-Process -FilePath (Join-Path $PWD "dist/$exe") -ArgumentList '--self-test' -PassThru -Wait
    if ($process.ExitCode -ne 0) { throw "Packaged executable self-test failed: $exe" }
}
New-Item -ItemType Directory -Force dist/client, dist/owner | Out-Null
Copy-Item dist/MouseFollower.exe dist/client/
Copy-Item docs/USER-GUIDE.md dist/client/
Copy-Item THIRD-PARTY-NOTICES.md dist/client/
Copy-Item dist/LicenseIssuer.exe dist/owner/
Copy-Item docs/OWNER-GUIDE.md dist/owner/
Copy-Item follower/assets/license-public.pem dist/owner/
Get-FileHash dist/MouseFollower.exe, dist/LicenseIssuer.exe -Algorithm SHA256 | Format-Table | Out-String | Set-Content dist/SHA256SUMS.txt
Write-Host 'Client and owner-only distributions built separately.'
