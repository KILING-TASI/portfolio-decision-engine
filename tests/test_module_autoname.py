from pathlib import Path
import json
from portfolio_engine.__main__ import main


def test_module_auto_name_preserves_existing_account_report(tmp_path):
    source = Path(__file__).resolve().parents[1] / 'examples/account-exposure-demo.json'
    existing = tmp_path / 'account'
    existing.mkdir()
    sentinel = existing / 'keep.txt'
    sentinel.write_text('original', encoding='utf-8')
    assert main(['account-exposure', '--input', str(source), '--out-dir', str(existing), '--auto-name']) == 0
    assert sentinel.read_text(encoding='utf-8') == 'original'
    generated = list(tmp_path.glob('account-*'))
    assert len(generated) == 1
    assert main(['account-exposure', '--input', str(source), '--out-dir', str(tmp_path / 'reference')]) == 0
    actual = json.loads((generated[0] / 'account-exposure.json').read_text(encoding='utf-8'))
    reference = json.loads((tmp_path / 'reference/account-exposure.json').read_text(encoding='utf-8'))
    assert actual == reference
