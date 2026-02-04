"""
Módulo de Regras Fiscais e Tarifárias (Iluminação Pública).
Responsável por armazenar as tabelas de leis municipais e calcular os valores esperados.
"""

# --- CONFIGURAÇÕES GERAIS ---
# Tarifa Base de Iluminação Pública (B4a) usada para cálculos percentuais.
# Valor estimado via engenharia reversa da fatura de Jan/2025 (R$ 23,01 / 20,72%).
# Fonte: Lei Municipal 757/03 (Percentual sobre tarifa vigente).
CURRENT_BASE_RATE = 111.05

# --- TABELAS DE LEGISLAÇÃO ---
# Estrutura: (Min_kWh, Max_kWh, Alíquota_ou_Valor)
# Se valor < 1.0 (ex: 0.20), é tratado como Percentual (20%).
# Se valor > 1.0 (ex: 15.50), é tratado como Valor Fixo (R$ 15,50).

TAX_TABLES = {
    # Tabela fornecida pelo usuário (Lei 757/03)
    # ATENÇÃO: Valores decimais representam PORCENTAGEM (0.2072 = 20.72%)
    "LEI_757_2003": [
        (0, 50, 0.00),       # Isento
        (51, 100, 0.0059),   # 0.59%
        (101, 150, 0.0145),  # 1.45%
        (151, 200, 0.0356),  # 3.56%
        (201, 250, 0.0617),  # 6.17%
        (251, 300, 0.1009),  # 10.09%
        (301, 400, 0.1447),  # 14.47%
        (401, 500, 0.2072),  # 20.72% <--- Faixa comum residencial
        (501, 99999, 0.2777) # 27.77%
    ]
}

# Define qual tabela está ativa no sistema de auditoria
ACTIVE_TABLE_KEY = "LEI_757_2003"

def get_law_rate(consumption_kwh: float, table_key: str = None) -> float:
    """
    Retorna a ALÍQUOTA (ex: 0.2072) ou o VALOR BASE (ex: 15.50) da tabela.
    Não faz a conversão monetária final, apenas consulta a tabela.
    """
    if table_key is None:
        table_key = ACTIVE_TABLE_KEY

    selected_table = TAX_TABLES.get(table_key, [])

    for min_k, max_k, value in selected_table:
        if min_k <= consumption_kwh <= max_k:
            return value

    return 0.0

def get_cip_expected_value(consumption_kwh: float, table_key: str = None) -> float:
    """
    Calcula o valor final esperado em REAIS (R$).
    Se a tabela for percentual, multiplica pela Tarifa Base.
    Se for valor fixo, retorna o valor direto.
    """
    rate = get_law_rate(consumption_kwh, table_key)

    # LÓGICA HÍBRIDA:
    # Se < 1.0 (e > 0), assumimos que é uma alíquota percentual (Lei 757/03)
    if 0.0 < rate < 1.0:
        return rate * CURRENT_BASE_RATE
    else:
        # É valor fixo (Leis antigas) ou Isento (0.0)
        return rate

def get_available_tables():
    """Retorna lista de tabelas disponíveis para seleção na UI."""
    return list(TAX_TABLES.keys())
