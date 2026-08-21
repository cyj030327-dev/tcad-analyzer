from pathlib import Path

from tcad_analyzer.gui import app_config


def test_save_and_load_roundtrip(tmp_path, monkeypatch):
    config_dir = tmp_path / ".tcad_analyzer"
    monkeypatch.setattr(app_config, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", config_dir / "config.json")

    data_dir = tmp_path / "data"
    data_dir.mkdir()

    app_config.save_last_import_dir(data_dir)
    loaded = app_config.load_last_import_dir()

    assert loaded == data_dir


def test_load_returns_none_when_no_config_file(tmp_path, monkeypatch):
    config_dir = tmp_path / ".tcad_analyzer"
    monkeypatch.setattr(app_config, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", config_dir / "config.json")

    assert app_config.load_last_import_dir() is None


def test_load_returns_none_when_remembered_dir_no_longer_exists(tmp_path, monkeypatch):
    config_dir = tmp_path / ".tcad_analyzer"
    monkeypatch.setattr(app_config, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", config_dir / "config.json")

    missing_dir = tmp_path / "does_not_exist"
    app_config.save_last_import_dir(missing_dir)

    assert app_config.load_last_import_dir() is None


def test_load_returns_none_on_corrupt_config(tmp_path, monkeypatch):
    config_dir = tmp_path / ".tcad_analyzer"
    config_path = config_dir / "config.json"
    monkeypatch.setattr(app_config, "_CONFIG_DIR", config_dir)
    monkeypatch.setattr(app_config, "_CONFIG_PATH", config_path)

    config_dir.mkdir(parents=True)
    config_path.write_text("not valid json {{{", encoding="utf-8")

    assert app_config.load_last_import_dir() is None


def test_save_does_not_raise_when_directory_uncreatable(tmp_path, monkeypatch):
    # 쓰기가 실패하는 경로를 흉내: 존재하는 파일을 디렉터리로 쓰려고 시도
    blocked = tmp_path / "blocked"
    blocked.write_text("i am a file, not a directory", encoding="utf-8")
    monkeypatch.setattr(app_config, "_CONFIG_DIR", blocked / "sub")
    monkeypatch.setattr(app_config, "_CONFIG_PATH", blocked / "sub" / "config.json")

    app_config.save_last_import_dir(tmp_path)  # 예외 없이 조용히 무시되어야 함
