Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

' pythonw.exe orqali oynasiz (yashirin fonda) to'g'ridan-to'g'ri bot ilovasini ishga tushirish
pythonwPath = "C:\Users\BRand\AppData\Local\Programs\Python\Python311\pythonw.exe"
scriptPath = currentDir & "\bot\bot_app.py"

cmd = """" & pythonwPath & """ """ & scriptPath & """"
WshShell.CurrentDirectory = currentDir
WshShell.Run cmd, 0, False
