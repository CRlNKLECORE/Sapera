"""Constrained local retokenizing prototype based on earlier Viper P9112 builder.
Attempts exact-size windows aligned to original ZIN control groups.
"""
import sys,time,csv,re,bisect,json
from pathlib import Path
from collections import defaultdict
from .benchmark_neutral import tokens,enc,getidx,lookup
from .core import zin_decompress as zin_decode_unbounded

def zin_decode(data, expected_output=None):
    out, used = zin_decode_unbounded(data)
    if expected_output is not None and len(out) != expected_output:
        raise ValueError("ZIN decoded output length mismatch")
    return out, used
root=Path.cwd()

class Group:
 __slots__=('idx','c0','c1','o0','o1','toks')
 def __init__(self,idx,c0,c1,o0,o1,toks): self.idx=idx;self.c0=c0;self.c1=c1;self.o0=o0;self.o1=o1;self.toks=toks

def groups(st):
 tks=tokens(st);p=0;o=0;out=[]
 while p<len(st):
  c0=p;p+=1;g=[]
  for j in range(8):
   if not tks:break
   tk=tks.pop(0) if False else None
  # efficient with pre-grouped tokens by compressed ctrl boundary
  ctrl=st[c0]
  starto=o
  for j in range(8):
   if ctrl>>j&1:
    g.append(('L',p,o,1,0));p+=1;o+=1
   else:
    a,b=st[p:p+2];d=((a&240)<<4)|b;ln=(a&15)+3
    g.append(('M' if d else 'E',p,o,ln,d));p+=2
    if not d:break
    o+=ln
  out.append(Group(len(out),c0,p,starto,o,g))
 return out

def encode_window(gv,t,idx,ga,gb,K=14):
 g0,g1=gv[ga],gv[gb]
 o0,o1=g0.o0,g1.o0;c0,c1=g0.c0,g1.c0;target_cost=c1-c0
 if o1<=o0 or o1-o0>10000:raise RuntimeError('window-too-large')
 costs={(o0,0):[0]};parent={};opcache={}
 def opt(pos):
  if pos not in opcache:
   o={}
   if pos+3<=o1:
    hits=idx.get(t[pos:pos+3],[]);hi=bisect.bisect_left(hits,pos);lo=bisect.bisect_left(hits,max(0,pos-4095),0,hi)
    for j in range(hi-1,max(lo-1,hi-48-1),-1):
     d=pos-hits[j];ml=min(18,o1-pos)
     n=3
     while n<ml and t[pos+n]==t[pos+n-d]:n+=1
     for ln in range(3,n+1):o.setdefault(ln,d)
     if len(o)==16:break
   opcache[pos]=o
  return opcache[pos]
 def add(np,nm,nc,prev,tok):
  if nc>target_cost:return
  key=(np,nm);lst=costs.setdefault(key,[])
  if nc in lst:return
  bisect.insort(lst,nc);parent[(np,nm,nc)]=(prev,tok)
  if len(lst)>K:lst.pop()
 for pos in range(o0,o1+1):
  for mod in range(8):
   for cost in costs.get((pos,mod),())[:]:
    extra=1 if mod==0 else 0;nm=(mod+1)%8
    if pos<o1:add(pos+1,nm,cost+extra+1,(pos,mod,cost),('L',t[pos]))
    for ln,dist in opt(pos).items():
     if pos+ln<=o1:add(pos+ln,nm,cost+extra+2,(pos,mod,cost),('M',dist,ln))
 goal=(o1,0,target_cost)
 if goal not in parent:raise RuntimeError(f'no-exact-window {ga}:{gb}, {o1-o0} output bytes, {target_cost} compressed bytes, near {costs.get((o1,0),[])[:10]}')
 toks=[];k=goal
 while k!=(o0,0,0):
  pr,tok=parent[k];toks.append(tok);k=pr
 toks.reverse();assert len(toks)%8==0
 out=bytearray()
 for j in range(0,len(toks),8):
  ctl=0;payload=bytearray()
  for bit,tok in enumerate(toks[j:j+8]):
   if tok[0]=='L':ctl|=1<<bit;payload.append(tok[1])
   else:payload.extend(enc(tok[1],tok[2]))
  out.append(ctl);out+=payload
 assert len(out)==target_cost
 return c0,c1,bytes(out)

