"""打包脚本 - 使用 PyInstaller 打包 StrangeUtaGame。

注意事项：
1. sounddevice 和 soundfile 依赖 PortAudio / libsndfile，需要确保 DLL 被打包
2. PyQt6 有平台插件需要处理
3. Windows main 变体使用 WinRT；Windows noWinIME 与 macOS/Linux 使用 Sudachi small
4. numpy 是音频引擎核心依赖，不可排除
5. 使用 --onedir 模式避免单文件解压问题
"""

import argparse
import contextlib
import PyInstaller.__main__
import re
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
parser.add_argument(
    "--variant",
    choices=["main", "noWinIME", "mac"],
    default=None,
    help="发布变体：main=默认，noWinIME=Windows 无 WinRT，mac=macOS",
)
_cli_args = parser.parse_args()

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.absolute()
VERSION_FILE = PROJECT_ROOT / "src" / "strange_uta_game" / "__version__.py"

_DEFAULT_VARIANT = "mac" if sys.platform == "darwin" else "main"
_CLI_VARIANT = _cli_args.variant or _DEFAULT_VARIANT
VARIANT = "" if _CLI_VARIANT == "main" else _CLI_VARIANT
APP_NAME = "StrangeUtaGame" if not VARIANT else f"StrangeUtaGame-{VARIANT}"
USE_WINRT_JAPANESE = sys.platform == "win32" and not VARIANT
USE_SUDACHI_JAPANESE = not USE_WINRT_JAPANESE

if VARIANT == "mac" and sys.platform != "darwin":
    raise SystemExit("mac 变体只能在 macOS 上构建")
if VARIANT == "noWinIME" and sys.platform != "win32":
    raise SystemExit("noWinIME 变体只用于 Windows 构建")


@contextlib.contextmanager
def _temporary_version_variant(variant: str):
    """打包期间写入 VARIANT，确保运行时和更新器读取到正确资产名。"""
    original = VERSION_FILE.read_text(encoding="utf-8")
    updated, count = re.subn(
        r'(^VARIANT\s*=\s*)["\'][^"\']*["\']',
        rf'\g<1>"{variant}"',
        original,
        count=1,
        flags=re.MULTILINE,
    )
    if count != 1:
        raise SystemExit(f"未能在 {VERSION_FILE} 中替换 VARIANT")
    VERSION_FILE.write_text(updated, encoding="utf-8")
    try:
        yield
    finally:
        VERSION_FILE.write_text(original, encoding="utf-8")

# 让当前 src/ 屏蔽环境中残留的旧 editable install，避免 PyInstaller
# 错误收集其它工作区的 bytecode。
_SRC_DIR = str(PROJECT_ROOT / "src")
while _SRC_DIR in sys.path:
    sys.path.remove(_SRC_DIR)
sys.path.insert(0, _SRC_DIR)
try:
    import strange_uta_game as _sug_probe

    _sug_path = Path(_sug_probe.__file__).resolve()
    _expected = (PROJECT_ROOT / "src" / "strange_uta_game" / "__init__.py").resolve()
    if _sug_path != _expected:
        raise SystemExit(
            "✗ 打包前自检失败：import strange_uta_game 命中的不是本仓库源码。\n"
            f"  期望: {_expected}\n"
            f"  实际: {_sug_path}\n"
            "  常见原因：环境里有旧位置的 `pip install -e .`（例如\n"
            "  E:\\KaraMaker\\StrangeUtaGame\\）。先 `pip uninstall strange-uta-game`\n"
            "  或确认 sys.path 头部为当前 src/ 后重试。"
        )
    print(f"✓ 打包将使用: {_sug_path}")
    del _sug_probe
except ImportError:
    # 还没装/没找到都没关系，sys.path 已经放进去了，PyInstaller 自己也能找到
    print(f"  (尚未 import strange_uta_game，将走 sys.path 首项: {_SRC_DIR})")

