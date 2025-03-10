import logging
import asyncio
from asyncio.subprocess import Process, PIPE, create_subprocess_exec
import json
from typing import List, Dict, Any, Optional
from copy import copy

from pylsp import hookimpl, uris, lsp
from pylsp.config.config import Config
from pylsp.workspace import Document, Workspace


logger = logging.getLogger(__name__)

diagnostics: Dict[str, Any] = {}
pyright_process: Optional[Process] = None
loop: Any = None

command_base: Optional[List[str]] = None

def pyright_command(config: Config, watched_files: List[str]) -> List[str]:
    global command_base
    if command_base is None:
        settings = config.plugin_settings("pylsp_pyright")
        executable = "basedpyright" if settings["based"] else "pyright"
        command_base = [executable, "--outputjson", "--watch"]
        if settings["level"]:
            level = settings["level"]
            command_base.append(f"--level={level}")
        if settings["pythonpath"]:
            pythonpath = settings["pythonpath"]
            command_base.append(f"--pythonpath={pythonpath}")
        if settings["ignoreexternal"]:
            command_base.append("--ignoreexternal")
        if settings["skipunannotated"]:
            command_base.append("--skipunannotated")
    command = copy(command_base)
    command.extend(watched_files)
    return command

async def get_pyright_process(config: Config, watch_file: str) -> Process:
    global diagnostics
    global pyright_process
    logger.error("in get_pyright_process")
    if pyright_process is not None and watch_file in diagnostics:
        logger.error("returning existing process")
        return pyright_process
    
    if pyright_process is not None:
        logger.error("killing old process")
        pyright_process.terminate()
        await pyright_process.wait()

    watched_files = list(diagnostics.keys())
    watched_files.append(watch_file)

    command = pyright_command(config, watched_files)
    command_line = " ".join(command)
    logger.error(f"starting new process {command_line}")
    pyright_process = await create_subprocess_exec(command[0], *command[1:], stdout=PIPE)
    logger.error("returning new process")
    return pyright_process

async def update_diagnostics(config: Config, watch_file: str) -> bool:
    logger.error("In update_diagnostics")
    settings = config.plugin_settings("pylsp_pyright")
    timeout = settings["update_timeout"] if watch_file in diagnostics else settings["initial_timeout"]
    process = await get_pyright_process(config, watch_file)
    stdout = process.stdout
    assert stdout

    json_chunks = []
    chunk = None
    logger.error("getting diagnostics output")
    while True:
        try:
            line_bytes: bytes = await asyncio.wait_for(stdout.readline(), timeout)
        except asyncio.TimeoutError:
            logger.error("timeout getting diagnostics output")
            break
        if len(line_bytes) == 0:
            raise RuntimeError("Empty output without timeout")
        line = line_bytes.decode('utf-8')
        logger.error(f"got line [{line}]")
        if line == "\n" or line == "":
            continue
        elif line == "{\n":
            if chunk is None:
                chunk = line
            else:
                raise RuntimeError(f"Broken json chunk: [{chunk}{line}]")
                #logger.error(f"Broken json chunk: \n {chunk}")
                chunk = None
        elif chunk is not None:
            chunk = chunk + line
            if line == "}\n":
                json_chunks.append(json.loads(chunk))
        else:
            raise RuntimeError(f"Broken json chunk start:[{line}]")
            #logger.error(f"Broken json chunk start:\n{line}")

    all_updated_files = set()
    logger.error("parsing chunks")
    for json_chunk in json_chunks:
        updated_files = set(d["file"] for d in json_chunk["generalDiagnostics"])
        for filename in updated_files:
            diagnostics[filename] = []
        for diagnostic in json_chunk["generalDiagnostics"]:
            converted = convert_diagnostic(diagnostic)
            if converted:
                logger.error(f"adding diagnostic {converted}")
                diagnostics[diagnostic["file"]].append(converted)
        all_updated_files.update(updated_files)

    logger.error("done parsing chunks")
    return watch_file in all_updated_files

def convert_diagnostic(pyright_diagnostic: dict[str, Any]) -> Optional[dict[str, Any]]:
    if {"range", "message", "severity", "rule"} <= pyright_diagnostic.keys():
        if pyright_diagnostic["severity"] == "error":
            severity = lsp.DiagnosticSeverity.Error
        elif pyright_diagnostic["severity"] == "warning":
            severity = lsp.DiagnosticSeverity.Warning
        elif pyright_diagnostic["severity"] == "info":
            severity = lsp.DiagnosticSeverity.Information
        elif pyright_diagnostic["severity"] == "hint":
            severity = lsp.DiagnosticSeverity.Hint
        return {
            "source": "pyright",
            "range": pyright_diagnostic["range"],
            "message": pyright_diagnostic["message"],
            "severity": severity,
            "code": pyright_diagnostic["rule"],
        }
    else:
        logger.info(f"Unknown diagnostic: {pyright_diagnostic}")
        return None

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
    global diagnostics
    global loop
    logger.error("In pyright plugin")
    if is_saved:
        if loop is None:
            loop = asyncio.new_event_loop()

            loop.run_until_complete(update_diagnostics(config, document.path))
            logger.error("Updated diagnostics")
    if document.path in diagnostics:
        logger.error(f"sending diagnostics {diagnostics[document.path]}")
        return diagnostics[document.path]
    else:
        return []
            

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
                "update_timeout": 3,
                "initial_timeout": 15,
            }
        },
    }

