import pdfplumber
import re

# --- FUNÇÕES AUXILIARES ---

def limpar_linha(linha):
    """
    Separa a string bruta em: Descrição | Unidade | String de Valores
    """
    # 1. REMOVER HISTÓRICO DE CONSUMO
    padrao_historico = r'\s(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[\s\/]?\d{2}.*$'
    linha_limpa = re.sub(padrao_historico, '', linha, flags=re.IGNORECASE).strip()

    if not linha_limpa:
        return None

    # 2. Tenta encontrar unidades conhecidas
    match_unidade = re.search(r'^(.*?)\s+(kWh|kW|dias|unid|un)\s+(.*)$', linha_limpa, re.IGNORECASE)
    if match_unidade:
        return {
            "descricao": match_unidade.group(1).strip(),
            "unidade": match_unidade.group(2).strip(),
            "valores_str": match_unidade.group(3).strip(),
            "tipo": "padrao"
        }

    # 3. Item sem unidade
    match_numero = re.search(r'^(.*?)\s+(\d+[.,]\d{2}.*)$', linha_limpa)
    if match_numero:
        return {
            "descricao": match_numero.group(1).strip(),
            "unidade": "",
            "valores_str": match_numero.group(2).strip(),
            "tipo": "simples"
        }

    return None

def processar_valores(valores_str, tipo_item):
    """
    Distribui os números nas colunas corretas de faturamento.
    """
    valores_limpos = re.sub(r'\s(I\s?CMS|LID|DE|FATURAMENTO|TRIBUTOS|COFINS|PIS).*', '', valores_str, flags=re.IGNORECASE).strip()
    tokens = valores_limpos.split()

    colunas = {
        "Quant.": "", "Preço unit (R$) com tributos": "", "Valor (R$)": "", "PIS/COFINS": "",
        "Base Calc ICMS (R$)": "", "Alíquota ICMS": "", "ICMS": "", "Tarifa unit (R$)": ""
    }

    if not tokens: return colunas

    if tipo_item == "padrao":
        campos = ["Quant.", "Preço unit (R$) com tributos", "Valor (R$)", "PIS/COFINS",
                  "Base Calc ICMS (R$)", "Alíquota ICMS", "ICMS", "Tarifa unit (R$)"]
        if len(tokens) >= 8:
            for i, c in enumerate(campos): colunas[c] = tokens[i]
        elif len(tokens) >= 3:
            colunas["Quant."] = tokens[0]
            colunas["Preço unit (R$) com tributos"] = tokens[1]
            colunas["Valor (R$)"] = tokens[2]
            # Preenche o resto sequencialmente
            for i, val in enumerate(tokens[3:]):
                if i < len(campos[3:]): colunas[campos[3+i]] = val

    elif tipo_item == "simples":
        colunas["Valor (R$)"] = tokens[0]
        campos = ["PIS/COFINS", "Base Calc ICMS (R$)", "Alíquota ICMS", "ICMS"]
        for i, val in enumerate(tokens[1:]):
            if i < len(campos): colunas[campos[i]] = val

    return colunas

def extrair_medicao(texto_completo):
    """
    Nova função para extrair a tabela de EQUIPAMENTOS DE MEDIÇÃO.
    Retorna uma lista de dicionários.
    """
    itens_medicao = []

    # Divide o texto em linhas
    linhas = texto_completo.split('\n')
    capturando = False

    # Regex para capturar a linha de medição
    # Ex: 6938979-ELE-728 HFP 07/08/2025 14653.0 05/09/2025 15165.0 1.0 512.0 30
    # Grupo 1: Medidor | Grupo 2: Segmento | Grupo 3: Data1 | Grupo 4: Leitura1
    # Grupo 5: Data2 | Grupo 6: Leitura2 | Grupo 7: Fator | Grupo 8: Consumo | Grupo 9: Dias
    regex_medicao = re.compile(
        r'(\S+)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)'
    )

    for linha in linhas:
        linha_upper = linha.upper().strip()

        # Gatilho de início
        if "EQUIPAMENTOS DE MEDIÇÃO" in linha_upper:
            capturando = True
            continue

        # Gatilho de fim (geralmente começa outra seção como MÊS/ANO ou Histórico)
        if capturando and ("MÊS/ANO" in linha_upper or "HISTÓRICO" in linha_upper or "PIS/PASEP" in linha_upper):
            break

        if capturando:
            match = regex_medicao.search(linha)
            if match:
                itens_medicao.append({
                    "N° Medidor": match.group(1),
                    "P.Horário/Segmento": match.group(2),
                    "Data Leitura (Anterior)": match.group(3),
                    "Leitura (Anterior)": match.group(4),
                    "Data Leitura (Atual)": match.group(5),
                    "Leitura (Atual)": match.group(6),
                    "Fator Multiplicador": match.group(7),
                    "Consumo kWh": match.group(8),
                    "N° Dias": match.group(9)
                })

    return itens_medicao

