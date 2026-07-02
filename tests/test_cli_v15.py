from __future__ import annotations

import json

from tests.fixtures_bun import build_macho_fixture

from claude_monkey.cli import main


def read_json(capsys):
    return json.loads(capsys.readouterr().out)


def test_inspect_binary_json_command(tmp_path, capsys):
    binary = tmp_path / "claude"
    binary.write_bytes(build_macho_fixture()[0])
    assert main(["inspect-binary", "--source", str(binary), "--json"]) == 0
    payload = read_json(capsys)
    assert payload["ok"] is True
    assert payload["sourcePath"] == str(binary)
    assert payload["modules"][0]["path"] == "/$bunfs/root/src/entrypoints/cli.js"
