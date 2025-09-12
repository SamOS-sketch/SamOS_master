param(
  [string]$BaseUrl = "http://127.0.0.1:8000",
  [int]$FailCount = 5
)

$ErrorActionPreference = "Stop"

function say($msg,[ConsoleColor]$c="Gray"){ $old=$host.UI.RawUI.ForegroundColor; $host.UI.RawUI.ForegroundColor=$c; Write-Host $msg; $host.UI.RawUI.ForegroundColor=$old }
function json($o){ $o | ConvertTo-Json -Depth 8 }

$ok = $true
$summary = @{
  health_ok              = $false
  session_started        = $false
  happy_path_ok          = $false
  fail_count_after_forced= 0
  pulse_reset_ok         = $false
  metrics_reset_ok       = $false
  ok_count_after_happy   = 0
}

try {
  say "1) Health" Cyan
  $health = Invoke-RestMethod "$BaseUrl/health"
  $summary.health_ok = $true

  say "2) Start session" Cyan
  $s = Invoke-RestMethod -Method POST "$BaseUrl/session/start"
  $summary.session_started = $true

  say "3) Happy path image (stub)" Cyan
  $okBody = @{ session_id = $s.session_id; prompt = "sanity ok" } | ConvertTo-Json
  $okResp = Invoke-RestMethod -Method POST "$BaseUrl/image/generate" -ContentType 'application/json' -Body $okBody
  $summary.happy_path_ok = $true

  say "4) Metrics (pre-fail)" DarkCyan
  $m1 = Invoke-RestMethod "$BaseUrl/metrics"
  $summary.ok_count_after_happy = [int]$m1."image.ok"

  say "5) Force failures x$FailCount" Cyan
  $failBody = @{ session_id = $s.session_id; prompt = "pulse test [force-fail]" } | ConvertTo-Json
  1..$FailCount | ForEach-Object {
    try { Invoke-RestMethod -Method POST "$BaseUrl/image/generate" -ContentType 'application/json' -Body $failBody } catch {}
  }
  $m2 = Invoke-RestMethod "$BaseUrl/metrics"
  $summary.fail_count_after_forced = [int]$m2."image.fail"

  say "6) Recent pulse alerts" DarkCyan
  $alerts = Invoke-RestMethod "$BaseUrl/events?kind=pulse.alert&limit=3"

  say "7) Reset pulse window" Cyan
  $pr = Invoke-RestMethod "$BaseUrl/pulse/reset"
  if ($pr.ok -and ($pr.cleared -or $pr.noop)) { $summary.pulse_reset_ok = $true }

  say "8) Reset metrics (also buckets)" Cyan
  $mr = Invoke-RestMethod -Method POST "$BaseUrl/metrics/reset?also_buckets=true"
  if ($mr.ok) { $summary.metrics_reset_ok = $true }

  say "9) Verify metrics cleared" DarkCyan
  $m3 = Invoke-RestMethod "$BaseUrl/metrics"
  # (no strict assert here; just show)

  say "==> Result snapshot" Green
  json @{
    ok_image          = $okResp
    metrics_before    = $m1
    metrics_after_fail= $m2
    pulse_alerts      = $alerts
    pulse_reset       = $pr
    metrics_reset     = $mr
    metrics_after     = $m3
  }

} catch {
  $ok = $false
  say "Smoke failed: $($_.Exception.Message)" Red
} finally {
  say "`n==> Summary" Yellow
  json $summary
  if ($ok -and $summary.health_ok -and $summary.session_started -and $summary.happy_path_ok -and $summary.pulse_reset_ok -and $summary.metrics_reset_ok) {
    say "`n✅ smoke passed." Green
    exit 0
  } else {
    say "`n❌ smoke failed." Red
    exit 1
  }
}
