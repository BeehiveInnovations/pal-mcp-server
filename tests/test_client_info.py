"""
Tests for utils/client_info.py

测试 utils/client_info.py 模块的功能。

这个模块的作用是：识别连接到 MCP 服务器的客户端是谁（Claude、Gemini、Cursor 等），
并提供友好的名称显示。
"""

from unittest.mock import MagicMock

import pytest

import utils.client_info as client_info_module
from utils.client_info import (
    CLIENT_NAME_MAPPINGS,
    DEFAULT_FRIENDLY_NAME,
    format_client_info,
    get_cached_client_info,
    get_client_friendly_name,
    get_client_info_from_context,
    get_friendly_name,
    log_client_info,
)


@pytest.fixture(autouse=True)
def reset_client_info_cache(monkeypatch):
    """
    每个测试运行前自动重置客户端信息缓存。

    使用 monkeypatch 而不是直接修改私有变量，这样更符合测试最佳实践。
    """
    monkeypatch.setattr(client_info_module, "_client_info_cache", None)


class TestGetFriendlyName:
    """测试 get_friendly_name() 函数"""

    def test_empty_string_returns_default(self):
        """传入空字符串时，应该返回默认名称"""
        assert get_friendly_name("") == DEFAULT_FRIENDLY_NAME

    def test_none_returns_default(self):
        """传入 None 时，应该返回默认名称"""
        assert get_friendly_name(None) == DEFAULT_FRIENDLY_NAME

    @pytest.mark.parametrize(
        "client_name",
        [
            "claude-ai",
            "Claude-AI",
            "CLAUDE-AI",
            "claude",
            "claude-desktop",
            "claude-code",
            "anthropic",
        ],
    )
    def test_claude_variants(self, client_name):
        """各种 Claude 客户端名称都应该识别为 'Claude'"""
        assert get_friendly_name(client_name) == "Claude"

    @pytest.mark.parametrize(
        "client_name",
        [
            "gemini-cli-mcp-client",
            "gemini-cli",
            "gemini",
            "google",
        ],
    )
    def test_gemini_variants(self, client_name):
        """各种 Gemini 客户端名称都应该识别为 'Gemini'"""
        assert get_friendly_name(client_name) == "Gemini"

    @pytest.mark.parametrize(
        ("client_name", "expected"),
        [
            ("cursor", "Cursor"),
            ("vscode", "VS Code"),
            ("codeium", "Codeium"),
            ("copilot", "GitHub Copilot"),
            ("mcp-client", "MCP Client"),
            ("test-client", "Test Client"),
        ],
    )
    def test_other_known_clients(self, client_name, expected):
        """其他已知客户端应该正确识别"""
        assert get_friendly_name(client_name) == expected

    @pytest.mark.parametrize(
        "client_name",
        [
            "unknown-client",
            "random-app",
            "my-custom-tool",
        ],
    )
    def test_unknown_client_returns_default(self, client_name):
        """未知的客户端名称应该返回默认值"""
        assert get_friendly_name(client_name) == DEFAULT_FRIENDLY_NAME

    @pytest.mark.parametrize(
        ("client_name", "expected"),
        [
            ("CLAUDE", "Claude"),
            ("GEMINI", "Gemini"),
            ("CuRsOr", "Cursor"),
        ],
    )
    def test_case_insensitive_matching(self, client_name, expected):
        """名称匹配应该不区分大小写"""
        assert get_friendly_name(client_name) == expected

    @pytest.mark.parametrize(
        ("client_name", "expected"),
        [
            ("my-claude-extension", "Claude"),
            ("gemini-custom-build", "Gemini"),
        ],
    )
    def test_partial_matching(self, client_name, expected):
        """部分匹配应该能工作"""
        assert get_friendly_name(client_name) == expected


class TestFormatClientInfo:
    """测试 format_client_info() 函数"""

    def test_none_returns_default(self):
        """传入 None 时，应该返回默认名称"""
        assert format_client_info(None) == DEFAULT_FRIENDLY_NAME

    def test_empty_dict_returns_default(self):
        """传入空字典时，应该返回默认名称"""
        assert format_client_info({}) == DEFAULT_FRIENDLY_NAME

    def test_with_friendly_name(self):
        """使用友好名称模式时，应该返回友好名称"""
        client_info = {
            "name": "claude-ai",
            "version": "1.0.0",
            "friendly_name": "Claude",
        }
        assert format_client_info(client_info, use_friendly_name=True) == "Claude"

    def test_without_friendly_name_flag(self):
        """不使用友好名称模式时，应该返回原始名称和版本号"""
        client_info = {
            "name": "claude-ai",
            "version": "1.0.0",
            "friendly_name": "Claude",
        }
        assert format_client_info(client_info, use_friendly_name=False) == "claude-ai v1.0.0"

    def test_without_version(self):
        """没有版本号时，应该只返回名称"""
        client_info = {"name": "claude-ai", "friendly_name": "Claude"}
        assert format_client_info(client_info, use_friendly_name=True) == "Claude"
        assert format_client_info(client_info, use_friendly_name=False) == "claude-ai"

    def test_fallback_to_name_when_no_friendly_name(self):
        """如果没有 friendly_name 字段，应该回退到使用 name 字段"""
        client_info = {"name": "custom-client"}
        assert format_client_info(client_info, use_friendly_name=True) == "custom-client"


