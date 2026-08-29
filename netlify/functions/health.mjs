import { neon } from '@neondatabase/serverless';
export default async () => { try { const sql=neon(process.env.DATABASE_URL); const r=await sql`SELECT now() now`; return Response.json({ok:true,db:true,now:r[0].now}); } catch(e){ return Response.json({ok:false,error:String(e)},{status:500}); } };
