# SPDX-License-Identifier: MIT
"""Original synthetic bars, not real securities, exchange sessions or profitability evidence."""
import json
from datetime import datetime,timedelta,timezone
from pathlib import Path


def example():
    origin=datetime(2024,1,1,16,tzinfo=timezone(timedelta(hours=8)))
    def stamp(day):return (origin+timedelta(days=day)).isoformat()
    samples=[]
    for day in range(10,42,2):
        for asset in range(4):
            bars=[]
            for step in range(8):
                close=10+asset+step*.03+day*.005*(asset+1)
                bars.append(dict(at=stamp(day-8+step),availableAt=stamp(day-8+step),
                                 open=close-.02,high=close+.1,low=close-.1,close=close,
                                 volumeShares=1000+asset*100+step*10,source='original-synthetic-teaching'))
            samples.append(dict(id=f'd{day}-a{asset}',security=f'TEACHING-{asset}',signalAt=stamp(day),
                                universeAvailableAt=stamp(0),membershipAtSignal=True,
                                adjustmentEvidence=dict(source='synthetic-no-corporate-actions',availableAt=stamp(0)),
                                history=bars,label=dict(returnStartAt=stamp(day),returnEndAt=stamp(day+1),
                                availableAt=stamp(day+1),horizonRecords=1,
                                forwardReturn=(asset-1.5)*.008+(day%7-3)*.001,source='original-synthetic-label')))
    def fold(train_start,train_end,val_start,val_end,test_start,test_end):
        return dict(trainStart=stamp(train_start),trainEnd=stamp(train_end),validationStart=stamp(val_start),
                    validationEnd=stamp(val_end),testStart=stamp(test_start),testEnd=stamp(test_end))
    return dict(schemaVersion='cnn-factor/1',researchId='original-cnn-teaching',dataVersion='synthetic/1',
                dataKind='synthetic-teaching',asOf=stamp(50),universeDefinition='Four invented teaching securities',
                universeVersion='1',priceBasis='synthetic-consistent-no-actions',volumeBasis='shares',
                labelDefinition='one-record synthetic simple total return',returnUnit='decimal-simple-total-return',
                lookbackRecords=8,horizonRecords=1,parameters=dict(epochs=4,seed=17,learningRate=.01),
                split=fold(10,18,20,24,26,30),folds=[fold(10,18,20,24,26,30),fold(10,26,28,32,34,40)],samples=samples)


if __name__=='__main__':
    output=Path(__file__).with_name('train.json')
    if output.exists():raise SystemExit('示例已存在，未覆盖')
    output.write_text(json.dumps(example(),ensure_ascii=False,indent=2),encoding='utf-8')
