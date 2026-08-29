from dataclasses import dataclass
from typing import Tuple, Optional

MAXDIM = 4
MAXORD = 4
INF = -1
RECURRENCE="RECURRENCE"; SYMMETRY="SYMMETRY"; BOUNDCOND="BOUNDCOND"; CARRIER="CARRIER"; CYCLE="CYCLE"; PRODUCT="PRODUCT"; BUNDLE="BUNDLE"; INTEGER="INTEGER"; BOUNDARY="BOUNDARY"; WEIGHT="WEIGHT"; FILTER="FILTER"

@dataclass(frozen=True)
class Struct:
    kind:str; dim:int=0; order:int=0; parts:Tuple=(); label:str=""; mult:int=1
    sq:Optional[int]=None; anti:Optional[bool]=None; sym:Optional[str]=None
    bc:Optional[str]=None; dual:int=0; occ:Optional[int]=None
    def sig(self):
        """Historical provenance-bearing signature.

        Kept for compatibility with sealed historical snapshots. New scientific
        comparison should prefer structural_sig(); derivation provenance belongs
        in derivation events, not structural identity.
        """
        return (self.kind,self.dim,self.order,str(self.sym),str(self.sq),str(self.anti),self.mult,str(self.bc),self.dual,str(self.occ),tuple(sorted(p.sig() for p in self.parts)))
    def structural_sig(self):
        """Provenance-free structural state signature."""
        return (self.kind,self.dim,self.order,str(self.sym),str(self.sq),str(self.anti),self.mult,str(self.bc),self.dual,str(self.occ))
    def key(self):
        return self.structural_sig()

def op_close(s):
    if s.kind!=RECURRENCE:return None
    return Struct(CYCLE,dim=1,order=s.order,parts=(s,),label="close")

def op_product(a,b):
    if a.kind not in (CYCLE,PRODUCT) or b.kind not in (CYCLE,PRODUCT):return None
    if a.dim+b.dim>MAXDIM:return None
    if a.sym!=b.sym or a.bc!=b.bc or a.order!=b.order:return None
    # The compact structural signature has no factor-level dual state. A mixed
    # pair therefore cannot be collapsed into one output flag without losing
    # information. Reject it until such a carrier exists in the grammar.
    if a.dual!=b.dual:return None
    return Struct(PRODUCT,dim=a.dim+b.dim,order=a.order,parts=(a,b),label="product",sym=a.sym,bc=a.bc,mult=max(a.mult,b.mult),dual=a.dual,occ=a.occ if a.occ==b.occ else None)

def op_winding(s):
    if s.kind not in (CYCLE,PRODUCT,BUNDLE):return None
    return Struct(INTEGER,dim=s.dim,order=s.order,parts=(s,),label="winding",sym=s.sym,bc=s.bc,mult=s.mult,dual=s.dual,occ=s.occ)

def op_fiber(base,fib):
    if fib.kind!=CYCLE:return None
    if base.kind not in (CYCLE,PRODUCT,BOUNDARY):return None
    if base.sym!=fib.sym or base.bc!=fib.bc or base.order!=fib.order:return None
    if base.dual!=fib.dual:return None
    return Struct(BUNDLE,dim=base.dim,order=base.order,parts=(base,fib),label="fiber",sym=fib.sym,bc=fib.bc,mult=max(base.mult,fib.mult),dual=base.dual,occ=fib.occ)

def op_boundary(s):
    if s.kind not in (PRODUCT,BUNDLE):return None
    return Struct(BOUNDARY,dim=max(s.dim-1,0),order=s.order,parts=(s,),label="boundary",sym=s.sym,bc=s.bc,mult=s.mult,dual=s.dual,occ=s.occ)

def op_weight(s):
    if s.kind not in (CYCLE,PRODUCT,BUNDLE):return None
    return Struct(WEIGHT,dim=s.dim,order=s.order,parts=(s,),label="weight",sym=s.sym,bc=s.bc,mult=s.mult,dual=s.dual,occ=s.occ)

def op_filter(s):
    if s.kind!=WEIGHT:return None
    return Struct(FILTER,dim=s.dim,order=s.order,parts=(s,),label="filter",sym=s.sym,bc=s.bc,mult=s.mult,dual=s.dual,occ=s.occ)

def op_degenerate(s,sym):
    if sym.kind!=SYMMETRY or not sym.anti:return None
    if s.kind not in (CYCLE,PRODUCT,BUNDLE,WEIGHT):return None
    if s.mult!=1:return None
    label="degenerate" if sym.sq==-1 else "antiunitary"
    return Struct(s.kind,dim=s.dim,order=s.order,parts=(s,sym),label=label,sym=sym.label,mult=2 if sym.sq==-1 else 1,bc=s.bc,dual=s.dual,occ=s.occ)

def op_dual(s):
    if s.kind not in (CYCLE,PRODUCT,BUNDLE,INTEGER,WEIGHT):return None
    if s.dual not in (0,1):return None
    # Duality is currently a structural branch marker, not a physical dual map.
    # Preserve intrinsic parts so the marker is a genuine involution:
    # op_dual(op_dual(X)).sig() == X.sig(). Provenance is recorded separately
    # by auditable derivation events.
    return Struct(s.kind,dim=s.dim,order=s.order,parts=s.parts,label=s.label,sym=s.sym,bc=s.bc,mult=s.mult,dual=1-s.dual,occ=s.occ)

# Self-duality is deliberately not a generative operation. Establishing D(X) ≡ X
# first requires a separately specified and tested structural equivalence relation.

def op_exclude(s,carrier):
    if carrier.kind!=CARRIER:return None
    if s.kind not in (CYCLE,PRODUCT,BUNDLE,INTEGER,WEIGHT) or s.occ is not None:return None
    return Struct(s.kind,dim=s.dim,order=s.order,parts=(s,carrier),label="exclude",sym=s.sym,bc=s.bc,mult=s.mult,dual=s.dual,occ=carrier.occ)

def op_fill(s):
    if s.occ is None or s.occ==INF or s.occ<0:return None
    if s.mult!=1 and s.mult!=2:return None
    return Struct(INTEGER,dim=s.dim,order=s.order,parts=(s,),label="fill",sym=s.sym,bc=s.bc,mult=s.occ*s.mult,dual=s.dual,occ=s.occ)

UNARY=[op_close,op_winding,op_boundary,op_weight,op_filter,op_dual,op_fill]
BINARY=[op_product,op_fiber,op_degenerate,op_exclude]
SEED_R=Struct(RECURRENCE,label="x~x+1",order=0)
SEED_Rn=[Struct(RECURRENCE,label=f"x~x+{n}",order=n) for n in range(2,MAXORD+1)]
SEED_S=[Struct(SYMMETRY,label="S+u",sq=+1,anti=False),Struct(SYMMETRY,label="S-u",sq=-1,anti=False),Struct(SYMMETRY,label="S+a",sq=+1,anti=True),Struct(SYMMETRY,label="S-a",sq=-1,anti=True)]
SEED_C=[Struct(CARRIER,label="excl",occ=1),Struct(CARRIER,label="free",occ=INF)]
SEEDS=[SEED_R]+SEED_Rn+SEED_S+SEED_C
