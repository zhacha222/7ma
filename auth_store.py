import os

CONFIG_DIR = "config"
AUTH_FILE = os.path.join(CONFIG_DIR, "authorizations.txt")
LEGACY_AUTH_FILE = os.path.join(CONFIG_DIR, "Authorization.txt")


def _read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, "r", encoding="utf-8") as handle:
        return [line.strip() for line in handle if line.strip()]


def _dedupe(tokens):
    seen = []
    for token in tokens:
        if token and token not in seen:
            seen.append(token)
    return seen


def load_authorizations():
    tokens = []
    if os.path.exists(AUTH_FILE):
        tokens = _read_lines(AUTH_FILE)
    elif os.path.exists(LEGACY_AUTH_FILE):
        legacy = _read_lines(LEGACY_AUTH_FILE)
        tokens = legacy
    return _dedupe(tokens)


def save_authorizations(tokens):
    tokens = _dedupe([token.strip() for token in tokens if token and token.strip()])
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(AUTH_FILE, "w", encoding="utf-8") as handle:
        handle.write("\n".join(tokens))
        if tokens:
            handle.write("\n")
    # 兼容旧版单文件：第一个 Authorization 同步写入 Authorization.txt
    with open(LEGACY_AUTH_FILE, "w", encoding="utf-8") as handle:
        handle.write(tokens[0] if tokens else "")
    return tokens


def add_authorizations(tokens):
    current = load_authorizations()
    for token in tokens:
        token = (token or "").strip()
        if token and token not in current:
            current.append(token)
    return save_authorizations(current)


def remove_authorization(index):
    current = load_authorizations()
    if 0 <= index < len(current):
        current.pop(index)
        save_authorizations(current)
    return current
