"""Reconstruct the U48 PostgreSQL custom-format backup entirely in Windows process memory."""
import argparse
import ctypes
import hashlib
import json
import os
from pathlib import Path

from package_sys_operator_release import verify


def reconstruct(directory, library):
    if os.name != "nt":
        raise ValueError("Use the standard recovery recipe on Linux")
    verify(directory)
    fg = (directory / "fg/source.dump").read_bytes()
    delta = (directory / "base193/source.dump.zstpatch").read_bytes()
    release = json.loads((directory / "base193/release.json").read_bytes())
    dll = ctypes.CDLL(str(library.resolve(strict=True)))
    ptr, size = ctypes.c_void_p, ctypes.c_size_t
    dll.ZSTD_createDCtx.restype = ptr
    dll.ZSTD_freeDCtx.argtypes = [ptr]
    dll.ZSTD_getFrameContentSize.argtypes = [ptr, size]
    dll.ZSTD_getFrameContentSize.restype = ctypes.c_ulonglong
    dll.ZSTD_decompress_usingDict.argtypes = [ptr, ptr, size, ptr, size, ptr, size]
    dll.ZSTD_decompress_usingDict.restype = size
    dll.ZSTD_isError.argtypes = [size]
    expected = dll.ZSTD_getFrameContentSize(delta, len(delta))
    if expected != 27699785:
        raise ValueError("Unexpected final SQL size")
    dest = ctypes.create_string_buffer(expected)
    context = dll.ZSTD_createDCtx()
    if not context:
        raise MemoryError()
    try:
        actual = dll.ZSTD_decompress_usingDict(context, dest, expected, delta, len(delta), fg, len(fg))
    finally:
        dll.ZSTD_freeDCtx(context)
    digest = hashlib.sha256(dest.raw).hexdigest()
    if dll.ZSTD_isError(actual) or actual != expected or digest != release["files"]["source.dump"] or dest.raw[:5] != b"PGDMP":
        raise ValueError("Independently reconstructed SQL differs")
    print(json.dumps({"bytes":actual,"sha256":digest,"format":"PGDMP","module":"18.0.1.6.2",
                      "libzstd_sha256":hashlib.sha256(library.read_bytes()).hexdigest()},sort_keys=True))


if __name__ == "__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory",type=Path)
    parser.add_argument("--libzstd",type=Path,required=True)
    args=parser.parse_args()
    reconstruct(args.directory,args.libzstd)
