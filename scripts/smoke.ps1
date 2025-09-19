# scripts/smoke.ps1
$ErrorActionPreference = "Stop"

# Fresh DB
if (Test-Path .\samos.db) { Remove-Item .\samos.db -Force }
python tools\db_bootstrap.py

# Start API
$api = Start-Process -FilePath "uvicorn" -ArgumentList "samos.api.main:app","--port","8000" -PassThru
Start-Sleep -Seconds 3

try {
  $session = Invoke-RestMethod http://127.0.0.1:8000/session/start -Method POST
  if (-not $session.session_id) { throw "No session_id" }

  $body = @{ prompt="smoke test image"; session_id=$session.session_id } | ConvertTo-Json
  $img  = Invoke-RestMethod http://127.0.0.1:8000/image/generate -Method POST -ContentType "application/json" -Body $body
  if (-not $img.id) { throw "No image id" }

  Invoke-RestMethod ("http://127.0.0.1:8000/image/{0}/file" -f $img.id) -OutFile smoke.png
  Write-Host "Smoke OK – image $($img.id) saved as smoke.png"
}
finally {
  if ($api) { Stop-Process -Id $api.Id -Force }
}
