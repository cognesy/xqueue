from capability_arch.core import VALUE
from capability_arch.runtime.composition import open_runtime


def enqueue() -> str:
    return VALUE + open_runtime()
