import pdfplumber
import re
import pandas as pd

# --- HELPER FUNCTIONS ---


def normalize_negative_value(value_str):
    """
    Normaliza valores negativos no formato "19,52-" para "-19.52"
    Também trata valores positivos convertendo vírgula para ponto.
    """
    if not value_str:
        return value_str

    # Converte para string se não for
    if not isinstance(value_str, str):
        value_str = str(value_str)

    value_str = value_str.strip()

    # Se estiver vazio após strip, retorna como está
    if not value_str:
        return value_str

    # Verifica se já tem sinal negativo no início
    is_negative = False
    if value_str.startswith("-"):
        is_negative = True
        value_str = value_str[1:]  # Remove o sinal do início temporariamente
    elif value_str.endswith("-"):
        # Sinal negativo no final (ex: "19,52-")
        is_negative = True
        value_str = value_str[:-1]  # Remove o sinal do final

    # Converte vírgula para ponto
    value_str = value_str.replace(",", ".")

    # Adiciona sinal negativo no início se necessário
    if is_negative:
        value_str = "-" + value_str

    return value_str


def clean_line(line):
    """
    Tenta separar a linha em: Descrição | Unidade | Valores
    """
    # 1. Remove Histórico (Estratégia Conservadora)
    # Remove apenas se tiver espaço antes (ex: " JAN/24") para não quebrar linhas que começam com texto
    history_pattern = (
        r"\s(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[\s\/]*\d{2,4}.*$"
    )
    cleaned_line = re.sub(history_pattern, "", line, flags=re.IGNORECASE).strip()

    if not cleaned_line:
        return None

    # 2. Tenta encontrar unidades conhecidas (kWh, dias, etc)
    unit_match = re.search(
        r"^(.*?)\s+(kWh|kW|dias|unid|un)\s+(.*)$", cleaned_line, re.IGNORECASE
    )
    if unit_match:
        return {
            "description": unit_match.group(1).strip(),
            "unit": unit_match.group(2).strip(),
            "values_str": unit_match.group(3).strip(),
            "type": "standard",
        }

    # 3. Itens Simples (Descrição + Valor)
    number_match = re.search(r"^(.*?)\s+(\d+[.,]\d{2}.*)$", cleaned_line)
    if number_match:
        return {
            "description": number_match.group(1).strip(),
            "unit": "",
            "values_str": number_match.group(2).strip(),
            "type": "simple",
        }

    return None


def process_values(values_str, item_type):
    """
    Mapeia a string de números para as colunas corretas.
    """
    clean_values = re.sub(
        r"\s(I\s?CMS|LID|DE|FATURAMENTO|TRIBUTOS|COFINS|PIS).*",
        "",
        values_str,
        flags=re.IGNORECASE,
    ).strip()
    tokens = clean_values.split()

    # Normaliza valores negativos (formato "19,52-" -> "-19.52")
    tokens = [normalize_negative_value(token) for token in tokens]

    columns = {
        "Quant.": "",
        "Preço unit (R$) com tributos": "",
        "Valor (R$)": "",
        "PIS/COFINS": "",
        "Base Calc ICMS (R$)": "",
        "Alíquota ICMS": "",
        "ICMS": "",
        "Tarifa unit (R$)": "",
    }

    if not tokens:
        return columns

    if item_type == "standard":
        fields = [
            "Quant.",
            "Preço unit (R$) com tributos",
            "Valor (R$)",
            "PIS/COFINS",
            "Base Calc ICMS (R$)",
            "Alíquota ICMS",
            "ICMS",
            "Tarifa unit (R$)",
        ]

        # Tenta encaixar os tokens nos campos
        if len(tokens) >= 8:
            for i, field in enumerate(fields):
                columns[field] = tokens[i]
        elif len(tokens) >= 3:
            columns["Quant."] = tokens[0]
            columns["Preço unit (R$) com tributos"] = tokens[1]
            columns["Valor (R$)"] = tokens[2]
            # Preenche o restante se houver
            for i, val in enumerate(tokens[3:]):
                if i < len(fields[3:]):
                    columns[fields[3 + i]] = val

    elif item_type == "simple":
        columns["Valor (R$)"] = tokens[0]
        fields = ["PIS/COFINS", "Base Calc ICMS (R$)", "Alíquota ICMS", "ICMS"]
        for i, val in enumerate(tokens[1:]):
            if i < len(fields):
                columns[fields[i]] = val

    return columns


