import os
import glob
import pandas as pd
from tqdm import tqdm  # Barra de progresso (opcional, se não tiver, remova)

# --- IMPORTS DA NOVA ARQUITETURA ---
try:
    from src.services.unlocker import unlock_pdf_file, check_is_encrypted
    from src.services.extractor import extract_data_from_pdf
    from src.database.manager import save_data
except ImportError as e:
    print(f"❌ Erro de Importação: {e}")
    print("Certifique-se de estar rodando na raiz do projeto.")
    exit()

# --- CONFIGURAÇÃO ---
INPUT_FOLDER = "data/raw"
EXTENSIONS = ["*.pdf", "*.PDF"]


def batch_process():
    """
    Processa todos os PDFs na pasta data/raw que ainda não foram importados.
    Útil para carga inicial ou reprocessamento em massa.
    """
    print("🚀 Iniciando Processamento em Lote (CLI)...")

    # 1. Lista Arquivos
    files = []
    for ext in EXTENSIONS:
        files.extend(glob.glob(os.path.join(INPUT_FOLDER, ext)))

    if not files:
        print(f"⚠️ Nenhum PDF encontrado em '{INPUT_FOLDER}'.")
        return

    print(f"📂 Encontrados {len(files)} arquivos.")

    sucesso = 0
    erros = 0

    # 2. Loop de Processamento
    # Se tiver tqdm instalado, usa barra de progresso. Se não, usa loop normal.
    try:
        iterator = tqdm(files, desc="Processando")
    except NameError:
        iterator = files

    for pdf_path in iterator:
        filename = os.path.basename(pdf_path)

        # Ignora arquivos temporários de desbloqueio
        if filename.startswith("unlocked_"):
            continue

        try:
            # A. Desbloqueio (Tenta sem senha primeiro)
            # Se falhar, não temos input de usuário aqui, então pulamos
            if check_is_encrypted(pdf_path):
                # Tenta desbloquear sem senha ou loga erro
                unlocked_path = unlock_pdf_file(pdf_path)
                if not unlocked_path:
                    print(
                        f"🔒 PULO: {filename} tem senha e não foi possível abrir automaticamente."
                    )
                    erros += 1
                    continue
            else:
                unlocked_path = pdf_path  # Já está aberto

            # B. Extração
            df_fin, df_med = extract_data_from_pdf(unlocked_path)

            if df_fin.empty:
                print(f"⚠️ VAZIO: {filename} não retornou dados financeiros.")
                erros += 1
                continue

            # C. Salvamento (Upsert)
            saved = save_data(df_fin, df_med)

            if saved:
                sucesso += 1
            else:
                print(f"❌ ERRO DB: Falha ao salvar {filename}.")
                erros += 1

            # Limpeza se foi criado arquivo temporário
            if unlocked_path != pdf_path and os.path.exists(unlocked_path):
                os.remove(unlocked_path)

        except Exception as e:
            print(f"❌ CRASH: Erro em {filename}: {e}")
            erros += 1

    print("-" * 30)
    print(f"🏁 Concluído!")
    print(f"✅ Sucessos: {sucesso}")
    print(f"❌ Falhas:   {erros}")
    print("💡 Abra o Dashboard ('streamlit run Home.py') para ver os dados.")


if __name__ == "__main__":
    batch_process()
