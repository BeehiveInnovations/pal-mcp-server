"""Tests for adding a CLI client through configuration alone."""

import json

import pytest

from clink.registry import ClinkRegistry, RegistryLoadError, available_cli_clients

CONFIG_ENV_VAR = "CLI_CLIENTS_CONFIG_PATH"


@pytest.fixture(autouse=True)
def _isolate_user_config(tmp_path, monkeypatch):
    """Keep a developer's own ~/.pal/cli_clients out of these tests.

    The registry searches that directory after the environment override, so a
    local claude.json or agy.json would otherwise change what is loaded here.
    """

    monkeypatch.setattr("clink.registry.USER_CONFIG_DIR", tmp_path / "unused-user-config")
    # Tests that build a registry from the bundled configs must not pick up a
    # developer's exported override.
    monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)


def _write_config(tmp_path, payload):
    config_dir = tmp_path / "cli_clients"
    config_dir.mkdir(exist_ok=True)
    path = config_dir / f"{payload['name']}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return config_dir


def _base_payload(**overrides):
    payload = {
        "name": "democli",
        "command": "demo-cli",
        "parser": "text",
        "roles": {"default": {"prompt_path": "systemprompts/clink/default.txt"}},
    }
    payload.update(overrides)
    return payload


class TestConfigDrivenClients:
    def test_unknown_cli_loads_when_parser_is_configured(self, tmp_path, monkeypatch):
        config_dir = _write_config(tmp_path, _base_payload())
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        registry = ClinkRegistry()
        client = registry.get_client("democli")

        assert client.parser == "text"
        assert client.prompt_delivery == "stdin"

    def test_unknown_cli_without_parser_is_rejected(self, tmp_path, monkeypatch):
        payload = _base_payload()
        payload.pop("parser")
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        with pytest.raises(RegistryLoadError, match="must define a parser"):
            ClinkRegistry()

    def test_parser_options_reach_the_client(self, tmp_path, monkeypatch):
        payload = _base_payload(parser="json", parser_options={"content_path": "data.text"})
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        client = ClinkRegistry().get_client("democli")
        assert client.parser_options == {"content_path": "data.text"}

    def test_argv_prompt_delivery_from_config(self, tmp_path, monkeypatch):
        payload = _base_payload(prompt_delivery="argv", prompt_args=["-p", "{prompt}"])
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        client = ClinkRegistry().get_client("democli")
        assert client.build_prompt_args("hi") == ["-p", "hi"]

    def test_argv_without_placeholder_is_rejected(self, tmp_path, monkeypatch):
        payload = _base_payload(prompt_delivery="argv", prompt_args=["-p"])
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        with pytest.raises(RegistryLoadError, match="exactly one"):
            ClinkRegistry()

    def test_argv_with_multiple_placeholders_is_rejected(self, tmp_path, monkeypatch):
        payload = _base_payload(prompt_delivery="argv", prompt_args=["{prompt}", "{prompt}"])
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        with pytest.raises(RegistryLoadError, match="exactly one"):
            ClinkRegistry()

    def test_unknown_parser_name_is_rejected(self, tmp_path, monkeypatch):
        payload = _base_payload(parser="not_a_parser")
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        with pytest.raises(RegistryLoadError, match="unknown parser"):
            ClinkRegistry()

    def test_unknown_runner_name_is_rejected(self, tmp_path, monkeypatch):
        """A typo previously fell back to the generic agent with no diagnostic."""

        payload = _base_payload(runner="not_a_runner")
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        with pytest.raises(RegistryLoadError, match="unknown runner"):
            ClinkRegistry()

    def test_prompt_args_without_argv_delivery_is_rejected(self, tmp_path, monkeypatch):
        payload = _base_payload(prompt_args=["-p", "{prompt}"])
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        with pytest.raises(RegistryLoadError, match="prompt_delivery"):
            ClinkRegistry()

    def test_explicit_stdin_delivery_drops_the_bundled_argv_template(self, tmp_path, monkeypatch):
        """A bundled argv client must be overridable back to stdin.

        Inheriting prompt_args unconditionally made the pair validation reject
        a config for an entry the author never wrote.
        """

        payload = _base_payload(name="agy", command="agy", prompt_delivery="stdin")
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        client = ClinkRegistry().get_client("agy")
        assert client.prompt_delivery == "stdin"
        assert client.build_prompt_args("hi") == []

    def test_parser_name_is_case_insensitive(self, tmp_path, monkeypatch):
        payload = _base_payload(parser="TEXT")
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        assert ClinkRegistry().get_client("democli").parser == "TEXT"

    def test_config_parser_overrides_internal_default(self, tmp_path, monkeypatch):
        payload = _base_payload(name="claude", command="claude", parser="text")
        config_dir = _write_config(tmp_path, payload)
        monkeypatch.setenv(CONFIG_ENV_VAR, str(config_dir))

        client = ClinkRegistry().get_client("claude")
        assert client.parser == "text"


class TestBundledAgyClient:
    def test_agy_is_registered_by_default(self):
        registry = ClinkRegistry()
        assert "agy" in registry.list_clients()

    def test_agy_uses_argv_prompt_delivery(self):
        client = ClinkRegistry().get_client("agy")
        assert client.prompt_delivery == "argv"
        assert client.build_prompt_args("hello") == ["-p", "hello"]

    def test_agy_requests_json_output(self):
        client = ClinkRegistry().get_client("agy")
        assert client.parser == "agy_json"
        assert "--output-format" in client.internal_args
        assert "json" in client.internal_args

    def test_permission_bypass_flag_is_visible_in_the_config(self):
        """Kept in agy.json, matching codex.json, so it can be seen and removed."""

        client = ClinkRegistry().get_client("agy")
        assert "--dangerously-skip-permissions" in client.config_args
        assert "--dangerously-skip-permissions" not in client.internal_args

    def test_agy_roles_match_the_other_clients(self):
        client = ClinkRegistry().get_client("agy")
        assert {"default", "planner", "codereviewer"}.issubset(set(client.list_roles()))


class TestAvailableCLIClients:
    """available_cli_clients() reads the cached module-level registry.

    Each test rebuilds it from the bundled configs so a monkeypatched
    CLI_CLIENTS_CONFIG_PATH elsewhere cannot poison this one.
    """

    @pytest.fixture(autouse=True)
    def _fresh_registry(self, monkeypatch):
        monkeypatch.delenv(CONFIG_ENV_VAR, raising=False)
        monkeypatch.setattr("clink.registry._REGISTRY", None)
        yield
        monkeypatch.setattr("clink.registry._REGISTRY", None)

    def test_returns_only_clients_on_path(self, monkeypatch):
        monkeypatch.setattr("clink.registry.shutil.which", lambda name: "/usr/bin/claude" if name == "claude" else None)
        assert available_cli_clients() == ["claude"]

    def test_returns_empty_when_nothing_installed(self, monkeypatch):
        monkeypatch.setattr("clink.registry.shutil.which", lambda name: None)
        assert available_cli_clients() == []
