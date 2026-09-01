# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only
"""Authoritative scoped filesystem resolution and manifest-backed artifacts."""
from __future__ import annotations
import hashlib, json, os, re, shutil
from pathlib import Path
def _path_is_within(base_dir: str, candidate: str) -> bool:
    base_abs, target_abs = os.path.abspath(base_dir), os.path.abspath(candidate)
    try:
        if os.path.commonpath([base_abs, target_abs]) != base_abs: return False
    except ValueError: return False
    probe, tail = target_abs, []
    while probe and not os.path.lexists(probe):
        parent=os.path.dirname(probe)
        if parent==probe: break
        tail.append(os.path.basename(probe)); probe=parent
    try: return os.path.commonpath([os.path.realpath(base_abs), os.path.realpath(os.path.join(probe,*reversed(tail)))]) == os.path.realpath(base_abs)
    except ValueError: return False

def _safe_join(base_dir: str, *parts: str) -> str:
    candidate=os.path.abspath(os.path.join(base_dir,*parts))
    if not _path_is_within(base_dir,candidate): raise ValueError("path escapes configured base")
    return candidate

class StorageResolver:
    def __init__(self, results_dir: str, workspace_dir: str):
        self.results_dir=os.path.abspath(results_dir); self.workspace_dir=os.path.abspath(workspace_dir)
    def scope_root(self, scope_type: str, storage_key: str) -> str:
        if scope_type not in {'personal','project'} or not re.fullmatch(r'[A-Za-z0-9_.-]{3,120}', storage_key): raise ValueError('invalid scope')
        return _safe_join(self.results_dir, 'users' if scope_type=='personal' else 'projects', storage_key)
    def task_root(self, scope_type: str, storage_key: str, task_id: str) -> str:
        if not re.fullmatch(r'[a-fA-F0-9]{32}', task_id): raise ValueError('invalid task id')
        return _safe_join(self.scope_root(scope_type, storage_key), 'tasks', task_id)
    def manifest_path(self, task: dict) -> str:
        root=task.get('result_dir') or self.task_root(task.get('scope_type','personal'), task['storage_key'], task['md5sum'])
        return _safe_join(root,'manifest.json')
    def resolve_artifact(self, task: dict, relative_path: str) -> dict | None:
        normalized=relative_path.replace('\\','/')
        if not normalized or normalized.startswith('/') or '..' in normalized.split('/'):
            return None
        try:
            with open(self.manifest_path(task), encoding='utf-8') as h: manifest=json.load(h)
        except (OSError, ValueError): return None
        item=next((a for a in manifest.get('artifacts',[]) if a.get('path')==normalized),None)
        if not item:return None
        path=_safe_join(task.get('result_dir') or '', *normalized.split('/'))
        if not os.path.isfile(path) or not _path_is_within(task.get('result_dir') or '',path): return None
        digest=hashlib.sha256(Path(path).read_bytes()).hexdigest()
        return {'path':normalized,'physical_path':path,'sha256':digest,'size':os.path.getsize(path),'type':item.get('type')}

def snapshot_artifact(source: dict, destination: str) -> dict:
    os.makedirs(os.path.dirname(destination), exist_ok=True); shutil.copyfile(source['physical_path'], destination); os.chmod(destination,0o440)
    return {k:source[k] for k in ('path','sha256','size','type') if k in source}
