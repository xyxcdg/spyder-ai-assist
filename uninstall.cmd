@echo off
title Spyder AI Assist Uninstall
powershell -NoProfile -ExecutionPolicy Bypass -Command "& {$p=$null; $sp=Get-Command spyder -ErrorAction SilentlyContinue; if($sp){$q=Join-Path (Split-Path $sp.Source) 'python.exe'; if(Test-Path $q){$p=$q}}; if(-not $p){$p='python'}; Write-Host ('Using Python: ' + $p); & $p -m pip uninstall -y spyder-ai-assist; Write-Host ''; Write-Host 'Uninstalled. Restart Spyder to take effect.'; Read-Host 'Press Enter to exit'}"
