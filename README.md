# 💰 vivIA: Sua IA Financeira

![Status](https://img.shields.io/badge/Status-Em%20Desenvolvimento-blue)
![Python](https://img.shields.io/badge/Python-3.10%2B-blue)
![AGNO](https://img.shields.io/badge/Framework-AGNO-orange)
![Reflex](https://img.shields.io/badge/UI-Reflex-purple)

Este projeto é a implementação do **Tema 6: Assessor financeiro pessoal** para o Trabalho Final da disciplina de Inteligência Artificial do curso de BSI do Instituto Federal do Espírito Santo (IFES), sob orientação do Prof. Dr. Sérgio Nery Simões (2026).

## 🎯 Objetivo do Projeto

Diferente de sistemas financeiros tradicionais que focam apenas em cortes drásticos, este agente foi projetado com **empatia computacional**. Ele atua como um assessor amigável que busca equilibrar a saúde financeira do usuário com a sua qualidade de vida e felicidade.

O agente realiza um *onboarding* conversacional para descobrir os hobbies do usuário (ex: robótica, motos, esportes) e trata os gastos nessas áreas como investimentos em bem-estar, ajudando a otimizar outras despesas (como assinaturas esquecidas).

## ✨ Funcionalidades

- **Onboarding Conversacional:** O agente entrevista o usuário no início da sessão para entender seu estilo de vida e prioridades.
- **Análise de Gastos:** Ingestão de dados financeiros sintéticos e categorização automática das despesas.
- **Integração com Mercado Real (YFinance):** Ferramenta autônoma que permite ao agente buscar cotações de ações e dados de empresas em tempo real para sugerir investimentos.
- **Memória de Sessão:** O agente retém o contexto de toda a conversa, somando novos gastos informados no chat com a base de dados inicial.
- **Interface Full-Stack Python:** Construída inteiramente em Python utilizando Reflex.

## 🛠️ Tecnologias Utilizadas

- **[AGNO](https://github.com/agno-agi/agno):** Framework veloz e nativo Python para construção de agentes autônomos utilizando o padrão ReAct (Reason + Act).
- **[Reflex](https://reflex.dev/):** Framework web full-stack para construção da interface de usuário.
- **[Groq](https://console.groq.com/):** Provedor da API de LLM garantindo inferência ultrarrápida (Modelo utilizado: `Llama-4-scout`).
- **YFinance / Pandas:** Ferramentas para manipulação de dados numéricos e consultas ao mercado financeiro.

## 🚀 Como Executar o Projeto

### Pré-requisitos
- Python 3.10 ou superior.
- Node.js e NPM (necessários para o motor de compilação do Reflex).
- Chave de API da [Groq](https://console.groq.com/).

### Instalação e execução

1. **Clone o repositório e acesse a pasta:**
   ```bash
   git clone https://github.com/guilhermbc/agno-assessor-financeiro.git
   cd agno-assessor-financeiro
   ```

2. **Crie e ative o ambiente virtual:**

    ```Bash
    python -m venv venv
    ```

    No Windows:
    ```Bash
    .\venv\Scripts\activate
    ```
    No Linux/Mac:
    ```Bash
    source venv/bin/activate
    ```

3. Instale as dependências Python:

    ```Bash
    pip install -r requirements.txt
    ```

4. Instale o Bun (Motor de compilação do Reflex) e inicia o reflex:

    ```Bash    
    npm install -g bun
    reflex init
    ```

5. Configuração de Variáveis de Ambiente:

    Crie um arquivo chamado .env na raiz do projeto. 
    
    ATENÇÃO: Este arquivo não deve ser comitado no Git.

    Snippet de código
    ```
    GROQ_API_KEY="sua_chave_api_aqui"
    ```

6. Inicie a aplicação:

    ```Bash
    reflex run
    ```
## Acesse no seu navegador: http://localhost:3000

🧪 Notas sobre Dados Sensíveis

Conforme as regras da disciplina, é estritamente proibido o uso de dados financeiros reais. Para testar a aplicação, utilizamos planilhas e gastos gerados com dados sintéticos (ex: utilizando a biblioteca Faker).

🧠 Análise de Reasoning Traces (Avaliação Crítica)

(Seção reservada para a entrega final do projeto, onde serão documentadas as análises de pelo menos cinco execuções reais do agente, detalhando chamadas de ferramentas e tratamentos de alucinação).