"""跨平台运行时目录测试。"""

from pathlib import Path

from strange_uta_game import runtime_paths


def test_macos_uses_user_library(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_paths.sys, "platform", "darwin")
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))

    assert runtime_paths.default_config_dir() == (
        tmp_path / "Library" / "Application Support" / "StrangeUtaGame"
    )
    assert runtime_paths.cache_dir() == (
        tmp_path / "Library" / "Caches" / "StrangeUtaGame"
    )


def test_non_macos_keeps_program_relative_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime_paths.sys, "platform", "linux")
    monkeypatch.setattr(runtime_paths, "program_dir", lambda: tmp_path)
    monkeypatch.delenv("SUG_CACHE_DIR", raising=False)

    assert runtime_paths.default_config_dir() == tmp_path
    assert runtime_paths.cache_dir() == tmp_path / ".cache"