def extract_measurement(full_text):
    measurement_items = []
    lines = full_text.split("\n")
    is_capturing = False

    # Regex ajustado para pegar medição (Consumo)
    # Procura linha com data (dd/mm/aaaa) e números
    regex_measure = re.compile(
        r"(\S+)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)"
    )

    for line in lines:
        line_upper = line.upper().strip()

        if "EQUIPAMENTOS DE MEDIÇÃO" in line_upper or "DADOS DE MEDIÇÃO" in line_upper:
            is_capturing = True
            continue

        if is_capturing:
            if (
                "MÊS/ANO" in line_upper
                or "HISTÓRICO" in line_upper
                or "NOTIFICAÇÃO" in line_upper
            ):
                break

            match = regex_measure.search(line)
            if match:
                measurement_items.append(
                    {
                        "N° Medidor": match.group(1),
                        "P.Horário/Segmento": match.group(2),
                        "Data Leitura (Anterior)": match.group(3),
                        "Leitura (Anterior)": match.group(4),
                        "Data Leitura (Atual)": match.group(5),
                        "Leitura (Atual)": match.group(6),
                        "Fator Multiplicador": match.group(7),
                        "Consumo kWh": match.group(8),
                        "N° Dias": match.group(9),
                    }
                )
    return measurement_items


# --- MAIN EXTRACTION FUNCTION ---


def extract_invoice_data(file_path, password=None):
    data = {
        "reference": "Not Found",
        "client_id": "Not Found",
        "items": [],
        "measurement": [],
    }

    IGNORED_TERMS = [
        "MÊS/ANO",
        "COMSUMO",
        "CONSUMO",
        "TIPOS DE FATURAMENTO",
        "DIAS",
        "TRIBUTOS",
        "ICMS UNIT",
        "PIS/PASEP",
        "DADOS DE MEDIÇÃO",
        "LEITURA",
        "CONST. MEDIDOR",
        "GRANDEZAS",
        "POSTOS TARIFÁRIOS",
        "ELE-",
        "HFP",
        "SALDO",
        "RESERVADO",
    ]

    try:
        # Verifica se é path string ou objeto de arquivo (Streamlit)
        if isinstance(file_path, str):
            pdf_context = pdfplumber.open(file_path, password=password)
        else:
            pdf_context = pdfplumber.open(file_path, password=password)

        with pdf_context as pdf:
            page = pdf.pages[0]
            # layout=True é essencial para manter a estrutura visual
            text = page.extract_text(layout=True)

            # 1. Reference (Mês/Ano)
            ref_match = re.search(r"(?<!\d/)\b(\d{2}/\d{4})\b", text)
            if ref_match:
                data["reference"] = ref_match.group(1)

            # 2. Client ID
            code_match = re.search(
                r"utilizando\s+o\s+código\s+(\d+)", text, re.IGNORECASE
            )
            if code_match:
                data["client_id"] = code_match.group(1)
            else:
                visual_match = re.search(r"\b(\d{7,12})\s*\n\s*\d{2}/\d{4}", text)
                if visual_match:
                    data["client_id"] = visual_match.group(1)

            # 3. Measurement Data
            data["measurement"] = extract_measurement(text)

            # 4. Financial Items extraction
            lines = text.split("\n")
            is_capturing = False
            temp_items = []

            for line in lines:
                clean_txt = line.strip()
                upper_txt = clean_txt.upper()

                if not clean_txt:
                    continue

                # Detecta início da tabela financeira
                if (
                    "DESCRI" in upper_txt or "ITENS" in upper_txt
                ) and "FATURA" in upper_txt:
                    is_capturing = True
                    continue

                # Detecta fim da tabela
                if is_capturing and ("TOTAL" in upper_txt or "SUBTOTAL" in upper_txt):
                    is_capturing = False
                    break

                if is_capturing:
                    # Filtros de ruído
                    if any(term in upper_txt for term in IGNORED_TERMS):
                        continue
                    if re.match(r"^\d{5,}", clean_txt):
                        continue  # Números soltos grandes

                    info = clean_line(clean_txt)

                    if info and info["description"] and len(info["description"]) > 2:
                        desc_upper = info["description"].upper().strip()

                        # --- FILTRO DE LIXO PÓS-EXTRAÇÃO (AQUI É A CORREÇÃO) ---
                        # Ignora linhas que sejam apenas cabeçalhos fiscais
                        if desc_upper in [
                            "PIS",
                            "COFINS",
                            "ICMS",
                            "I CMS",
                            "TOTAL",
                            "SUBTOTAL",
                        ]:
                            continue

                        # Ignora linhas que sejam HISTÓRICO (Ex: ABR/24 ou ABR 24)
                        # Isso elimina o erro [ABR24] sem quebrar as outras linhas
                        if re.match(
                            r"^(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[\s\/\-]*\d{2,4}$",
                            desc_upper,
                        ):
                            continue
                        # -------------------------------------------------------

                        value_cols = process_values(info["values_str"], info["type"])
                        item = {
                            "Itens de Fatura": info["description"],
                            "Unid.": info["unit"],
                            **value_cols,
                        }
                        temp_items.append(item)

            data["items"] = temp_items
            return data

    except Exception as e:
        # Se for erro de senha, avisa diferente
        if "Password" in str(e):
            print(f"❌ Erro de Senha: {e}")
        else:
            print(f"❌ Erro Crítico: {e}")
        return None


