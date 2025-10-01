# PowerShell脚本 - 运行CAB策略所有测试
param(
    [switch]$Verbose
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "🧪 运行CAB策略所有测试" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# 激活虚拟环境
Write-Host "🔧 激活虚拟环境..." -ForegroundColor Yellow
& "..\..\venv\Scripts\Activate.ps1"

$cabTests = @(
    @{
        Name = "CAB主测试"
        Path = "test\cab\test_closing_auction_bet.py"
        Description = "收盘竞价策略核心功能测试"
    },
    @{
        Name = "CAB动态参数测试"
        Path = "test\cab\test_dynamic_params.py"
        Description = "收盘竞价策略动态参数更新测试"
    },
    @{
        Name = "CAB演示脚本"
        Path = "test\cab\demo_closing_auction_bet.py"
        Description = "收盘竞价策略演示和参数展示"
    }
)

$totalTests = $cabTests.Count
$passedTests = 0
$failedTests = @()

Write-Host "📊 将运行 $totalTests 个CAB测试" -ForegroundColor Green
Write-Host ""

for ($i = 0; $i -lt $totalTests; $i++) {
    $test = $cabTests[$i]
    $testNumber = $i + 1
    
    Write-Host "========================================" -ForegroundColor Blue
    Write-Host "🧪 测试 $testNumber/$totalTests : $($test.Name)" -ForegroundColor Blue
    Write-Host "📝 描述: $($test.Description)" -ForegroundColor Gray
    Write-Host "📁 路径: $($test.Path)" -ForegroundColor Gray
    Write-Host "========================================" -ForegroundColor Blue
    
    try {
        $result = & python $test.Path 2>&1
        $exitCode = $LASTEXITCODE
        
        if ($exitCode -eq 0) {
            Write-Host "✅ $($test.Name) - 测试通过" -ForegroundColor Green
            $passedTests++
            
            if ($Verbose -and $result) {
                Write-Host "📤 输出:" -ForegroundColor Gray
                Write-Host $result -ForegroundColor White
            }
        } else {
            Write-Host "❌ $($test.Name) - 测试失败" -ForegroundColor Red
            $failedTests += $test.Name
            
            Write-Host "🚨 错误输出:" -ForegroundColor Red
            Write-Host $result -ForegroundColor Red
        }
    } catch {
        Write-Host "💥 $($test.Name) - 运行异常: $($_.Exception.Message)" -ForegroundColor Red
        $failedTests += $test.Name
    }
    
    Write-Host ""
}

# 输出总结
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📊 CAB测试总结" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "📈 总测试数: $totalTests" -ForegroundColor White
Write-Host "✅ 通过数量: $passedTests" -ForegroundColor Green
Write-Host "❌ 失败数量: $($totalTests - $passedTests)" -ForegroundColor Red
Write-Host "📊 通过率: $([math]::Round(($passedTests / $totalTests) * 100, 1))%" -ForegroundColor Yellow

if ($failedTests.Count -gt 0) {
    Write-Host ""
    Write-Host "❌ 失败的测试:" -ForegroundColor Red
    foreach ($failedTest in $failedTests) {
        Write-Host "  - $failedTest" -ForegroundColor Red
    }
}

Write-Host ""
if ($failedTests.Count -eq 0) {
    Write-Host "🎉 所有CAB测试都通过了！" -ForegroundColor Green
    exit 0
} else {
    Write-Host "⚠️  有 $($failedTests.Count) 个CAB测试失败" -ForegroundColor Yellow
    exit 1
}
