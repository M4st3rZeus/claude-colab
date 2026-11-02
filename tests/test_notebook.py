"""Consistency checks for the Colab server notebook."""

import json
import re
from pathlib import Path

import pytest

from claude_colab import __version__

NOTEBOOK = Path(__file__).parent.parent / "notebooks" / "claude_colab_server.ipynb"


@pytest.fixture(scope="module")
def code_cells():
    nb = json.loads(NOTEBOOK.read_text(encoding="utf-8"))
    return ["".join(c["source"]) for c in nb["cells"] if c["cell_type"] == "code"]


def _cell_containing(cells, needle):
    matches = [c for c in cells if needle in c]
    assert matches, f"No notebook cell contains {needle!r}"
    return matches[0]


def test_notebook_version_matches_package(code_cells):
    cell = _cell_containing(code_cells, "VERSION = ")
    match = re.search(r"VERSION = ['\"]([^'\"]+)['\"]", cell)
    assert match.group(1) == __version__


def test_tunnel_dropdown_offers_both_options(code_cells):
    cell = _cell_containing(code_cells, "TUNNEL = ")
    line = next(l for l in cell.splitlines() if l.startswith("TUNNEL = "))
    assert "#@param" in line
    assert '"cloudflare"' in line
    assert '"ngrok"' in line


def test_tunnel_cell_handles_both_options(code_cells):
    cell = _cell_containing(code_cells, "connection_string")
    assert "ngrok.forward" in cell
    assert "cloudflared" in cell
