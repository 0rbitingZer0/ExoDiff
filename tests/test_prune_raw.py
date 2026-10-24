import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "prune_raw.py"


def load():
    spec = importlib.util.spec_from_file_location("prune_raw", SCRIPT)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod


def test_keeps_the_newest_copy_of_each_source_with_its_manifest():
    names = ["exoplanet_eu_20261008T060000Z.csv", "exoplanet_eu_20261008T060000Z.manifest.json",
             "exoplanet_eu_20261015T060000Z.csv", "exoplanet_eu_20261015T060000Z.manifest.json",
             "exoplanet_eu_index_20261008T060000Z.json",
             "gaia_dr3_distances_20261001T060000Z.csv", ".gitkeep"]
    assert load().older_copies(names) == ["exoplanet_eu_20261008T060000Z.csv", "exoplanet_eu_20261008T060000Z.manifest.json"]


def test_dry_run_deletes_nothing(tmp_path, monkeypatch):
    mod = load()
    (tmp_path / "data" / "raw").mkdir(parents=True)
    for name in ("simbad_idents_20261008T060000Z.json", "simbad_idents_20261015T060000Z.json"):
        (tmp_path / "data" / "raw" / name).write_text("{}")
    monkeypatch.setattr(mod, "ROOT", tmp_path)
    monkeypatch.setattr(mod.sys, "argv", ["prune_raw.py"])
    mod.main()
    assert len(list((tmp_path / "data" / "raw").iterdir())) == 2
    monkeypatch.setattr(mod.sys, "argv", ["prune_raw.py", "--delete"])
    mod.main()
    assert [p.name for p in (tmp_path / "data" / "raw").iterdir()] == ["simbad_idents_20261015T060000Z.json"]
