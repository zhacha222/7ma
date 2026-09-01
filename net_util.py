import requests

SESSION = requests.Session()
# 绕过系统/环境代理：直接访问目标服务器，避免本地失效代理（127.0.0.1:9）导致 ProxyError
SESSION.trust_env = False


def session():
    return SESSION

def request(method, url, **kwargs):
    kwargs.setdefault("timeout", 15)
    return SESSION.request(method, url, **kwargs)
