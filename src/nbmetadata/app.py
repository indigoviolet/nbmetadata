from __future__ import annotations

import json
from pathlib import Path
from typing import Optional, List, Dict
import _jsonnet as jsonnet
import typer
from importlib_resources import files
from dataclasses import dataclass, field
import re
from functools import cached_property
import nbformat
from deepmerge import Merger as DeepMerger
from in_place import InPlace
from contextlib import contextmanager
from copy import deepcopy


run = typer.Typer()


def jsonnet_file(pth: Path, *args, **kwargs):
    return json.loads(jsonnet.evaluate_file(str(pth), *args, **kwargs))


@dataclass
class Config:
    user_config_file: Optional[Path] = None

    @cached_property
    def merged(self):
        config_file = files("nbmetadata").joinpath("config.jsonnet")
        if self.user_config_file is not None:
            user_config = jsonnet_file(self.user_config_file)
        else:
            user_config = {}

        return jsonnet_file(
            config_file, tla_codes={"user_config": json.dumps(user_config)}
        )

    def get(self, key):
        return self.merged[key]


def append_list_unique(config, path, base: List, nxt: List):
    base.extend([k for k in nxt if k not in base])
    return base


@dataclass
class Merger:
    deep_merger: DeepMerger = field(init=False)
    journal_key: str = "_nbmd_keys"

    def __post_init__(self):
        self.deep_merger = DeepMerger(
            [(dict, ["merge"]), (list, [append_list_unique])],
            ["override"],
            ["override"],
        )

    def merge(self, node: nbformat.notebooknode.NotebookNode, data: Dict):
        data.update({self.journal_key: list(data.keys())})
        self.deep_merger.merge(node, data)

    def clean(self, node: nbformat.notebooknode.NotebookNode):
        if self.journal_key not in node:
            return
        keys_to_clean = node.pop(self.journal_key)
        for k in keys_to_clean:
            if k in node:
                del node[k]


def add_metadata(
    key: str,
    cell_metadata: nbformat.notebooknode.NotebookNode,
    notebook_metadata: nbformat.notebooknode.NotebookNode,
    config: Config,
    merger: Merger,
):
    to_add = config.get(key)

    if to_add.get("_top", False):
        del to_add["_top"]
        merger.merge(notebook_metadata, to_add)
    else:
        merger.merge(cell_metadata, to_add)


@dataclass
class TrackModification:
    modified: bool = field(init=False, default=False)

    @contextmanager
    def track(self, obj):
        orig = deepcopy(obj)
        yield obj
        self.modified |= orig != obj


@run.command()
def main(
    notebook_files: List[Path],
    prefix: str = "nbmd:",
    config_file: Optional[Path] = None,
    backup: bool = True,
):
    cfg = Config(user_config_file=config_file)
    comment_re = re.compile(rf"^\s*#+\s*{prefix}(?P<key>\w+)", re.MULTILINE)
    merger = Merger()

    for notebook_file in notebook_files:
        # Note (https://stackoverflow.com/a/2031100/14044156): if this succeeds, a
        # new file will be moved to have this name, but any existing filehandles
        # will point at the original inode

        # backup & backup_ext are mutually exclusive in InPlace()
        backup_kwargs = dict(backup=None) if backup is False else dict(backup_ext="~")
        with InPlace(name=notebook_file, **backup_kwargs) as nf:
            notebook = nbformat.read(nf, as_version=nbformat.NO_CONVERT)
            tm = TrackModification()
            with tm.track(notebook.metadata) as nm:
                merger.clean(nm)
                for cell in notebook.cells:
                    with tm.track(cell.metadata) as cm:
                        merger.clean(cm)
                        keys = [
                            m.group("key") for m in comment_re.finditer(cell.source)
                        ]
                        for k in set(keys):
                            add_metadata(k, cm, nm, config=cfg, merger=merger)

            if tm.modified:
                nbformat.write(notebook, nf)
            else:
                nf.rollback()


if __name__ == "__main__":
    run()
