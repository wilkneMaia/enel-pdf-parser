# tax_rules.py

# --- CONFIGURAÇÕES GERAIS ---
# Tarifa Base Estimada (Engenharia Reversa: R$ 23,01 / 0.2072 ≈ R$ 111.05)
# Ajuste este valor se descobrir o valor exato da tarifa B4a da Enel CE.
CURRENT_BASE_RATE = 111.05

# --- TABELAS DE LEGISLAÇÃO ---
TAX_TABLES = {
    # Tabela fornecida pelo usuário (Lei 757/03)
    "LEI_757_2003": [
        (0, 50, 0.00),
        (51, 100, 0.0059),   # 0.59%
        (101, 150, 0.0145),  # 1.45%
        (151, 200, 0.0356),  # 3.56%
        (201, 250, 0.0617),  # 6.17%
        (251, 300, 0.1009),  # 10.09%
        (301, 400, 0.1447),  # 14.47%
        (401, 500, 0.2072),  # 20.72% <--- Sua faixa atual
        (501, 99999, 0.2777) # 27.77%
    ]
}

# Define qual tabela está ativa
ACTIVE_TABLE_KEY = "LEI_757_2003"

def get_law_rate(consumption_kwh, table_key=None):
    """
    Retorna apenas a ALÍQUOTA (ex: 0.2072) da tabela, sem calcular o valor em reais.
    """
    if table_key is None:
        table_key = ACTIVE_TABLE_KEY

    selected_table = TAX_TABLES.get(table_key, [])

    for min_k, max_k, value in selected_table:
        if min_k <= consumption_kwh <= max_k:
            return value
    return 0.0

def get_cip_expected_value(consumption_kwh, table_key=None):
    """
    Calcula o valor esperado em REAIS (Alíquota * Tarifa Base).
    """
    rate = get_law_rate(consumption_kwh, table_key)

    # Se a taxa for percentual (< 1.0), multiplica pela base
    if rate < 1.0:
        return rate * CURRENT_BASE_RATE
    else:
        return rate # Se for valor fixo (leis antigas)

def get_available_tables():
    return list(TAX_TABLES.keys())
