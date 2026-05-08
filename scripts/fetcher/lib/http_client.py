"""自适应 HTTP 客户端 — 自动检测直连/代理模式。

ClickHouse 服务器在不同网络环境下可能需要不同连接方式:
- 关闭 TUN/VPN: 直连最快
- 开启 TUN 模式: 需要走本地代理 (如 Clash 127.0.0.1:7897)

本模块通过快速连通性测试自动选择可用模式并缓存结果。
"""
import urllib.request

import requests

# 缓存已探测成功的代理配置
# DIRECT = {"http": None, "https": None} (显式绕过代理)
# PROXY = {"http": "http://127.0.0.1:7897", "https": "http://127.0.0.1:7897"}
_proxy_cache: dict | None = None

DIRECT = {"http": None, "https": None}


def _detect_proxy_mode(test_url: str, auth: tuple | None = None, timeout: float = 5.0) -> dict:
    """快速测试直连和代理模式，返回最佳 proxies 参数。

    直连模式使用 `{"http": None, "https": None}` 显式绕过环境代理。
    """
    candidates: list[tuple[str, dict]] = [
        ("direct", DIRECT),
    ]

    sys_proxies = urllib.request.getproxies()
    proxy_url = (
        sys_proxies.get("http")
        or sys_proxies.get("all")
        or sys_proxies.get("all_proxy", "")
    )
    if proxy_url:
        candidates.append(("proxy", {"http": proxy_url, "https": proxy_url}))

    for label, proxies in candidates:
        try:
            s = requests.Session()
            s.trust_env = (label != "direct")
            resp = s.get(test_url, auth=auth, timeout=timeout, proxies=proxies)
            if resp.ok:
                return proxies
        except Exception:
            continue

    return DIRECT


def get_http_proxies(test_url: str, auth: tuple | None = None, timeout: float = 5.0) -> dict:
    """获取可用的代理配置，结果会被缓存。

    Args:
        test_url: 连通性测试 URL
        auth: (user, password) 元组，用于需要认证的服务
        timeout: 单次探测超时秒数

    Returns:
        dict: proxies 参数传给 requests.get(proxies=...)
    """
    global _proxy_cache
    if _proxy_cache is not None:
        return _proxy_cache

    _proxy_cache = _detect_proxy_mode(test_url, auth=auth, timeout=timeout)
    is_proxy = _proxy_cache and _proxy_cache.get("http") is not None
    label = f"proxy ({_proxy_cache['http']})" if is_proxy else "direct"
    print(f"[INFO] 网络模式: {label}")
    return _proxy_cache
