import pikepdf
import os

def desbloquear_pdf(nome_arquivo, senha, pasta_input="input", pasta_output="output"):
    """
    Remove a senha de um PDF e salva na pasta de output.
    Retorna o caminho do arquivo desbloqueado ou None em caso de erro.
    """

    # Monta os caminhos completos
    caminho_entrada = os.path.join(pasta_input, nome_arquivo)
    caminho_saida = os.path.join(pasta_output, f"unlocked_{nome_arquivo}")

    # Garante que a pasta de saída existe
    if not os.path.exists(pasta_output):
        os.makedirs(pasta_output)

    print(f"🔓 Tentando desbloquear: {caminho_entrada}...")

    try:
        # Abre o PDF com a senha e salva uma cópia sem criptografia
        with pikepdf.open(caminho_entrada, password=senha) as pdf:
            pdf.save(caminho_saida)

        print(f"✅ Sucesso! Arquivo salvo em: {caminho_saida}")
        return caminho_saida

    except pikepdf.PasswordError:
        print("❌ Erro: A senha informada está incorreta.")
        return None
    except FileNotFoundError:
        print(f"❌ Erro: O arquivo '{nome_arquivo}' não foi encontrado na pasta '{pasta_input}'.")
        return None
    except Exception as e:
        print(f"❌ Erro inesperado: {e}")
        return None

# --- Bloco de Teste (Só roda se você executar este arquivo diretamente) ---
if __name__ == "__main__":
    # Para testar, coloque um arquivo real na pasta input e ajuste o nome abaixo
    arquivo_teste = "minha_fatura.pdf"
    senha_teste = "000000"

    desbloquear_pdf(arquivo_teste, senha_teste)
