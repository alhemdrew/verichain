from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class StorageService(ABC):
    @abstractmethod
    def store(self, *, name: str, content: bytes) -> str:
        raise NotImplementedError

    @abstractmethod
    def read(self, *, reference: str) -> bytes:
        raise NotImplementedError


class LocalStorageService(StorageService):
    def __init__(self, base_dir: str | Path):
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)

    def store(self, *, name: str, content: bytes) -> str:
        target = self.base_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(content)
        return str(target)

    def read(self, *, reference: str) -> bytes:
        return Path(reference).read_bytes()
