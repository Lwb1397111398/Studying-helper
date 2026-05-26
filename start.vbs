Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
projectPath = fso.GetParentFolderName(WScript.ScriptFullName)

' 创建必要目录
Dim backendPath, frontendPath
backendPath = projectPath & "\backend"
frontendPath = projectPath & "\frontend"

If Not fso.FolderExists(backendPath & "\data\files") Then
    fso.CreateFolder backendPath & "\data\files"
End If
If Not fso.FolderExists(backendPath & "\data\backups") Then
    fso.CreateFolder backendPath & "\data\backups"
End If

' 启动后端（最小化窗口）
WshShell.Run "cmd /c cd /d """ & backendPath & """ && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000", 7, False

' 等待后端启动
WScript.Sleep 5000

' 启动前端（最小化窗口）
WshShell.Run "cmd /c cd /d """ & frontendPath & """ && npm run dev", 7, False

' 等待前端启动
WScript.Sleep 5000

' 打开浏览器
WshShell.Run "http://localhost:3000", 1, False
