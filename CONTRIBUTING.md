# Contribuindo

Obrigado pelo interesse no Marcos DemoFlow.

## Antes de contribuir

A licença do projeto não permite republicar o repositório em outra conta ou serviço. Não crie forks ou mirrors com a finalidade de redistribuir o projeto.

Para bugs e sugestões, abra uma issue no repositório oficial. Pessoas com acesso de escrita podem trabalhar em uma branch separada e abrir Pull Request normalmente.

## Fluxo recomendado

1. Descreva o problema ou melhoria em uma issue.
2. Mantenha a alteração pequena e focada.
3. Preserve compatibilidade com macOS e Windows quando a mudança afetar captura, automação ou build.
4. Rode `python scripts/verify.py`.
5. Teste manualmente a interface quando houver alteração visual ou de automação.
6. No Pull Request, explique o problema, a solução e como foi testada.

## Estilo

- Python legível e direto;
- evitar dependências quando a biblioteca padrão resolve o problema de forma simples;
- não esconder exceções que impedem gravação ou automação;
- automações devem falhar de forma segura: se um alvo não puder ser localizado, é melhor pular a ação do que clicar em uma coordenada incorreta;
- mudanças na interface devem continuar utilizáveis em telas menores e nos temas Claro e Escuro.
