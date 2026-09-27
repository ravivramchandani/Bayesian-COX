"""Bayesian piecewise-exponential proportional-hazards model and its MCMC diagnostics."""

from .diagnostics import check_convergence, divergences, summarise
from .model import SUPPORTED_PRIORS, BayesianCoxModel

__all__ = [
    "SUPPORTED_PRIORS",
    "BayesianCoxModel",
    "check_convergence",
    "divergences",
    "summarise",
]
