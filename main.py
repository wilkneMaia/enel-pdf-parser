import os
import pandas as pd
from dotenv import load_dotenv
import logging
from datetime import datetime
import time
import json  # <--- Importante para o novo log

# Tenta importar o extrator
try:
    from extractor import extract_invoice_data
except ImportError:
    from src.extractor import extract_invoice_data

# --- 1. CONFIGURAÇÃO DE LOGS (Visual/Humano) ---
if not os.path.exists("logs"):
    os.makedirs("logs")
# Log para leitura humana (txt)
log_file_txt = datetime.now().strftime("logs/execucao_%Y-%m-%d.log")
# Log para leitura de máquina (jsonl) - Futuro Dashboard
log_file_json = "logs/historico_geral.jsonl"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
    datefmt="%H:%M:%S",
    handlers=[
        logging.FileHandler(log_file_txt, encoding="utf-8"),
        logging.StreamHandler(),
    ],
)
# -------------------------------

load_dotenv()


def universal_converter(val):
    if pd.isna(val) or str(val).strip() == "":
        return 0.0
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip().upper().replace("R$", "").replace(" ", "").replace("-", "")
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        sign = -1.0 if "-" in str(val) else 1.0
        return float(s) * sign
    except ValueError:
        return 0.0


# --- NOVO: SALVA O LOG PARA O FUTURO DASHBOARD ---
def salvar_log_estruturado(dados_evento):
    """
    Grava uma linha JSON no arquivo historico_geral.jsonl.
    Isso permitirá criar filtros de data, cliente e valor no futuro.
    """
    try:
        with open(log_file_json, "a", encoding="utf-8") as f:
            # Adiciona timestamp automático
            dados_evento["timestamp"] = datetime.now().isoformat()
            # Grava como JSON numa única linha
            f.write(json.dumps(dados_evento, ensure_ascii=False) + "\n")
    except Exception as e:
        logging.error(f"Erro ao salvar log estruturado: {e}")


# --- RELATÓRIO VISUAL (MANTIDO) ---
def log_visual_report(filename, data):
    client = data.get("client_id", "N/A")
    ref = data.get("reference", "N/A")
    items = data.get("items", [])
    measurements = data.get("measurement", [])

    total_fin = sum(universal_converter(i.get("Valor (R$)")) for i in items)

    # Lógica de Consumo vs Injeção
    consumo_ativo = 0.0
    energia_injetada = 0.0
    for m in measurements:
        kwh = universal_converter(m.get("Consumo kWh"))
        segmento = str(m.get("P.Horário/Segmento", "")).upper()
        if "INJ" in segmento:
            energia_injetada += kwh
        else:
            consumo_ativo += kwh

    # Linha extra para injeção
    txt_injecao = ""
    if energia_injetada > 0:
        txt_injecao = f"\n   ☀️ Injetado:     {energia_injetada:,.0f} kWh"

    # 1. Mostra no Terminal (Bonito)
    msg = (
        f"\n{'=' * 50}"
        f"\n📄 ARQUIVO: {filename}"
        f"\n{'=' * 50}"
        f"\n   ✅ Status:       Sucesso"
        f"\n   🏠 Cliente:      {client}"
        f"\n   📅 Referência:   {ref}"
        f"\n   💰 Valor Total:  R$ {total_fin:,.2f}"
        f"\n   ⚡ Consumo Real: {consumo_ativo:,.0f} kWh{txt_injecao}"
        f"\n{'-' * 50}"
    )
    logging.info(msg)

    # 2. Salva no JSON Estruturado (Dados Puros para Dashboard)
    # Aqui montamos o dicionário que o seu futuro dashboard vai ler
    log_data = {
        "arquivo": filename,
        "status": "sucesso",
        "client_id": client,
        "referencia": ref,
        "valor_total": total_fin,
        "consumo_kwh": consumo_ativo,
        "injesao_kwh": energia_injetada,
        "qtd_itens": len(items),
    }
    salvar_log_estruturado(log_data)


def main():
    start_time = time.time()
    logging.info("\n🚀 INICIANDO PROCESSAMENTO...\n")

    input_folder = "input"
    output_folder = "output"
    pdf_password = os.getenv("PDF_PASSWORD")

    if not os.path.exists(output_folder):
        os.makedirs(output_folder)
    pdf_files = [f for f in os.listdir(input_folder) if f.lower().endswith(".pdf")]

    if not pdf_files:
        logging.warning("⚠️ Nenhum arquivo PDF encontrado.")
        return

    all_invoices = []
    all_measurements = []
    sucessos = 0
    erros = 0

    for filename in pdf_files:
        file_path = os.path.join(input_folder, filename)

        try:
            data = extract_invoice_data(file_path, pdf_password)

            if data and data.get("items"):
                # Log Visual + Log Estruturado
                log_visual_report(filename, data)

                # Consolidação
                client_id = data.get("client_id")
                reference = data.get("reference")

                for item in data.get("items", []):
                    item["Nº do Cliente"] = client_id
                    item["Referência"] = reference
                    all_invoices.append(item)

                for meas in data.get("measurement", []):
                    meas["Nº do Cliente"] = client_id
                    meas["Referência"] = reference
                    all_measurements.append(meas)

                sucessos += 1
            else:
                logging.warning(f"⚠️ {filename}: Vazio/Erro.")
                # Log de Erro Estruturado
                salvar_log_estruturado(
                    {
                        "arquivo": filename,
                        "status": "erro_vazio",
                        "detalhe": "Extrator retornou vazio",
                    }
                )
                erros += 1

        except Exception as e:
            logging.error(f"❌ {filename}: Erro Fatal - {str(e)}", exc_info=True)
            # Log de Erro Estruturado
            salvar_log_estruturado(
                {"arquivo": filename, "status": "erro_fatal", "detalhe": str(e)}
            )
            erros += 1

    # Salvamento Parquet (Mantido)
    if all_invoices:
        df_inv = pd.DataFrame(all_invoices)
        for col in [
            "Quant.",
            "Preço unit (R$) com tributos",
            "Valor (R$)",
            "PIS/COFINS",
            "Base Calc ICMS (R$)",
            "Alíquota ICMS",
            "ICMS",
            "Tarifa unit (R$)",
        ]:
            if col in df_inv.columns:
                df_inv[col] = df_inv[col].apply(universal_converter)
        df_inv.to_parquet(os.path.join(output_folder, "faturas.parquet"), index=False)

    if all_measurements:
        df_meas = pd.DataFrame(all_measurements)
        for col in [
            "Leitura (Anterior)",
            "Leitura (Atual)",
            "Fator Multiplicador",
            "Consumo kWh",
        ]:
            if col in df_meas.columns:
                df_meas[col] = df_meas[col].apply(universal_converter)
        df_meas.to_parquet(os.path.join(output_folder, "medicao.parquet"), index=False)

    elapsed_time = time.time() - start_time
    logging.info(
        f"🏁 FIM: {sucessos} Sucessos | {erros} Erros | Tempo: {elapsed_time:.2f}s"
    )


if __name__ == "__main__":
    main()
