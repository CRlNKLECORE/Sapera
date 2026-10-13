"""Benchmark checksum-neutral fixed-token patchability for supplied Viper builds.
Only write output streams after full byte-for-byte verification. Does NOT validate gameplay.
"""
import csv,hashlib,json,sys,re,time,bisect
from pathlib import Path
from collections import defaultdict
from .core import zin_decompress as zin_decode_unbounded

def zin_decode(data, expected_output=None):
    out, used = zin_decode_unbounded(data)
    if expected_output is not None and len(out) != expected_output:
        raise ValueError("ZIN decoded output length mismatch")
    return out, used
root=Path.cwd()

class Token:
 __slots__=('kind','pay','pos','ln','dist')
 def __init__(self,k,pa,po,l,d):self.kind=k;self.pay=pa;self.pos=po;self.ln=l;self.dist=d

def tokens(st):
 i=pos=0;out=[]
 while i<len(st):
  ctrl=st[i];i+=1
  for bit in range(8):
   if ctrl>>bit&1:out.append(Token('L',i,pos,1,0));i+=1;pos+=1
   else:
    pay=i;a,b=st[i:i+2];i+=2;d=((a&0xf0)<<4)|b;ln=(a&15)+3
    out.append(Token('M' if d else 'E',pay,pos,ln,d))
    if not d:
     assert i==len(st),f'Unexpected token count {i} {len(st)}'
     return out
    pos+=ln
 raise ValueError('no EOS')

def enc(d,ln):return bytes(((((d>>8)&15)<<4)|(ln-3),d&0xff))

def getidx(data):
 d=defaultdict(list)
 for i in range(len(data)-2):d[data[i:i+3]].append(i)
 return d

def lookup(t,ix,p,ln,orig=0,maxtry=500):
 if p+ln>len(t):return []
 hits=ix.get(t[p:p+3],())
 hi=bisect.bisect_left(hits,p)
 lo=bisect.bisect_left(hits,max(0,p-4095),0,hi)
 out=[]
 # prefer the nearest and sample positions across original dictionary
 for j in range(hi-1,max(lo-1,hi-maxtry-1),-1):
  d=p-hits[j]
  if d==orig:continue
  if t[p:p+ln]==t[p-d:p-d+ln]:out.append(d)
 return out

def rewrite(st,original,target,toks=None,ix=None,neutralize=True):
 if toks is None:toks=tokens(st)
 if ix is None:ix=getidx(target)
 assert len(original)==len(target)
 dst=bytearray(st);repaired=[]
 for tk in toks:
  if tk.kind=='L':dst[tk.pay]=target[tk.pos]
  if tk.kind!='M':continue
  p=tk.pos;d=tk.dist;ln=tk.ln
  if target[p:p+ln]==target[p-d:p-d+ln]:continue
  matches=lookup(target,ix,p,ln,orig=d)
  if not matches:
   return {'result':'unencodable','failed_offset':p,'length':ln,'original_distance':d,'repaired':len(repaired)}
  candidate=min(matches,key=lambda nd:abs(sum(enc(nd,ln))-sum(st[tk.pay:tk.pay+2])))
  dst[tk.pay:tk.pay+2]=enc(candidate,ln);repaired.append((p,d,candidate))
 check,used=zin_decode(bytes(dst),len(target))
 assert check==target and used==len(st)
 diff=sum(st)-sum(dst)
 if diff and neutralize:
  # Search for semantically equivalent alternative matches, changing only token payloads.
  # Greedy selection along with a small exact two-token fallback.
  def options():
   avail=[]
   for tk in toks:
    if tk.kind!='M':continue
    old=int(dst[tk.pay])+int(dst[tk.pay+1]);opts={}
    for nd in lookup(target,ix,tk.pos,tk.ln,tk.dist,maxtry=60):
     e=enc(nd,tk.ln);delta=sum(e)-old
     if delta and abs(delta)<=270 and delta not in opts:opts[delta]=e
    if opts:avail.append((tk.pay,opts))
    if len(avail)>=4500:break
   return avail
  avail=options()
  # exact DP for small balances, same token at most once. Prefer few changes
  limit=max(2048,abs(diff)+512)
  paths={0:()}
  for pay,opts in avail:
   nxt=dict(paths)
   for cur,path in paths.items():
    if len(path)>=6:continue
    for d,e in opts.items():
     x=cur+d
     if abs(x)<=limit and x not in nxt:nxt[x]=path+((pay,e,d),)
   paths=nxt
   if diff in paths:
    for pay,e,d in paths[diff]:dst[pay:pay+2]=e
    break
   if len(paths)>20000:
    keep=sorted(paths,key=lambda n:(abs(diff-n),len(paths[n])))[:6000]
    paths={k:paths[k] for k in keep}
  else:return {'result':'checksum_unsolved','repaired':len(repaired),'needed_sum':diff,'alternatives':len(avail)}
 if sum(dst)!=sum(st):return {'result':'checksum_mismatch','needed':sum(st)-sum(dst)}
 p,used=zin_decode(bytes(dst),len(target))
 assert p==target and used==len(st)
 return {'result':'pass','repaired':len(repaired),'compressed_bytes_changed':sum(x!=y for x,y in zip(st,dst)),'stream':bytes(dst),'checksum':sum(dst)&0xffffffff}

