import os
import pdfplumber
from dotenv import load_dotenv

load_dotenv()

# Pega o primeiro PDF da pasta input
input_folder = "input"
arquivos = [f for f in os.listdir(input_folder) if f.endswith(".pdf")]

if not arquivos:
    print("❌ Nenhum PDF encontrado na pasta input.")
else:
    arquivo_teste = os.path.join(input_folder, arquivos[0])
    senha = os.getenv("PDF_PASSWORD")

    print(f"🔍 Analisando arquivo: {arquivo_teste}")
    print(f"🔑 Senha usada: {senha if senha else 'Nenhuma'}")
    print("-" * 40)

    try:
        with pdfplumber.open(arquivo_teste, password=senha) as pdf:
            if not pdf.pages:
                print("⚠️ O PDF está vazio (0 páginas).")
            else:
                pagina = pdf.pages[0]
                texto = pagina.extract_text()

                if not texto:
                    print(
                        "⚠️ AVISO: O PDF abriu, mas não tem texto (pode ser imagem/scan)."
                    )
                else:
                    print("✅ TEXTO EXTRAÍDO COM SUCESSO:")
                    print("-" * 40)
                    print(texto[:1000])  # Mostra os primeiros 1000 caracteres
                    print("-" * 40)

                    # Teste Rápido de Regex
                    if "CLIENTE" in texto.upper() or "INSTALAÇÃO" in texto.upper():
                        print("✅ Palavra 'CLIENTE/INSTALAÇÃO' encontrada.")
                    else:
                        print(
                            "❌ Palavra 'CLIENTE' NÃO encontrada (Verifique o layout)."
                        )

    except Exception as e:
        print(f"❌ ERRO AO ABRIR PDF: {e}")
