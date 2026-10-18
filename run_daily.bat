@echo off
chcp 65001 > nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d C:\Users\butik\Documents\Control_Center
call venv\Scripts\activate.bat
python daily_auto.py >> data\scheduler\task_output.log 2>&1