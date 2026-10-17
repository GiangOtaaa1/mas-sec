import config


def test_get_wsl_gateway_uses_default_route_with_lowest_metric(tmp_path):
    route_file = tmp_path / "route"
    route_file.write_text(
        "Iface Destination Gateway Flags RefCnt Use Metric Mask\n"
        "eth0 00000000 015015AC 0003 0 0 100 00000000\n"
        "eth1 00000000 010015AC 0003 0 0 50 00000000\n",
        encoding="ascii",
    )

    assert config._get_wsl_gateway(str(route_file)) == "172.21.0.1"


def test_default_ollama_url_uses_wsl_gateway(monkeypatch):
    monkeypatch.setattr(config, "_is_wsl", lambda: True)
    monkeypatch.setattr(config, "_get_wsl_gateway", lambda: "172.21.80.1")

    assert config._default_ollama_base_url() == "http://172.21.80.1:11434"


def test_default_ollama_url_uses_localhost_outside_wsl(monkeypatch):
    monkeypatch.setattr(config, "_is_wsl", lambda: False)

    assert config._default_ollama_base_url() == "http://localhost:11434"
