"""Bundled config loader for the plugin."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, Optional


_MISSING = object()


def _package_root() -> Path:
    return Path(__file__).resolve().parent


class ConfigManager:
    """Load and serve the plugin's bundled JSON config."""

    def __init__(self) -> None:
        self._config_path = _package_root() / "resources" / "interaction_config.json"
        self._config: Dict[str, Any] = {}
        self.reload()

    @property
    def path(self) -> Path:
        return self._config_path

    @property
    def raw(self) -> Dict[str, Any]:
        return self._config

    def reload(self) -> None:
        with self._config_path.open("r", encoding="utf-8") as handle:
            self._config = json.load(handle)

    def _lookup(self, node: Any, keys: Iterable[str], default: Any = None) -> Any:
        current = node
        for key in keys:
            if not isinstance(current, dict) or key not in current:
                return default
            current = current[key]
        return current

    def get(self, *keys: str, default: Any = None) -> Any:
        return self._lookup(self._config, keys, default=default)

    def profiles(self) -> Iterable[str]:
        profiles = self.get("profiles", default={})
        if isinstance(profiles, dict):
            return profiles.keys()
        return ()

    def has_profile(self, profile_name: str) -> bool:
        return profile_name in self.profiles()

    def resolve_profile(self, profile_name: Optional[str] = None) -> str:
        profiles = self.get("profiles", default={})
        if not isinstance(profiles, dict):
            profiles = {}
        configured_default = str(self.get("plugin", "default_profile", default="Maestro"))

        if profile_name and profile_name in profiles:
            return profile_name
        if configured_default in profiles or not profiles:
            return configured_default
        return next(iter(profiles))

    def default_profile(self) -> str:
        configured_default = str(self.get("plugin", "default_profile", default="Maestro"))
        return self.resolve_profile(configured_default)

    def profile_data(self, profile_name: Optional[str] = None) -> Dict[str, Any]:
        resolved_profile = self.resolve_profile(profile_name)
        profile = self.get("profiles", resolved_profile, default={})
        if isinstance(profile, dict):
            return profile
        return {}

    def get_profile(self, profile_name: Optional[str], *keys: str, default: Any = None) -> Any:
        return self._lookup(self.profile_data(profile_name), keys, default=default)

    def get_for_profile(self, profile_name: Optional[str], *keys: str, default: Any = None) -> Any:
        override = self.get_profile(profile_name, "overrides", *keys, default=_MISSING)
        if override is not _MISSING:
            return override

        scoped_value = self.get_profile(profile_name, *keys, default=_MISSING)
        if scoped_value is not _MISSING:
            return scoped_value

        return self.get(*keys, default=default)

    def interaction_config(self, interaction_type: str, profile_name: Optional[str] = None) -> Dict[str, Any]:
        settings = self.get("interactions", interaction_type, default={})
        merged_settings = dict(settings) if isinstance(settings, dict) else {}

        override = self.get_profile(profile_name, "overrides", "interactions", interaction_type, default=_MISSING)
        if override is _MISSING:
            override = self.get_profile(profile_name, "interactions", interaction_type, default={})

        if isinstance(override, dict):
            merged_settings.update(override)
        return merged_settings

    def set_interaction_color(self, interaction_type: str, color_value: str) -> None:
        interactions = self._config.setdefault("interactions", {})
        if not isinstance(interactions, dict):
            return
        node = interactions.setdefault(interaction_type, {})
        if not isinstance(node, dict):
            return
        node["color"] = color_value
