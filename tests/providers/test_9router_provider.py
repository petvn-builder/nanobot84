"""Tests for the 9Router provider registration."""

from nanobot.config.schema import Config, ProvidersConfig
from nanobot.providers.registry import PROVIDERS, find_by_name


def test_9router_config_field_exists() -> None:
    config = ProvidersConfig.model_validate(
        {
            "9router": {
                "apiKey": "router-key",
                "apiBase": "https://9router.pvn.world/v1",
            }
        }
    )

    assert hasattr(config, "nine_router")
    assert config.nine_router.api_key == "router-key"


def test_9router_provider_in_registry() -> None:
    specs = {spec.name: spec for spec in PROVIDERS}

    assert "nine_router" in specs
    router = specs["nine_router"]
    assert router.backend == "openai_compat"
    assert router.env_key == "NANOBOT_9ROUTER_API_KEY"
    assert router.display_name == "9Router"
    assert router.is_gateway is True
    assert router.detect_by_base_keyword == "9router.pvn.world"
    assert router.default_api_base == "https://9router.pvn.world/v1"


def test_find_by_name_9router_alias() -> None:
    spec = find_by_name("9router")

    assert spec is not None
    assert spec.name == "nine_router"


def test_forced_9router_provider_uses_configured_gateway() -> None:
    config = Config.model_validate(
        {
            "providers": {
                "9router": {
                    "apiKey": "router-key",
                    "apiBase": "https://9router.pvn.world/v1",
                },
            },
            "agents": {
                "defaults": {
                    "provider": "9router",
                    "model": "anthropic/claude-sonnet-4-5",
                },
            },
        }
    )

    assert config.get_provider_name("anthropic/claude-sonnet-4-5") == "nine_router"
    assert config.get_api_key("anthropic/claude-sonnet-4-5") == "router-key"
    assert config.get_api_base("anthropic/claude-sonnet-4-5") == "https://9router.pvn.world/v1"
