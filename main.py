import os
import pandas as pd
from src.desbloqueador import desbloquear_pdf
from src.extrator import extrair_dados_fatura

# --- Configurações ---
PASTA_INPUT = "input"
PASTA_OUTPUT = "output"
SENHA_PADRAO = "97413"

def processar_faturas():
    if not os.path.exists(PASTA_INPUT):
        print(f"❌ Erro: Pasta '{PASTA_INPUT}' não encontrada.")
        return

    arquivos = [f for f in os.listdir(PASTA_INPUT) if f.lower().endswith('.pdf')]

    if not arquivos:
        print(f"⚠️  Nenhum arquivo PDF encontrado em '{PASTA_INPUT}'.")
        return

    print(f"📂 Encontrados {len(arquivos)} arquivos.\n")

    relatorio_geral = []

    for arquivo in arquivos:
        print(f"--- 📄 Processando: {arquivo} ---")

        caminho_desbloqueado = desbloquear_pdf(arquivo, SENHA_PADRAO, PASTA_INPUT, PASTA_OUTPUT)

        if caminho_desbloqueado:
            dados = extrair_dados_fatura(caminho_desbloqueado)

            if dados and dados['itens']:
                print(f"   ✅ Referência: {dados['referencia']}")
                print(f"   ⚡ Itens capturados: {len(dados['itens'])}")

                for item in dados['itens']:
                    # Adiciona metadados do arquivo
                    item['Arquivo'] = arquivo
                    item['Referência'] = dados['referencia']
                    relatorio_geral.append(item)
            else:
                print("   ⚠️  Nenhum item encontrado.")
        print("")

    # --- SALVAMENTO ---
    if relatorio_geral:
        df = pd.DataFrame(relatorio_geral)

        # Define a ordem exata das colunas que você pediu
        colunas_ordenadas = [
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
            "Tarifa unit (R$)"
        ]

        # Reorganiza o DataFrame (garante que só essas colunas apareçam)
        # O try/except evita erro se alguma coluna faltar por acaso
        try:
            df = df[colunas_ordenadas]
        except KeyError as e:
            print(f"⚠️ Aviso: Alguma coluna esperada não foi gerada: {e}")

        # Visualização Terminal
        print("\n" + "="*100)
        print("RESUMO DETALHADO")
        print("="*100)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.max_colwidth', 20)
        print(df[["Itens de Fatura", "Quant.", "Valor (R$)", "ICMS"]].to_string(index=False)) # Mostra as principais
        print("="*100 + "\n")

        # Excel
        arquivo_excel = os.path.join(PASTA_OUTPUT, "relatorio_enel_detalhado.xlsx")
        df.to_excel(arquivo_excel, index=False)
        print(f"📊 Excel completo salvo em: {arquivo_excel}")

        # CSV
        arquivo_csv = os.path.join(PASTA_OUTPUT, "dados_fatura_detalhado.csv")
        df.to_csv(arquivo_csv, index=False, sep=';', encoding='utf-8-sig')
        print(f"💾 CSV salvo em:           {arquivo_csv}")

    else:
        print("🏁 Nenhum dado extraído.")

if __name__ == "__main__":
    processar_faturas()
