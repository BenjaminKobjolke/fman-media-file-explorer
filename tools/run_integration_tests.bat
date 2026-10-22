@echo off
setlocal
set "PYTHONPATH=%~dp0..\tests\fman-stubs;%FMAN_SRC%;%~dp0.."
python -m unittest discover -s "%~dp0..\tests\integration" -p "test_*.py" -v
exit /b %errorlevel%
