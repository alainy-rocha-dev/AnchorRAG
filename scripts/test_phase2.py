#!/usr/bin/env python3
"""
Script de teste rápido para validar Fase 2 (Retrieval Híbrido).
"""

from __future__ import annotations

import asyncio
import tempfile
import os
from pathlib import Path
from uuid import uuid4

from anchor_rag.config import AppConfig
from anchor_rag.retrieval import FTS5Store, HybridRetriever, rrf_fusion, create_reranker
from anchor_rag.ingestion import StructuredChunker
from anchor_rag.vector_store.sqlite_vec import SQLiteVecStore
from anchor_rag.domain.models import Chunk
from anchor_rag.embeddings.huggingface import HuggingFaceEmbeddingProvider
from anchor_rag.config import EmbeddingConfig


async def test_rrf_fusion():
    """Testa fusão RRF."""
    print("Testando RRF fusion...")
    
    ranking1 = [uuid4() for _ in range(5)]
    ranking2 = [uuid4() for _ in range(5)]
    ranking2[0] = ranking1[2]
    ranking2[1] = ranking1[4]
    
    fused = rrf_fusion([ranking1, ranking2])
    
    assert len(fused) == 8
    top_ids = [cid for cid, _ in fused[:3]]
    assert ranking1[2] in top_ids
    assert ranking1[4] in top_ids
    
    print("  [OK] RRF fusion OK")


async def test_structured_chunker():
    """Testa chunking estruturado."""
    print("Testando StructuredChunker...")
    
    sample_text = """
    Art. 1º Esta Resolução estabelece normas para capital.
    
    § 1º As instituições devem manter capital mínimo de 8%.
    
    § 2º O capital será composto por Tier 1 e Tier 2.
    
    Art. 2º Ficam revogadas as disposições em contrário.
    
    Inciso I - Disposição transitória.
    
    Inciso II - Disposição permanente.
    
    a) Alínea primeira.
    b) Alínea segunda.
    """
    
    chunker = StructuredChunker(chunk_size=200, chunk_overlap=20)
    document_id = uuid4()
    result = chunker.chunk_document(document_id, sample_text)
    
    print(f"  Chunks criados: {result.total_chunks}")
    for i, chunk in enumerate(result.chunks):
        print(f"  Chunk {i}: tipo={chunk.metadata.get('chunk_tipo')}, "
              f"num={chunk.metadata.get('chunk_numero')}, "
              f"tokens={chunk.token_count}, "
              f"titulo={chunk.metadata.get('chunk_titulo')}")
    
    artigos = [c for c in result.chunks if c.metadata.get("chunk_tipo") == "artigo"]
    print(f"  Artigos extraidos: {len(artigos)}")
    assert len(artigos) >= 1
    print("  [OK] StructuredChunker OK")


async def test_fts5_store():
    """Testa FTS5 store."""
    print("Testando FTS5Store...")
    
    # Use a fixed temp path to avoid Windows file locking issues
    import tempfile
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    
    try:
        vs = SQLiteVecStore(str(db_path), embedding_dimensions=384)
        await vs.init_db()
        await vs.init_fts()
        
        chunks = [
            Chunk(
                id=uuid4(),
                document_id=uuid4(),
                content="Art. 1º Capital mínimo de 8% para instituições financeiras.",
                chunk_index=0,
                page_number=1,
                start_char=0,
                end_char=50,
                token_count=15,
                embedding=[0.1] * 384,
                metadata={"norma": "resolucao_cmn_123", "artigo": "1"},
            ),
            Chunk(
                id=uuid4(),
                document_id=uuid4(),
                content="Art. 2º Requisitos de liquidez para bancos.",
                chunk_index=1,
                page_number=1,
                start_char=50,
                end_char=90,
                token_count=12,
                embedding=[0.2] * 384,
                metadata={"norma": "resolucao_cmn_123", "artigo": "2"},
            ),
            Chunk(
                id=uuid4(),
                document_id=uuid4(),
                content="Circular sobre câmbio e operações de crédito.",
                chunk_index=0,
                page_number=1,
                start_char=0,
                end_char=45,
                token_count=10,
                embedding=[0.3] * 384,
                metadata={"norma": "circular_456", "artigo": "1"},
            ),
        ]
        
        await vs.add_chunks(chunks)
        
        # Use same connection for FTS5
        fts = FTS5Store(str(db_path))
        await fts.init_fts()
        count = await fts.rebuild_fts()
        print(f"  FTS5 rebuild count: {count}")
        
        # Busca por termo
        results = await fts.search("capital minimo", top_k=5)
        print(f"  Resultados para 'capital minimo': {len(results)}")
        for chunk, score in results:
            print(f"    score={score:.3f} | {chunk.content[:60]}...")
        
        assert len(results) >= 1, f"Esperava >=1 resultado, obteve {len(results)}"
        assert results[0][1] > 0.5
        
        # Busca com filtro de norma
        results_norma = await fts.search("capital", top_k=5, norma_filter="resolucao_cmn_123")
        print(f"  Resultados filtrados por norma: {len(results_norma)}")
        assert all("resolucao_cmn_123" in c.metadata.get("norma", "") for c, _ in results_norma)
        
        await vs.close()
        await fts.close()
        print("  [OK] FTS5Store OK")
    finally:
        # Cleanup on Windows
        try:
            await vs.close()
        except:
            pass
        try:
            await fts.close()
        except:
            pass
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


