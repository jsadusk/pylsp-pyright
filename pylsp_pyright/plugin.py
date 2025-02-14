import logging
import subprocess
import json
from typing import List, Dict, Any
import sys

from pylsp import hookimpl, uris
from pylsp.config.config import Config
from pylsp.workspace import Document, Workspace


logger = logging.getLogger(__name__)

@hookimpl
def pylsp_lint(
    config: Config, workspace: Workspace, document: Document, is_saved: bool
) -> List[Dict[str, Any]]:
    """
    Call the linter.

    Parameters
    ----------
    config : Config
        The pylsp config.
    workspace : Workspace
        The pylsp workspace.
    document : Document
        The document to be linted.
    is_saved : bool
        Weather the document is saved.

    Returns
    -------
    List[Dict[str, Any]]
        List of the linting data.

    """
    if not is_saved:
        return []

    settings = config.plugin_settings("pylsp_pyright")
    executable = "basedpyright" if settings["based"] else "pyright"
    command = [executable, "--outputjson"]
    if settings["level"]:
        level = settings["level"]
        command.append(f"--level={level}")
    if settings["pythonpath"]:
        pythonpath = settings["pythonpath"]
        command.append(f"--pythonpath={pythonpath}")
    if settings["ignoreexternal"]:
        command.append("--ignoreexternal")
    if settings["skipunannotated"]:
        command.append("--skipunannotated")
    command.append(document.path)
    proc = subprocess.run(command, capture_output=True)
    output = proc.stdout
    report = json.loads(output)
    pyright_diagnostics = report["generalDiagnostics"]
    lsp_diagnostics = []
    for pyright_diagnostic in pyright_diagnostics:
        if {"range", "message", "severity", "rule"} <= pyright_diagnostic.keys():
            lsp_diagnostics.append(
                {
                    "source": "pyright",
                    "range": pyright_diagnostic["range"],
                    "message": pyright_diagnostic["message"],
                    "severity": 1 if pyright_diagnostic["severity"] == "error" else 3,
                    "code": pyright_diagnostic["rule"],
                }
            )

    return lsp_diagnostics

@hookimpl
def pylsp_settings():
    logger.error("Initializing pylsp_pyright")

    # Disable default plugins that conflicts with our plugin
    return {
        "plugins": {
            "pylsp_pyright": {
                "based": True,
                "level": None,
                "pythonpath": None,
                "ignoreexternal": False,
                "skipunannotated": False,
            }
        },
    }

