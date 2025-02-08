import logging

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
    settings = config.plugin_settings("pylsp_pyright")

@hookimpl
def pylsp_settings():
    logger.info("Initializing pylsp_pyright")

    # Disable default plugins that conflicts with our plugin
    return {
        "plugins": {
            "pylsp_pyright": {
                "enabled": True,
                "based
                "level": 0,
            }
        },
    }


@hookimpl
def pylsp_code_actions(config, workspace, document, range, context):
    logger.info("textDocument/codeAction: %s %s %s", document, range, context)

    return [
        {
            "title": "Extract method",
            "kind": "refactor.extract",
            "command": {
                "command": "example.refactor.extract",
                "arguments": [document.uri, range],
            },
        },
    ]


@hookimpl
def pylsp_execute_command(config, workspace, command, arguments):
    logger.info("workspace/executeCommand: %s %s", command, arguments)

    if command == "example.refactor.extract":
        current_document, range = arguments

        workspace_edit = {
            "changes": {
                current_document: [
                    {
                        "range": range,
                        "newText": "replacement text",
                    },
                ]
            }
        }

        logger.info("applying workspace edit: %s %s", command, workspace_edit)
        workspace.apply_edit(workspace_edit)


@hookimpl
def pylsp_definitions(config, workspace, document, position):
    logger.info("textDocument/definition: %s %s", document, position)

    filename = __file__
    uri = uris.uri_with(document.uri, path=filename)
    with open(filename) as f:
        lines = f.readlines()
        for lineno, line in enumerate(lines):
            if "def pylsp_definitions" in line:
                break
    return [
        {
            "uri": uri,
            "range": {
                "start": {
                    "line": lineno,
                    "character": 4,
                },
                "end": {
                    "line": lineno,
                    "character": line.find(")") + 1,
                },
            }
        }
    ]
