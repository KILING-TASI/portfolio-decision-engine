import hashlib
import json
import os
import tempfile
from contextlib import contextmanager
from pathlib import Path

from .io import write_json
from .validation import InputError


def strict_json(text):
    def pairs(items):
        result={}
        for key,value in items:
            if key in result: raise InputError("duplicate JSON key: "+key)
            result[key]=value
        return result
    def constant(value): raise InputError("nonfinite JSON constant: "+value)
    def number(value):
        import math
        value=float(value)
        if not math.isfinite(value): raise InputError("nonfinite JSON number")
        return value
    return json.loads(text,object_pairs_hook=pairs,parse_constant=constant,parse_float=number)


def read_json(path):
    return strict_json(Path(path).read_text(encoding="utf-8-sig"))


def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


@contextmanager
def atomic_output(destination):
    destination=Path(destination)
    if destination.exists(): raise FileExistsError("output already exists; choose a new directory")
    destination.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".portfolio-stage-",dir=destination.parent) as temporary:
        stage=Path(temporary)/"result";stage.mkdir()
        yield stage
        if destination.exists(): raise FileExistsError("output created during calculation; nothing overwritten")
        os.rename(stage,destination)


def method_hashes():
    return {p.name:digest(p) for p in sorted(Path(__file__).parent.glob("*.py"))}


def manifest(directory):
    root=Path(directory)
    files={p.relative_to(root).as_posix():digest(p) for p in sorted(root.rglob("*")) if p.is_file() and p.name!="report-manifest.json"}
    value={"schema_version":1,"files":files,"methods":method_hashes(),
           "scope":"stored content and method integrity; not source truth, numeric validity or visual acceptance"}
    write_json(root/"report-manifest.json",value)
    return value


def verify(directory):
    root=Path(directory).resolve();data=read_json(root/"report-manifest.json")
    if data.get("schema_version")!=1 or not isinstance(data.get("files"),dict) or not isinstance(data.get("methods"),dict):
        raise InputError("invalid manifest")
    problems=[]
    for name,expected in data["files"].items():
        relative=Path(name);path=(root/relative).resolve()
        if relative.is_absolute() or ".." in relative.parts or not path.is_relative_to(root):
            raise InputError("manifest path escapes report directory")
        if not path.is_file(): problems.append("missing: "+name)
        elif digest(path)!=expected: problems.append("changed: "+name)
    actual={p.relative_to(root).as_posix() for p in root.rglob("*") if p.is_file() and p.name!="report-manifest.json"}
    if actual!=set(data["files"]): problems.append("report file set changed")
    methods=method_hashes();changed=sorted(name for name in set(methods)|set(data["methods"]) if methods.get(name)!=data["methods"].get(name))
    return {"status":"content_mismatch" if problems else "stored_content_verified_method_changed" if changed else "stored_content_verified",
            "problems":problems,"method_changes":changed,"source_verification":"not_verified","visual_review":"not_performed"}