def main():
 rows={r['chd']:r for r in csv.DictReader(open(root/'viper-master-corpus-status-v0.2.csv'))}
 results=[]
 for key in ('a29b02','a41b02','b41c02','b11a02','a13c02'):
  row=rows[key];base=int(row['load_address'],0);prog=(root/(key+'.prog')).read_bytes();st=(root/(key+'.stream')).read_bytes();toks=tokens(st)
  exp=[]
  for s in row['patch_candidates'].split(';'):
   x=re.search(r'([^@ ]+)@(0x[0-9A-Fa-f]+):([0-9A-Fa-f]+)->([0-9A-Fa-f]+)',s.strip())
   if not x:continue
   name,addr,old,new=x.groups();a=int(addr,16);off=a-base
   exp.append((name,a,off,bytes.fromhex(old),bytes.fromhex(new)))
  print('\nBUILD',key,'patches',len(exp),'tokens',len(toks),'program',len(prog),'stream',len(st),flush=True)
  for name,a,off,old,new in exp:
   if prog[off:off+len(old)]!=old:
    res={'result':'instruction_mismatch','found':prog[off:off+len(old)].hex()}
   else:
    target=bytearray(prog);target[off:off+len(old)]=new;target=bytes(target)
    t=time.time()
    res=rewrite(st,prog,target,toks=toks,ix=getidx(target),neutralize=True)
    res['seconds']=round(time.time()-t,2)
   res.pop('stream',None)
   rec={'build':key,'game':row['game'],'profile':'single','site':name,'address':hex(a),**res};results.append(rec)
   print(name,rec['result'],{k:v for k,v in res.items() if k not in ('result',)},flush=True)
  if exp:
   target=bytearray(prog);valid=[]
   for name,a,off,old,new in exp:
    if prog[off:off+len(old)]!=old:continue
    target[off:off+len(old)]=new;valid.append(name)
   t=time.time();res=rewrite(st,prog,bytes(target),toks=toks,ix=getidx(bytes(target)),neutralize=True);res['seconds']=round(time.time()-t,2)
   if 'stream' in res and res['result']=='pass':
    out=root/(key+'.neutral.stream');out.write_bytes(res['stream']);res.pop('stream')
   rec={'build':key,'game':row['game'],'profile':'all','site':'+'.join(valid),**res};results.append(rec)
   print('ALL',rec['result'],{k:v for k,v in res.items() if k not in ('result',)},flush=True)
  (root/'benchmark.json').write_text(json.dumps(results,indent=2))
 (root/'benchmark.json').write_text(json.dumps(results,indent=2))

if __name__=='__main__':main()
