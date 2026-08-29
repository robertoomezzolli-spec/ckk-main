import os,psycopg

def main():
  conn=psycopg.connect(os.environ['DATABASE_URL'])
  with conn,conn.cursor() as c:
    c.execute('''WITH deg AS (SELECT id, paths, (SELECT count(*) FROM edges e WHERE e.source_id=s.id OR e.target_id=s.id) degree FROM structures s), kn AS (SELECT s.id,count(*) FILTER (WHERE n.verdict IN ('KNOWN','REDISCOVERED','ADMITTED')) known_neighbors,count(*) total_neighbors FROM structures s LEFT JOIN edges e ON e.source_id=s.id OR e.target_id=s.id LEFT JOIN structures n ON n.id=CASE WHEN e.source_id=s.id THEN e.target_id ELSE e.source_id END GROUP BY s.id) INSERT INTO research_queue(structure_id,priority,status) SELECT s.id, d.paths*(0.2+COALESCE(kn.known_neighbors::real/NULLIF(kn.total_neighbors,0),0)),'QUEUED' FROM structures s JOIN deg d USING(id) JOIN kn USING(id) WHERE s.verdict='UNMATCHED' ON CONFLICT(structure_id) DO UPDATE SET priority=EXCLUDED.priority''')
  print('queue rebuilt')
if __name__=='__main__': main()