# 检查依赖
print(f"构建变体: {_CLI_VARIANT} (app={APP_NAME})")
print("日语注音引擎:", "WinRT" if USE_WINRT_JAPANESE else "SudachiPy + SudachiDict-small")
print("检查依赖...")
try:
    import PyQt6
    import sounddevice
    import soundfile
    import pedalboard
    import qfluentwidgets
    import numpy
    import pykakasi
    import jaconv
    if USE_WINRT_JAPANESE:
        import winrt.windows.globalization
        import winrt.windows.foundation
        import winrt.windows.foundation.collections
    else:
        import sudachipy
        import sudachidict_small

    print("✓ 所有依赖已安装")
    # 打印版本信息
    print(f"  PyQt6: {PyQt6.QtCore.PYQT_VERSION_STR}")
    print(f"  sounddevice: {sounddevice.__version__}")
    print(f"  soundfile: {soundfile.__version__}")
    print(f"  pedalboard: {pedalboard.__version__}")
    print(f"  numpy: {numpy.__version__}")
    print(f"  pykakasi: {getattr(pykakasi, '__version__', 'unknown')}")
    print(f"  jaconv: {getattr(jaconv, '__version__', 'unknown')}")
except ImportError as e:
    print(f"✗ 缺少依赖: {e}")
    print("请先运行: pip install -r requirements.txt")
    if USE_SUDACHI_JAPANESE and sys.platform == "win32":
        print("Windows noWinIME 变体还需要:")
        print("  pip install -e .[sudachi]")
    print("  pip install -e .[dev,build]")
    sys.exit(1)

# PyInstaller --add-data 分隔符：Windows 用 ;，Unix 用 :
_DATA_SEP = ";" if sys.platform == "win32" else ":"

if USE_WINRT_JAPANESE:
    _platform_imports = [
        "--hidden-import=winrt.windows.globalization",
        "--hidden-import=winrt.windows.foundation",
        "--hidden-import=winrt.windows.foundation.collections",
    ]
    _platform_collect = ["--collect-all=winrt"]
    _platform_excludes = [
        "--exclude-module=sudachipy",
        "--exclude-module=sudachidict_small",
        "--exclude-module=sudachidict_core",
        "--exclude-module=sudachidict_full",
    ]
else:
    _platform_imports = [
        "--hidden-import=sudachipy",
        "--hidden-import=sudachidict_small",
    ]
    _platform_collect = [
        "--collect-all=sudachipy",
        "--collect-data=sudachidict_small",
        "--additional-hooks-dir=pyinstaller_hooks",
    ]
    _platform_excludes = [
        "--exclude-module=winrt",
        "--exclude-module=winrt.windows.globalization",
        "--exclude-module=winrt.windows.foundation",
        "--exclude-module=winrt.windows.foundation.collections",
        "--exclude-module=sudachidict_core",
        "--exclude-module=sudachidict_full",
    ]

# 构建 PyInstaller 参数
args = [
    "main.py",  # 主脚本
    f"--name={APP_NAME}",  # 应用名称
    "--onedir",  # 使用目录模式（推荐，启动更快）
    "--windowed",  # 隐藏控制台窗口（macOS 生成 .app bundle）
    "--noconfirm",  # 不确认覆盖
    # 数据文件
    f"--add-data=src/strange_uta_game{_DATA_SEP}strange_uta_game",  # 源代码
    f"--add-data=src/strange_uta_game/resource/icon.ico{_DATA_SEP}strange_uta_game/resource",  # Windows 图标
    f"--add-data=src/strange_uta_game/resource/icon.icns{_DATA_SEP}strange_uta_game/resource",  # macOS 图标
    f"--add-data=src/strange_uta_game/resource/icon_macos.png{_DATA_SEP}strange_uta_game/resource",  # macOS 运行时图标
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
    "--hidden-import=pykakasi",
    "--hidden-import=pykakasi.kakasi",
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
    "--collect-all=qfluentwidgets",
    "--collect-binaries=soundfile",
    # 图标（macOS 需要 .icns，Windows 需要 .ico）
    *([f"--icon=src/strange_uta_game/resource/icon.ico"] if sys.platform == "win32" else []),
    *([f"--icon=src/strange_uta_game/resource/icon.icns"] if sys.platform == "darwin" else []),
]
args.extend(_platform_imports)
args.extend(_platform_collect)
args.extend(_platform_excludes)

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
with _temporary_version_variant(VARIANT):
    PyInstaller.__main__.run(args)

print("\n✓ 打包完成!")
print(f"可执行文件位于: {PROJECT_ROOT / 'dist' / APP_NAME}")

