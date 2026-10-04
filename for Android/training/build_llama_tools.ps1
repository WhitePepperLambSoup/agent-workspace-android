param(
    [string]$SourceDirectory = (Join-Path $PSScriptRoot '../kotlin_app/.cxx/Debug/313v243c/arm64-v8a/_deps/llama_cpp-src'),
    [string]$BuildDirectory = (Join-Path $PSScriptRoot '../../output/qwen-agent-training/llama-host')
)
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path -LiteralPath $SourceDirectory).Path
$build = [System.IO.Path]::GetFullPath($BuildDirectory)
$sdkRoot = if ($env:ANDROID_HOME) { $env:ANDROID_HOME } else { Join-Path $env:LOCALAPPDATA 'Android/Sdk' }
$sdkCmake = Join-Path $sdkRoot 'cmake/3.22.1/bin'
$developerShell = 'C:/Program Files (x86)/Microsoft Visual Studio/2022/BuildTools/Common7/Tools/VsDevCmd.bat'
# Import the compiler environment locally; do not print system environment values.
$compilerEnvironment = & $env:ComSpec /d /c "`"$developerShell`" -arch=x64 -host_arch=x64 >nul && set"
if ($LASTEXITCODE -ne 0) { throw 'Unable to initialize MSVC' }
foreach ($line in $compilerEnvironment) {
    if ($line -match '^([^=]+)=(.*)$') {
        [System.Environment]::SetEnvironmentVariable($Matches[1], $Matches[2], 'Process')
    }
}
& "$sdkCmake/cmake.exe" -S $source -B $build -G Ninja `
    "-DCMAKE_MAKE_PROGRAM=$sdkCmake/ninja.exe" -DCMAKE_BUILD_TYPE=Release `
    -DBUILD_SHARED_LIBS=OFF -DGGML_NATIVE=OFF -DLLAMA_CURL=OFF `
    -DLLAMA_BUILD_TESTS=OFF -DLLAMA_BUILD_EXAMPLES=OFF -DLLAMA_BUILD_TOOLS=ON
if ($LASTEXITCODE -ne 0) { throw 'llama.cpp configure failed' }
& "$sdkCmake/cmake.exe" --build $build --target llama-quantize llama-cli llama-completion --parallel 2
if ($LASTEXITCODE -ne 0) { throw 'llama.cpp host tools build failed' }
