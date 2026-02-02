import pandas as pd
import os
import logging

OUTPUT_FOLDER = "output"
FILE_FATURAS = os.path.join(OUTPUT_FOLDER, "faturas.parquet")
FILE_MEDICAO = os.path.join(OUTPUT_FOLDER, "medicao.parquet")


def _upsert_dataframe(df_new, file_path, keys=["Nº do Cliente", "Referência"]):
    """
    Remove registros antigos com a mesma chave e insere os novos.
    """
    if not os.path.exists(file_path):
        # Se não existe arquivo, cria um novo
        df_new.to_parquet(file_path, index=False)
        return "criado"

    try:
        # 1. Carrega dados antigos
        df_old = pd.read_parquet(file_path)

        # 2. Identifica as chaves que estamos tentando inserir
        # (Ex: Cliente 123 + Ref 01/2025)
        novas_chaves = df_new[keys].drop_duplicates()

        # 3. Filtra o DataFrame antigo, REMOVENDO o que tiver a mesma chave
        # Isso garante que não duplicamos e permite "reprocessar" uma fatura corrigida
        df_merged = df_old.merge(novas_chaves, on=keys, how="left", indicator=True)
        df_kept = df_old[df_merged["_merge"] == "left_only"]

        # 4. Concatena (Antigos Mantidos + Novos)
        df_final = pd.concat([df_kept, df_new], ignore_index=True)

        # 5. Salva
        df_final.to_parquet(file_path, index=False)
        return "atualizado"

    except Exception as e:
        logging.error(f"Erro ao salvar parquet: {e}")
        raise e


def save_invoice_data(invoices_list, measurements_list):
    """Salva faturas e medições garantindo unicidade por Cliente/Ref"""
    if not os.path.exists(OUTPUT_FOLDER):
        os.makedirs(OUTPUT_FOLDER)

    status_inv = "ignorado"
    status_meas = "ignorado"

    if invoices_list:
        df_inv = pd.DataFrame(invoices_list)
        status_inv = _upsert_dataframe(df_inv, FILE_FATURAS)

    if measurements_list:
        df_meas = pd.DataFrame(measurements_list)
        status_meas = _upsert_dataframe(df_meas, FILE_MEDICAO)

    return status_inv, status_meas
