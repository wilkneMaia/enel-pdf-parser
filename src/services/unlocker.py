import pikepdf
import os
import streamlit as st


def unlock_pdf_file(uploaded_file, password=None):
    """
    Recebe um arquivo (UploadedFile ou caminho) e retorna o caminho
    de uma versão desbloqueada temporária.

    Args:
        uploaded_file: Objeto do Streamlit ou caminho str.
        password (str, opcional): Senha para tentar desbloquear.
    """

    # Define onde salvar o arquivo temporário
    output_dir = "data/raw"
    os.makedirs(output_dir, exist_ok=True)

    # Nome seguro para o arquivo
    if hasattr(uploaded_file, "name"):
        filename = uploaded_file.name
    else:
        filename = os.path.basename(uploaded_file)

    output_path = os.path.join(output_dir, f"unlocked_{filename}")

    try:
        # Tenta abrir o PDF
        # O pikepdf é inteligente: aceita bytes (Streamlit) ou caminho de arquivo
        pdf = pikepdf.open(uploaded_file, password=password)

        # Salva a versão desbloqueada (sobrescreve se existir)
        pdf.save(output_path)

        # É importante fechar o arquivo original se foi aberto pelo pikepdf
        pdf.close()

        return output_path

    except pikepdf.PasswordError:
        # Se a senha estiver errada ou não for fornecida para um arquivo protegido
        return None

    except Exception as e:
        print(f"❌ Erro ao desbloquear PDF: {e}")
        return None


def check_is_encrypted(uploaded_file):
    """Verifica se o arquivo precisa de senha sem tentar desbloquear totalmente."""
    try:
        pdf = pikepdf.open(uploaded_file)
        pdf.close()
        return False  # Não tem senha
    except pikepdf.PasswordError:
        return True  # Tem senha
    except:
        return False  # Erro de leitura, assume sem senha por enquanto
