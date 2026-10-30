"""Remove credential-shaped strings before anything is stored, logged or sent to a browser."""

import re

PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_-]{16,}"),                       # OpenAI / Anthropic style keys
    re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}"),  # JWTs (OAuth tokens)
    re.compile(r"gh[pousr]_[A-Za-z0-9]{30,}"),                  # GitHub tokens
    re.compile(r"[0-9]{8,10}:[A-Za-z0-9_-]{35}"),               # Telegram bot tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),                            # AWS access keys
    re.compile(r"(?i)(refresh_token|access_token|id_token|api_key|password|secret)(\"?\s*[:=]\s*\"?)[^\s\",}]{6,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"postgres(?:ql)?://[^\s\"']+"),                 # connection strings carry passwords
]


def redact(text):
    if not isinstance(text, str):
        return text
    for p in PATTERNS:
        if p.groups >= 2:
            text = p.sub(lambda m: m.group(1) + m.group(2) + "[REDACTED]", text)
        else:
            text = p.sub("[REDACTED]", text)
    return text


def redact_obj(obj):
    if isinstance(obj, str):
        return redact(obj)
    if isinstance(obj, dict):
        return {k: redact_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [redact_obj(v) for v in obj]
    return obj