async def test_hybrid_retriever():
    """Testa HybridRetriever com embeddings locais."""
    print("Testando HybridRetriever...")
    
    try:
        from anchor_rag.embeddings.huggingface import HuggingFaceEmbeddingProvider
        from anchor_rag.config import EmbeddingConfig
    except ImportError:
        print("  [SKIP] sentence-transformers nao instalado")
        return
    
    import tempfile
    tmpdir = tempfile.mkdtemp()
    db_path = Path(tmpdir) / "test.db"
    
    try:
        vs = SQLiteVecStore(str(db_path), embedding_dimensions=384)
        await vs.init_db()
        await vs.init_fts()
        
        fts = FTS5Store(str(db_path))
        await fts.init_fts()
        
        embed_config = EmbeddingConfig(
            provider="huggingface",
            model="sentence-transformers/all-MiniLM-L6-v2",
            dimensions=384,
        )
        embedder = HuggingFaceEmbeddingProvider(embed_config)
        
        chunks = [
            Chunk(
                id=uuid4(),
                document_id=uuid4(),
                content="Art. 1º Capital mínimo de 8% para instituições financeiras.",
                chunk_index=0,
                page_number=1,
                start_char=0,
                end_char=50,
                token_count=15,
                embedding=None,
                metadata={"norma": "resolucao_cmn_123", "artigo": "1"},
            ),
            Chunk(
                id=uuid4(),
                document_id=uuid4(),
                content="Art. 2º Requisitos de liquidez: LCR mínimo de 100%.",
                chunk_index=1,
                page_number=1,
                start_char=50,
                end_char=90,
                token_count=12,
                embedding=None,
                metadata={"norma": "resolucao_cmn_123", "artigo": "2"},
            ),
        ]
        
        for chunk in chunks:
            emb = await embedder.embed(chunk.content)
            chunk.embedding = emb
        await vs.add_chunks(chunks)
        await fts.rebuild_fts()
        
        retriever = HybridRetriever(
            vector_store=vs,
            fts_store=fts,
            embedder=embedder.embed,
            top_k=5,
        )
        
        results = await retriever.retrieve("qual o capital minimo?", top_k=3)
        print(f"  Resultados hibridos: {len(results)}")
        for chunk in results:
            print(f"    {chunk.content[:60]}... (norma: {chunk.metadata.get('norma')})")
        
        assert len(results) > 0
        
        await embedder.close()
        await vs.close()
        await fts.close()
        print("  [OK] HybridRetriever OK")
    except RuntimeError as e:
        if "sentence-transformers" in str(e):
            print("  [SKIP] sentence-transformers nao instalado")
            return
        raise
    finally:
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


async def main():
    print("=" * 50)
    print("TESTES FASE 2 - RETRIEVAL HIBRIDO")
    print("=" * 50)
    
    await test_rrf_fusion()
    await test_structured_chunker()
    await test_fts5_store()
    await test_hybrid_retriever()
    
    print("=" * 50)
    print("TODOS OS TESTES PASSARAM [OK]")
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())