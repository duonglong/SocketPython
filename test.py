from win32com.client import Dispatch

wscript = Dispatch("WScript.Shell")
wscript.AppActivate("Choose File to Upload")
wscript.SendKeys("%d C:\Users\Administrator %n Git-2.9.2-32-bit.exe {ENTER}")
