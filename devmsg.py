from datetime import datetime
from os import path
import sys
import traceback


def devmsg(msg):
    ts = datetime.now().time()
    c = sys._getframe().f_back.f_code.co_name
    f = path.basename(sys._getframe().f_back.f_code.co_filename)
    l = sys._getframe().f_back.f_lineno
    spc = " " * sys._getframe().f_back.f_code.co_stacksize
    if (msg == "trace"):
        print(f"{ts}{spc}{f} {c} {l}: tracing...", flush=True)
        traceback.print_stack()
        return
    print(f"{ts}{spc}{f} {c} {l}: {msg}")
    return
