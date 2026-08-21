# TCAD 분석기를 배포용 .exe로 빌드한다.
# 코드를 고친 뒤에는 이 스크립트만 다시 실행하면 dist\TCAD_Analyzer.exe가 새로 만들어진다.
# 사용법: 프로젝트 폴더에서 `powershell -ExecutionPolicy Bypass -File .\build_exe.ps1`
#         (또는 VS Code 터미널에서 `.\build_exe.ps1`)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

Write-Host "이전 빌드 결과물 정리 중..."
Remove-Item -Recurse -Force build, dist -ErrorAction SilentlyContinue

Write-Host "PyInstaller로 exe 빌드 중... (처음엔 몇 분 걸릴 수 있습니다)"
& ".\.venv\Scripts\python.exe" -m PyInstaller `
    --name TCAD_Analyzer `
    --onefile `
    --windowed `
    --paths src `
    --collect-all matplotlib `
    --clean `
    --noconfirm `
    run_app.py

if ($LASTEXITCODE -ne 0) {
    Write-Host "빌드 실패 — 위 에러 메시지를 확인하세요." -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "완료! dist\TCAD_Analyzer.exe 를 확인하세요." -ForegroundColor Green
