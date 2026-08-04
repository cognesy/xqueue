from capability_arch.workers import run
from capability_arch.workspace import config


def supervise() -> str:
    return run() + config()
