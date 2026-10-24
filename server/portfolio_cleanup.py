"""Remove only media owned solely by explicitly purged workspace records."""
import json
from pathlib import Path
import re


def media_keys(value):
    keys=set()
    if isinstance(value,dict):
        for k,v in value.items():
            if k=='key' and isinstance(v,str) and re.fullmatch(r'[a-f0-9]{64}\.(png|mp4|wav)',v): keys.add(v)
            else: keys.update(media_keys(v))
    elif isinstance(value,list):
        for item in value: keys.update(media_keys(item))
    return keys


def cleanup(root, candidates, retained, snapshots):
    root=Path(root).resolve()
    media=(root/'portfolio-media').resolve()
    if media.is_relative_to(root):
        for key in candidates-retained:
            path=media/key
            if path.is_file() and not path.is_symlink() and path.resolve().parent==media:
                path.unlink()
    reader=(root/'reader-public').resolve()
    if not reader.is_relative_to(root): return
    for snapshot in snapshots:
        if not re.fullmatch(r'[a-f0-9]{32}',snapshot): continue
        target=reader/snapshot
        if not target.is_dir() or target.is_symlink() or target.resolve().parent!=reader: continue
        # Resolve every entry; never follow symlinks outside this exact snapshot.
        for item in sorted(target.rglob('*'),key=lambda p:len(p.parts),reverse=True):
            if item.is_symlink(): item.unlink()
            elif item.resolve().is_relative_to(target):
                if item.is_file(): item.unlink()
                elif item.is_dir(): item.rmdir()
        target.rmdir()
