# SPDX-License-Identifier: MIT
"""Original synthetic CN edge conditions; not actual stock histories or exchange calendars."""
from datetime import datetime,timedelta
import copy,json
from pathlib import Path
from make_example import example


def generate():
    spec=example();spec['researchId']='original-pattern-comparison-teaching';spec['dataVersion']='pattern-synthetic/1'
    spec['comparisonPlan']='ohlcv-vs-rules-vs-geometry/1';spec['studyHorizons']=[1,5,10,20,60]
    spec['patternParameters']={'trendRecords':3,'trendReturnMin':.01}
    for row in spec['samples']:
        asset=int(row['security'][-1]);bars=row['history']
        if asset==0: shapes=[dict(open=10,close=10.5,high=10.55,low=8.5)];prior=[12,11,10]
        elif asset==1:shapes=[dict(open=10,close=10.5,high=12,low=9.95)];prior=[10,11,12]
        elif asset==2:shapes=[dict(open=10,close=10,high=11,low=9)];prior=[10,10,10]
        else:shapes=[dict(open=11,close=10,high=11.05,low=9.95),dict(open=9.9,close=11.1,high=11.15,low=9.85)];prior=[12,11,10]
        length=len(shapes)
        for b,value in zip(bars[-length-3:-length],prior):b.update(open=value,close=value,high=value+.05,low=value-.05)
        for b,shape in zip(bars[-length:],shapes):b.update(shape)
        row['cnExecution']=dict(entryTradable=None,exitTradable=None,tPlusOneSatisfied=None,settlementAvailable=None,feesKnown=None)
        if asset==0:row['cnExecution'].update(entryTradable=False,tPlusOneSatisfied=False)
        row['outcomes']=[copy.deepcopy(row['label'])]
        for h in (5,10,20,60):
            if asset==2 and h==20:continue  # Deliberately unknown outcome, not zero-filled.
            outcome=copy.deepcopy(row['label']);end=(datetime.fromisoformat(row['signalAt'])+timedelta(days=h)).isoformat()
            outcome.update(horizonRecords=h,returnEndAt=end,availableAt=end,forwardReturn=row['label']['forwardReturn']*min(h,5),source='original-synthetic-outcome')
            if asset%2==0:
                outcome.update(benchmarkReturn=.001*h,benchmarkSource='original-synthetic-benchmark',benchmarkStartAt=outcome['returnStartAt'],benchmarkEndAt=end,benchmarkAvailableAt=end)
            row['outcomes'].append(outcome)
    return spec


if __name__=='__main__':
    target=Path(__file__).with_name('patterns.json')
    if target.exists():raise SystemExit('示例已存在，未覆盖')
    target.write_text(json.dumps(generate(),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
