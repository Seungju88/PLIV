"""PyMOL plugin entrypoint for PLIV."""

from __future__ import annotations

from typing import Optional

PLUGIN_MENU_LABEL = "PLIV"

_controller = None


def __init_plugin__(app: Optional[object] = None) -> None:
    """Register the plugin in the PyMOL menu."""
    from pymol.plugins import addmenuitemqt

    addmenuitemqt(PLUGIN_MENU_LABEL, open_plugin)
    _register_commands()


def _register_commands() -> None:
    """Expose a small command surface for scripted use."""
    try:
        from pymol import cmd
    except ImportError:
        return

    cmd.extend("pliv_open", open_plugin)


def open_plugin() -> None:
    """Open the plugin dialog."""
    global _controller

    from .gui import PLIVController

    if _controller is None:
        _controller = PLIVController()
    _controller.show()