# ── 修复 ARM64 Windows 上 PortAudio DLL 缺失问题 ──────────────
# sounddevice 在 ARM64 Windows 上会查找 libportaudioarm64.dll（platform.machine()
# 返回 'ARM64'），但 portaudio-binaries 目录只包含 x64 版本。ARM64 Windows 可通过
# x64 模拟层加载 x64 DLL，所以直接复制重命名即可。
if sys.platform == "win32":
    _internal = PROJECT_ROOT / "dist" / APP_NAME / "_internal"
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
# Windows/Linux 放在主程序根目录；macOS 放进 .app 的 Contents/MacOS，
# 与主可执行文件同级，保证运行时可以直接定位并启动。
# 本步骤幂等：若产物存在则复制到主程序产物，否则警告但不阻断。
_UPDATER_BIN = "Updater.exe" if sys.platform == "win32" else "Updater"
_updater_src = PROJECT_ROOT / "updater_app" / "dist" / _UPDATER_BIN
if sys.platform == "darwin":
    _updater_dst_dir = (
        PROJECT_ROOT
        / "dist"
        / f"{APP_NAME}.app"
        / "Contents"
        / "MacOS"
    )
else:
    _updater_dst_dir = PROJECT_ROOT / "dist" / APP_NAME
_updater_dst = _updater_dst_dir / _UPDATER_BIN
_updater_found = False
if _updater_dst_dir.exists():
    if _updater_src.exists():
        try:
            import shutil as _shutil
            _shutil.copy2(str(_updater_src), str(_updater_dst))
            if sys.platform != "win32":
                _updater_dst.chmod(_updater_dst.stat().st_mode | 0o111)
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
    print(f"! 主程序输出目录不存在，跳过 {_UPDATER_BIN} 复制: {_updater_dst_dir}")

# PyInstaller 会在生成 macOS App 时完成一次签名。之后新增 Updater 会改变 bundle，
# 因此需要重新做 ad-hoc 签名，避免 Gatekeeper 判定 App 已被修改。
if sys.platform == "darwin" and _updater_found:
    _app_bundle = PROJECT_ROOT / "dist" / f"{APP_NAME}.app"
    try:
        import subprocess as _subprocess

        _subprocess.run(
            ["codesign", "--force", "--deep", "--sign", "-", str(_app_bundle)],
            check=True,
        )
        print(f"✓ 已重新签名 macOS App: {_app_bundle}")
    except (OSError, _subprocess.CalledProcessError) as _e:
        raise SystemExit(f"✗ macOS App 重新签名失败: {_e}") from _e

# ── 验证 updater 子包是否被 PyInstaller 收集 ──────────────────────
if sys.platform == "darwin":
    _updater_pkg_candidates = [
        PROJECT_ROOT / "dist" / f"{APP_NAME}.app" / "Contents" / location
        / "strange_uta_game" / "updater"
        for location in ("Frameworks", "Resources")
    ]
else:
    _updater_pkg_candidates = [
        PROJECT_ROOT / "dist" / APP_NAME / "_internal"
        / "strange_uta_game" / "updater"
    ]

_updater_pkg = next((p for p in _updater_pkg_candidates if p.is_dir()), None)
if _updater_pkg is not None:
    _n = len(list(_updater_pkg.iterdir()))
    print(f"✓ strange_uta_game.updater 子包已收集（{_n} 文件）: {_updater_pkg}")
else:
    _checked_paths = "\n".join(f"    - {p}" for p in _updater_pkg_candidates)
    print(
        "✗ strange_uta_game.updater 子包未被打包!\n"
        "  这将导致设置界面的代理和更新卡片消失, 版本号不会刷新.\n"
        "  请确认 build.py 中包含 --collect-submodules=strange_uta_game.updater.\n"
        f"  已检查:\n{_checked_paths}"
    )

# 打包后的说明
print("\n" + "=" * 60)
print("打包后注意事项：")
print("=" * 60)
print("1. 测试音频功能是否正常（播放/暂停/变速）")
print("2. 检查项目保存和打开功能")
print("3. 验证导出功能（LRC/KRA/ASS 等）")
if sys.platform == "win32":
    if USE_WINRT_JAPANESE:
        print("4. 测试日语注音功能（WinRT JapanesePhoneticAnalyzer）")
    else:
        print("4. 测试日语注音功能（SudachiPy + SudachiDict-small）")
else:
    print("4. 测试日语注音功能（SudachiPy + SudachiDict-small）")
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
#   --hidden-import=sudachipy \
#   --hidden-import=sudachidict_small \
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
#   --collect-all=sudachipy \
#   --collect-data=sudachidict_small \
#   --collect-all=qfluentwidgets \
#   --collect-binaries=soundfile \
#   main.py
