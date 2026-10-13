from pathlib import Path
from .benchmark_neutral import tokens,getidx,lookup,enc
from .core import zin_decompress as zin_decode_unbounded

def zin_decode(data, expected_output=None):
    out, used = zin_decode_unbounded(data)
    if expected_output is not None and len(out) != expected_output:
        raise ValueError("ZIN decoded output length mismatch")
    return out, used
import sys,time,json
root=Path.cwd()

def balance(base,patched,target,printprogress=False):
 st=bytearray(patched);need=sum(base)-sum(st)
 ix=getidx(target)
 tk=tokens(st)
 changes=[];alternatives=0
 for q in tk:
  if need==0:break
  if q.kind!='M':continue
  old=st[q.pay]+st[q.pay+1]
  matches=lookup(target,ix,q.pos,q.ln,orig=q.dist,maxtry=96)
  best=None
  for nd in matches:
   e=enc(nd,q.ln);delta=sum(e)-old
   if need>0 and 0<delta<=need and (best is None or delta>best[0]):best=(delta,nd,e)
   elif need<0 and need<=delta<0 and (best is None or delta<best[0]):best=(delta,nd,e)
  if best:
   alternatives+=len(matches)
   st[q.pay:q.pay+2]=best[2];need-=best[0]
   changes.append((q.pos,best[0]))
   if printprogress and len(changes)%25==0:print('adjusted',len(changes),'needed',need,flush=True)
 if need!=0:return {'result':'failed','residual':need,'edits':len(changes),'options':alternatives}
 assert len(st)==len(base) and sum(st)==sum(base)
 p,used=zin_decode(bytes(st),len(target));assert p==target and used==len(base)
 return {'result':'PASS','edits':len(changes),'changed_stream_bytes':sum(a!=b for a,b in zip(st,base)), 'checksum':sum(st)&0xffffffff,'stream':bytes(st)}

if __name__=='__main__':
 results={}
 for key,site in [('a29b02','0x0008FA1C'),('a41b02','0x0004CBCC'),('b41c02','0x000BD74C'),('b11a02','0x010B2F6C')]:
  prog=(root/(key+'.prog')).read_bytes();base=(root/(key+'.stream')).read_bytes();patch=(root/(key+'.boot.retoken.stream')).read_bytes()
  load=int((root/(key+'.meta')).read_text().split(',')[3]);off=int(site,0)-load
  import csv,re
  rows={r['chd']:r for r in csv.DictReader(open(root/'viper-master-corpus-status-v0.2.csv'))}
  x=next(re.search(r'([^@ ]+)@(0x[0-9A-Fa-f]+):([0-9A-Fa-f]+)->([0-9A-Fa-f]+)',s.strip()) for s in rows[key]['patch_candidates'].split(';') if 'rtc_boot_aggregate' in s)
  assert prog[off:off+4]==bytes.fromhex(x.group(3))
  target=bytearray(prog);target[off:off+4]=bytes.fromhex(x.group(4));target=bytes(target)
  print('BALANCE',key,'need',sum(base)-sum(patch),flush=True);now=time.time()
  result=balance(base,patch,target,printprogress=True);stream=result.pop('stream',None)
  if stream:(root/(key+'.boot.neutral.stream')).write_bytes(stream)
  result['seconds']=round(time.time()-now,2)
  results[key]=result
  print('RESULT',key,result,flush=True)
 (root/'rebalance-results.json').write_text(json.dumps(results,indent=2))
