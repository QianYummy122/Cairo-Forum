"""全局配置加载器。

整个项目统一从本模块读取配置，配置源为项目根目录下的 ``config.yml``。
配置完全自包含：不读取任何环境变量，也不使用 ``.env``。

用法::

    from utils.config import CONFIG, PROJECT_ROOT

    model = CONFIG.get("llm.multimodal.model")
    out_dir = CONFIG.path("paths.output_dir")      # -> 绝对路径 Path
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Optional, Union

import yaml

# 项目根目录（utils/ 的上一级）与配置文件路径
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
CONFIG_PATH: Path = PROJECT_ROOT / "config.yml"


def _load(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(
            f"未找到配置文件：{path}\n请确认 config.yml 位于项目根目录。"
        )
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


class Config:
    """对 YAML 配置的轻量封装，支持点号路径访问。"""

    def __init__(self, data: dict):
        self._data = data

    # ---- 读取 ---------------------------------------------------------------
    def get(self, path: str, default: Any = None) -> Any:
        """按点号路径读取配置，例如 ``CONFIG.get("milvus.dim")``。"""
        node: Any = self._data
        for key in path.split("."):
            if not isinstance(node, dict) or key not in node:
                return default
            node = node[key]
        return node

    def section(self, path: str) -> dict:
        """读取一个配置段，始终返回 dict。"""
        value = self.get(path, {})
        return value if isinstance(value, dict) else {}

    def path(self, key: str, default: Optional[str] = None) -> Path:
        """读取一个路径配置并解析为相对于项目根目录的绝对路径。"""
        raw = self.get(key, default)
        if raw is None:
            raise KeyError(f"配置项 {key} 不存在且没有默认值")
        p = Path(str(raw))
        return p if p.is_absolute() else (PROJECT_ROOT / p)

    def as_dict(self) -> dict:
        """返回原始配置字典（只读用途）。"""
        return self._data

    def __getitem__(self, path: str) -> Any:
        return self.get(path)

    def __contains__(self, path: str) -> bool:
        marker = object()
        return self.get(path, marker) is not marker


CONFIG = Config(_load(CONFIG_PATH))


def get(path: str, default: Any = None) -> Any:
    """模块级快捷函数，等价于 ``CONFIG.get``。"""
    return CONFIG.get(path, default)


def ensure_dir(path: Union[str, Path]) -> Path:
    """确保目录存在并返回 Path。"""
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


__all__ = ["CONFIG", "Config", "PROJECT_ROOT", "CONFIG_PATH", "get", "ensure_dir"]
