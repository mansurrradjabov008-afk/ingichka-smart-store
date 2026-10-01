Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

' pythonw.exe orqali oynasiz (yashirin fonda) ishga tushirish
pythonwPath = "C:\Users\BRand\AppData\Local\Programs\Python\Python311\pythonw.exe"
scriptPath = currentDir & "\bot_supervisor.py"

cmd = """" & pythonwPath & """ """ & scriptPath & """"
WshShell.CurrentDirectory = currentDir
WshShell.Run cmd, 0, False
