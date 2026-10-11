"""Register OpenLP's build hooks without importing Qt or application code."""
from pathlib import Path


def get_hook_dirs():
    return [str(Path(__file__).resolve().parent)]
