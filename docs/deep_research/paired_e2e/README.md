# GLM / DeepSeek single-paper paired design

两份 plan 使用同一 approved single-paper task、brief、冻结 corpus、Planner/Writer prompt hashes、Executor/Validator、token caps、calls、retry、replan、timeout 和 replay 合同，仅 provider、model、endpoint、native currency/pricing 与 credential 环境变量不同。两份 plan 的 attempt/run/artifact identity 独立，禁止 fallback、hot switch、择优重试或先改另一方配置。

- GLM：`glm-5.3-flash` / CNY native pricing，沿用现有 GLM adapter；
- DeepSeek：`deepseek-flash` / USD peak pricing，使用新的 cache-aware adapter；
- 两者均 text-only、thinking enabled、Planner `low`、Writer `high`、2 calls、2 attempts、0 retries、1 replan、60s operation、180s run；
- 每一方先单独执行一次，terminal、grounding、claims/citations、replay zero calls、tokens、provider-native actual cost、client elapsed 和 author review 均预注册；不自动判定语义优胜。

两份 plan 当前均为 dry-run/preflight design freeze，artifact 目录必须不存在。`paired_cli` 的 `--execute` 仍保留为后续单独授权入口；本轮不读取任何 credential、不发 Provider 请求。

安全执行模板（仅在分别授权后使用；每个 provider 只在当前 PowerShell 进程设置对应环境变量，退出前清除）：

```powershell
$secureKey = Read-Host "GLM API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:ZHIPUAI_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  python -m litflow.deep_research.paired_cli --plan docs/deep_research/paired_e2e/paired_glm_single_paper_plan.json --execute
} finally {
  $env:ZHIPUAI_API_KEY = $null
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```

```powershell
$secureKey = Read-Host "DeepSeek API key" -AsSecureString
$bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
try {
  $env:DEEPSEEK_API_KEY = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($bstr)
  python -m litflow.deep_research.paired_cli --plan docs/deep_research/paired_e2e/paired_deepseek_single_paper_plan.json --execute
} finally {
  $env:DEEPSEEK_API_KEY = $null
  [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}
```
