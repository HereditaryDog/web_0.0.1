$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

& "$projectRoot\.venv\Scripts\python.exe" manage.py collectstatic --noinput
& "$projectRoot\.venv\Scripts\python.exe" manage.py migrate
& "$projectRoot\.venv\Scripts\waitress-serve.exe" --listen=0.0.0.0:8000 config.wsgi:application
