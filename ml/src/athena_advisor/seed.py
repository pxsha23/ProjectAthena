"""Seeding, so every trained condition can be repeated exactly (the papers report 5 seeds per condition)."""

import os
import random

import numpy as np


def set_seed(seed: int, *, deterministic: bool = False) -> None:
    """Seeds Python, NumPy and PyTorch (CPU and every GPU).

    deterministic=True also forces deterministic GPU kernels: slower, but bit-for-bit repeatable.
    PyTorch is imported here, not at module level, so code that never trains stays light.
    """
    random.seed(seed)
    np.random.seed(seed)
    # Only affects subprocesses (for example data loader workers) started after this point.
    os.environ["PYTHONHASHSEED"] = str(seed)
    try:
        import torch
    except ImportError:
        return
    torch.manual_seed(seed)
    torch.cuda.manual_seed_all(seed)
    if deterministic:
        # Required by cuBLAS for deterministic matrix multiplies on CUDA >= 10.2.
        os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
        torch.use_deterministic_algorithms(True)
        torch.backends.cudnn.benchmark = False
