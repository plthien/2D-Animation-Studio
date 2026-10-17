"""Minimal local diagnostics sanitization used by the adapted provider transport."""
from __future__ import annotations
import re
REDACTION_MARKER="[REDACTED]"
def sanitize_diagnostic_value(value, *, max_string_chars=4096):
    if isinstance(value,str):
        value=re.sub(r"(?i)(api[_-]?key|authorization|token|secret)([\\s:=]+)[^\\s,;]+",r"\\1\\2"+REDACTION_MARKER,value)
        return value[:max_string_chars]
    if isinstance(value,dict):
        return {sanitize_diagnostic_value(str(k),max_string_chars=max_string_chars):
                (REDACTION_MARKER if re.search(r"(?i)key|secret|token|password",str(k)) else sanitize_diagnostic_value(v,max_string_chars=max_string_chars))
                for k,v in value.items()}
    if isinstance(value,list):
        return [sanitize_diagnostic_value(v,max_string_chars=max_string_chars) for v in value]
    return value if value is None or isinstance(value,(int,bool,float)) else str(value)[:max_string_chars]
