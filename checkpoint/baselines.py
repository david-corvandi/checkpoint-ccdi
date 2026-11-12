"""Two scripted reference analysts, scored by the same engine as any AI agent.

  uncorrected  tests every gene-diagnosis pair it happens to look at and reports p < 0.05
  corrected    removes hypermutated cases and corrects for the full number of tests performed
"""
import collections

from . import stats
from .dataset import HYPERMUTATION_THRESHOLD
from .quality import is_nonspecific


def _scan(cohort, drop_hyper, min_dx=20, min_hit=3):
    cases, genes, _, n_rows = cohort
    ids = [c for c in cases if not drop_hyper or n_rows[c] <= HYPERMUTATION_THRESHOLD]
    by_dx = collections.defaultdict(list)
    for c in ids:
        by_dx[cases[c]["diagnosis"]].append(c)
    tot = collections.Counter(g for c in ids for g in genes[c])
    res, n_dx = [], 0
    for dx, cs in by_dx.items():
        if len(cs) < min_dx or is_nonspecific(dx):
            continue
        n_dx += 1
        gc = collections.Counter(g for c in cs for g in genes[c])
        for g, a in gc.items():
            if a >= min_hit:
                res.append((stats.hypergeom_tail(a, len(cs), tot[g], len(ids)), dx, g, a / len(cs)))
    return res, len(tot) * n_dx


def _claims(rows):
    return [{"diagnosis": dx, "gene": g, "expected_frequency": round(min(max(f, 0.01), 0.99), 3),
             "probability": round(max(0.5, min(0.99, 1 - p)), 3)} for p, dx, g, f in sorted(rows)]


def uncorrected(cohort):
    res, _ = _scan(cohort, drop_hyper=False)
    return _claims([r for r in res if r[0] < 0.05])


def corrected(cohort):
    res, m = _scan(cohort, drop_hyper=True)
    keep = stats.benjamini_hochberg([r[0] for r in res], 0.05, m)
    return _claims([res[i] for i in keep])
