from pathlib import Path
import subprocess
import sys
from unittest.mock import Mock

import pytest
from sapera import user_cli


def test_help_no_arguments_without_interactive(monkeypatch, capsys):
    monkeypatch.setattr(user_cli.sys.stdin,'isatty',lambda: False)
    assert user_cli.main([])==0
    assert 'sapera scan' in capsys.readouterr().out


def test_new_version_and_doctor(capsys):
    with pytest.raises(SystemExit) as e:
        user_cli.main(['--version'])
    assert e.value.code == 0
    assert user_cli.main(['doctor']) == 0
    assert '27 recognized program hashes' in capsys.readouterr().out


def test_scan_delegates_to_identify(monkeypatch):
    called=[]
    monkeypatch.setattr(user_cli.cli,'main',lambda argv: called.append(argv) or 0)
    assert user_cli.main(['scan','example.chd'])==0
    assert called==[['--identify','example.chd']]


def test_experimental_must_be_explicit(monkeypatch, tmp_path):
    fakebuild={'games':['Test'], 'profiles':{'x':{'status':'static_candidate'}}}
    monkeypatch.setattr(user_cli,'_one_profile',lambda *a:(fakebuild,'x',{'status':'static_candidate'}))
    captured=[]
    monkeypatch.setattr(user_cli.cli,'main',lambda argv:captured.append(argv) or 0)
    assert user_cli.main(['patch','dummy.chd'])==1
    assert captured==[]
    assert user_cli.main(['patch','dummy.chd','--experimental','--output-dir',str(tmp_path)])==0
    assert '--allow-unverified' in captured[0]
    assert '--output-dir' in captured[0]


def test_known_incomplete_requires_double_opt_in(monkeypatch):
    fakebuild={'games':['Test']}
    monkeypatch.setattr(user_cli,'_one_profile',lambda *a:(fakebuild,'x',{'status':'known_incomplete'}))
    called=[]
    monkeypatch.setattr(user_cli.cli,'main',lambda argv:called.append(argv) or 0)
    assert user_cli.main(['patch','test.raw','--experimental'])==1
    assert called == []
    assert user_cli.main(['patch','test.raw','--experimental','--allow-incomplete'])==0
    assert '--allow-incomplete' in called[0]


def test_no_external_chdman_needed_for_raw(monkeypatch, tmp_path):
    # Friendly CLI requires no binary media or external commands just to show help.
    code = subprocess.run([sys.executable,'-m','sapera','doctor'],capture_output=True,text=True)
    assert code.returncode == 0
    assert 'RAW/BIN support: ready' in code.stdout
