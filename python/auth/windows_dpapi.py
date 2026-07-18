import ctypes
import os
from ctypes import wintypes


CRYPTPROTECT_UI_FORBIDDEN = 0x1
_ENTROPY = b"DingFeng-License-Issuer-Ed25519-v2"


class DataBlob(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def protect_current_user(data: bytes) -> bytes:
    return _crypt(data, protect=True)


def unprotect_current_user(data: bytes) -> bytes:
    return _crypt(data, protect=False)


def _blob(data: bytes):
    buffer = ctypes.create_string_buffer(data)
    return DataBlob(len(data), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte))), buffer


def _crypt(data: bytes, protect: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("Windows DPAPI is required for the issuer private key")
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    input_blob, input_buffer = _blob(bytes(data))
    entropy_blob, entropy_buffer = _blob(_ENTROPY)
    output_blob = DataBlob()
    if protect:
        ok = crypt32.CryptProtectData(
            ctypes.byref(input_blob), "DingFeng License Issuer", ctypes.byref(entropy_blob),
            None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(output_blob),
        )
    else:
        ok = crypt32.CryptUnprotectData(
            ctypes.byref(input_blob), None, ctypes.byref(entropy_blob),
            None, None, CRYPTPROTECT_UI_FORBIDDEN, ctypes.byref(output_blob),
        )
    del input_buffer, entropy_buffer
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)
