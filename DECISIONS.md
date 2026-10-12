o review exige terminal interativo, porque um agente chegou a gravar decisões no dataset
## Corpus alterado durante a revisao (12/10)
- O agente reingeriu o corpus (commit bfe8611, 06:59) enquanto a revisao estava aberta; o review mostrava a versao antiga carregada na memoria.
- Verificacao: termos das 73 respostas-ouro comparados com o texto atual dos chunks; 8 itens com termos ausentes, todos parafrases. Nenhum item invalidado.
- Medida futura: congelar o corpus durante a revisao e gravar no item um hash do texto do chunk revisado.
