from providers.shared import ProviderType
from tools.chat import ChatTool


class FakeCapabilities:
    def __init__(
        self,
        provider=ProviderType.OPENROUTER,
        max_image_size_mb=5.0,
        max_total_image_size_mb=10.0,
        max_image_count=None,
        supports_images=True,
    ):
        self.provider = provider
        self.max_image_size_mb = max_image_size_mb
        self.max_total_image_size_mb = max_total_image_size_mb
        self.max_image_count = max_image_count
        self.supports_images = supports_images


class FakeModelContext:
    def __init__(self, capabilities, model_name="stub-model"):
        self.capabilities = capabilities
        self.model_name = model_name


def test_get_effective_limit_caps_custom():
    tool = ChatTool()
    caps = FakeCapabilities(provider=ProviderType.CUSTOM)
    assert tool._get_effective_limit(100.0, caps) == 40.0
    assert tool._get_effective_limit(20.0, caps) == 20.0


def test_calculate_image_size_data_url_and_error():
    tool = ChatTool()
    data_url = (
        "data:image/png;base64,"
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    size_mb, err = tool._calculate_image_size(data_url)
    assert err is None
    assert size_mb and size_mb > 0

    # Test invalid base64 that will fail to decode
    bad_url = "data:image/png;base64,!!!invalid!!!"
    size_mb, err = tool._calculate_image_size(bad_url)
    assert size_mb is None
    assert err is not None
    assert "Failed to read image" in err


def test_validate_image_limits_missing_file_returns_error(tmp_path):
    tool = ChatTool()
    caps = FakeCapabilities()
    ctx = FakeModelContext(caps)
    missing = tmp_path / "missing.png"

    result = tool._validate_image_limits([str(missing)], model_context=ctx)
    assert result is not None
    assert result["status"] == "error"
    assert "not found" in result["content"]


def test_validate_image_limits_hits_per_image_limit(tmp_path):
    tool = ChatTool()
    caps = FakeCapabilities(max_image_size_mb=0.001, max_total_image_size_mb=1.0)
    ctx = FakeModelContext(caps)

    img_path = tmp_path / "too_big.png"
    # 写入 2KB，约 0.0019MB，大于 0.001MB 限制
    img_path.write_bytes(b"\x00" * 2048)

    result = tool._validate_image_limits([str(img_path)], model_context=ctx)
    assert result is not None
    assert result["status"] == "error"
    assert "size limit exceeded" in result["content"]


def test_validate_image_limits_respects_custom_total_cap(tmp_path):
    tool = ChatTool()
    caps = FakeCapabilities(provider=ProviderType.CUSTOM, max_image_size_mb=50.0, max_total_image_size_mb=80.0)
    ctx = FakeModelContext(caps)

    img1 = tmp_path / "img1.bin"
    img2 = tmp_path / "img2.bin"
    # 两张各 30MB，总计 60MB，超过自定义 40MB 上限（被 40MB cap 约束）
    for path in (img1, img2):
        with path.open("wb") as f:
            f.write(b"\x00" * 30 * 1024 * 1024)

    result = tool._validate_image_limits([str(img1), str(img2)], model_context=ctx)
    assert result is not None
    assert result["status"] == "error"
    assert "Total image size limit exceeded" in result["content"]
