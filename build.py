"""打包脚本 - 使用 PyInstaller 打包 StrangeUtaGame（fugashi-only 分支）

注意事项：
1. sounddevice 和 soundfile 依赖 PortAudio / libsndfile，需要确保 DLL 被打包
2. PyQt6 有平台插件需要处理
3. 日语注音用 fugashi (MeCab) + unidic-lite；跨平台，无需 WinRT IME
4. numpy 是音频引擎核心依赖，不可排除
5. 使用 --onedir 模式避免单文件解压问题
6. fugashi 基于 Cython，打包时需要确保 _MeCab.dll / 词典文件被收集
"""

import argparse
import PyInstaller.__main__
import os
import sys
from pathlib import Path


def _force_utf8_stdio() -> None:
    """强制 stdout/stderr 使用 UTF-8。GitHub Actions Windows runner 默认 cp1252
    会让我们脚本里的中文 print 直接抛 UnicodeEncodeError。"""
    for stream_name in ("stdout", "stderr"):
        stream = getattr(sys, stream_name, None)
        if stream is None or not hasattr(stream, "reconfigure"):
            continue
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_force_utf8_stdio()

# 命令行参数
parser = argparse.ArgumentParser(description="PyInstaller 打包脚本")
parser.add_argument("--clean", action="store_true", help="传给 PyInstaller --clean，完整重建")
_cli_args = parser.parse_args()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()

# 检查依赖
print("检查依赖...")
try:
    import PyQt6
    import sounddevice
    import soundfile
    import pedalboard
    import qfluentwidgets
    import numpy
    import fugashi
    import unidic_lite
    import jaconv

    print("✓ 所有依赖已安装")
    # 打印版本信息
    print(f"  PyQt6: {PyQt6.QtCore.PYQT_VERSION_STR}")
    print(f"  sounddevice: {sounddevice.__version__}")
    print(f"  soundfile: {soundfile.__version__}")
    print(f"  pedalboard: {pedalboard.__version__}")
    print(f"  numpy: {numpy.__version__}")
    _fugashi_ver = "unknown"
    try:
        from importlib.metadata import version as _ver
        _fugashi_ver = _ver("fugashi")
    except Exception:
        pass
    print(f"  fugashi: {_fugashi_ver}")
    print(f"  jaconv: {getattr(jaconv, '__version__', 'unknown')}")
except ImportError as e:
    print(f"✗ 缺少依赖: {e}")
    print("请先运行: pip install -r requirements.txt")
    print("  pip install -e .[dev]")
    sys.exit(1)

# PyInstaller --add-data 分隔符：Windows 用 ;，Unix 用 :
_DATA_SEP = ";" if sys.platform == "win32" else ":"

# 构建 PyInstaller 参数
args = [
    "main.py",  # 主脚本
    "--name=StrangeUtaGame",  # 应用名称
    "--onedir",  # 使用目录模式（推荐，启动更快）
    "--windowed",  # 隐藏控制台窗口（macOS 生成 .app bundle）
    "--noconfirm",  # 不确认覆盖
    # 数据文件
    f"--add-data=src/strange_uta_game{_DATA_SEP}strange_uta_game",  # 源代码
    f"--add-data=src/strange_uta_game/resource/icon.ico{_DATA_SEP}strange_uta_game/resource",  # 图标
    f"--add-data=src/strange_uta_game/config/config.json{_DATA_SEP}strange_uta_game/config",  # 默认配置
    f"--add-data=src/strange_uta_game/config/dictionary.json{_DATA_SEP}strange_uta_game/config",  # 默认字典
    f"--add-data=src/strange_uta_game/config/singers.json{_DATA_SEP}strange_uta_game/config",  # 默认演唱者
    f"--add-data=src/strange_uta_game/config/e2k.txt{_DATA_SEP}strange_uta_game/config",  # 英语注音词典 (CMU-based)
    f"--add-data=src/strange_uta_game/config/cmudict-0.7b{_DATA_SEP}strange_uta_game/config",  # CMU Pronouncing Dictionary (e2k 引擎数据源)
    # ── 隐藏导入（PyInstaller 可能检测不到的模块） ──
    # 音频
    "--hidden-import=sounddevice",
    "--hidden-import=soundfile",
    "--hidden-import=pedalboard",
    "--hidden-import=pedalboard.io",
    "--hidden-import=pedalboard.io.AudioFile",
    "--hidden-import=pedalboard.io.StreamResampler",
    "--hidden-import=pedalboard.time_stretch",
    "--hidden-import=numpy",
    "--hidden-import=numpy.core",
    "--hidden-import=numpy.fft",
    "--hidden-import=numpy.lib",
    # 日语处理
    "--hidden-import=fugashi",
    "--hidden-import=unidic_lite",
    "--hidden-import=jaconv",
    # Qt / UI
    "--hidden-import=qfluentwidgets",
    "--hidden-import=PyQt6.sip",
    "--hidden-import=PyQt6.QtCore",
    "--hidden-import=PyQt6.QtGui",
    "--hidden-import=PyQt6.QtWidgets",
    # 收集 Qt 平台插件和 Windows 风格插件（qwindowsvistastyle 等），
    # 确保在 Windows Server 2025（CI）上菜单不出现灰色边框。
    "--collect-all=PyQt6.QtWidgets",
    # 标准库可能被跳过的模块
    "--hidden-import=encodings.idna",
    "--hidden-import=pkg_resources",
    # ── 标准库小模块：PyInstaller 偶尔漏检（取决于版本与缓存） ─────────────
    # `colorsys` 由 backend/domain/entities.py 直接 import；同时 qfluentwidgets
    # 内部也用它做主题色变换。一旦漏掉，用户启动主程序会看到
    # ``ModuleNotFoundError: No module named 'colorsys'`` 的 PyInstaller bootloader
    # 弹窗，对发布是灾难性的。显式声明做兜底。
    "--hidden-import=colorsys",
    # ── 自动更新模块：settings_interface / main_window 中以 try/except 导入，
    # PyInstaller 静态分析无法追踪，必须显式收集整个子包。
    "--collect-submodules=strange_uta_game.updater",
    # 注：不使用 --exclude-module 手动裁剪，让 PyInstaller 自行决定，
    # 避免遗漏运行时通过 importlib / 反射间接加载的模块。
    # 项目使用 PyQt6 + PyQt6-Fluent-Widgets，环境内不应再有 PyQt5。
    # ── 收集所有二进制文件和数据 ──
    "--collect-all=sounddevice",
    "--collect-all=soundfile",
    "--collect-all=pedalboard",
    "--collect-all=fugashi",
    "--collect-all=unidic_lite",
    "--collect-all=qfluentwidgets",
    "--collect-binaries=soundfile",
    # 图标（macOS 需要 .icns / .png，windows 需要 .ico）
    *([f"--icon=src/strange_uta_game/resource/icon.ico"] if sys.platform == "win32" else []),
]

