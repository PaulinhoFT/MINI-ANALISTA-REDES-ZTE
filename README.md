# 🤖 Mini-Analista de Redes (ONUs ZTE)

Um script automatizado em Python capaz de atuar como um "Mini-Analista", acessando ONUs da marca ZTE (modelos F6600, F6600P, F680, F670L) de forma limpa e automática para auditar redes locais, encontrar conflitos de IP e validar saúde do hardware.

## 🚀 Funcionalidades

- **Login Universal Automático**: Burla pop-ups, wizards chatos e assistentes de configuração iniciais.
- **Identificador Inteligente de Modelo**: Verifica a versão do hardware (F6600 ou legado F680) e molda a estratégia de leitura de dados baseado no firmware.
- **Topologia Mapeada**: Monta uma tabela linda no terminal de todos os aparelhos conectados, dividindo-os em **Cabo (LAN)**, **Wi-Fi 2.4GHz** e **Wi-Fi 5GHz**.
- **Auditor de Rede (Detector de Conflitos)**: Usa biblioteca nativa de cálculo de rede para avisar na hora se tem aparelho com `0.0.0.0`, fora da Sub-rede, com IP duplicado ou estático fora do Range do DHCP.
- **Verificador de Saúde Óptica**: Lê o Sinal RX (dBm) da fibra e avisa se a qualidade do laser da CTO está ruim ou operando em nível crítico.
- **Validador de Firmware**: Lê o firmware do equipamento em tempo real e verifica se você possui o arquivo mais atualizado na pasta `Firmwares`.
- **Interface Gráfica no Terminal**: Utiliza a poderosa biblioteca `Rich` para apresentar tabelas flutuantes, cores hexadecimais, ícones e alertas sem precisar de uma interface Web.

## 📦 Como Instalar

1. Clone este repositório para o seu computador.
2. Certifique-se de que o Python 3.10+ está instalado.
3. Instale as dependências via Pip:
```bash
pip install -r requirements.txt
```
4. Baixe os navegadores internos do Playwright (se for a primeira vez usando):
```bash
playwright install chromium
```

## 💻 Como Usar

Abra o terminal na pasta do projeto e rode o script principal:
```bash
python configurar_onu.py
```

Siga os prompts na tela:
1. Ele pedirá o `IP WAN` ou de acesso local do roteador (Ex: `192.168.1.1` ou `100.x.x.x`).
2. Ele fará todo o processo invisível no fundo e vomitará o mapa de calor da rede e a saúde no terminal!

## 🧪 Testes Automatizados

Para testar as lógicas matemáticas sem precisar bater numa ONU física, a arquitetura do projeto possui funções puras testáveis com `pytest`:

```bash
pytest test_configurar_onu.py -v
```

## 🛠 Bibliotecas Usadas
- `playwright`: Para automação de navegadores Headless (Navegação invisível sem depender de APIs abertas do roteador).
- `rich`: Para renderização em console avançada (cores, painéis, tabelas).
- `pytest`: Para testes de unidade.

## 📝 Avisos
- O script por padrão tenta usar o usuário `multipro` / senha `multipro`. Caso suas ONUs usem credenciais diferentes, basta editar no arquivo `configurar_onu.py` na última linha de execução.
- Para a função de "Validador de Firmware" funcionar, basta colocar seus arquivos binários oficiais de firmware de atualização na pastinha local `Firmwares/`.
