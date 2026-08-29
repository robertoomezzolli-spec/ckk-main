import os,json,psycopg
from openai import OpenAI
client=OpenAI()
PROMPT='''You are the adversarial research worker for a generative structure graph. Research ONE queued abstract structure. Do not force a match. Return strict JSON with keys verdict (REDISCOVERED|FORBIDDEN|UNRESOLVED), domain, title, claim, source_url, caveat, confidence, proposed_missing_primitive. A REDISCOVERED verdict requires a concrete published realization in the relevant discipline (for example mathematics, physics, chemistry, biology, computer science, or another explicit domain) with a rigorous structural correspondence. Do not privilege physics. FORBIDDEN requires a concrete theorem, empirical constraint, impossibility result, or domain-standard obstruction appropriate to that discipline. Otherwise UNRESOLVED. Distinguish structural analogy from equivalence and never infer a domain identity from a label alone.'''
def main():
  conn=psycopg.connect(os.environ['DATABASE_URL']);
  with conn,conn.cursor() as c:
    c.execute("SELECT q.id,q.structure_id,s.kind,s.dim,s.recurrence_order,s.signature FROM research_queue q JOIN structures s ON s.id=q.structure_id WHERE q.status='QUEUED' AND q.next_attempt_at<=now() ORDER BY q.priority DESC LIMIT 1 FOR UPDATE SKIP LOCKED")
    row=c.fetchone();
    if not row: print('queue empty'); return
    qid,sid,kind,dim,order,sig=row; c.execute("UPDATE research_queue SET status='RUNNING',attempts=attempts+1 WHERE id=%s",(qid,))
  query=f"Structure: kind={kind}, dimension={dim}, recurrence_order={order}, signature={sig}. Find whether this abstract slot has a rigorous known realization or a rigorous obstruction."
  r=client.responses.create(model=os.getenv('OPENAI_MODEL','gpt-5.6'),tools=[{'type':'web_search'}],input=PROMPT+'\n\n'+query)
  text=r.output_text.strip();
  try: data=json.loads(text[text.find('{'):text.rfind('}')+1])
  except Exception: data={'verdict':'UNRESOLVED','domain':'','title':'parse failure','claim':text[:4000],'source_url':'','caveat':'agent output not JSON','confidence':0.0,'proposed_missing_primitive':''}
  with conn,conn.cursor() as c:
    c.execute("INSERT INTO evidence(structure_id,status,domain,title,claim,source_url,caveat,confidence) VALUES(%s,%s,%s,%s,%s,%s,%s,%s)",(sid,data['verdict'],data.get('domain'),data.get('title'),data.get('claim',''),data.get('source_url'),data.get('caveat'),float(data.get('confidence',0))))
    c.execute("UPDATE structures SET verdict=%s WHERE id=%s",(data['verdict'],sid)); c.execute("UPDATE research_queue SET status='DONE' WHERE id=%s",(qid,)); c.execute("INSERT INTO discoveries(structure_id,event_type,summary,payload) VALUES(%s,%s,%s,%s::jsonb)",(sid,data['verdict'],data.get('title') or data.get('claim','')[:180],json.dumps(data)))
    if data.get('proposed_missing_primitive'): c.execute("INSERT INTO proposals(proposal_type,target,rationale,status) VALUES('MISSING_PRIMITIVE',%s,%s,'PENDING')",(sid,data['proposed_missing_primitive']))
  print(data['verdict'],sid)
if __name__=='__main__': main()
