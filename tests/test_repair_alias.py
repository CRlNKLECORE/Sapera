from sapera.user_cli import parser, _legacy_options


def test_repair_alias_and_patch_compatibility():
    for word in ('repair', 'patch'):
        args = parser().parse_args([word, 'game.chd', '--experimental'])
        opts = _legacy_options(args, 'patch')
        assert '--allow-unverified' in opts
        assert '--output-dir' in opts
        assert args.encoder == 'neutral'


def test_scan_is_read_only():
    args = parser().parse_args(['scan', 'game.chd'])
    assert _legacy_options(args, 'scan') == ['--identify']
