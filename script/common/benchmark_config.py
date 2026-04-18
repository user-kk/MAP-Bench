#!/usr/bin/env python3
import json
import re
from pathlib import Path
from typing import Any, Dict, Optional, Union

PLACEHOLDER_RE = re.compile(r"__MB_[A-Za-z0-9_]+__")
DEFAULT_CONFIG_PATH = Path(__file__).with_name("benchmark_config.json")


def load_benchmark_config(config_path: Optional[Union[Path, str]] = None) -> Dict[str, Any]:
    path = Path(config_path) if config_path else DEFAULT_CONFIG_PATH
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def get_dataset_conf(config: Dict[str, Any], system: str, dataset: str) -> Dict[str, Any]:
    try:
        return config["datasets"][dataset][system]
    except KeyError as exc:
        raise KeyError(f"缺少数据集配置: dataset={dataset}, system={system}") from exc


def get_query_params(
    config: Dict[str, Any], system: str, workload: str, dataset: str
) -> Dict[str, Any]:
    return (
        config.get("queries", {})
        .get(system, {})
        .get(workload, {})
        .get(dataset, {})
    )


def render_query_template(text: str, params: Dict[str, Any]) -> str:
    rendered = text
    for key, value in params.items():
        placeholder = f"__MB_{key}__"
        if placeholder not in rendered:
            raise KeyError(f"模板中缺少占位符 {placeholder}")
        rendered = rendered.replace(placeholder, str(value))

    unresolved = sorted(set(PLACEHOLDER_RE.findall(rendered)))
    if unresolved:
        raise ValueError(f"模板仍有未替换占位符: {', '.join(unresolved)}")
    return rendered
