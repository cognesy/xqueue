from capability_arch.core import VALUE
from capability_arch.maintenance import doctor


def enqueue() -> str:
    return VALUE + doctor()
