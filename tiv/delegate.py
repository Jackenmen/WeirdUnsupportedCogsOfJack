import functools
from typing import Any


def delegate(cls: type, attr_name: str) -> Any:
    meth_or_property = getattr(cls, attr_name)

    @functools.wraps(getattr(meth_or_property, "fget", meth_or_property))
    def func(self) -> Any:
        return getattr(cls, attr_name).__get__(self, type(self))

    func.__name__ = attr_name

    return property(func)
