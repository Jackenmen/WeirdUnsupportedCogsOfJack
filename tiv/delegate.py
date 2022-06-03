import functools
from typing import Any


def delegate(cls: type, attr_name: str) -> Any:
    @property
    @functools.wraps(getattr(cls, attr_name))
    def func(self) -> Any:
        return getattr(cls, attr_name).__get__(self, type(self))

    return func