def windows_merge(w):
 w=sorted(w);out=[]
 for a,b in w:
  if out and a<=out[-1][1]:out[-1]=(out[-1][0],max(out[-1][1],b))
  else:out.append((a,b))
 return out

def retoken(st,prog,target,site_name,limit=16):
 ix=getidx(target);gv=groups(st);ends=[g.o1 for g in gv];windows=[];trials=[]
 for iteration in range(limit):
  dst=bytearray(st);blocked=set();encoded=[]
  for a,b in windows:
   c0,c1,dat=encode_window(gv,target,ix,a,b)
   dst[c0:c1]=dat
   for g in range(a,b):blocked.add(g)
  failed=None;repairs=0
  for g in gv:
   if g.idx in blocked:continue
   for kind,pay,pos,ln,d in g.toks:
    if kind=='L':dst[pay]=target[pos]
    elif kind=='M' and target[pos:pos+ln]!=target[pos-d:pos-d+ln]:
     hits=lookup(target,ix,pos,ln,orig=d)
     if not hits:
      failed=(g.idx,pos,ln,d);break
     nd=min(hits,key=lambda nd:abs(sum(enc(nd,ln))-sum(st[pay:pay+2])))
     dst[pay:pay+2]=enc(nd,ln);repairs+=1
   if failed:break
  if failed is None:
   p,used=zin_decode(bytes(dst),len(target));assert p==target and used==len(st)
   return {'result':'structural_pass','windows':windows,'retokened_groups':sum(b-a for a,b in windows),'repaired_matches':repairs,'checksum_delta':sum(st)-sum(dst),'stream':bytes(dst)}
  group,pos,ln,d=failed
  # first try single group, then widen small group window. Merge existing windows if required.
  trialgood=False
  for total in range(1,13):
   for left in range(total):
    a=max(0,group-left);b=min(len(gv)-1,group+(total-left))
    if a==b:continue
    merged=windows_merge(windows+[(a,b)])
    around=next((x for x in merged if x[0]<=group<x[1]),None)
    if around is None:continue
    try:
     encode_window(gv,target,ix,*around)
     windows=merged;trialgood=True;break
    except RuntimeError:pass
   if trialgood:break
  if not trialgood:
   for rad in (8,16,24,32,48,64,90):
    a=max(0,group-rad);b=min(len(gv)-1,group+rad)
    merged=windows_merge(windows+[(a,b)])
    around=next((x for x in merged if x[0]<=group<x[1]),None)
    if around is None:continue
    try:
     encode_window(gv,target,ix,*around,K=20)
     windows=merged;trialgood=True;break
    except RuntimeError:pass
  trials.append({'failure_offset':pos,'length':ln,'group':group,'repair_window_found':trialgood})
  if not trialgood:return {'result':'no_local_retoken_solution','fail_offset':pos,'length':ln,'windows':windows,'trials':trials}
 return {'result':'window_iteration_limit','windows':windows,'trials':trials}

if __name__=='__main__':
 rows={r['chd']:r for r in csv.DictReader(open(root/'viper-master-corpus-status-v0.2.csv'))}
 for key,name in [('a29b02','rtc_boot_aggregate'),('a41b02','rtc_boot_aggregate'),('b41c02','rtc_boot_aggregate'),('b11a02','rtc_boot_aggregate')]:
  row=rows[key]; base=int(row['load_address'],0)
  patch=next((re.search(r'([^@ ]+)@(0x[0-9A-Fa-f]+):([0-9A-Fa-f]+)->([0-9A-Fa-f]+)',s.strip()) for s in row['patch_candidates'].split(';') if name in s),None)
  if not patch:continue
  _,addr,old,new=patch.groups();off=int(addr,16)-base
  src=(root/(key+'.prog')).read_bytes();st=(root/(key+'.stream')).read_bytes()
  assert src[off:off+4]==bytes.fromhex(old)
  target=bytearray(src);target[off:off+4]=bytes.fromhex(new)
  print('\nRE-TOKEN',key,name,hex(off),flush=True);t=time.time()
  out=retoken(st,src,bytes(target),name)
  if 'stream' in out:
   (root/(key+'.boot.retoken.stream')).write_bytes(out.pop('stream'))
  out['seconds']=round(time.time()-t,2)
  print(out,flush=True)
  f=root/'retoken-results.json';existing=json.loads(f.read_text()) if f.exists() else {};existing[key]=out;f.write_text(json.dumps(existing,indent=2))
