import pandas as pd
import os
import streamlit as st

# --- CONFIGURAÇÃO DE CAMINHOS (Clean Architecture) ---
DB_FOLDER = "data/database"
FILE_FATURAS = os.path.join(DB_FOLDER, "faturas.parquet")
FILE_MEDICAO = os.path.join(DB_FOLDER, "medicao.parquet")

def init_db():
    """Garante que a pasta e os arquivos existam."""
    os.makedirs(DB_FOLDER, exist_ok=True)

    if not os.path.exists(FILE_FATURAS):
        pd.DataFrame().to_parquet(FILE_FATURAS)

    if not os.path.exists(FILE_MEDICAO):
        pd.DataFrame().to_parquet(FILE_MEDICAO)

def _upsert_dataframe(df_new, file_path, keys=["Referência"]):
    """
    Insere novos dados, substituindo os antigos se a chave (Referência) coincidir.
    Isso permite reprocessar uma fatura para corrigir dados sem duplicar.
    """
    if df_new.empty:
        return False

    if not os.path.exists(file_path):
        df_new.to_parquet(file_path, index=False)
        return True

    try:
        # 1. Carrega dados existentes
        df_old = pd.read_parquet(file_path)

        # Se o banco estiver vazio, apenas salva o novo
        if df_old.empty:
            df_new.to_parquet(file_path, index=False)
            return True

        # 2. Garante que as colunas chave existem em ambos
        # (Se for a primeira execução, pode não ter a coluna, então salvamos direto)
        missing_keys = [k for k in keys if k not in df_old.columns]
        if missing_keys:
            # Estrutura incompatível (banco antigo ou vazio), sobrescreve ou append simples
            df_final = pd.concat([df_old, df_new], ignore_index=True)
            df_final.to_parquet(file_path, index=False)
            return True

        # 3. Identifica quais referências estamos atualizando
        # (Ex: Estamos importando JAN/2025 de novo)
        refs_to_update = df_new[keys].drop_duplicates()

        # 4. Remove do banco antigo tudo que coincidir com as novas referências
        # Merge com indicator=True ajuda a achar a interseção
        df_merged = df_old.merge(refs_to_update, on=keys, how="left", indicator=True)
        df_kept = df_old[df_merged["_merge"] == "left_only"] # Mantém só o que NÃO está no novo lote

        # 5. Concatena (Antigos Mantidos + Novos)
        df_final = pd.concat([df_kept, df_new], ignore_index=True)

        # 6. Salva
        df_final.to_parquet(file_path, index=False)
        return True

    except Exception as e:
        print(f"❌ Erro ao salvar parquet: {e}")
        return False

def save_data(df_financeiro, df_medicao):
    """
    Salva os DataFrames de Financeiro e Medição no banco de dados.
    Chama o upsert para evitar duplicatas.
    """
    init_db()

    success_fin = True
    success_med = True

    # Salva Financeiro (Chave: Referência + Itens de Fatura para garantir unicidade fina)
    # Mas para substituir o mês inteiro, melhor usar apenas 'Referência' como chave de deleção do antigo
    if not df_financeiro.empty:
        success_fin = _upsert_dataframe(df_financeiro, FILE_FATURAS, keys=["Referência"])

    # Salva Medição
    if not df_medicao.empty:
        success_med = _upsert_dataframe(df_medicao, FILE_MEDICAO, keys=["Referência"])

    return success_fin and success_med

def load_data():
    """Carrega os dados dos arquivos Parquet para memória."""
    init_db()
    try:
        df_fat = pd.read_parquet(FILE_FATURAS)
        df_med = pd.read_parquet(FILE_MEDICAO)
        return df_fat, df_med
    except Exception as e:
        st.error(f"Erro ao ler banco de dados: {e}")
        return pd.DataFrame(), pd.DataFrame()
