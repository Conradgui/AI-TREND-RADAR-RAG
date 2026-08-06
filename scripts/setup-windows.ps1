$ErrorActionPreference = 'Stop'

$projectRoot = Split-Path -Parent $PSScriptRoot
Set-Location $projectRoot

function Stop-WithMessage([string] $message) {
    Write-Host $message -ForegroundColor Yellow
    Read-Host '按回车键退出'
    exit 1
}

docker info *> $null
if ($LASTEXITCODE -ne 0) {
    Stop-WithMessage 'Docker Desktop 尚未运行。请先启动 Docker Desktop，再重新双击 setup.bat。'
}

$envPath = Join-Path $projectRoot '.env'
if (Test-Path $envPath) {
    Write-Host '.env 已存在，为保护已有配置，本向导不会覆盖它。' -ForegroundColor Yellow
    Write-Host '如需重新配置，请先备份并手动删除 .env 后再运行本向导。'
    Read-Host '按回车键启动已有配置'
    & (Join-Path $projectRoot 'start.bat')
    exit $LASTEXITCODE
}

Write-Host 'AI Trend Radar RAG 首次配置' -ForegroundColor Cyan
Write-Host '只需一个模型 Provider 的 API Key；密钥仅保存在本机 .env，不会写入 Git。'
$provider = (Read-Host '请选择 Provider [deepseek/anthropic/openai]（默认 deepseek）').Trim().ToLowerInvariant()
if ([string]::IsNullOrWhiteSpace($provider)) { $provider = 'deepseek' }
if ($provider -notin @('deepseek', 'anthropic', 'openai')) {
    Stop-WithMessage "不支持的 Provider：$provider"
}

$secureKey = Read-Host "请输入 $provider API Key（输入不会显示）" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
    $providerKey = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
}
finally {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ([string]::IsNullOrWhiteSpace($providerKey)) {
    Stop-WithMessage 'API Key 不能为空。'
}

$lines = @(
    "LLM_PROVIDER=$provider",
    'DEEPSEEK_API_KEY=',
    'ANTHROPIC_API_KEY=',
    'OPENAI_API_KEY=',
    "NEO4J_PASSWORD=$([Guid]::NewGuid().ToString('N'))",
    'RAG_ENABLE_DEEP_FETCH=false',
    'RAG_CORPUS_RECHECK_DAYS=30'
)

switch ($provider) {
    'deepseek'  { $lines[1] = "DEEPSEEK_API_KEY=$providerKey" }
    'anthropic' { $lines[2] = "ANTHROPIC_API_KEY=$providerKey" }
    'openai'    { $lines[3] = "OPENAI_API_KEY=$providerKey" }
}

[System.IO.File]::WriteAllLines($envPath, $lines, [System.Text.UTF8Encoding]::new($false))
$providerKey = $null

Write-Host '配置已保存到本机 .env。现在开始启动服务。' -ForegroundColor Green
& (Join-Path $projectRoot 'start.bat')
exit $LASTEXITCODE
