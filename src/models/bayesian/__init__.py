"""Bayesian survival modelling and Markov chain Monte Carlo (MCMC) diagnostics.

``model`` defines and fits the piecewise-exponential proportional-hazards
model, ``piecewise`` builds its Poisson likelihood rows, ``predictive_checks``
produces prior/posterior checks, and ``diagnostics`` evaluates convergence.
"""

from .diagnostics import check_convergence, divergences, summarise
from .model import SUPPORTED_PRIORS, BayesianCoxModel

__all__ = [
    "SUPPORTED_PRIORS",
    "BayesianCoxModel",
    "check_convergence",
    "divergences",
    "summarise",
]
