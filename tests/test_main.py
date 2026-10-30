from types import SimpleNamespace

from app import main


def result(digest):
    return SimpleNamespace(digest=digest, considered=7, usage=SimpleNamespace(input_tokens=1, output_tokens=2))


def test_cmd_update_reports_skipped_update(monkeypatch, capsys):
    monkeypatch.setattr(main, "run_update", lambda s, send: result(None))
    assert main.cmd_update(None) == 0
    assert "No update sent" in capsys.readouterr().out


def test_cmd_preview_update_writes_file_only_when_there_is_an_update(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(main, "run_update", lambda s, send: result(None))
    main.cmd_preview_update(None)
    assert not (tmp_path / "preview-update.html").exists()

    digest = SimpleNamespace(html="<p>hi</p>", subject="S")
    monkeypatch.setattr(main, "run_update", lambda s, send: result(digest))
    main.cmd_preview_update(None)
    assert (tmp_path / "preview-update.html").read_text(encoding="utf-8") == "<p>hi</p>"
