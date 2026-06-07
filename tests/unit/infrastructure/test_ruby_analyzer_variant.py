from strange_uta_game import __version__ as version
from strange_uta_game.backend.infrastructure.parsers import ruby_analyzer


def test_create_analyzer_uses_winrt_for_windows_main(monkeypatch):
    monkeypatch.setattr(ruby_analyzer.sys, "platform", "win32")
    monkeypatch.setattr(version, "VARIANT", "")
    monkeypatch.setattr(ruby_analyzer, "WinRTAnalyzer", lambda: "winrt")
    monkeypatch.setattr(
        ruby_analyzer,
        "SudachiAnalyzer",
        lambda: (_ for _ in ()).throw(AssertionError("Sudachi should not be used")),
    )

    assert ruby_analyzer.create_analyzer(use_pykakasi=False) == "winrt"


def test_create_analyzer_uses_sudachi_for_windows_nowinime(monkeypatch):
    monkeypatch.setattr(ruby_analyzer.sys, "platform", "win32")
    monkeypatch.setattr(version, "VARIANT", "noWinIME")
    monkeypatch.setattr(
        ruby_analyzer,
        "WinRTAnalyzer",
        lambda: (_ for _ in ()).throw(AssertionError("WinRT should not be used")),
    )
    monkeypatch.setattr(ruby_analyzer, "SudachiAnalyzer", lambda: "sudachi")

    assert ruby_analyzer.create_analyzer(use_pykakasi=False) == "sudachi"
