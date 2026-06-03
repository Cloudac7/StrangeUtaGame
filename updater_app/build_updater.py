"""打包 Updater —— 跨平台独立更新可执行文件。

输出位置（由平台决定）：
  Windows: ``<repo>/updater_app/dist/Updater.exe``
  Linux:   ``<repo>/updater_app/dist/Updater``
  macOS:   ``<repo>/updater_app/dist/Updater``

主程序 ``build.py`` 会自动把 Updater 复制到 ``dist/StrangeUtaGame/``。

使用:

.. code:: bash

    python updater_app/build_updater.py
    python updater_app/build_updater.py --clean
    python updater_app/build_updater.py --skip-if-exists
    python updater_app/build_updater.py --app-version 1.0.7

设计权衡:

* ``--onefile`` —— Updater 是一次性流程，体积比启动速度更重要。
* ``--console`` —— 用户能看到控制台进度（与 March7thAssistant 一致）。
* 不引入 PyQt6 等重依赖；只走标准库 + ``requests``，约 12~16 MB。
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def _force_utf8_stdio() -> None:
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()

PROJECT_ROOT = Path(__file__).resolve().parent
REPO_ROOT = PROJECT_ROOT.parent


def _updater_name() -> str:
    """返回当前平台 Updater 二进制文件名。"""
    return "Updater.exe" if sys.platform == "win32" else "Updater"


def _output_path() -> Path:
    """返回 Updater 产物的完整路径（PyInstaller --distpath 内）。"""
    return PROJECT_ROOT / "dist" / _updater_name()


def _icon_path() -> str | None:
    """返回适合当前平台的图标路径，无可用图标时返回 None。"""
    icon_ico = REPO_ROOT / "src" / "strange_uta_game" / "resource" / "icon.ico"
    if sys.platform == "win32" and icon_ico.exists():
        return str(icon_ico)
    # macOS: 需要 .icns 格式
    if sys.platform == "darwin":
        icon_icns = icon_ico.with_suffix(".icns")
        if icon_icns.exists():
            return str(icon_icns)
    # Linux / 无合适图标 → 跳过
    return None


def _read_updater_version() -> str:
    """读取 updater_app 自身的版本号。"""
    try:
        from updater_app import __version__ as ver
        return ver
    except ImportError:
        return "0.0.0"


def _should_skip(output_bin: Path, app_version: str) -> bool:
    """已存在且版本匹配 → 跳过重建。"""
    if not output_bin.exists():
        return False
    # 简单校验：文件 > 1 MB 视为有效（PyInstaller onefile 产物不会太小）
    if output_bin.stat().st_size < 1_000_000:
        return False
    return True


def main() -> int:
    ap = argparse.ArgumentParser(description="打包 Updater（跨平台）")
    ap.add_argument(
        "--clean",
        action="store_true",
        default=False,
        help="传给 PyInstaller --clean，完整重建",
    )
    ap.add_argument(
        "--skip-if-exists",
        action="store_true",
        default=False,
        help="产物已存在且有效时跳过重建（用于 CI 缓存加速）",
    )
    ap.add_argument(
        "--app-version",
        default="",
        help="主程序版本号（填入 Updater 元数据）；默认从 updater_app/__init__.py 读取",
    )
    cli = ap.parse_args()

    app_version = cli.app_version or _read_updater_version()
    output_bin = _output_path()

    # ── 增量跳过 ──
    if cli.skip_if_exists and _should_skip(output_bin, app_version):
        size_mb = output_bin.stat().st_size / 1024 / 1024
        print(f"✓ Updater 已存在 ({size_mb:.1f} MB)，跳过重建")
        return 0

    # ── 检查 PyInstaller ──
    try:
        import PyInstaller.__main__  # noqa: F401
    except ImportError:
        print("缺少 pyinstaller。请先 `pip install pyinstaller`。", file=sys.stderr)
        return 1

    # ── 构建参数 ──
    args = [
        str(PROJECT_ROOT / "main.py"),
        "--name=Updater",
        "--onefile",
        "--console",          # Updater 走控制台 UI
        "--noconfirm",
        "--distpath", str(PROJECT_ROOT / "dist"),
        "--workpath", str(PROJECT_ROOT / "build"),
        "--specpath", str(PROJECT_ROOT),
        # ── 仅依赖标准库 + requests ──
        "--hidden-import=requests",
        "--hidden-import=urllib3",
        "--hidden-import=charset_normalizer",
        "--hidden-import=idna",
        "--hidden-import=certifi",
        # ── 易被 --exclude-module 副作用漏掉的标准库 ──
        "--hidden-import=colorsys",
        "--hidden-import=encodings",
        "--hidden-import=encodings.idna",
        "--hidden-import=encodings.utf_8",
        "--hidden-import=encodings.utf_8_sig",
        "--hidden-import=encodings.cp1252",
        "--hidden-import=encodings.cp437",
        "--hidden-import=encodings.cp65001",
        "--hidden-import=encodings.gbk",
        "--hidden-import=encodings.mbcs",
        "--hidden-import=hashlib",
        "--hidden-import=zipfile",
        "--hidden-import=tempfile",
        "--hidden-import=ssl",
        "--hidden-import=_ssl",
        # ── 排除主程序的重型依赖，缩小体积 ──
        "--exclude-module=PyQt6",
        "--exclude-module=qfluentwidgets",
        "--exclude-module=numpy",
        "--exclude-module=sounddevice",
        "--exclude-module=soundfile",
        "--exclude-module=pedalboard",
        "--exclude-module=av",
        "--exclude-module=jaconv",
        "--exclude-module=matplotlib",
        "--exclude-module=scipy",
        "--exclude-module=tkinter",
    ]

    # 图标
    icon = _icon_path()
    if icon:
        args.append(f"--icon={icon}")

    if cli.clean:
        args.append("--clean")

    # ── 执行构建 ──
    import PyInstaller.__main__ as pi_main
    print(f"开始打包 Updater ({app_version}) ...")
    print(f"  目标: {output_bin}")
    pi_main.run(args)
    print()

    if output_bin.exists():
        size_mb = output_bin.stat().st_size / 1024 / 1024
        print(f"✓ 打包完成: {output_bin}")
        print(f"  体积: {size_mb:.1f} MB")
    else:
        print(f"! 未找到 {output_bin}，请检查 PyInstaller 输出。")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
