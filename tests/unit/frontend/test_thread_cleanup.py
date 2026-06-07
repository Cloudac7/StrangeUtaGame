"""Qt 后台线程退出清理测试。"""

from PyQt6.QtCore import QObject, QThread

from strange_uta_game.frontend.thread_cleanup import (
    stop_child_qthreads,
    stop_qthread,
)


def test_stop_running_qthread(qtbot):
    thread = QThread()
    thread.start()
    qtbot.waitUntil(thread.isRunning, timeout=1000)

    assert stop_qthread(thread, timeout_ms=1000)
    assert not thread.isRunning()


def test_stop_child_qthreads(qtbot):
    owner = QObject()
    thread = QThread(owner)
    thread.start()
    qtbot.waitUntil(thread.isRunning, timeout=1000)

    assert stop_child_qthreads(owner, timeout_ms=1000)
    assert not thread.isRunning()
