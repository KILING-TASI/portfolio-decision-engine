"""Offline teaching launcher; Python required, no automatic installation."""
import argparse,importlib,sys,webbrowser
from pathlib import Path
ROOT=Path(__file__).resolve().parent
def main():
    for stream in (sys.stdout,sys.stderr):
        if hasattr(stream,'reconfigure'):stream.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description='先看教学报告；不下载资料、不安装组件、不覆盖旧结果')
    p.add_argument('--no-open',action='store_true');p.add_argument('--out-dir',type=Path,default=ROOT/'reports/demo');p.add_argument('--check',action='store_true')
    a=p.parse_args()
    if sys.version_info<(3,10):
        print('Python版本不足，下一步：按README安装适用版本。',file=sys.stderr);return 2
    sys.path.insert(0,str(ROOT/'src'))
    try:
        tool=importlib.import_module('portfolio_engine._entry')
        if a.check:return tool.main(['doctor'])
        print('阶段1/2：运行本仓教学输入；不是你的真实基金、账户或行情。')
        before=set(a.out_dir.parent.glob(a.out_dir.stem+'*')) if a.out_dir.parent.exists() else set()
        result=tool.main(['demo','--out-dir',str(a.out_dir),'--auto-name'])
        if result:return result
        created=[x for x in a.out_dir.parent.glob(a.out_dir.stem+'*') if x not in before and x.is_dir()]
        if len(created)!=1:raise ValueError('未能唯一定位本次结果，查看命令输出中的路径')
        reports=list(created[0].glob('*.html'));preferred=created[0]/tool.REPORT_FILE if tool.REPORT_FILE else None
        report=preferred if preferred and preferred.is_file() else reports[0] if len(reports)==1 else None
        if report is None:raise ValueError('没有找到明确的教学报告入口')
        print('阶段2/2：报告已生成：'+str(report.resolve()))
        print('下一步：先看教学范围；用自己的资料时按 BEGINNER.md 确认来源、日期和单位。')
        if not a.no_open and not webbrowser.open(report.resolve().as_uri()):print('浏览器未自动打开，请手动打开上述报告。')
        return 0
    except (ImportError,ValueError,OSError) as error:
        print('教学未完成：'+str(error)+'；下一步：运行 python try_demo.py --check，查看README；不会自动安装。',file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
