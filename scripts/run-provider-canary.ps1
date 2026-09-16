param(
    [Parameter(Mandatory=$true)][ValidateSet('zhipu-bigmodel','deepseek')][string]$Provider,
    [Parameter(Mandatory=$true)][string]$Plan,
    [string]$Python = '.\.venv\Scripts\python.exe'
)

$planObject = Get-Content -LiteralPath $Plan -Raw | ConvertFrom-Json
if ($planObject.provider -ne $Provider) { throw 'Provider does not match frozen plan.' }
$artifactPath = $planObject.artifact_dir
if (Test-Path -LiteralPath $artifactPath) { throw 'Frozen artifact directory already exists; refusing to overwrite.' }
$secureKey = Read-Host "$Provider API key" -AsSecureString
$keyPointer = [IntPtr]::Zero
$credentialVariable = [string]$planObject.credential_environment_variable
try {
    $keyPointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($secureKey)
    [Environment]::SetEnvironmentVariable($credentialVariable, [Runtime.InteropServices.Marshal]::PtrToStringBSTR($keyPointer), 'Process')
    [Environment]::SetEnvironmentVariable('LITFLOW_PAIRED_EXECUTE_RUN_ID', [string]$planObject.run_id, 'Process')
    & $Python -m litflow.deep_research.paired_cli --plan $Plan --artifact-dir $artifactPath --execute
    $exitCode = $LASTEXITCODE
} finally {
    [Environment]::SetEnvironmentVariable($credentialVariable, $null, 'Process')
    [Environment]::SetEnvironmentVariable('LITFLOW_PAIRED_EXECUTE_RUN_ID', $null, 'Process')
    if ($keyPointer -ne [IntPtr]::Zero) { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($keyPointer) }
    $secureKey = $null
    $keyPointer = [IntPtr]::Zero
}
Write-Output ("provider=$Provider exit_code=$exitCode artifact=$artifactPath")
if (Test-Path -LiteralPath $artifactPath) {
    Get-ChildItem -LiteralPath $artifactPath -File | ForEach-Object { Write-Output ("artifact_file=$($_.Name) bytes=$($_.Length)") }
}
exit $exitCode
