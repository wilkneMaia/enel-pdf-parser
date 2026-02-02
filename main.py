import os
import pandas as pd
from dotenv import load_dotenv
from src.extractor import extract_invoice_data, validate_totals

# --- CONFIGURAÇÃO ---
load_dotenv()

INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
PDF_PASSWORD = os.getenv("PDF_PASSWORD")

# --- CONVERSOR UNIVERSAL (A Solução Definitiva) ---
def universal_converter(val):
    """
    Converte qualquer formato numérico (BR ou US) para float.
    - '220,79'  -> 220.79
    - '512.0'   -> 512.0
    - '49,90-'  -> -49.90
    - '1.200,00'-> 1200.00
    """
    if pd.isna(val) or str(val).strip() == "":
        return 0.0

    # 1. Normalização Básica
    s = str(val).strip().upper()

    # 2. Detecção de Sinal Negativo (Enel usa no final: "49,78-")
    sign = -1.0 if '-' in s else 1.0
    s = s.replace('-', '').replace('R$', '').strip()

    # 3. Decisão de Formato Inteligente
    if ',' in s:
        # Se tem vírgula, assumimos formato BR (Decimal = Vírgula)
        # Ex: "1.200,50" -> Tira ponto, troca vírgula por ponto
        s = s.replace('.', '').replace(',', '.')
    else:
        # Se NÃO tem vírgula, assumimos formato US ou Inteiro Simples
        # Ex: "512.0" -> Mantém o ponto
        # Ex: "1200"  -> Mantém
        pass

    try:
        return float(s) * sign
    except ValueError:
        # Se falhar, retorna 0.0 mas avisa no log se for algo estranho
        # print(f"⚠️ Falha ao converter: {val}")
        return 0.0

def process_invoices():
    if not PDF_PASSWORD:
        print("❌ Erro: 'PDF_PASSWORD' não encontrado no .env")
        return

    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Erro: Pasta '{INPUT_FOLDER}' não encontrada.")
        return

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith('.pdf')]

    if not files:
        print(f"⚠️  Nenhum PDF encontrado em '{INPUT_FOLDER}'.")
        return

    print(f"📂 Encontrados {len(files)} arquivos.\n")

    invoices_list = []
    measurements_list = []

    for file_name in files:
        print(f"--- 📄 Processando: {file_name} ---")

        file_path = os.path.join(INPUT_FOLDER, file_name)
        data = extract_invoice_data(file_path, password=PDF_PASSWORD)

        if data:
            ref = data['reference']
            client_id = data['client_id']

            print(f"   ✅ Referência: {ref}")
            print(f"   🏠 ID Cliente: {client_id}")

            # --- Faturas ---
            if data['items']:
                print(f"   ⚡ Itens Financeiros: {len(data['items'])}")

                # Validação no Terminal (Debug)
                total_debug = sum([universal_converter(i.get('Valor (R$)', '0')) for i in data['items']])
                print(f"   💰 Total Validado (Main): R$ {total_debug:.2f}")

                for item in data['items']:
                    item['Nº do Cliente'] = client_id
                    item['Arquivo'] = file_name
                    item['Referência'] = ref
                    invoices_list.append(item)

            # --- Medição ---
            if data['measurement']:
                print(f"   📏 Itens de Medição: {len(data['measurement'])}")
                for item_med in data['measurement']:
                    item_med['Nº do Cliente'] = client_id
                    item_med['Arquivo'] = file_name
                    item_med['Referência'] = ref
                    measurements_list.append(item_med)
            else:
                print("   ⚠️  Nenhuma medição encontrada.")

        print("")

    # --- SALVAR PARQUET (Limpo e Convertido) ---
    if invoices_list or measurements_list:
        print("💾 Salvando arquivos Parquet...")

        # 1. FATURAS
        if invoices_list:
            df_inv = pd.DataFrame(invoices_list)

            # Aplica o conversor universal em colunas numéricas
            cols_num = ['Quant.', 'Preço unit (R$) com tributos', 'Valor (R$)',
                        'PIS/COFINS', 'Base Calc ICMS (R$)', 'Alíquota ICMS',
                        'ICMS', 'Tarifa unit (R$)']

            for col in cols_num:
                if col in df_inv.columns:
                    df_inv[col] = df_inv[col].apply(universal_converter)

            output_inv = os.path.join(OUTPUT_FOLDER, "faturas.parquet")
            df_inv.to_parquet(output_inv, index=False)
            print(f"   ✅ Faturas salvas: {output_inv}")

        # 2. MEDIÇÃO
        if measurements_list:
            df_meas = pd.DataFrame(measurements_list)

            # Aplica o mesmo conversor (funciona para ponto também!)
            cols_tec = ['Leitura (Anterior)', 'Leitura (Atual)', 'Fator Multiplicador', 'Consumo kWh']
            for col in cols_tec:
                if col in df_meas.columns:
                    df_meas[col] = df_meas[col].apply(universal_converter)

            output_meas = os.path.join(OUTPUT_FOLDER, "medicao.parquet")
            df_meas.to_parquet(output_meas, index=False)
            print(f"   ✅ Medições salvas: {output_meas}")

        print("="*60)
    else:
        print("🏁 Nenhum dado extraído.")

if __name__ == "__main__":
    process_invoices()
