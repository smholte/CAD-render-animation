"""An app start prunes import caches of an older CACHE_VERSION – never one being written (task 0325, bug hunt 0328
"seen in passing": a 0.2.159 import running while a 0.2.244 app started lost its half-written cache)."""

import json

from fresing_render.importer import runner, step_reader


def test_a_half_written_cache_is_never_pruned_even_with_its_tree_written(tmp_path):
    def make(name, version):
        d = tmp_path / name
        d.mkdir()
        (d / "tree.json").write_text(json.dumps({"version": version}))
        (d / "meshes.npz").write_bytes(b"")
        return d
    old = step_reader.CACHE_VERSION - 1
    done = make("model_ab12", old)                             # an old version's finished cache: pruned
    writing = make("model_cd34.partial-4242-1", old)           # an older app writing right now: kept
    writing_old_name = make("model_ef56.partial", old)         # the name before task 0117: kept too
    current = make("model_gh78", step_reader.CACHE_VERSION)
    assert runner.prune_old_caches(str(tmp_path)) == 1
    assert not done.exists()
    assert writing.exists() and writing_old_name.exists() and current.exists()
