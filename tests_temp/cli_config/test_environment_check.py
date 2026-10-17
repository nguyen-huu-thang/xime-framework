"""Check raw overlays for typos, and merged overlays for required fields."""

from pathlib import Path

import pytest
import yaml

from xime.cli._config_check import check


def _check(tmp_path, common=None, local=None, server=None):
    raw = {"xime": {"dev": True}, "environments": {"local": local or {}, "server": server or {}}}
    raw.update(common or {})
    path = tmp_path / "application.yml"
    path.write_text(yaml.safe_dump(raw), encoding="utf-8")
    return check(path)


@pytest.mark.parametrize("branch", ["local", "server"])
@pytest.mark.parametrize("block,expected", [
    ({"websever": {}}, "websever"),
    ({"webserver": {"ss1": {}}}, "webserver.ss1"),
    ({"webserver": {"ssl": {"certfil": "/cert"}}}, "webserver.ssl.certfil"),
])
def test_checks_selected_and_unselected_raw_branch(tmp_path, branch, block, expected):
    result = _check(tmp_path, **{branch: block})
    assert result.verdict == "findings"
    assert f"environments.{branch}.{expected}" in [f.where for f in result.findings]


@pytest.mark.parametrize("branch", [None, "local", "server"])
@pytest.mark.parametrize("plural", [False, True])
@pytest.mark.parametrize("endpoint,tail", [
    ({"ss1": {}}, "ss1"), ({"ssl": {"certfil": "/cert"}}, "ssl.certfil"),
])
def test_dynamic_process_and_endpoint_names_are_checked(tmp_path, branch, plural, endpoint, tail):
    process = {"web": {"customer-http-v2": {"port": 0, **endpoint}}}
    block = {"processes": {"custom-worker": process}} if plural else {"process": process}
    result = _check(tmp_path, **({branch: block} if branch else {"common": block}))
    prefix = f"environments.{branch}." if branch else ""
    topology = "processes.custom-worker" if plural else "process"
    assert f"{prefix}{topology}.web.customer-http-v2.{tail}" in [f.where for f in result.findings]


def test_inherited_required_fields_do_not_trigger_false_findings(tmp_path):
    result = _check(
        tmp_path, common={"lmdb": {"path": "/common"}},
        local={"lmdb": {"map_size": "1MB"}}, server={"lmdb": {"map_size": "2MB"}},
    )
    assert result.verdict == "clean"


def test_common_required_field_can_be_supplied_by_both_branches(tmp_path):
    result = _check(
        tmp_path, common={"lmdb": {}},
        local={"lmdb": {"path": "/local"}}, server={"lmdb": {"path": "/server"}},
    )
    assert result.verdict == "clean"


def test_missing_required_field_is_checked_on_effective_branch(tmp_path):
    result = _check(tmp_path, common={"lmdb": {}}, server={"lmdb": {"path": "/server"}})
    assert [f.where for f in result.findings] == ["environments.local.lmdb.path"]


def test_alias_conflict_created_by_merge_is_reported(tmp_path):
    result = _check(tmp_path, common={"server": {}}, server={"webserver": {}})
    assert any(f.where == "environments.server.server/webserver" for f in result.findings)


def test_app_blocks_http_and_empty_ssl_remain_valid(tmp_path):
    result = _check(tmp_path, local={
        "my_app": {"arbitrary": {"password": "private-value"}},
        "webserver": {"ssl": {}},
        "processes": {"arbitrary-worker": {"web": {"arbitrary-endpoint": {"ssl": {}}}}},
    })
    assert result.verdict == "clean"


def test_findings_do_not_echo_credentials_or_key_material(tmp_path):
    secret = "sensitive-example-do-not-print"
    result = _check(tmp_path, server={"webserver": {
        "ssl": {"certfil": secret, "keyfile_password": secret},
    }})
    assert result.verdict == "findings"
    assert secret not in repr(result)


@pytest.mark.parametrize("kind", ["quoted-password", "password-in-url", "secret-in-tag"])
def test_yaml_parse_failures_do_not_echo_credentials(tmp_path, kind):
    secret = "parser-secret-7x"
    contents = {
        "quoted-password": 'webserver:\n  ssl:\n    keyfile_password: "' + secret + '\n',
        "password-in-url": 'database:\n  url: [postgresql://user:' + secret + '@example.invalid/db\n',
        "secret-in-tag": 'webserver:\n  ssl:\n    keyfile_password: !' + secret + ' value\n',
    }
    path = tmp_path / "application.yml"
    path.write_text(contents[kind], encoding="utf-8")
    result = check(path)
    assert result.verdict == "inconclusive"
    assert secret not in repr(result)
    assert result.unreadable is not None
    assert "line" in result.unreadable and "column" in result.unreadable
    assert str(path) in result.unreadable


def test_endpoint_ssl_shape_is_checked(tmp_path: Path):
    result = _check(tmp_path, server={"process": {"web": {"http": {"ssl": "bad"}}}})
    assert any(f.where == "environments.server.process.web.http.ssl" for f in result.findings)
