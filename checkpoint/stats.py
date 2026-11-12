"""Statistics used by Checkpoint. Standard library only, exact where possible."""
import math


def _lc(n, k):
    return math.lgamma(n + 1) - math.lgamma(k + 1) - math.lgamma(n - k + 1)


def hypergeom_tail(a, n_draw, k_success, total):
    """P(X >= a) for X ~ Hypergeometric: one-sided Fisher exact test for enrichment."""
    n_rest = total - n_draw
    base = _lc(total, k_success)
    p = 0.0
    for x in range(a, min(n_draw, k_success) + 1):
        if k_success - x > n_rest:
            continue
        p += math.exp(_lc(n_draw, x) + _lc(n_rest, k_success - x) - base)
    return min(1.0, p)


def binom_tail(a, n, p):
    """P(X >= a) for X ~ Binomial(n, p)."""
    if a <= 0:
        return 1.0
    if p <= 0:
        return 0.0
    return min(1.0, sum(math.exp(_lc(n, x) + x * math.log(p) + (n - x) * math.log1p(-p))
                        for x in range(a, n + 1)))


def benjamini_hochberg(pvals, q=0.05, m=None):
    """Indices of rejected hypotheses. `m` is the full number of tests performed,
    which must include tests that were never written down (the usual source of error)."""
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m = m or len(pvals)
    keep = 0
    for rank, i in enumerate(order, 1):
        if pvals[i] <= q * rank / m:
            keep = rank
    return order[:keep]


def log_likelihood_ratio(a, n, p1, p0):
    """log of the e-value for H0: p <= p0 against the registered alternative p1 > p0.
    E = (p1/p0)^a * ((1-p1)/(1-p0))^(n-a). Under any p <= p0 its expectation is <= 1,
    so it is a valid e-value and can be multiplied across independent releases."""
    return a * math.log(p1 / p0) + (n - a) * math.log((1 - p1) / (1 - p0))


def elond_levels(n_claims, alpha=0.05):
    """e-LOND (Xu and Ramdas, 2024): online false discovery rate control for a stream of
    e-values under arbitrary dependence. Returns a function giving the test level for the
    t-th claim (1-based) given the number of discoveries so far."""
    norm = 6 / math.pi ** 2

    def level(t, discoveries_so_far):
        return alpha * (norm / t ** 2) * (discoveries_so_far + 1)
    return level


def power_binomial(n, p1, p0, alpha):
    """Power of the exact one-sided binomial test of H0: p <= p0 at level alpha when truth is p1."""
    crit = next((a for a in range(n + 2) if binom_tail(a, n, p0) <= alpha), n + 1)
    return binom_tail(crit, n, p1) if crit <= n else 0.0


def min_detectable(n, p0, alpha, power=0.8):
    """Smallest within-group frequency detectable with the requested power, or None."""
    for i in range(1, 100):
        p1 = i / 100
        if p1 > p0 and power_binomial(n, p1, p0, alpha) >= power:
            return p1
    return None


def brier(pairs):
    """Mean squared error of stated probabilities against 0/1 outcomes."""
    pairs = list(pairs)
    return sum((p - y) ** 2 for p, y in pairs) / len(pairs) if pairs else None
