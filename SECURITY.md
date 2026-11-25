# Política de segurança

A aplicação gerencia dados operacionais e comerciais. Credenciais, informações pessoais, documentos de clientes e dados de infraestrutura não devem ser publicados no repositório, em issues ou em capturas de tela.

## Reportar uma questão de segurança

Informações sobre possíveis vulnerabilidades devem ser encaminhadas de modo privado aos responsáveis pelo desenvolvimento. Não publique credenciais, dados reais ou detalhes exploráveis em issues públicas.

## Proteção de ambientes

O MVP não possui autenticação individual. Uma implantação pública deve utilizar **banco de demonstração isolado e dados fictícios/anonimizados**, sem conexão à base operacional. Tornar o repositório privado não restringe o acesso a um aplicativo Streamlit que permaneça público.

As configurações sensíveis são mantidas fora do versionamento. Antes de alterações de esquema ou publicação de novas funcionalidades, utilizar backup e validar em ambiente separado.

Consulte [Segurança e privacidade](docs/seguranca_privacidade.md) para as diretrizes de implantação e tratamento de dados.
