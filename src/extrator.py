import pdfplumber
import re

def limpar_linha(linha):
    """
    Separa a string bruta em: Descrição | Unidade | String de Valores
    """
    # 1. REMOVER HISTÓRICO DE CONSUMO
    # Remove meses seguidos de números no final da linha (ex: SET25 512.00...)
    padrao_historico = r'\s(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[\s\/]?\d{2}.*$'
    linha_limpa = re.sub(padrao_historico, '', linha, flags=re.IGNORECASE).strip()

    if not linha_limpa:
        return None

    # 2. Tenta encontrar unidades conhecidas (pivô) -> Item Padrão
    match_unidade = re.search(r'^(.*?)\s+(kWh|kW|dias|unid|un)\s+(.*)$', linha_limpa, re.IGNORECASE)
    if match_unidade:
        return {
            "descricao": match_unidade.group(1).strip(),
            "unidade": match_unidade.group(2).strip(),
            "valores_str": match_unidade.group(3).strip(),
            "tipo": "padrao"
        }

    # 3. Item sem unidade (CIP, Juros) -> Separa pelo primeiro número encontrado
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
    # Remove resíduos de textos que não são números
    valores_limpos = re.sub(r'\s(I\s?CMS|LID|DE|FATURAMENTO|TRIBUTOS|COFINS|PIS).*', '', valores_str, flags=re.IGNORECASE).strip()
    tokens = valores_limpos.split()

    colunas = {
        "Quant.": "",
        "Preço unit (R$) com tributos": "",
        "Valor (R$)": "",
        "PIS/COFINS": "",
        "Base Calc ICMS (R$)": "",
        "Alíquota ICMS": "",
        "ICMS": "",
        "Tarifa unit (R$)": ""
    }

    if not tokens:
        return colunas

    if tipo_item == "padrao":
        campos = ["Quant.", "Preço unit (R$) com tributos", "Valor (R$)", "PIS/COFINS",
                  "Base Calc ICMS (R$)", "Alíquota ICMS", "ICMS", "Tarifa unit (R$)"]

        if len(tokens) >= 8:
            for i, campo in enumerate(campos):
                colunas[campo] = tokens[i]
        elif len(tokens) >= 3:
            colunas["Quant."] = tokens[0]
            colunas["Preço unit (R$) com tributos"] = tokens[1]
            colunas["Valor (R$)"] = tokens[2]

            restantes = tokens[3:]
            campos_restantes = campos[3:]
            for i, val in enumerate(restantes):
                if i < len(campos_restantes):
                    colunas[campos_restantes[i]] = val

    elif tipo_item == "simples":
        colunas["Valor (R$)"] = tokens[0]

        campos_impostos = ["PIS/COFINS", "Base Calc ICMS (R$)", "Alíquota ICMS", "ICMS"]
        restantes = tokens[1:]
        for i, val in enumerate(restantes):
            if i < len(campos_impostos):
                colunas[campos_impostos[i]] = val

    return colunas

def extrair_dados_fatura(caminho_arquivo):
    dados = {
        "referencia": "Não encontrado",
        "itens": []
    }

    print(f"🔍 Analisando: {caminho_arquivo}")

    # --- LISTA NEGRA (BLACKLIST) ---
    # Termos que MATAM a linha imediatamente.
    # Adicionei 'ELE-' e 'HFP' para matar as linhas do medidor.
    # REMOVI 'ICMS' e 'COFINS' daqui para não matar a CIP.
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

            match_ref = re.search(r'(?<!\d/)\b(\d{2}/\d{4})\b', texto)
            if match_ref:
                dados["referencia"] = match_ref.group(1)

            linhas = texto.split('\n')
            capturando = False
            itens_temp = []

            for linha in linhas:
                linha_limpa = linha.strip()
                linha_upper = linha_limpa.upper()

                # --- FILTRO 1: Ignorar termos proibidos ---
                if any(termo in linha_upper for termo in TERMOS_IGNORADOS):
                    continue

                # --- FILTRO 1.1: Ignorar linhas de medidor que começam com números longos ---
                # Ex: 6938979-ELE...
                if re.match(r'^\d{5,}', linha_limpa):
                    continue

                # Gatilhos de Início
                if ("DESCRI" in linha_upper or "ITENS" in linha_upper) and "FATURA" in linha_upper:
                    capturando = True
                    continue

                # Gatilhos de Fim
                if capturando and ("TOTAL" in linha_upper or "SUBTOTAL" in linha_upper):
                    capturando = False
                    break

                if capturando:
                    info = limpar_linha(linha_limpa)

                    if info and info["descricao"] and len(info["descricao"]) > 2:
                        # --- FILTRO 2: Descrição é apenas nome de imposto? ---
                        # Se a descrição for SÓ "COFINS" ou "ICMS", ignora.
                        desc_upper = info["descricao"].upper().strip()
                        if desc_upper in ["PIS", "COFINS", "ICMS", "I CMS", "TOTAL", "SUBTOTAL"]:
                            continue

                        colunas_valores = processar_valores(info["valores_str"], info["tipo"])
                        item = {
                            "Itens de Fatura": info["descricao"],
                            "Unid.": info["unidade"],
                            **colunas_valores
                        }
                        itens_temp.append(item)

            # PLANO B (Se falhar a captura normal)
            if not itens_temp:
                print("   ⚠️ Cabeçalho não detectado. Ativando busca por palavras-chave...")
                palavras_chave = ["ENERGIA", "ILUM", "BANDEIRA", "JUROS", "MULTA", "TUSD", "TE"]

                for linha in linhas:
                    linha_limpa = linha.strip()
                    linha_upper = linha_limpa.upper()

                    if any(termo in linha_upper for termo in TERMOS_IGNORADOS): continue
                    if re.match(r'^\d{5,}', linha_limpa): continue # Ignora medidor no plano B tbm
                    if "TOTAL" in linha_upper or "VENCIMENTO" in linha_upper: continue

                    if any(p in linha_upper for p in palavras_chave) and re.search(r'\d+[.,]\d{2}', linha):
                        info = limpar_linha(linha_limpa)
                        if info and info["descricao"] and len(info["descricao"]) > 2:
                             # Reaplica filtro de descrição proibida
                            desc_upper = info["descricao"].upper().strip()
                            if desc_upper in ["PIS", "COFINS", "ICMS", "I CMS"]:
                                continue

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
