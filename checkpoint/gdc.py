"""Download open-access masked somatic mutation files from the NCI Genomic Data Commons.

Only open-access files are requested, so no token or dbGaP approval is needed.
Standard library only.
"""
import glob
import json
import os
import tarfile
import time
import urllib.request

GDC = "https://api.gdc.cancer.gov"
FIELDS = ",".join([
    "file_id", "file_name", "file_size", "cases.submitter_id", "cases.project.project_id",
    "cases.diagnoses.primary_diagnosis", "cases.diagnoses.age_at_diagnosis",
    "cases.diagnoses.tissue_or_organ_of_origin", "cases.diagnoses.morphology",
    "cases.demographic.sex_at_birth", "cases.demographic.vital_status",
])


def _post(path, payload, timeout=300):
    req = urllib.request.Request(GDC + path, data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def manifest(project):
    flt = {"op": "and", "content": [
        {"op": "in", "content": {"field": "cases.project.project_id", "value": [project]}},
        {"op": "in", "content": {"field": "access", "value": ["open"]}},
        {"op": "in", "content": {"field": "data_type", "value": ["Masked Somatic Mutation"]}}]}
    return json.loads(_post("/files", {"filters": flt, "fields": FIELDS, "size": 10000}))["data"]["hits"]


def _have(out_dir):
    have = set()
    for t in glob.glob(os.path.join(out_dir, "*.tar.gz")):
        try:
            with tarfile.open(t) as tf:
                have.update(m.name.split("/")[0] for m in tf if m.name.endswith(".maf.gz"))
        except (tarfile.TarError, EOFError, OSError):
            os.remove(t)
    return have


def fetch(project, out_dir, batch=100, log=print, only_ids=None):
    """Fetch open MAFs for a project. Safe to re-run: only missing files are requested.

    `only_ids` restricts the download to a fixed list of GDC file ids, so that a benchmark version
    is rebuilt from exactly the files it was frozen on.
    """
    os.makedirs(out_dir, exist_ok=True)
    hits = manifest(project)
    if only_ids is not None:
        wanted = set(only_ids)
        hits = [h for h in hits if h["file_id"] in wanted]
        if len(hits) < len(wanted):
            log(f"warning: {len(wanted) - len(hits)} pinned files are no longer listed as open on the GDC")
    with open(os.path.join(out_dir, "manifest.json"), "w") as fh:
        json.dump(hits, fh)
    missing = [h["file_id"] for h in hits if h["file_id"] not in _have(out_dir)]
    log(f"{project}: {len(hits)} open files, {len(missing)} to download")
    for i in range(0, len(missing), batch):
        for attempt in range(4):
            try:
                raw = _post("/data", {"ids": missing[i:i + batch]})
                with open(os.path.join(out_dir, f"batch_{int(time.time())}_{i:05d}.tar.gz"), "wb") as fh:
                    fh.write(raw)
                break
            except Exception as exc:  # network errors are retried
                log(f"  retry {attempt + 1} for batch {i}: {exc}")
                time.sleep(5)
    return len(hits), len(_have(out_dir))
