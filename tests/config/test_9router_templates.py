import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_template(name: str) -> dict:
    return json.loads((REPO_ROOT / name).read_text(encoding="utf-8"))


def test_9router_templates_allow_web_fetch_without_shell_exec() -> None:
    for template_name in ("config.template.json", "config.coolify.json"):
        config = _load_template(template_name)

        assert config["tools"]["web"]["enable"] is True
        assert config["tools"]["exec"]["enable"] is False
        assert config["tools"]["restrictToWorkspace"] is True
