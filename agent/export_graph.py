import os,sys,json,hashlib,collections
from pathlib import Path
import psycopg
ROOT=Path(__file__).resolve().parents[1];GEN=ROOT/'ckk_snapshot'/'ckk'/'gen';sys.path.insert(0,str(GEN));os.chdir(GEN)
import grammar as G
from expand import expand

def sid(s): return hashlib.sha256(repr(s.sig()).encode()).hexdigest()[:32]
def confluences(nodes,edges):
    byid={n['id']:n for n in nodes}; inc=collections.defaultdict(list)
    for e in edges: inc[e['target_id']].append(e)
    seedk={'RECURRENCE','SYMMETRY','BOUNDCOND','CARRIER'}; memo={}
    def paths(t,seen=frozenset()):
        if t in memo:return memo[t]
        if t in seen:return []
        n=byid.get(t); es=inc[t]
        if not n:return []
        if n['kind'] in seedk or not es:return [[t]]
        out=[]
        for e in es:
            for p in paths(e['source_id'],seen|{t}):out.append(p+[t])
        uniq={tuple(p):p for p in out}; memo[t]=sorted(uniq.values(),key=lambda p:(len(p),p))[:64];return memo[t]
    out=[]
    for n in nodes:
        parents={e['source_id'] for e in inc[n['id']]}
        if len(parents)<2:continue
        ps=paths(n['id']); groups=collections.defaultdict(list)
        for p in ps:groups[p[0]].append(p)
        if len(groups)<2:continue
        branches=[]
        for i,(root,pp) in enumerate(sorted(groups.items())):branches.append({'branch':i,'root_node_id':root,'root_kind':byid[root]['kind'],'seed_chain':min(pp,key=lambda p:(len(p),p))})
        union=set().union(*(set(b['seed_chain']) for b in branches)); shared=set(branches[0]['seed_chain'])
        for b in branches[1:]:shared &= set(b['seed_chain'])
        out.append({'target_node_id':n['id'],'canonical_type':f"{n['kind']} dim={n['dim']} order={n['recurrence_order']}",'branches':branches,'reduction_ratio':len(shared)/len(union) if union else 0.0,'parent_count':len(parents)})
    return sorted(out,key=lambda c:(-len(c['branches']),c['target_node_id']))

def main():
    pool,raw=expand(levels=4,cap=30000);bykey={s.sig():s for s in pool.values()};nodes=[]
    depths={sid(s):0 for s in G.SEEDS if s.sig() in bykey}
    for _ in range(12):
      for a,b,_ in raw:
        if a in bykey and b in bykey and sid(bykey[a]) in depths: depths[sid(bykey[b])]=min(depths.get(sid(bykey[b]),10**9),depths[sid(bykey[a])]+1)
    for s in pool.values():nodes.append({'id':sid(s),'kind':s.kind,'dim':s.dim,'recurrence_order':s.order,'depth':depths.get(sid(s),0),'label':s.label})
    ec=collections.Counter()
    for a,b,op in raw:
      if a in bykey and b in bykey:ec[(sid(bykey[a]),sid(bykey[b]),op)]+=1
    edges=[{'source_id':a,'target_id':b,'operator':op,'paths':n} for (a,b,op),n in ec.items()];clusters=confluences(nodes,edges)
    (ROOT/'agent'/'graph_export.json').write_text(json.dumps({'nodes':nodes,'edges':edges,'duality_clusters':clusters},indent=2),encoding='utf-8')
    conn=psycopg.connect(os.environ['DATABASE_URL'])
    with conn,conn.cursor() as c:
      for s in pool.values():
        i=sid(s);sig={'key':s.key(),'sig':repr(s.sig())};c.execute('''INSERT INTO structures(id,kind,dim,recurrence_order,symmetry,sq,anti,multiplicity,boundary_condition,dual,occupancy,lifecycle,verdict,paths,depth,label,signature,last_seen) VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'GENERABLE','UNMATCHED',1,%s,%s,%s::jsonb,now()) ON CONFLICT(id) DO UPDATE SET depth=EXCLUDED.depth,last_seen=now(),signature=EXCLUDED.signature''',(i,s.kind,s.dim,s.order,s.sym,s.sq,s.anti,s.mult,s.bc,s.dual,s.occ,depths.get(i,0),s.label,json.dumps(sig,default=str)))
      for e in edges:c.execute('''INSERT INTO edges(source_id,target_id,operator,paths) VALUES(%s,%s,%s,%s) ON CONFLICT(source_id,target_id,operator) DO UPDATE SET paths=EXCLUDED.paths''',(e['source_id'],e['target_id'],e['operator'],e['paths']))
      c.execute("INSERT INTO runs(grammar_version,node_count,edge_count,unmatched_count,note) VALUES(%s,%s,%s,%s,%s)",('v8-confluence',len(nodes),len(edges),len(nodes),f'{len(clusters)} structural confluences'))
    print('exported',len(nodes),'nodes',len(edges),'edges',len(clusters),'confluences')
if __name__=='__main__':main()
