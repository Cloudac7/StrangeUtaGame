"""Qt 后台线程的退出清理工具。"""

from __future__ import annotations

import logging
from typing import Iterable

from PyQt6.QtCore import QObject, QThread

log = logging.getLogger(__name__)


def stop_qthread(thread: QThread, timeout_ms: int = 3000) -> bool:
    """请求 ``thread`` 退出并等待，必要时在应用退出阶段强制终止。"""
    try:
        if not thread.isRunning():
            return True
        thread.requestInterruption()
        thread.quit()
        if thread.wait(max(0, timeout_ms)):
            return True

        log.warning("后台 QThread 未在 %dms 内退出，执行终止兜底", timeout_ms)
        thread.terminate()
        return thread.wait(1000)
    except RuntimeError:
        # C++ 对象可能已由其它 finished/deleteLater 路径释放。
        return True


def stop_child_qthreads(owner: QObject, timeout_ms: int = 3000) -> bool:
    """停止 ``owner`` 对象树内仍在运行的全部 ``QThread``。"""
    try:
        threads: Iterable[QThread] = owner.findChildren(QThread)
    except RuntimeError:
        return True

    ok = True
    current = QThread.currentThread()
    for thread in list(threads):
        if thread is current:
            continue
        ok = stop_qthread(thread, timeout_ms=timeout_ms) and ok
    return ok
