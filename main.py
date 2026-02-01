import os
import pandas as pd
from dotenv import load_dotenv
from src.extractor import extract_invoice_data, validate_totals

# --- CONFIGURATION ---
load_dotenv()

INPUT_FOLDER = "input"
OUTPUT_FOLDER = "output"
PDF_PASSWORD = os.getenv("PDF_PASSWORD")


def process_invoices():
    if not PDF_PASSWORD:
        print("❌ Error: 'PDF_PASSWORD' not found in .env file.")
        return

    if not os.path.exists(INPUT_FOLDER):
        print(f"❌ Error: Folder '{INPUT_FOLDER}' not found.")
        return

    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    files = [f for f in os.listdir(INPUT_FOLDER) if f.lower().endswith(".pdf")]

    if not files:
        print(f"⚠️  No PDF files found in '{INPUT_FOLDER}'.")
        return

    print(f"📂 Found {len(files)} files ready to process.\n")

    invoices_list = []
    measurements_list = []

    for file_name in files:
        print(f"--- 📄 Processing: {file_name} ---")

        file_path = os.path.join(INPUT_FOLDER, file_name)
        data = extract_invoice_data(file_path, password=PDF_PASSWORD)

        if data:
            ref = data["reference"]
            client_id = data["client_id"]  # Pegamos o número do cliente

            print(f"   ✅ Reference: {ref}")
            print(f"   🏠 Client ID: {client_id}")  # Mostra no terminal

            # --- Process Financial Items ---
            if data["items"]:
                print(f"   ⚡ Financial Items: {len(data['items'])}")
                total_sum = validate_totals(data)
                print(f"   💰 Calculated Total: R$ {total_sum}")

                for item in data["items"]:
                    item["Nº do Cliente"] = client_id  # Adiciona a nova coluna
                    item["Arquivo"] = file_name
                    item["Referência"] = ref
                    invoices_list.append(item)

            # --- Process Measurement ---
            if data["measurement"]:
                print(f"   📏 Measurement Items: {len(data['measurement'])}")
                for item_med in data["measurement"]:
                    item_med["Nº do Cliente"] = client_id  # Adiciona a nova coluna
                    item_med["Arquivo"] = file_name
                    item_med["Referência"] = ref
                    measurements_list.append(item_med)
            else:
                print("   ⚠️  No measurement data found.")

        print("")

    # --- SAVE REPORTS ---
    if invoices_list or measurements_list:
        excel_path = os.path.join(OUTPUT_FOLDER, "enel_full_report.xlsx")

        try:
            with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
                # Aba 1: Fatura
                if invoices_list:
                    df_invoice = pd.DataFrame(invoices_list)
                    # Colocamos "Nº do Cliente" como a PRIMEIRA coluna
                    cols_inv = [
                        "Nº do Cliente",
                        "Arquivo",
                        "Referência",
                        "Itens de Fatura",
                        "Unid.",
                        "Quant.",
                        "Preço unit (R$) com tributos",
                        "Valor (R$)",
                        "PIS/COFINS",
                        "Base Calc ICMS (R$)",
                        "Alíquota ICMS",
                        "ICMS",
                        "Tarifa unit (R$)",
                    ]

                    existing_cols = [c for c in cols_inv if c in df_invoice.columns]
                    df_invoice = df_invoice[existing_cols]
                    df_invoice.to_excel(
                        writer, sheet_name="Invoice Details", index=False
                    )

                # Aba 2: Medição
                if measurements_list:
                    df_measure = pd.DataFrame(measurements_list)
                    # Colocamos "Nº do Cliente" como a PRIMEIRA coluna
                    cols_med = [
                        "Nº do Cliente",
                        "Arquivo",
                        "Referência",
                        "N° Medidor",
                        "P.Horário/Segmento",
                        "Data Leitura (Anterior)",
                        "Leitura (Anterior)",
                        "Data Leitura (Atual)",
                        "Leitura (Atual)",
                        "Fator Multiplicador",
                        "Consumo kWh",
                        "N° Dias",
                    ]

                    existing_cols = [c for c in cols_med if c in df_measure.columns]
                    df_measure = df_measure[existing_cols]
                    df_measure.to_excel(writer, sheet_name="Measurement", index=False)

            print("=" * 60)
            print(f"📊 Success! Report saved at: {excel_path}")
            print("=" * 60)

        except Exception as e:
            print(f"❌ Error saving Excel: {e}")

    else:
        print("🏁 Process finished, but no data was extracted.")


if __name__ == "__main__":
    process_invoices()
