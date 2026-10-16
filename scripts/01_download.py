"""Download the Eedi Misconceptions Graph v1.0 CSVs into data/raw/ and record the commit hash."""

import json
import shutil
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = RAW / "manifest.json"

# Pinned revisions (repo -> commit). Canonical first, duplicate as fallback.
REPOS = {
    "Eedi/Eedi-Misconceptions-Graph": "2ae0839debf73c0ce7dd6578d8ea8b99e7be8631",
    "wangwangduishuidajiao/Eedi-Misconceptions-Graph": "ca299f48cfa3ca4ce5256185f6efb1fbe58beb5f",
}
FILES = ["data/construct-map.csv", "data/misconception-map.csv"]


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    targets = [RAW / Path(f).name for f in FILES]
    if all(t.exists() for t in targets):
        print(f"skip: {', '.join(t.name for t in targets)} already in data/raw/")
        if MANIFEST.exists():
            print(MANIFEST.read_text())
        return

    last_error = None
    for repo, sha in REPOS.items():
        try:
            for f, target in zip(FILES, targets):
                cached = hf_hub_download(repo_id=repo, filename=f, repo_type="dataset", revision=sha)
                shutil.copyfile(cached, target)
        except Exception as e:  # repo missing, private or network error: try the next one
            print(f"failed: {repo}: {e}")
            last_error = e
            continue
        manifest = {"repo": repo, "revision": sha, "files": FILES}
        MANIFEST.write_text(json.dumps(manifest, indent=2) + "\n")
        print(json.dumps(manifest, indent=2))
        return
    raise SystemExit(f"could not download from any repo: {last_error}")


if __name__ == "__main__":
    main()
