# Política de assinatura de código

Documento exigido pela SignPath Foundation e mantido público por escolha do
projeto: quem instala um binário assinado tem o direito de saber quem decidiu
assinar e sob quais regras.

## Créditos

Os binários do Xdiag Privacy para Windows são assinados gratuitamente por
[SignPath.io](https://signpath.io/), com certificado fornecido pela
[SignPath Foundation](https://signpath.org/).

O certificado é emitido em nome da **SignPath Foundation**, e não da Xdiag
Tecnologias. Portanto o editor exibido pelo Windows ao instalar é "SignPath
Foundation". Isso é como o programa deles funciona: a fundação atesta que o
binário foi construído a partir deste repositório público, em vez de validar
a identidade da empresa.

## Equipe e papéis

| Papel | Quem | O que faz |
| --- | --- | --- |
| Autor | Antonio Massucatti ([@Xdiag-IA](https://github.com/Xdiag-IA)) | Escreve e modifica o código |
| Revisor | Antonio Massucatti ([@Xdiag-IA](https://github.com/Xdiag-IA)) | Aprova pull requests |
| Aprovador | Antonio Massucatti ([@Xdiag-IA](https://github.com/Xdiag-IA)) | Autoriza cada assinatura de release |

Todos os integrantes usam autenticação de dois fatores no GitHub.

Contribuições externas entram apenas por pull request, passam por revisão e
nunca são assinadas sem aprovação explícita de um Aprovador.

## Como os binários são produzidos

Os instaladores são compilados exclusivamente pelo GitHub Actions, no
workflow [`build-installer.yml`](.github/workflows/build-installer.yml), a
partir do código deste repositório. Nenhum binário compilado em máquina
pessoal é assinado ou distribuído.

O workflow verifica, antes de empacotar, que a interface não saiu com
endereço de API fixo e que o instalador está dentro da faixa de tamanho
esperada. Build que falhe nessas checagens não gera artefato.

## Privacidade

O Xdiag Privacy **não coleta absolutamente nenhum dado**. Essa não é uma
concessão, é a razão de existir do produto:

- Nenhuma telemetria, nenhuma métrica de uso, nenhum relatório de erro
  enviado a servidor.
- Nenhuma conta, nenhum cadastro, nenhum login.
- Os documentos processados nunca saem da máquina. Todo o OCR e toda a
  detecção rodam localmente.
- A única comunicação externa acontece na primeira execução, para baixar o
  runtime Python e os modelos de aprendizado de máquina. Depois disso o
  aplicativo funciona sem internet, o que pode ser verificado com um
  analisador de tráfego (o procedimento está no [README](README.md)).
- Nenhum dado pessoal é gravado em disco pelo aplicativo além dos arquivos
  que o próprio usuário escolhe exportar, no local que ele escolher.

Como não há coleta, não existe opção de desativação a oferecer.

## Alterações no sistema e desinstalação

A instalação é por usuário, em `%LOCALAPPDATA%\Programs\Xdiag Privacy`, sem
elevação de privilégio e sem modificar configuração do sistema, do registro
compartilhado ou de outros programas.

O aplicativo abre um servidor HTTP local ligado exclusivamente a
`127.0.0.1`, em porta efêmera, acessível apenas pela própria máquina.

A desinstalação está disponível em Configurações do Windows, Aplicativos. Os
componentes baixados na primeira execução ficam em
`%APPDATA%\Xdiag Privacy` e podem ser apagados manualmente; eles são
preservados na desinstalação para que uma reinstalação não precise baixar
tudo de novo.

## Segurança

Falhas de segurança devem ser reportadas pelo canal privado descrito em
[SECURITY.md](SECURITY.md), nunca em issue pública.
