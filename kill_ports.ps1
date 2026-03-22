# tailorCV - Kill processes occupying ports (Enhanced Version)
# Usage: powershell -ExecutionPolicy Bypass -File kill_ports.ps1

# 扩展端口范围：常用开发端口 + tailorCV 相关端口
$ports = @(5000, 5001, 5002, 5003, 5004, 6001, 6002, 8000, 8001, 8080, 8888)
$killed = 0
$failed = 0

Write-Host "Scanning ports: $($ports -join ', ')..." -ForegroundColor Gray

foreach ($port in $ports) {
    $connections = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    foreach ($conn in $connections) {
        $pid = $conn.OwningProcess
        try {
            $process = Get-Process -Id $pid -ErrorAction Stop
            $processName = $process.ProcessName
            Stop-Process -Id $pid -Force -ErrorAction Stop
            Write-Host "  [KILLED] PID $pid ($processName) on port $port" -ForegroundColor Green
            $killed++
        } catch {
            Write-Host "  [FAILED] PID $pid on port $port (need admin?)" -ForegroundColor Red
            $failed++
        }
    }
}

Write-Host ""
Write-Host "Summary: $killed killed, $failed failed" -ForegroundColor $(if ($killed -gt 0) { "Green" } else { "Yellow" })

# 检查是否还有残留
Start-Sleep -Milliseconds 500
$remaining = 0
foreach ($port in $ports) {
    $r = Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue
    if ($r) { $remaining += @($r).Count }
}

if ($remaining -gt 0) {
    Write-Host "Warning: $remaining port(s) still in use" -ForegroundColor Yellow
    Write-Host "Try running as Administrator for full cleanup" -ForegroundColor Yellow
} else {
    Write-Host "All ports released successfully!" -ForegroundColor Green
}
