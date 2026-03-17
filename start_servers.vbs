Set WshShell = CreateObject("WScript.Shell")
WshShell.CurrentDirectory = "c:\Users\DELL\OneDrive\Desktop\AIAC\project"
WshShell.Run "pythonw web_app.py", 0, False
WshShell.Run "pythonw admin_app.py", 0, False
