import base64
from dataclasses import dataclass
import json
import hashlib
import os
import os.path
import re
import shutil
from typing import Callable, TextIO, Any
import uuid
import zlib

from cryptography.fernet import Fernet
from filelock import FileLock
import toml


def write_toml(path, struct):
    with open(path, 'w') as fout:
        fout.write(toml.dumps(struct))


def read_toml(path):
    with open(path) as fin:
        return toml.loads(fin.read())


def locked_read_file(lock_path, file_path, timeout=-1):
    try:
        with FileLock(lock_path, timeout=timeout):
            if not os.path.exists(file_path):
                return True, None
            with open(file_path) as fin:
                return True, fin.read()
    except TimeoutError:
        return False, ''


def locked_read_toml(lock_path, file_path, timeout=-1):
    status, text = locked_read_file(lock_path, file_path, timeout=timeout)
    struct = None
    if status and text is not None:
        struct = toml.loads(text)
    return status, struct


def locked_write_file(lock_path, file_path, text, timeout=-1):
    try:
        with FileLock(lock_path, timeout=timeout):
            with open(file_path, 'w') as fout:
                fout.write(text)
            return True
    except TimeoutError:
        return False


def locked_write_toml(lock_path, file_path, struct, timeout=-1):
    return locked_write_file(lock_path, file_path, toml.dumps(struct), timeout=timeout)


def locked_copy_file(lock_path, src_path, dst_path, timeout=-1):
    try:
        with FileLock(lock_path, timeout=timeout):
            shutil.copyfile(src_path, dst_path)
            return True
    except TimeoutError:
        return False


def file_lock_is_busy(lock_path):
    flock = FileLock(lock_path)
    busy = False
    try:
        flock.acquire(timeout=0.1, poll_intervall=0.05)
    except TimeoutError:
        busy = True
    finally:
        flock.release()
    return busy


@dataclass
class LockedFileLikeObject(TextIO):  # pylint: disable=abstract-method
    lock_path: str
    write_func: Callable

    def write(self, s: str) -> int:
        with FileLock(self.lock_path):
            self.write_func(s)
        return 0


def normalize_distribution_name(name: str) -> str:
    # https://www.python.org/dev/peps/pep-0503/#normalized-names
    return re.sub(r"[-_.]+", "-", name).lower()


def update_hash_algo_with_file(path: str, hash_alog: Any) -> None:
    with open(path, 'rb') as fin:
        # 64KB block.
        for block in iter(lambda: fin.read(65536), b''):
            hash_alog.update(block)


def git_hash_sha(path: str) -> str:
    # https://stackoverflow.com/questions/5290444/why-does-git-hash-object-return-a-different-hash-than-openssl-sha1
    sha1_algo = hashlib.sha1()
    size = os.path.getsize(path)
    sha1_algo.update(f"blob {size}\0".encode())
    update_hash_algo_with_file(path, sha1_algo)
    return sha1_algo.hexdigest()


def get_secret_key():
    secret_key = os.getenv('PRIVATE_PYPI_SECRET_KEY')
    if secret_key is None:
        secret_key = str(uuid.getnode())
    return secret_key


_FERNET_SECRET_KEY = Fernet.generate_key()


def encrypt_object_to_base64(obj):
    try:
        dumped = json.dumps(obj).encode()
        compressed_dumped = zlib.compress(dumped)
        data = Fernet(_FERNET_SECRET_KEY).encrypt(compressed_dumped)
        return base64.b64encode(data).decode()
    except Exception:  # pylint: disable=broad-except
        return None


def decrypt_base64_to_object(text):
    try:
        base64_decoded = base64.b64decode(text.encode())
        compressed_dumped = Fernet(_FERNET_SECRET_KEY).decrypt(base64_decoded)
        dumped = zlib.decompress(compressed_dumped)
        return json.loads(dumped.decode())
    except Exception:  # pylint: disable=broad-except
        return None
