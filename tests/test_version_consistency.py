import json
import re
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_release_version_is_single_semver_across_manifests():
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert re.fullmatch(r"\d+\.\d+\.\d+", version)

    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    web_package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    desktop_package = json.loads(
        (ROOT / "apps/desktop/package.json").read_text(encoding="utf-8")
    )
    cargo = tomllib.loads(
        (ROOT / "apps/desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
    )
    tauri_config = json.loads(
        (ROOT / "apps/desktop/src-tauri/tauri.conf.json").read_text(encoding="utf-8")
    )
    web_version_source = (ROOT / "apps/web/src/version.ts").read_text(encoding="utf-8")
    updater_pubkey = tauri_config["plugins"]["updater"]["pubkey"]

    assert pyproject["project"]["version"] == version
    assert web_package["version"] == version
    assert desktop_package["version"] == version
    assert cargo["package"]["version"] == version
    assert tauri_config["version"] == version
    assert f'APP_VERSION = "{version}"' in web_version_source

    assert tauri_config["bundle"]["createUpdaterArtifacts"] is True
    assert updater_pubkey.strip()
    assert tauri_config["plugins"]["updater"]["endpoints"] == [
        "https://github.com/CZ0012/novelagent/releases/latest/download/latest.json"
    ]


def test_desktop_updater_dependencies_are_explicitly_pinned():
    web_package = json.loads((ROOT / "apps/web/package.json").read_text(encoding="utf-8"))
    desktop_package = json.loads(
        (ROOT / "apps/desktop/package.json").read_text(encoding="utf-8")
    )
    cargo = tomllib.loads(
        (ROOT / "apps/desktop/src-tauri/Cargo.toml").read_text(encoding="utf-8")
    )
    capability = json.loads(
        (ROOT / "apps/desktop/src-tauri/capabilities/default.json").read_text(
            encoding="utf-8"
        )
    )

    assert desktop_package["devDependencies"]["@tauri-apps/cli"] == "2.10.1"
    assert desktop_package["dependencies"]["@tauri-apps/plugin-updater"] == "2.10.1"
    assert web_package["dependencies"]["@tauri-apps/api"] == "2.11.1"
    assert web_package["dependencies"]["@tauri-apps/plugin-updater"] == "2.10.1"
    assert cargo["dependencies"]["tauri"]["version"].startswith("=")
    assert cargo["dependencies"]["tauri-plugin-updater"].startswith("=")
    assert "updater:default" in capability["permissions"]