# --clean 由命令行参数控制（改了 import 或打包配置时使用）
if _cli_args.clean:
    args.append("--clean")
    print("启用 PyInstaller --clean（完整重建）")

# 平台特定配置
if sys.platform == "win32":
    # Windows 平台
    print("检测到 Windows 平台")

    # 尝试找到 PortAudio DLL 并添加
    try:
        import sounddevice as _sd

        sd_path = Path(_sd.__file__).parent
        portaudio_dll = (
            sd_path
            / "_sounddevice_data"
            / "portaudio-binaries"
            / "libportaudio64bit.dll"
        )
        if not portaudio_dll.exists():
            portaudio_dll = sd_path / "_sounddevice_data" / "portaudio.dll"
        if portaudio_dll.exists():
            args.append(f"--add-binary={portaudio_dll};.")
            print(f"✓ 找到 PortAudio DLL: {portaudio_dll}")
        else:
            print(
                "! 未找到独立的 portaudio.dll，将依赖 --collect-all=sounddevice 自动加载"
            )
    except Exception:
        pass

elif sys.platform == "darwin":
    # macOS
    print("检测到 macOS 平台")
    args.extend(
        [
            "--osx-bundle-identifier=com.xuancc.strangeutagame",
        ]
    )

else:
    # Linux
    print("检测到 Linux 平台")

print("\n开始打包...")
print(f"输出目录: {PROJECT_ROOT / 'dist'}")

# 运行 PyInstaller
PyInstaller.__main__.run(args)

print("\n✓ 打包完成!")
print(f"可执行文件位于: {PROJECT_ROOT / 'dist' / 'StrangeUtaGame'}")

# ── 修复 ARM64 Windows 上 PortAudio DLL 缺失问题 ──────────────
# sounddevice 在 ARM64 Windows 上会查找 libportaudioarm64.dll（platform.machine()
# 返回 'ARM64'），但 portaudio-binaries 目录只包含 x64 版本。ARM64 Windows 可通过
# x64 模拟层加载 x64 DLL，所以直接复制重命名即可。
if sys.platform == "win32":
    _internal = PROJECT_ROOT / "dist" / "StrangeUtaGame" / "_internal"
    _pa_64bit = _internal / "libportaudio64bit.dll"
    _pa_arm64 = _internal / "libportaudioarm64.dll"
    if _pa_64bit.exists() and not _pa_arm64.exists():
        try:
            import shutil as _shutil
            _shutil.copy2(str(_pa_64bit), str(_pa_arm64))
            print(f"✓ 已生成 ARM64 PortAudio DLL: {_pa_arm64}")
        except Exception as _e:
            print(f"! 生成 ARM64 PortAudio DLL 失败: {_e}")
    elif _pa_arm64.exists():
        print(f"✓ ARM64 PortAudio DLL 已存在: {_pa_arm64}")
    else:
        print("! libportaudio64bit.dll 未找到，跳过 ARM64 DLL 修复")

