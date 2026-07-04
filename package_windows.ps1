$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$dist = Join-Path $root "dist"
$bundle = Join-Path $dist "PaddleOCR-GUI"
$zip = Join-Path $dist "PaddleOCR-GUI-windows-x64.zip"
$spec = Join-Path $root "bundle\PaddleOCR-GUI.spec"
$buildLog = Join-Path $dist "pyinstaller-build.log"
$buildOut = Join-Path $dist "pyinstaller-build.out.log"
$buildErr = Join-Path $dist "pyinstaller-build.err.log"

if (-not (Test-Path -LiteralPath $spec)) {
    throw "Missing PyInstaller spec: $spec"
}

Push-Location $root
try {
    uv sync --dev --extra ocr --extra gpu --python 3.13
    $baiduUtils = Join-Path $root ".venv\Lib\site-packages\baidubce\utils.py"
    if (Test-Path -LiteralPath $baiduUtils) {
        $content = Get-Content -LiteralPath $baiduUtils -Raw
        $fixedContent = $content.Replace(
            "compile_ip=re.compile(b'((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})(.((2(5[0-5]|[0-4]\d))|[0-1]?\d{1,2})){3}')",
            "compile_ip=re.compile(b'((2(5[0-5]|[0-4]\\d))|[0-1]?\\d{1,2})(\\.((2(5[0-5]|[0-4]\\d))|[0-1]?\\d{1,2})){3}')"
        )
        if ($fixedContent -ne $content) {
            Set-Content -LiteralPath $baiduUtils -Value $fixedContent -NoNewline -Encoding UTF8
        }
    }
    if (-not (Test-Path -LiteralPath $dist)) {
        New-Item -ItemType Directory -Path $dist | Out-Null
    }
    $arguments = @("run", "pyinstaller", "--noconfirm", "--clean", "--log-level", "ERROR", $spec)
    $process = Start-Process -FilePath "uv" -ArgumentList $arguments -WorkingDirectory $root -RedirectStandardOutput $buildOut -RedirectStandardError $buildErr -Wait -PassThru
    Get-Content -LiteralPath $buildOut, $buildErr | Set-Content -LiteralPath $buildLog
    if ($process.ExitCode -ne 0) {
        Get-Content -LiteralPath $buildLog
        throw "PyInstaller failed; see $buildLog"
    }

    if (-not (Test-Path -LiteralPath $bundle)) {
        throw "PyInstaller did not create $bundle"
    }

    Copy-Item -LiteralPath "README.md" -Destination (Join-Path $bundle "README.md") -Force

    $notes = @"
PaddleOCR-GUI Windows x64 bundle

Run:
  PaddleOCR-GUI.exe

Agent/CLI use:
  PaddleOCR-GUI-CLI.exe convert input.pdf --out output --format markdown --vl-server-url http://127.0.0.1:8118/v1 --agent

Before converting PDFs, start an optimized PaddleOCR-VL server and set:
  PADDLEOCR_VL_SERVER_URL=http://127.0.0.1:8118/v1

This bundle includes the Python runtime, PySide6/Qt files, PaddleOCR client code,
PaddlePaddle GPU runtime files, and NVIDIA CUDA 12.9 DLL package files collected
from the locked UV environment.
"@
    Set-Content -LiteralPath (Join-Path $bundle "RUN-PADDLEOCR-GUI.txt") -Value $notes -Encoding UTF8

    if (Test-Path -LiteralPath $zip) {
        Remove-Item -LiteralPath $zip -Force
    }
    Compress-Archive -Path $bundle -DestinationPath $zip -Force
    Write-Output "Created $zip"
}
finally {
    Pop-Location
}
