# Post para LinkedIn: Lançamento do AnchorRAG (Agendado para Terça-feira)

## 📌 Metadados da Publicação
- **Data Sugerida:** Terça-feira
- **Horário Recomendado:** 08:30 às 10:00 ou 11:45 às 13:00 (Horário de Brasília)
- **Objetivo:** Divulgação do repositório Open Source AnchorRAG e engajamento da comunidade de IA/Engenharia de Software.
- **Link do Repositório:** https://github.com/alainy-rocha-dev/AnchorRAG

---

## 📝 Texto do Post (Copiar e Colar)

🚀 Por que construí um engine de RAG do zero com SQLite-Vec e Ancoragem Estrita (e como ele resolve alucinações em IA)

---

💡 Quando trabalhamos com Retrieval-Augmented Generation (RAG) em produção, o maior desafio não é fazer o LLM responder — é garantir que ele nunca alucine e cite exatamente a fonte de onde tirou a informação.

Para resolver isso na prática, desenvolvi o AnchorRAG ⚓: um pipeline RAG modular em Python com busca vetorial local e ancoragem estrita de respostas.

✨ O que torna a arquitetura do AnchorRAG diferenciada?

1️⃣ Busca Vetorial Ultra-leve com `sqlite-vec`: Nada de infraestrutura pesada ou bancos vetoriais em nuvem caros para começar. Usamos virtual tables com matemática de similaridade de cosseno direto no SQLite.

2️⃣ Ancoragem Estrita & Rastreabilidade: O engine só responde com base nos trechos recuperados do arquivo fonte. Toda frase vem acompanhada de citações automáticas [N] mapeadas para o chunk exato do PDF original.

3️⃣ Arquitetura Multi-Provedor Plugável:
• Embeddings: OpenAI (text-embedding-3), Ollama local ou HuggingFace (sentence-transformers).
• LLMs: OpenAI, Anthropic ou Ollama (100% offline).

4️⃣ Defesa contra Prompt Injection: System prompt estruturado com poucos exemplos (few-shot defense) para evitar vazamento de contexto ou manipulação externa.

---

🛠️ Stack utilizada: Python 3.10+, Typer (CLI), Pydantic v2, sqlite-vec, Tiktoken, Pytest.

📂 O projeto é Open Source! Documentação completa, comparativo de embeddings e guia de benchmark disponíveis no GitHub:
👉 https://github.com/alainy-rocha-dev/AnchorRAG
(Dê uma ⭐️ no repositório se o projeto for útil para você!)

💭 Como você lida com rastreabilidade e alucinações em sistemas de IA na sua empresa? Vamos debater nos comentários!

#ArtificialIntelligence #Python #RAG #LLM #SQLite #OpenSource #SoftwareEngineering #MachineLearning

---

## 💡 Dicas de Execução & Algoritmo no Dia

1. **Mídia Anexa:** Anexe a imagem do diagrama de arquitetura ou a gravação/demonstração em vídeo do terminal.
2. **Engajamento Inicial:** Fique online nos primeiros 60 minutos após a publicação para responder a todos os comentários recebidos.
