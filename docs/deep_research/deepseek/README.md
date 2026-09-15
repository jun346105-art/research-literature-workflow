# DeepSeek V4.1 Flash Canary Contract

第五轮 Phase A-D 只冻结并实现受控的单次 text-only Canary adapter；本批不执行真实 Provider 请求，不读取 `DEEPSEEK_API_KEY`，不创建正式 Canary artifact。

冻结合同：

- provider `deepseek`，model code `deepseek-flash`（DeepSeek V4.1-Flash）
- endpoint `https://api.deepseek.com/chat/completions`
- Chat Completions JSON、non-streaming、JSON mode；thinking enabled
- Planner reasoning effort `low`；Writer 接入时使用 `high`
- 不启用 temperature、tools、Web、vision、video、files、parallel 或 fallback
- 单次 Canary 最多 1 call、0 retry、operation timeout 60s、run deadline 180s
- 预算币种 USD，hard limit `$0.02`
- peak pricing snapshot：cache miss input `$0.30/M`、output `$1.20/M`、cache hit input `$0.006/M`。完整 usage 必须包含 `prompt_tokens`、`completion_tokens`、`total_tokens`、`prompt_cache_hit_tokens`、`prompt_cache_miss_tokens`；计价为 `miss*0.30/M + hit*0.006/M + completion*1.20/M`，并验证 input split 与 total sum。

当前 immutable binding：implementation commit `b5e93f548a52e1bc0580bcfb5742be4358136a62`（允许其祖先之后的 plan/docs commit），runtime source fingerprint `d0c4f2f75fab94aab1f78e3997baabd40532eb2d60860f2dbea5d370931334d8`。

费用只按响应中的 `usage` reconcile；失败响应若带有完整 usage 也记账，attempt 按 ID 去重，replay 不调用 Provider、不重复计费。missing/inconsistent usage 不得完成 Canary。reasoning 内容只用于请求处理，不进入事件、checkpoint 或 artifact。

唯一未来真实执行命令（需用户在 clean worktree、确认 Key 已由外部环境注入后手动执行）：

```powershell
$secureKey = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  python -m litflow.deep_research.deepseek_cli --plan docs/deep_research/deepseek/canary_execution_plan.attempt-001.json --artifact-dir outputs/deep_research/canary/v1/dr-run-0381179dd264e4f8324c3214 --execute
} finally {
  $env:DEEPSEEK_API_KEY = $null
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

上面是唯一包含 `--execute` 的合同示例；本轮不运行它。

官方依据（访问日：2026-09-15）：

- [DeepSeek V4.1 release](https://api-docs.deepseek.com/news/news260910/)
- [Models and pricing](https://api-docs.deepseek.com/quick_start/pricing/)
- [Thinking mode](https://api-docs.deepseek.com/guides/thinking_mode/)
