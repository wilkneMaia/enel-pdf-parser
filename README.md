# ⚡ Enel PDF Parser & Dashboard

Uma ferramenta completa desenvolvida em Python para automatizar a leitura, extração e análise de faturas de energia da Enel. Transforme PDFs complexos em dashboards interativos e insights financeiros claros.

![Python](https://img.shields.io/badge/Python-3.9%2B-blue)
![Streamlit](https://img.shields.io/badge/Streamlit-App-red)
![Status](https://img.shields.io/badge/Status-Active-success)

## 🚀 Funcionalidades

### 📂 Processamento de Arquivos
- **Desbloqueio Automático:** Remove senhas de PDFs protegidos (suporte a senhas baseadas em CPF).
- **Leitura Inteligente:** Utiliza OCR e extração de texto (`pdfplumber`) para estruturar dados de faturas digitais.

### 📊 Dashboards e Análises
- **Taxômetro:** Visualize a "mordida fiscal" (Impostos vs. Energia Real) com gráficos de Treemap.
- **Fluxo Financeiro:** Entenda suas despesas e economias (créditos de geração) de forma clara.
- **Monitor de Consumo:** Acompanhe a evolução do kWh, sazonalidade e eficiência energética.
- **Suporte a Energia Solar:** Identifica automaticamente injeção de energia e calcula o saldo energético.

### 💾 Banco de Dados
- **Histórico Local:** Armazena dados extraídos em arquivos Parquet para performance e persistência.
- **Exportação:** Dados estruturados prontos para análise.

---

## 🛠️ Tecnologias Utilizadas

- **Linguagem:** Python 3
- **Interface:** Streamlit
- **Visualização:** Plotly Express
- **Processamento PDF:** `pdfplumber`, `pikepdf`
- **Dados:** Pandas, PyArrow

---

## 📦 Instalação e Configuração

Siga os passos abaixo para rodar o projeto localmente.

### 1. Pré-requisitos
Certifique-se de ter o **Python 3.9+** instalado.

### 2. Clonar o Repositório
```bash
git clone https://github.com/seu-usuario/enel-pdf-parser.git
cd enel-pdf-parser
```

### 3. Criar Ambiente Virtual (Recomendado)
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux/Mac
python3 -m venv venv
source venv/bin/activate
```

### 4. Instalar Dependências
Instale as bibliotecas necessárias:
```bash
pip install streamlit pandas plotly pdfplumber pikepdf pyarrow
```

---

## 🖥️ Como Usar

1. **Inicie a Aplicação:**
   Execute o comando abaixo na raiz do projeto:
   ```bash
   streamlit run Home.py
   ```
   *(Nota: Caso não tenha um arquivo `Home.py`, execute `streamlit run pages/1_📂_Importar_Fatura.py` para acessar o importador diretamente).*

2. **Importar Fatura:**
   - Navegue até a página **Importar Fatura** no menu lateral.
   - Faça o upload do PDF da sua conta de energia.
   - Se necessário, informe a senha (geralmente os 5 primeiros dígitos do CPF).
   - Clique em **Processar Arquivo**.

3. **Explorar Dashboards:**
   - Navegue pelas páginas para ver o **Taxômetro**, **Histórico de Consumo** e **Fluxo Financeiro**.

---

## 📄 Licença

Este projeto é de uso livre para fins educacionais e pessoais.