# --- FUNÇÃO PRINCIPAL ---

def extrair_dados_fatura(caminho_arquivo):
    dados = {
        "referencia": "Não encontrado",
        "itens": [],   # Itens financeiros (Energia, CIP...)
        "medicao": []  # Nova lista para Equipamentos de Medição
    }

    print(f"🔍 Analisando: {caminho_arquivo}")

    TERMOS_IGNORADOS = [
        "MÊS/ANO", "COMSUMO", "CONSUMO", "TIPOS DE FATURAMENTO", "DIAS",
        "TRIBUTOS", "ICMS UNIT", "PIS/PASEP", "DADOS DE MEDIÇÃO",
        "LEITURA", "CONST. MEDIDOR", "GRANDEZAS", "POSTOS TARIFÁRIOS",
        "ELE-", "HFP"
    ]

    try:
        with pdfplumber.open(caminho_arquivo) as pdf:
            pagina = pdf.pages[0]
            texto = pagina.extract_text(layout=True)

            # 1. Referência
            match_ref = re.search(r'(?<!\d/)\b(\d{2}/\d{4})\b', texto)
            if match_ref:
                dados["referencia"] = match_ref.group(1)

            # 2. Extração de Medição (NOVA CHAMADA)
            dados["medicao"] = extrair_medicao(texto)

            # 3. Extração de Itens Financeiros
            linhas = texto.split('\n')
            capturando = False
            itens_temp = []

            for linha in linhas:
                linha_limpa = linha.strip()
                linha_upper = linha_limpa.upper()

                if any(termo in linha_upper for termo in TERMOS_IGNORADOS): continue
                if re.match(r'^\d{5,}', linha_limpa): continue # Ignora medidor aqui (já pegamos na função nova)

                if ("DESCRI" in linha_upper or "ITENS" in linha_upper) and "FATURA" in linha_upper:
                    capturando = True
                    continue

                if capturando and ("TOTAL" in linha_upper or "SUBTOTAL" in linha_upper):
                    capturando = False
                    break

                if capturando:
                    info = limpar_linha(linha_limpa)
                    if info and info["descricao"] and len(info["descricao"]) > 2:
                        desc_upper = info["descricao"].upper().strip()
                        if desc_upper in ["PIS", "COFINS", "ICMS", "I CMS", "TOTAL", "SUBTOTAL"]: continue

                        colunas_valores = processar_valores(info["valores_str"], info["tipo"])
                        item = {
                            "Itens de Fatura": info["descricao"],
                            "Unid.": info["unidade"],
                            **colunas_valores
                        }
                        itens_temp.append(item)

            # PLANO B para Financeiro
            if not itens_temp:
                palavras_chave = ["ENERGIA", "ILUM", "BANDEIRA", "JUROS", "MULTA", "TUSD", "TE"]
                for linha in linhas:
                    linha_limpa = linha.strip()
                    linha_upper = linha_limpa.upper()

                    if any(termo in linha_upper for termo in TERMOS_IGNORADOS): continue
                    if re.match(r'^\d{5,}', linha_limpa): continue
                    if "TOTAL" in linha_upper or "VENCIMENTO" in linha_upper: continue

                    if any(p in linha_upper for p in palavras_chave) and re.search(r'\d+[.,]\d{2}', linha):
                        info = limpar_linha(linha_limpa)
                        if info and info["descricao"] and len(info["descricao"]) > 2:
                            desc_upper = info["descricao"].upper().strip()
                            if desc_upper in ["PIS", "COFINS", "ICMS", "I CMS"]: continue
                            colunas_valores = processar_valores(info["valores_str"], info["tipo"])
                            item = {
                                "Itens de Fatura": info["descricao"],
                                "Unid.": info["unidade"],
                                **colunas_valores
                            }
                            itens_temp.append(item)

            dados["itens"] = itens_temp
            return dados

    except Exception as e:
        print(f"❌ Erro crítico: {e}")
        return None