# ── 复制 Updater 二进制（如已构建） ────────────────────────────
# Updater 由 `python updater_app/build_updater.py` 独立打包，输出至
# `updater_app/dist/Updater[.exe]`（平台相关后缀）。
# 本步骤幂等：若产物存在则复制到主程序 dist，否则警告但不阻断。
_UPDATER_BIN = "Updater.exe" if sys.platform == "win32" else "Updater"
_updater_src = PROJECT_ROOT / "updater_app" / "dist" / _UPDATER_BIN
_updater_dst_dir = PROJECT_ROOT / "dist" / "StrangeUtaGame"
_updater_dst = _updater_dst_dir / _UPDATER_BIN
_updater_found = False
if _updater_dst_dir.exists():
    if _updater_src.exists():
        try:
            import shutil as _shutil
            _shutil.copy2(str(_updater_src), str(_updater_dst))
            print(f"✓ 已复制 {_UPDATER_BIN} → {_updater_dst}")
            _updater_found = True
        except Exception as _e:
            print(f"✗ 复制 {_UPDATER_BIN} 失败: {_e}")
    else:
        print(
            f"✗ 未找到 updater_app/dist/{_UPDATER_BIN}。\n"
            "  自动更新功能不可用。请先运行:\n"
            "    python updater_app/build_updater.py\n"
            "  再重新打包主程序。\n"
            "  若无需自动更新功能，可忽略此警告。"
        )
        _updater_found = False
else:
    print("! dist/StrangeUtaGame/ 目录不存在，跳过 Updater.exe 复制")

# ── 验证 updater 子包是否被 PyInstaller 收集 ──────────────────────
_updater_pkg = PROJECT_ROOT / "dist" / "StrangeUtaGame" / "_internal" / "strange_uta_game" / "updater"
if _updater_pkg.is_dir():
    _n = len(list(_updater_pkg.iterdir()))
    print(f"✓ strange_uta_game.updater 子包已收集（{_n} 文件）")
else:
    print(
        "✗ strange_uta_game.updater 子包未被打包!\n"
        "  这将导致设置界面的代理和更新卡片消失, 版本号不会刷新.\n"
        "  请确认 build.py 中包含 --collect-submodules=strange_uta_game.updater."
    )

# 打包后的说明
print("\n" + "=" * 60)
print("打包后注意事项：")
print("=" * 60)
print("1. 测试音频功能是否正常（播放/暂停/变速）")
print("2. 检查项目保存和打开功能")
print("3. 验证导出功能（LRC/KRA/ASS 等）")
print("4. 测试日语注音功能（fugashi + unidic-lite）")
print("5. 如缺少 DLL，请安装 Visual C++ Redistributable")
print("   https://aka.ms/vs/17/release/vc_redist.x64.exe")
print("=" * 60)

# ── 完整的命令行打包命令（供参考） ──
#
# pip install pyinstaller
#
# pyinstaller --noconfirm --onedir --windowed --clean \
#   --name "StrangeUtaGame" \
#   --icon=src/strange_uta_game/resource/icon.ico \
#   --add-data "src/strange_uta_game;strange_uta_game" \
#   --add-data "src/strange_uta_game/resource/icon.ico;strange_uta_game/resource" \
#   --add-data "src/strange_uta_game/config/config.json;strange_uta_game/config" \
#   --add-data "src/strange_uta_game/config/dictionary.json;strange_uta_game/config" \
#   --add-data "src/strange_uta_game/config/singers.json;strange_uta_game/config" \
#   --hidden-import=sounddevice \
#   --hidden-import=soundfile \
#   --hidden-import=numpy \
#   --hidden-import=numpy.core \
#   --hidden-import=numpy.fft \
#   --hidden-import=fugashi \
#   --hidden-import=unidic_lite \
#   --hidden-import=jaconv \
#   --hidden-import=qfluentwidgets \
#   --hidden-import=PyQt6.sip \
#   --hidden-import=PyQt6.QtCore \
#   --hidden-import=PyQt6.QtGui \
#   --hidden-import=PyQt6.QtWidgets \
#   --hidden-import=encodings.idna \
#   --hidden-import=pkg_resources \
#   --exclude-module=matplotlib \
#   --exclude-module=scipy \
#   --exclude-module=pandas \
#   --exclude-module=tkinter \
#   --exclude-module=unittest \
#   --exclude-module=pdb \
#   --exclude-module=pydoc \
#   --exclude-module=test \
#   --collect-all=sounddevice \
#   --collect-all=soundfile \
#   --collect-all=fugashi \
#   --collect-all=unidic_lite \
#   --collect-all=qfluentwidgets \
#   --collect-binaries=soundfile \
#   main.py
