import { neon } from '@neondatabase/serverless';
import { analyzeConfluence } from './_grammar.mjs';

const PROBES=[{id:'probe:einstein:mass-energy',name:'Einstein · mass–energy equivalence',formula:'E = mc²',domain:'Relativity',status:'PROBE',attached_node_id:null}];

export default async()=>{
  const now=new Date().toISOString();
  const url=process.env.DATABASE_URL;
  if(!url)return new Response(JSON.stringify({ok:false,error:'database unavailable',now}),{status:503,headers:{'content-type':'application/json','cache-control':'no-store'}});
  try{
    const sql=neon(url);
    const [nodes,edges,runs,evidence]=await Promise.all([
      sql`SELECT id,kind,dim,recurrence_order,symmetry,sq,anti,multiplicity,boundary_condition,dual,occupancy,lifecycle,verdict,paths,depth,label FROM structures ORDER BY depth,kind,id LIMIT 3000`,
      sql`SELECT source_id,target_id,operator,paths FROM edges LIMIT 10000`,
      sql`SELECT grammar_version,node_count,edge_count,created_at,note FROM runs ORDER BY id DESC LIMIT 1`,
      sql`SELECT structure_id,status,domain,title,claim,caveat,confidence FROM evidence ORDER BY confidence DESC,created_at DESC LIMIT 500`
    ]);
    const duality_clusters=analyzeConfluence(nodes,edges);
    const counts={structures:nodes.length,relations:edges.length,confluences:duality_clusters.length,known:nodes.filter(n=>n.verdict==='KNOWN').length,rediscovered:nodes.filter(n=>n.verdict==='REDISCOVERED').length,unmatched:nodes.filter(n=>n.verdict==='UNMATCHED').length};
    const known_physics=nodes.filter(n=>n.verdict==='KNOWN'||n.verdict==='REDISCOVERED').map(n=>({id:n.id,label:n.label,verdict:n.verdict,kind:n.kind,dim:n.dim,order:n.recurrence_order,confluence:duality_clusters.some(c=>c.target_node_id===n.id)}));
    return new Response(JSON.stringify({ok:true,now,run:runs[0]||null,counts,probes:PROBES,known_physics,duality_clusters,nodes,edges,evidence}),{headers:{'content-type':'application/json','cache-control':'public,max-age=0,s-maxage=10','access-control-allow-origin':'*'}});
  }catch(error){return new Response(JSON.stringify({ok:false,error:String(error),now}),{status:500,headers:{'content-type':'application/json','cache-control':'no-store','access-control-allow-origin':'*'}})}
};