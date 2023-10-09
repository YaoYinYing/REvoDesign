@echo off

setlocal

set "git_repo_dir=%~dp0"
set "pymol_startup_dir=%USERPROFILE%\.pymol\startup"
set "revo_design_dir=%git_repo_dir%\REvoDesign"

REM Ensure the REvoDesign directory exists in the git repository
if not exist "%revo_design_dir%" (
    echo The REvoDesign directory does not exist in the git repository.
    exit /b 1
)

REM Remove the existing REvoDesign directory
if exist "%pymol_startup_dir%\REvoDesign" (
    rmdir /s /q "%pymol_startup_dir%\REvoDesign"
)

REM Copy the REvoDesign directory from the git repository to the PyMOL startup directory
xcopy /e /i "%revo_design_dir%" "%pymol_startup_dir%\REvoDesign"

endlocal
