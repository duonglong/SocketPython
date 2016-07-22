from subprocess import Popen
from win32process import DETACHED_PROCESS

pid = Popen("python.exe", "long_run.py"],creationflags=DETACHED_PROCESS,shell=True).pid
print pid
print 'done'
