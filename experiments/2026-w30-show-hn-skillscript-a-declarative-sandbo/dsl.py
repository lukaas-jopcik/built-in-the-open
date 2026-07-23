"""Parser/validator for .sky files (stdlib json only, no PyYAML)."""
import json
import os


class SkyError(ValueError):
    pass


def load_sky(path):
    with open(path, "r") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise SkyError(f"invalid .sky JSON in {path}: {e}") from e

    if "steps" not in data or not isinstance(data["steps"], list):
        raise SkyError(f"{path}: missing top-level 'steps' list")
    if not data["steps"]:
        raise SkyError(f"{path}: 'steps' must not be empty")

    seen = set()
    for i, step in enumerate(data["steps"]):
        if "id" not in step:
            raise SkyError(f"{path}: step at index {i} missing 'id'")
        if "tool" not in step:
            raise SkyError(f"{path}: step '{step['id']}' missing 'tool'")
        if step["id"] in seen:
            raise SkyError(f"{path}: duplicate step id '{step['id']}'")
        seen.add(step["id"])
        step.setdefault("deps", [])
        step.setdefault("args", {})

    data.setdefault("output", "report.json")
    data["_base_dir"] = os.path.dirname(os.path.abspath(path))
    return data
