## Inserção via ctx-dispatch-router

Às vezes você vai rodar em modo headless (`claude -p`) disparado pelo ctx-dispatch-router.
O prompt traz o caminho de um print da tela e o conteúdo já transcrito dele. Nesse caso:

1. **Leia a imagem** (com Read) para conferir a transcrição. Se as duas divergirem, vale a imagem.
2. **Escolha o arquivo:** <!-- EDITE: ex. "uma vaga por arquivo em `vagas/<empresa>-<cargo>.md`" ou "acrescente em `disciplinas/<sigla>.md`, na seção da aula" -->
3. **Formato:** <!-- EDITE: cole aqui o modelo de entrada (frontmatter, cabeçalhos, campos obrigatórios) -->
4. **Evite duplicatas:** antes de escrever, procure (com Grep) por identificadores do conteúdo,
   como nome da empresa e cargo, título da aula ou data. Se já existir:
   - informação idêntica: não altere nada e responda "já existia: <onde>";
   - informação nova sobre o mesmo item (ex.: mudança de status): atualize a entrada existente.
5. **Não invente:** registre só o que está no print. Campo sem informação fica vazio ou como `?`.
6. **Commit (só se esta pasta for um repo git):** `git add` só dos arquivos que você alterou e depois
   `git commit -m "dispatch: <o que entrou, em poucas palavras>"`. Não faça push.
7. **Não mexa** em nada fora do que a inserção exige: sem refatorar, sem reorganizar e sem corrigir outros arquivos.
