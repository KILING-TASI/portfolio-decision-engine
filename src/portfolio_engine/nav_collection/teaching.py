"""Original synthetic response, not a market observation."""
from .nav import parse

def build():
    req=dict(id='teaching',source='eastmoney-fund-nav',fundCode='900001',start='2026-01-02',end='2026-01-03',asOf='2026-01-03',currency='CNY',frequency='daily',fields=['unit_nav','distribution_text'])
    raw=b'var fS_code="900001";var fS_name="Teaching synthetic fund";var Data_netWorthTrend=[{"x":1767283200000,"y":1.0000,"unitMoney":""},{"x":1767369600000,"y":1.0500,"unitMoney":"unverified teaching text"}];'
    result=parse(raw,req,retrieved_at='2026-01-04T10:00:00+08:00',origin='teaching-synthetic-response')
    return result,raw
