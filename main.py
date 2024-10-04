from multiprocessing import Process
from multiprocessing import Pipe
import multiprocessing

import UI
import Deal

# 不加这个判断的话，使用多进程可能导致弹出不必要的窗口
if __name__ == "__main__":
    multiprocessing.freeze_support()

    ppp = Pipe()
    ui = UI.UI(800, 400, ppp[0])
    deal = Deal.Deal(ppp[1])

    # daemon 设为 True，会在进程无响应时关闭进程
    tr = Process(target=deal.run)
    tr.daemon = True
    tr.start()
    
    ui.run()
