from simplememkitty.core.settings import Settings, DEFAULTS


def test_defaults_after_load(tmp_path):
    s = Settings(path=str(tmp_path / "s.json")).load()
    assert s.get("auto_clean_enabled") == DEFAULTS["auto_clean_enabled"]
    assert s.get("mem_threshold_percent") == DEFAULTS["mem_threshold_percent"]


def test_save_load_roundtrip(tmp_path):
    p = str(tmp_path / "s.json")
    s = Settings(path=p)
    s.set("auto_clean_enabled", True)
    s.set("mem_threshold_percent", 72)
    s.save()

    s2 = Settings(path=p).load()
    assert s2.get("auto_clean_enabled") is True
    assert s2.get("mem_threshold_percent") == 72


def test_type_coercion(tmp_path):
    p = tmp_path / "s.json"
    p.write_text(
        '{"mem_threshold_percent": "85", "auto_clean_enabled": "true"}',
        encoding="utf-8",
    )
    s = Settings(path=str(p)).load()
    # 损坏/字符串类型应被校回为正确类型
    assert s.get("mem_threshold_percent") == 85
    assert s.get("auto_clean_enabled") is True


def test_corrupt_file_falls_back(tmp_path):
    p = tmp_path / "s.json"
    p.write_text("{not valid json", encoding="utf-8")
    s = Settings(path=str(p)).load()
    assert s.get("auto_clean_enabled") == DEFAULTS["auto_clean_enabled"]
