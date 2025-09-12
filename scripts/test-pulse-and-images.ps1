<#
Phase A6a — Pulse Alerting & Hardening
End-to-end regression for Pulse + Image integration.

Pre-reqs:
- Run API WITHOUT --reload:
    uvicorn samos.api.main:app --host 127.0.0.1 --port 8000
- .env has: SAM_IMAGE_PROVIDER=stub  (for deterministic happy path)
- .env has the alert config (defaults are fine):
    PULSE_ALERT_WINDOW_SECS=300
    PULSE_FAILRATE_THRESHOLD=0.2
#>

[CmdletBinding()]
param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [int]$ForceFailCount = 5,           # enough to breach 0.2 threshold
  [int]$Depth = 6
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

function Show-Step($msg) { Write-Host "==> $msg" -ForegroundColor Cyan }
function J($obj)       { $obj | ConvertTo-Json -Depth $Depth }
function Get-Json($url){ Invoke-RestMethod -Uri $url -Method GET }
function Post-Json($url, $body) {
    $json = $body | ConvertTo-Json -Depth $Depth -Compress
    return Invoke-RestMethod -Uri $url -Method POST -ContentType 'application/json' -Body $json
}

$summary = @{
  health_ok                      = $false
  session_started                = $false
  happy_path_ok                  = $false
  fail_count_after_forced        = 0
  ok_count_after_happy           = 0
  pulse_alert_seen               = $false
  pulse_reset_ok                 = $false
  metrics_reset_ok               = $false
}

try {
  Show-Step "Health"
  $health = Get-Json "$BaseUrl/health"
  $summary.health_ok = $health.status -eq 'heartbeat.ok'
  Write-Host (J $health)

  Show-Step "Start session"
  $session = Invoke-RestMethod -Method POST "$BaseUrl/session/start"
  $sid = $session.session_id
  if (-not $sid) { throw "No session_id" }
  $summary.session_started = $true
  Write-Host "session_id: $sid"

  Show-Step "Happy path image (stub provider expected)"
  $okBody = @{ session_id = $sid; prompt = "sanity ok" }
  $okRes  = Post-Json "$BaseUrl/image/generate" $okBody
  Write-Host (J $okRes)
  # check metrics
  $m1 = Get-Json "$BaseUrl/metrics"
  $summary.ok_count_after_happy = ($m1.'image.ok' | ForEach-Object { $_ }) # handle missing keys gracefully
  if (-not $summary.ok_count_after_happy) { $summary.ok_count_after_happy = 0 }
  $summary.happy_path_ok = $summary.ok_count_after_happy -ge 1
  Write-Host (J $m1)

  Show-Step "Force provider failures ($ForceFailCount times)"
  for ($i=1; $i -le $ForceFailCount; $i++) {
    $failBody = @{ session_id = $sid; prompt = "pulse test [force-fail]" }
    try {
      Post-Json "$BaseUrl/image/generate" $failBody | Out-Null
    } catch {
      # expected 500
      Write-Host "  forced fail #$i (500 expected)"
    }
  }

  $m2 = Get-Json "$BaseUrl/metrics"
  $summary.fail_count_after_forced = ($m2.'image.fail' | ForEach-Object { $_ })
  if (-not $summary.fail_count_after_forced) { $summary.fail_count_after_forced = 0 }
  Write-Host (J $m2)

  Show-Step "Check for pulse.alert events (if threshold breached)"
  $alerts = Get-Json "$BaseUrl/events?kind=pulse.alert&limit=5"
  $summary.pulse_alert_seen = @($alerts).Count -gt 0
  Write-Host (J $alerts)

  Show-Step "Reset pulse window"
  $pr = Get-Json "$BaseUrl/pulse/reset"
  $summary.pulse_reset_ok = $pr.ok -eq $true
  Write-Host (J $pr)

  Show-Step "Reset metrics (also_buckets=true)"
  $mr = Invoke-RestMethod -Method POST "$BaseUrl/metrics/reset?also_buckets=true"
  $summary.metrics_reset_ok = $mr.ok -eq $true -and $mr.after.'image.ok' -eq 0 -and $mr.after.'image.fail' -eq 0
  Write-Host (J $mr)

  Show-Step "Summary"
  Write-Host (J $summary)

  # Basic assertions to fail the script in CI if something critical is wrong
  if (-not $summary.health_ok) { throw "Health failed" }
  if (-not $summary.session_started) { throw "Session not started" }
  if (-not $summary.happy_path_ok) { throw "Happy path did not increment image.ok" }
  if ($summary.fail_count_after_forced -lt 1) { throw "Forced failures did not increment image.fail" }
  if (-not $summary.pulse_reset_ok) { throw "Pulse reset failed" }
  if (-not $summary.metrics_reset_ok) { throw "Metrics reset failed" }

  Write-Host "`n✅ A6a regression passed." -ForegroundColor Green
  exit 0
}
catch {
  Write-Host "`n❌ A6a regression FAILED: $($_.Exception.Message)" -ForegroundColor Red
  Write-Host (J $summary)
  exit 1
}
