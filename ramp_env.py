"""Pin numerical-library thread counts to 1.

Import this module BEFORE numpy/scipy in every module that uses them
so the optimiser stays bit-for-bit reproducible: multi-threaded BLAS
re-orders floating-point summations between threads, which perturbs
differential_evolution's convergence path even with a fixed seed.
Importing it first (rather than relying on ramp_optimizer being
imported first) guarantees the pin regardless of entry point."""
import os

# Set each threading knob to 1 unless the environment already pins it.
for _var in (
    "OPENBLAS_NUM_THREADS",
    "MKL_NUM_THREADS",
    "OMP_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
    "VECLIB_MAXIMUM_THREADS",
    "BLIS_NUM_THREADS",
):
    os.environ.setdefault(_var, "1")
del _var
