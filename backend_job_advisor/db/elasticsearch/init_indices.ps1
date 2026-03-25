# PowerShell：创建 ES 索引（需本机 ES 已启动，默认无认证）
$ErrorActionPreference = "Stop"
$base = "http://localhost:9200"
$root = Split-Path -Parent $MyInvocation.MyCommand.Path

foreach ($pair in @(
    @{ Name = "job_advisor_facts"; File = "job_advisor_facts.json" },
    @{ Name = "job_advisor_jobs"; File = "job_advisor_jobs.json" }
)) {
    $uri = "$base/$($pair.Name)"
    $body = Get-Content (Join-Path $root $pair.File) -Raw -Encoding UTF8
    try {
        Invoke-RestMethod -Method Put -Uri $uri -ContentType "application/json" -Body $body
        Write-Host "OK: PUT $uri"
    } catch {
        Write-Host "FAIL: $uri — $($_.Exception.Message)"
        throw
    }
}
