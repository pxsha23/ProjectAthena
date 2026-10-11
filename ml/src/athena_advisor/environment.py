"""Checks the Python environment before a run: versions, GPU, and whether every dependency imports."""

import importlib.util
import platform
import sys
from typing import Any

# Import name of every runtime dependency in pyproject.toml.
REQUIRED_MODULES = (
    "torch",
    "transformers",
    "sentence_transformers",
    "setfit",
    "datasets",
    "sklearn",
    "pandas",
    "pyarrow",
    "numpy",
    "scipy",
    "yaml",
    "bs4",
    "matplotlib",
    "onnx",
    "onnxruntime",
    "optimum",
    "tokenizers",
    "tqdm",
)


def missing_modules(modules: tuple[str, ...] = REQUIRED_MODULES) -> list[str]:
    """Modules that cannot be found, without importing them (importing torch alone takes seconds)."""
    return [name for name in modules if importlib.util.find_spec(name) is None]


def environment_report() -> dict[str, Any]:
    report: dict[str, Any] = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "missing_modules": missing_modules(),
    }
    try:
        import torch
    except ImportError:
        report["torch"] = None
        return report
    report["torch"] = torch.__version__
    report["cuda_available"] = torch.cuda.is_available()
    if torch.cuda.is_available():
        report["cuda"] = torch.version.cuda
        report["gpus"] = [torch.cuda.get_device_name(i) for i in range(torch.cuda.device_count())]
    return report
