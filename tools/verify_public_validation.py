# SPDX-License-Identifier: MIT
"""Verify frozen public-case inventory; gaps never count as real-market validation."""
import argparse,hashlib,json,re,subprocess,sys
from pathlib import Path

def verify(root,run_checks=False):
 root=Path(root).resolve();spec=json.loads((root/'PUBLIC_VALIDATION.json').read_text(encoding='utf-8'));items=spec['evidence'];files=[]
 if spec.get('schemaVersion')!='public-validation/1' or not spec.get('gaps') or spec.get('sourceAuthenticityCertified') is not False:raise ValueError('version, explicit gaps and non-certification required')
 for row in items:
  p=(root/row['path']).resolve()
  if not p.is_relative_to(root) or p.is_symlink() or not p.is_file() or p.stat().st_size>16*1024*1024:raise ValueError('evidence path missing or unsafe')
  if hashlib.sha256(p.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()!=row['normalizedSha256']:raise ValueError('frozen input text changed: '+row['path'])
  if row['kind'] not in ('public-facts','official-rule-evidence','mixed-teaching-and-public','public-derived-summary'):raise ValueError('unknown evidence kind')
  if not row.get('sourceUrls') or any(not u.startswith('https://') or 'example.' in u for u in row['sourceUrls']):raise ValueError('real source URLs required, no example-domain promotion')
  files.append(row['path'])
 if spec['coverage']!=('limited-public-inputs' if items else 'no-eligible-public-inputs'):raise ValueError('coverage status conflicts with evidence')
 checks=[]
 if run_checks:
  for pattern in spec.get('checkFiles',[]):
   if not re.fullmatch(r'test_[A-Za-z0-9_]+\.py',pattern) or not (root/'tests'/pattern).is_file():raise ValueError('explicit local unittest file required')
   r=subprocess.run([sys.executable,'-X','utf8','-m','unittest','discover','-s','tests','-p',pattern,'-v'],cwd=root,capture_output=True,text=True,encoding='utf-8',timeout=120)
   log=r.stdout+r.stderr
   if r.returncode or 'Ran 0 tests' in log or not re.search(r'Ran \d+ test',log):raise ValueError('case checks failed or empty: '+pattern+'\n'+log[-3000:])
   checks.append({'file':pattern,'status':'passed','testCount':int(re.search(r'Ran (\d+) test',log)[1])})
 return {'schemaVersion':'public-validation-receipt/1','repository':spec['repository'],'inventoryValid':True,'coverage':spec['coverage'],'verifiedFrozenFiles':files,'checks':checks,'gaps':spec['gaps'],'sourceAuthenticityCertified':False,'limits':'offline normalised input text and selected logic only; no new original-document verification, live coverage, current legal applicability or investment-effect certification'}

def main():
 p=argparse.ArgumentParser();p.add_argument('--run-checks',action='store_true');p.add_argument('--output',type=Path,required=True);a=p.parse_args()
 try:
  if a.output.exists():raise ValueError('use a new receipt path')
  result=verify(Path(__file__).resolve().parents[1],a.run_checks);a.output.parent.mkdir(parents=True,exist_ok=True)
  with a.output.open('x',encoding='utf-8') as f:json.dump(result,f,ensure_ascii=False,allow_nan=False,indent=2)
  print('底稿登记通过；公开资料覆盖：'+('有限公开底稿' if result['coverage']=='limited-public-inputs' else '尚缺合格公开样本')+'；真实来源与当前市场效果未认证。');return 0
 except (ValueError,KeyError,TypeError,OSError,subprocess.TimeoutExpired) as e:print('验收未完成：'+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
