from __future__ import annotations


def tiny_binary() -> bytes:
    return b"HEAD case\"a\":{OLD_A_BODY} case\"b\":{OLD_B_BODY} TAIL"


def utf8(value: str) -> bytes:
    return value.encode("utf-8")
