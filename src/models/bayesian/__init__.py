"""Bayesian piecewise-exponential proportional-hazards model and its MCMC diagnostics."""

from .diagnostics import check_convergence, divergences, summarise
from .likelihood import CoxPartialLikelihood
from .model import SUPPORTED_PRIORS, BayesianCoxModel

__all__ = [
    "SUPPORTED_PRIORS",
    "BayesianCoxModel",
    "CoxPartialLikelihood",
    "check_convergence",
    "divergences",
    "summarise",
]
