!define STORYGRAPH_INSTALLER_HOOK_DIR "${__FILEDIR__}"

LangString storygraphBackendLocked ${LANG_ENGLISH} "The backend executable could not be released for this update. No application files have been replaced. Quit StoryGraph from its tray menu, then run this installer again."
LangString storygraphBackendLocked ${LANG_SIMPCHINESE} "后端程序文件仍被占用或无法写入，本次尚未替换应用文件。请从托盘菜单退出 StoryGraph，再重新运行安装程序。"

!macro NSIS_HOOK_PREINSTALL
  ; Older clients may leave their PyInstaller child alive. Run this before the
  ; template copies either executable so failure cannot produce mixed versions.
  !insertmacro CheckIfAppIsRunning "${MAINBINARYNAME}.exe" "${PRODUCTNAME}"
  InitPluginsDir
  File "/oname=$PLUGINSDIR\storygraph-update-check.ps1" "${STORYGRAPH_INSTALLER_HOOK_DIR}\check-backend-update.ps1"
  ${If} ${RunningX64}
    StrCpy $R8 "$WINDIR\Sysnative\WindowsPowerShell\v1.0\powershell.exe"
  ${Else}
    StrCpy $R8 "$SYSDIR\WindowsPowerShell\v1.0\powershell.exe"
  ${EndIf}
  nsExec::ExecToStack /TIMEOUT=20000 '"$R8" -NoLogo -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\storygraph-update-check.ps1" -InstallDir "$INSTDIR"'
  Pop $R8
  Pop $R9
  ${If} $R8 != "0"
    SetErrorLevel 2
    MessageBox MB_OK|MB_ICONSTOP "$(storygraphBackendLocked)" /SD IDOK
    Abort "$(storygraphBackendLocked)"
  ${EndIf}
!macroend
