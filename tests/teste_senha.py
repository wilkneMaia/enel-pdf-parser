import os
import pdfplumber
from dotenv import load_dotenv

# 1. Tenta carregar o .env
load_dotenv()
senha = os.getenv("PDF_PASSWORD")

print(f"🔑 Senha carregada do .env: {senha}")

# 2. Tenta abrir o arquivo problemático
arquivo = "input/Enel-09-2025.pdf"  # Confirme se o arquivo está nesta pasta

if os.path.exists(arquivo):
    try:
        with pdfplumber.open(arquivo, password=senha) as pdf:
            print(f"✅ PDF aberto com sucesso! Páginas: {len(pdf.pages)}")

            # Tenta ler a primeira página
            texto = pdf.pages[0].extract_text()
            if texto:
                print("📄 Texto extraído (primeiros 50 carac.):")
                print(texto[:50])
            else:
                print("⚠️ O PDF abriu, mas NÃO retornou texto (pode ser imagem/scan).")
    except Exception as e:
        print(f"❌ Erro ao abrir PDF (Provável senha errada): {e}")
else:
    print(f"❌ Arquivo não encontrado: {arquivo}")
