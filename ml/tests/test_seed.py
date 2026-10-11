import random

import numpy as np
import torch

from athena_advisor.seed import set_seed


def draw() -> tuple[float, float, float]:
    return random.random(), float(np.random.rand()), float(torch.rand(1))


def test_same_seed_gives_the_same_numbers() -> None:
    set_seed(7)
    first = draw()
    set_seed(7)
    assert draw() == first


def test_different_seeds_differ() -> None:
    set_seed(1)
    one = draw()
    set_seed(2)
    assert draw() != one
