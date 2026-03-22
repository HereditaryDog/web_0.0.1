$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

& "$projectRoot\.venv\Scripts\python.exe" manage.py migrate
& "$projectRoot\.venv\Scripts\python.exe" manage.py runserver
