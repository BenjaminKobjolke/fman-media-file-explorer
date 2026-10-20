@echo off
setlocal
set "PYTHONPATH=%FMAN_SRC%;%~dp0.."
python -m unittest discover -s "%~dp0..\tests\integration" -p "test_*.py"
exit /b %errorlevel%