# --- FUNÇÃO DE INTERFACE (Compatível com a Nova Arquitetura) ---


def extract_data_from_pdf(file_path, password=None):
    """
    Extrai dados do PDF e retorna dois DataFrames:
    - df_financeiro: Dados financeiros com coluna 'Referência'
    - df_medicao: Dados de medição com coluna 'Referência'

    Esta função é a interface principal usada pelo sistema de importação.
    """
    # 1. Extrai dados brutos usando a função original
    raw_data = extract_invoice_data(file_path, password)

    if not raw_data:
        return pd.DataFrame(), pd.DataFrame()

    reference = raw_data.get("reference", "Not Found")

    # 2. Converte items financeiros em DataFrame
    items = raw_data.get("items", [])
    if items:
        df_fin = pd.DataFrame(items)
        # Adiciona coluna Referência em todas as linhas
        df_fin["Referência"] = reference

        # Converte valores numéricos de string para float
        numeric_cols = [
            "Quant.",
            "Preço unit (R$) com tributos",
            "Valor (R$)",
            "PIS/COFINS",
            "Base Calc ICMS (R$)",
            "Alíquota ICMS",
            "ICMS",
            "Tarifa unit (R$)",
        ]

        for col in numeric_cols:
            if col in df_fin.columns:
                # Normaliza valores negativos e converte para string
                df_fin[col] = (
                    df_fin[col].astype(str).apply(normalize_negative_value).str.strip()
                )
                # Converte para float, ignorando valores vazios ou inválidos
                df_fin[col] = pd.to_numeric(df_fin[col], errors="coerce").fillna(0)
    else:
        df_fin = pd.DataFrame()

    # 3. Converte dados de medição em DataFrame
    measurements = raw_data.get("measurement", [])
    if measurements:
        df_med = pd.DataFrame(measurements)
        # Adiciona coluna Referência em todas as linhas
        df_med["Referência"] = reference

        # Converte valores numéricos de string para float
        numeric_cols_med = [
            "Leitura (Anterior)",
            "Leitura (Atual)",
            "Fator Multiplicador",
            "Consumo kWh",
            "N° Dias",
        ]

        for col in numeric_cols_med:
            if col in df_med.columns:
                # Normaliza valores negativos e converte para string
                df_med[col] = (
                    df_med[col].astype(str).apply(normalize_negative_value).str.strip()
                )
                # Converte para float, ignorando valores vazios ou inválidos
                df_med[col] = pd.to_numeric(df_med[col], errors="coerce").fillna(0)
    else:
        df_med = pd.DataFrame()

    return df_fin, df_med
