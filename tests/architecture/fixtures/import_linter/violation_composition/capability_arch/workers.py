from capability_arch.jobs import enqueue
from capability_arch.queues import stats


def run() -> str:
    return enqueue() + stats()
