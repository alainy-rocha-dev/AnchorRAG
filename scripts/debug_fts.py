import sqlite3
import tempfile
from pathlib import Path

with tempfile.TemporaryDirectory() as tmpdir:
    db_path = Path(tmpdir) / 'test.db'
    conn = sqlite3.connect(str(db_path))
    conn.enable_load_extension(True)
    import sqlite_vec
    sqlite_vec.load(conn)
    
    conn.execute('CREATE TABLE chunks (id TEXT PRIMARY KEY, content TEXT, metadata TEXT)')
    conn.execute('CREATE VIRTUAL TABLE chunks_fts USING fts5(content, document_id UNINDEXED, chunk_id UNINDEXED, norma UNINDEXED, artigo UNINDEXED)')
    
    conn.execute("INSERT INTO chunks VALUES ('1', 'Art. 1 Capital minimo', '{\"norma\": \"resolucao_cmn_123\", \"artigo\": \"1\"}')")
    conn.execute("INSERT INTO chunks VALUES ('2', 'Art. 2 Liquidez', '{\"norma\": \"resolucao_cmn_123\", \"artigo\": \"2\"}')")
    
    conn.execute('DELETE FROM chunks_fts')
    conn.execute('INSERT INTO chunks_fts(rowid, content, document_id, chunk_id, norma, artigo) SELECT id, content, "doc1", id, json_extract(metadata, "$.norma"), json_extract(metadata, "$.artigo") FROM chunks')
    
    cursor = conn.execute("SELECT * FROM chunks_fts WHERE chunks_fts MATCH 'capital'")
    rows = cursor.fetchall()
    print('FTS results:', len(rows))
    for r in rows:
        print(' ', r)
    
    conn.close()