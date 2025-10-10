import tempfile
from pathlib import Path

import yaml

from scripts import seed_dry_run_cluster as seeder


def test_collect_crds_gathers_unique_definitions() -> None:
    crd = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {"name": "widgets.example.com"},
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        path = tmp / "crd.yaml"
        path.write_text(yaml.safe_dump_all([crd, crd]), encoding="utf-8")
        gathered = seeder.collect_crds([path])
        assert len(gathered) == 1
        assert gathered[0]["metadata"]["name"] == "widgets.example.com"


def test_write_docs_outputs_yaml() -> None:
    crd = {
        "apiVersion": "apiextensions.k8s.io/v1",
        "kind": "CustomResourceDefinition",
        "metadata": {"name": "gadgets.example.com"},
    }
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        out_path = tmp / "crds.yaml"
        seeder.write_docs([crd], out_path)
        content = list(yaml.safe_load_all(out_path.read_text(encoding="utf-8")))
        assert content[0]["metadata"]["name"] == "gadgets.example.com"

