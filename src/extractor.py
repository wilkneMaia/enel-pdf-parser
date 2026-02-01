import pdfplumber
import re

# --- HELPER FUNCTIONS ---


def clean_line(line):
    """
    Separates the raw string into: Description | Unit | Values String
    """
    # 1. Remove Historical Data (e.g., SET25 512.00...)
    history_pattern = (
        r"\s(JAN|FEV|MAR|ABR|MAI|JUN|JUL|AGO|SET|OUT|NOV|DEZ)[\s\/]?\d{2}.*$"
    )
    cleaned_line = re.sub(history_pattern, "", line, flags=re.IGNORECASE).strip()

    if not cleaned_line:
        return None

    # 2. Try to find known units (Pivot)
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

    # 3. Items without unit (Simple items)
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
    Maps the string of numbers to the correct columns.
    """
    clean_values = re.sub(
        r"\s(I\s?CMS|LID|DE|FATURAMENTO|TRIBUTOS|COFINS|PIS).*",
        "",
        values_str,
        flags=re.IGNORECASE,
    ).strip()
    tokens = clean_values.split()

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

        if len(tokens) >= 8:
            for i, field in enumerate(fields):
                columns[field] = tokens[i]
        elif len(tokens) >= 3:
            columns["Quant."] = tokens[0]
            columns["Preço unit (R$) com tributos"] = tokens[1]
            columns["Valor (R$)"] = tokens[2]
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
    """
    Extracts the 'EQUIPAMENTOS DE MEDIÇÃO' table.
    """
    measurement_items = []
    lines = full_text.split("\n")
    is_capturing = False

    regex_measure = re.compile(
        r"(\S+)\s+(.+?)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+(\d{2}/\d{2}/\d{4})\s+([\d.]+)\s+([\d.]+)\s+([\d.]+)\s+(\d+)"
    )

    for line in lines:
        line_upper = line.upper().strip()

        if "EQUIPAMENTOS DE MEDIÇÃO" in line_upper:
            is_capturing = True
            continue

        if is_capturing and (
            "MÊS/ANO" in line_upper
            or "HISTÓRICO" in line_upper
            or "PIS/PASEP" in line_upper
        ):
            break

        if is_capturing:
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


def validate_totals(data):
    total_calculated = 0.0
    for item in data["items"]:
        try:
            val_str = item.get("Valor (R$)", "0").replace(".", "").replace(",", ".")
            val_float = float(val_str.replace("R$", "").strip())
            if item.get("Valor (R$)", "").endswith("-"):
                val_float = val_float * -1
            total_calculated += val_float
        except ValueError:
            continue
    return round(total_calculated, 2)


# --- MAIN EXTRACTION FUNCTION ---


def extract_invoice_data(file_path, password=None):  # <--- ATUALIZADO AQUI
    data = {"reference": "Not Found", "items": [], "measurement": []}

    print(f"🔍 Analyzing: {file_path}")

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
    ]

    try:
        # pdfplumber aceita a senha nativamente, sem precisar salvar arquivo extra
        with pdfplumber.open(file_path, password=password) as pdf:
            page = pdf.pages[0]
            text = page.extract_text(layout=True)

            # 1. Reference
            ref_match = re.search(r"(?<!\d/)\b(\d{2}/\d{4})\b", text)
            if ref_match:
                data["reference"] = ref_match.group(1)

            # 2. Measurement Data
            data["measurement"] = extract_measurement(text)

            # 3. Financial Items
            lines = text.split("\n")
            is_capturing = False
            temp_items = []

            for line in lines:
                clean_txt = line.strip()
                upper_txt = clean_txt.upper()

                if any(term in upper_txt for term in IGNORED_TERMS):
                    continue
                if re.match(r"^\d{5,}", clean_txt):
                    continue

                if (
                    "DESCRI" in upper_txt or "ITENS" in upper_txt
                ) and "FATURA" in upper_txt:
                    is_capturing = True
                    continue

                if is_capturing and ("TOTAL" in upper_txt or "SUBTOTAL" in upper_txt):
                    is_capturing = False
                    break

                if is_capturing:
                    info = clean_line(clean_txt)
                    if info and info["description"] and len(info["description"]) > 2:
                        desc_upper = info["description"].upper().strip()
                        if desc_upper in [
                            "PIS",
                            "COFINS",
                            "ICMS",
                            "I CMS",
                            "TOTAL",
                            "SUBTOTAL",
                        ]:
                            continue

                        value_cols = process_values(info["values_str"], info["type"])
                        item = {
                            "Itens de Fatura": info["description"],
                            "Unid.": info["unit"],
                            **value_cols,
                        }
                        temp_items.append(item)

            # 4. Fallback Strategy
            if not temp_items:
                keywords = [
                    "ENERGIA",
                    "ILUM",
                    "BANDEIRA",
                    "JUROS",
                    "MULTA",
                    "TUSD",
                    "TE",
                ]
                for line in lines:
                    clean_txt = line.strip()
                    upper_txt = clean_txt.upper()

                    if any(term in upper_txt for term in IGNORED_TERMS):
                        continue
                    if re.match(r"^\d{5,}", clean_txt):
                        continue
                    if "TOTAL" in upper_txt or "VENCIMENTO" in upper_txt:
                        continue

                    if any(kw in upper_txt for kw in keywords) and re.search(
                        r"\d+[.,]\d{2}", line
                    ):
                        info = clean_line(clean_txt)
                        if (
                            info
                            and info["description"]
                            and len(info["description"]) > 2
                        ):
                            desc_upper = info["description"].upper().strip()
                            if desc_upper in ["PIS", "COFINS", "ICMS", "I CMS"]:
                                continue

                            value_cols = process_values(
                                info["values_str"], info["type"]
                            )
                            item = {
                                "Itens de Fatura": info["description"],
                                "Unid.": info["unit"],
                                **value_cols,
                            }
                            temp_items.append(item)

            data["items"] = temp_items
            return data

    except Exception as e:
        print(f"❌ Critical Error: {e}")
        return None
