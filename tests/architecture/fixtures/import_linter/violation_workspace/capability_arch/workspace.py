from capability_arch.core import VALUE
from capability_arch.jobs import enqueue


def config() -> str:
    return VALUE + enqueue()
