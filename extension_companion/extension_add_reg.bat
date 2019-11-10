@echo off
REM dir of script
REM was using script_dir = %~dp0
REM The space before the = is interpreted as part of the name, and the space after it are interpreted as part of the value
REM %~dp0 ends in a slash
REM To remove the final backslash, you can use the :n,m substring syntax: %script_dir:~0,-1%
set script_dir=%~dp0
REG ADD "HKEY_CURRENT_USER\SOFTWARE\Mozilla\NativeMessagingHosts\fourcdl" /ve /d "%script_dir%extension_comm_manifest.json" /f
REG ADD "HKEY_LOCAL_MACHINE\SOFTWARE\Mozilla\NativeMessagingHosts\fourcdl" /ve /d "%script_dir%extension_comm_manifest.json" /f