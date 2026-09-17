from __future__ import annotations

from pathlib import Path


def test_windows_demo_script_is_project_local_and_keyless():
    script = Path("scripts/start-demo.ps1").read_text(encoding="utf-8")
    assert ".venv\\Scripts\\python.exe" in script
    assert "litflow_api.app:app" in script
    assert "127.0.0.1" in script
    assert "ZHIPUAI_API_KEY" not in script and "DEEPSEEK_API_KEY" not in script
    assert "Start-Process" in script
