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

    lista_faturas = []
    lista_medicao = []

    for arquivo in arquivos:
        print(f"--- 📄 Processando: {arquivo} ---")

        caminho_desbloqueado = desbloquear_pdf(arquivo, SENHA_PADRAO, PASTA_INPUT, PASTA_OUTPUT)

        if caminho_desbloqueado:
            dados = extrair_dados_fatura(caminho_desbloqueado)

            if dados:
                ref = dados['referencia']
                print(f"   ✅ Referência: {ref}")

                # 1. Processa Itens da Fatura
                if dados['itens']:
                    print(f"   ⚡ Itens Financeiros: {len(dados['itens'])}")
                    for item in dados['itens']:
                        item['Arquivo'] = arquivo
                        item['Referência'] = ref
                        lista_faturas.append(item)

                # 2. Processa Medição
                if dados['medicao']:
                    print(f"   📏 Itens de Medição:  {len(dados['medicao'])}")
                    for item_med in dados['medicao']:
                        item_med['Arquivo'] = arquivo
                        item_med['Referência'] = ref
                        lista_medicao.append(item_med)
                else:
                    print("   ⚠️  Nenhuma medição encontrada.")

        print("")

    # --- SALVAMENTO (Excel com Múltiplas Abas) ---
    if lista_faturas or lista_medicao:
        arquivo_excel = os.path.join(PASTA_OUTPUT, "relatorio_completo_enel.xlsx")

        with pd.ExcelWriter(arquivo_excel, engine='openpyxl') as writer:

            # Aba 1: Fatura Detalhada
            if lista_faturas:
                df_fatura = pd.DataFrame(lista_faturas)
                # Ordenação das colunas
                cols_fat = ["Arquivo", "Referência", "Itens de Fatura", "Unid.", "Quant.",
                           "Preço unit (R$) com tributos", "Valor (R$)", "PIS/COFINS",
                           "Base Calc ICMS (R$)", "Alíquota ICMS", "ICMS", "Tarifa unit (R$)"]
                try:
                    df_fatura = df_fatura[cols_fat]
                except KeyError: pass
                df_fatura.to_excel(writer, sheet_name="Fatura Detalhada", index=False)

            # Aba 2: Medição
            if lista_medicao:
                df_medicao = pd.DataFrame(lista_medicao)
                # Ordenação das colunas
                cols_med = ["Arquivo", "Referência", "N° Medidor", "P.Horário/Segmento",
                           "Data Leitura (Anterior)", "Leitura (Anterior)",
                           "Data Leitura (Atual)", "Leitura (Atual)",
                           "Fator Multiplicador", "Consumo kWh", "N° Dias"]
                try:
                    df_medicao = df_medicao[cols_med]
                except KeyError: pass
                df_medicao.to_excel(writer, sheet_name="Medicao", index=False)

        print("="*60)
        print(f"📊 Relatório Completo salvo em: {arquivo_excel}")
        print("   (Verifique as abas 'Fatura Detalhada' e 'Medicao')")
        print("="*60)

    else:
        print("🏁 Nenhum dado extraído.")

if __name__ == "__main__":
    processar_faturas()
