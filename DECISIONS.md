o review exige terminal interativo, porque um agente chegou a gravar decisões no dataset
## Corpus alterado durante a revisao (12/10)
- O agente reingeriu o corpus (commit bfe8611, 06:59) enquanto a revisao estava aberta; o review mostrava a versao antiga carregada na memoria.
- Verificacao: termos das 73 respostas-ouro comparados com o texto atual dos chunks; 8 itens com termos ausentes, todos parafrases. Nenhum item invalidado.
- Medida futura: congelar o corpus durante a revisao e gravar no item um hash do texto do chunk revisado.
## sem_resposta: perguntas escritas a mao em vez de geradas (12/10)
- O gerador (qwen2.5:7b) partia de um trecho e pedia uma pergunta que o corpus nao respondesse. Das candidatas geradas, so 4 sobreviveram a revisao: na maioria, o proprio trecho de origem ou o seguinte respondia.
- Causa frequente: titulo de capitulo no fim do chunk ("DAS PENALIDADES APLICAVEIS", "DA FINALIDADE") virava pergunta, embora o capitulo exista logo adiante (ver eval/datasets/pendencias_agente.md).
- Para completar a categoria, 19 perguntas sobre temas regulatorios vizinhos fora das 12 normas (FGC, IOF, compulsorio, LCR, Drex etc.), conferidas com overlap_top e busca de termos no corpus; 5 outras foram descartadas antes da revisao porque algum trecho respondia em parte. Varias tem distratores de proposito (ex.: 90 dias de desligamento do Pix x encerramento de conta).
- Itens marcados gerado_por "manual:claude" em eval/datasets/candidatas_manuais_sem_resposta.jsonl; todos passaram pelo mesmo review humano. Resultado: 23 sem_resposta (4 geradas + 19 manuais).
- Licao: overlap lexical alto nao indica resposta (Pronaf: 0.71, sem resposta) e overlap baixo nao garante ausencia; o filtro continua sendo a revisao humana.
