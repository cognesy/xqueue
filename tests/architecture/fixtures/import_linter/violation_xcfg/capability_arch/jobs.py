import xcfg

from capability_arch.core import VALUE


def enqueue() -> str:
    """A capability reading configuration for itself, which the contract forbids."""
    return VALUE + xcfg.__name__
