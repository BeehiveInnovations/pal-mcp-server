"""Headroom must never rewrite system prompts or prose user prompts."""

from providers.router import headroom_adapter as h

PROSE = "\n".join(f"Rule {i}: keep answer {i} verbatim and concise." for i in range(400))


def test_structured_only_skips_prose():
    assert h.compress_tool_result(PROSE, structured_only=True) == PROSE


def test_payload_skips_system_and_user_prose():
    msgs = [{"role": "system", "content": PROSE}, {"role": "user", "content": PROSE}]
    assert h.compress_payload(msgs) == msgs


def test_log_summary_keeps_real_first_line():
    text = "\n".join(f"conn {i} ok" for i in range(3000))
    out = h._compress_log(text)
    assert "conn 0 ok" in out and "conn #" not in out


def test_system_prompt_byte_exact_even_if_structured():
    nmap = "Starting Nmap 7.94\n" + "\n".join(f"{i}/tcp open svc{i}" for i in range(800))
    for content in (PROSE, nmap):
        msgs = [{"role": "system", "content": content}]
        out = h.compress_payload(msgs)
        assert out[0]["content"].encode() == content.encode()


def test_user_assistant_history_and_tool_args_untouched():
    nmap = "Starting Nmap 7.94\n" + "\n".join(f"{i}/tcp open svc{i}" for i in range(800))
    msgs = [
        {"role": "user", "content": nmap},
        {"role": "assistant", "content": nmap, "tool_calls": [{"function": {"name": "x", "arguments": nmap}}]},
    ]
    assert h.compress_payload(msgs) == msgs


def test_tool_role_result_is_compressed_and_canonical_skipped():
    nmap = "Starting Nmap 7.94\n" + "\n".join(f"{i}/tcp open svc{i}" for i in range(800))
    out = h.compress_payload([{"role": "tool", "content": nmap}])
    assert len(out[0]["content"]) < len(nmap)
    canon = {"role": "tool", "content": nmap, "evidence": True}
    assert h.compress_payload([canon])[0]["content"] == nmap


def test_gemini_provider_does_not_call_headroom():
    import inspect

    from providers import gemini

    src = inspect.getsource(gemini)
    assert "import headroom_adapter" not in src and "compress_tool_result" not in src
