# SPDX-License-Identifier: MIT
"""Optional CNN command and verified frozen-artifact loading."""
import argparse
import hashlib
import sys
from pathlib import Path
from . import cnn_contract as contract
from .review_io import read, publish, digest, instant


def frozen(directory, expected):
    root=Path(directory)
    if root.is_symlink() or not root.is_dir(): raise ValueError('冻结目录无效')
    receipt=read(root/'receipt.json')
    if digest(receipt)!=expected: raise ValueError('冻结回执摘要不一致')
    for name in ('input.json','result.json','report.html'):
        path=root/name
        if path.is_symlink() or not path.is_file() or path.stat().st_size>16*1024*1024:
            raise ValueError('冻结文件缺失、链接或过大')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=receipt['files'].get(name):
            raise ValueError('冻结文件摘要不一致')
    spec,result=read(root/'input.json'),read(root/'result.json')
    if digest(spec)!=result.get('inputSha256'): raise ValueError('冻结输入绑定不一致')
    return result


def bridge(spec, result):
    """Only actually-created predictions can enter a normal point-in-time panel."""
    from .factor_research import panel
    if result.get('availabilityMode')!='created-before-declared-signal':
        raise ValueError('回顾性模拟不能导出普通历史可得因子；保留CNN模拟报告')
    cutoff=instant(spec['asOf'])
    signature=result['dataSignature']
    for key in ('labelDefinition','returnUnit','horizonRecords','priceBasis'):
        if spec.get(key)!=signature[key]: raise ValueError('实测标签口径与模型不一致')
    labels=spec['labels']
    if not isinstance(labels,list): raise ValueError('核对标签须列表')
    by_id={r['id']:r for r in labels}
    if len(by_id)!=len(labels) or set(by_id)!={r['id'] for r in result['scores']}:
        raise ValueError('实测标签与冻结得分样本须一一对应')
    rows=[]
    for scored in result['scores']:
        label=by_id[scored['id']]
        if label['security']!=scored['security'] or label['signalAt']!=scored['signalAt']:
            raise ValueError('实测标签身份或信号不一致')
        if label.get('horizonRecords')!=signature['horizonRecords']:
            raise ValueError('实测标签期限不一致')
        if instant(label['availableAt'])>cutoff: raise ValueError('实测标签晚于复查截止')
        row=dict(signalDate=instant(scored['signalAt']).date().isoformat(),security=scored['security'],
                 signalAt=scored['signalAt'],factorAvailableAt=result['scoreComputedAt'],
                 factor=scored['score'],forwardReturn=contract.finite(label['forwardReturn']),
                 returnStartAt=label['returnStartAt'],returnEndAt=label['returnEndAt'],
                 returnAvailableAt=label['availableAt'],universeAvailableAt=scored['universeAvailableAt'],
                 membershipAtSignal=scored['membershipAtSignal'])
        contract.text(label.get('source'),'实测标签来源')
        rows.append(row)
    panel_input=dict(asOf=spec['asOf'],groups=spec['groups'],rows=rows,
                     universeDefinition=result['dataSignature']['universeDefinition'],
                     universeVersion=result['dataSignature']['universeVersion'],
                     factorSource='CNN '+result['modelFingerprint'],dataKind=result['dataKind'])
    reviewed=panel(panel_input)
    return dict(conclusion='已将冻结预测与后来取得的实测标签逐项绑定，可继续PDE条件审查。',
                panelInput=panel_input,panelReview=reviewed,modelFingerprint=result['modelFingerprint'],dataKind=result['dataKind'],
                humanRows=[['绑定样本',len(rows)],['数据性质',result['dataKind']]],
                limitations=result['limitations']+reviewed['limitations'])


def main(argv=None):
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'): stream.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description='CNN可选研究模块：CPU回归得分，非交易或盈利认证')
    parser.add_argument('command',choices=('validate','train','walk-forward','predict','bridge','compare'))
    parser.add_argument('--input',required=True,type=Path)
    parser.add_argument('--out-dir',required=True,type=Path)
    parser.add_argument('--artifact-dir',type=Path)
    parser.add_argument('--receipt-sha256')
    parser.add_argument('--model-fingerprint')
    options=parser.parse_args(argv)
    try:
        if options.out_dir.exists(): raise ValueError('输出目录已存在，旧结果保留')
        spec=read(options.input)
        print('阶段：已读取输入，正在检查声明时点与数据口径。',file=sys.stderr)
        if options.command=='validate':
            rows,excluded=contract.validate(spec,labels=spec.get('mode')!='prediction')
            result=contract.base(spec,excluded)
            result.update(conclusion='输入结构和声明时点通过检查；没有训练，也未认证原始数据。',
                          humanRows=[['合格样本',len(rows)],['排除样本',len(excluded)]])
        elif options.command=='compare':
            from .candle_comparison import compare
            print('阶段：正在按预声明窗口做三路线对照。',file=sys.stderr)
            result=compare(spec)
        elif options.command in ('train','walk-forward'):
            from .cnn_engine import train,walk_forward
            print('阶段：正在CPU拟合、验证选型和冻结后的测试评估。',file=sys.stderr)
            result=(train if options.command=='train' else walk_forward)(spec)
        else:
            if not options.artifact_dir or not options.receipt_sha256:
                raise ValueError('须指定冻结目录和回执摘要')
            archive=frozen(options.artifact_dir,options.receipt_sha256)
            print('阶段：冻结文件摘要通过，正在预测或绑定实测标签。',file=sys.stderr)
            if options.command=='bridge': result=bridge(spec,archive)
            else:
                if not options.model_fingerprint or 'model' not in archive:
                    raise ValueError('预测须指定单模型训练目录和模型摘要')
                from .cnn_engine import predict
                result=predict(spec,archive['model'],options.model_fingerprint)
        human_rows=result.get('humanRows',[])
        if not any(row[0]=='资料性质' for row in human_rows):
            human_rows=[['资料性质','原创合成教学样本' if result.get('dataKind')=='synthetic-teaching' else '用户声明历史底稿，未认证']]+human_rows
        result['humanRows']=human_rows
        print('阶段：计算完成，正在保存新报告与回执。',file=sys.stderr)
        output=publish(spec,result,options.out_dir,'CNN因子研究复查')
        print('报告已生成：'+str(output/'report.html'))
        print('下一步：核对来源、模型可得性及成本；回归得分不是上涨概率。')
        return 0
    except (ValueError,TypeError,KeyError,OSError,ArithmeticError,RuntimeError) as error:
        print('未完成：'+str(error)+'。请补齐资料并使用新目录。',file=sys.stderr)
        return 2


if __name__=='__main__': raise SystemExit(main())