class TestGetClientInfoFromContext:
    """测试 get_client_info_from_context() 函数"""

    def test_none_server_returns_none(self):
        """传入 None 服务器时，应该返回 None"""
        assert get_client_info_from_context(None) is None

    def test_server_without_request_context(self):
        """服务器没有 request_context 属性时，应该返回 None"""
        server = MagicMock(spec=[])
        assert get_client_info_from_context(server) is None

    def test_server_with_none_request_context(self):
        """服务器的 request_context 是 None 时，应该返回 None"""
        server = MagicMock()
        server.request_context = None
        assert get_client_info_from_context(server) is None

    def test_client_params_without_client_info(self):
        """_client_params 存在但没有 clientInfo 属性时，应该返回 None"""
        server = MagicMock()
        server.request_context.session._client_params = MagicMock(spec=[])
        assert get_client_info_from_context(server) is None

    def test_successful_extraction(self):
        """成功从有效的服务器上下文中提取客户端信息"""
        server = MagicMock()
        server.request_context.session._client_params.clientInfo.name = "claude-ai"
        server.request_context.session._client_params.clientInfo.version = "1.0.0"

        result = get_client_info_from_context(server)

        assert result is not None
        assert result["name"] == "claude-ai"
        assert result["version"] == "1.0.0"
        assert result["friendly_name"] == "Claude"

    def test_caching_behavior(self):
        """缓存机制是否正常工作"""
        # 第一次调用
        server1 = MagicMock()
        server1.request_context.session._client_params.clientInfo.name = "gemini-cli"
        server1.request_context.session._client_params.clientInfo.version = "2.0.0"

        result1 = get_client_info_from_context(server1)
        assert result1["name"] == "gemini-cli"

        # 第二次调用应该返回缓存的结果
        server2 = MagicMock()
        server2.request_context.session._client_params.clientInfo.name = "different-client"

        result2 = get_client_info_from_context(server2)
        assert result2["name"] == "gemini-cli"  # 仍然是缓存的值

    def test_extraction_with_missing_version(self):
        """客户端信息缺少 version 字段时，应该能正常处理"""
        server = MagicMock()
        client_info_mock = MagicMock(spec=["name"])
        client_info_mock.name = "test-client"
        server.request_context.session._client_params.clientInfo = client_info_mock

        result = get_client_info_from_context(server)

        assert result is not None
        assert result["name"] == "test-client"
        assert "version" not in result


class TestGetCachedClientInfo:
    """测试 get_cached_client_info() 函数"""

    def test_returns_none_when_not_cached(self):
        """没有缓存时，应该返回 None"""
        assert get_cached_client_info() is None

    def test_returns_cached_value(self, monkeypatch):
        """有缓存时，应该返回缓存的值"""
        test_info = {"name": "test", "friendly_name": "Test"}
        monkeypatch.setattr(client_info_module, "_client_info_cache", test_info)

        assert get_cached_client_info() == test_info


class TestGetClientFriendlyName:
    """测试 get_client_friendly_name() 函数"""

    def test_returns_default_when_not_cached(self):
        """没有缓存时，应该返回默认名称"""
        assert get_client_friendly_name() == DEFAULT_FRIENDLY_NAME

    def test_returns_friendly_name_from_cache(self, monkeypatch):
        """有缓存时，应该返回缓存中的友好名称"""
        monkeypatch.setattr(
            client_info_module,
            "_client_info_cache",
            {"name": "gemini-cli", "friendly_name": "Gemini"},
        )

        assert get_client_friendly_name() == "Gemini"

    def test_returns_default_when_friendly_name_missing(self, monkeypatch):
        """缓存中没有 friendly_name 字段时，应该返回默认名称"""
        monkeypatch.setattr(client_info_module, "_client_info_cache", {"name": "some-client"})

        assert get_client_friendly_name() == DEFAULT_FRIENDLY_NAME


class TestLogClientInfo:
    """测试 log_client_info() 函数"""

    def test_logs_client_info_when_available(self):
        """成功提取客户端信息时，应该记录 info 级别的日志"""
        server = MagicMock()
        server.request_context.session._client_params.clientInfo.name = "claude-ai"
        server.request_context.session._client_params.clientInfo.version = "1.0.0"

        mock_logger = MagicMock()
        log_client_info(server, logger_instance=mock_logger)

        mock_logger.info.assert_called()
        call_args = mock_logger.info.call_args[0][0]
        assert "Claude" in call_args

    def test_logs_debug_when_not_available(self):
        """无法提取客户端信息时，应该记录 debug 级别的日志"""
        mock_logger = MagicMock()
        log_client_info(None, logger_instance=mock_logger)

        mock_logger.debug.assert_called_with("Could not extract client info from MCP protocol")


class TestClientNameMappings:
    """测试 CLIENT_NAME_MAPPINGS 常量"""

    def test_mappings_not_empty(self):
        """映射字典不应该为空"""
        assert len(CLIENT_NAME_MAPPINGS) > 0

    def test_all_mappings_have_string_values(self):
        """所有的键和值都应该是字符串"""
        for key, value in CLIENT_NAME_MAPPINGS.items():
            assert isinstance(key, str)
            assert isinstance(value, str)

    def test_default_friendly_name_is_string(self):
        """默认友好名称应该是非空字符串"""
        assert isinstance(DEFAULT_FRIENDLY_NAME, str)
        assert len(DEFAULT_FRIENDLY_NAME) > 0
