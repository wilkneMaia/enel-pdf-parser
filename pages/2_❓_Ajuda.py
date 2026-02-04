import streamlit as st

st.set_page_config(page_title="Ajuda e Suporte", page_icon="❓", layout="wide")

st.title("❓ Central de Ajuda")
st.markdown(
    """
    Bem-vindo ao **Enel PDF Parser**! Esta ferramenta foi desenvolvida para transformar suas faturas de energia
    em dados claros e acionáveis. Abaixo você encontra um guia rápido de como utilizar o sistema.
    """
)

st.divider()

st.header("🚀 Como Começar")

col_step1, col_step2, col_step3 = st.columns(3)

with col_step1:
    st.subheader("1. Baixe sua Fatura")
    st.markdown(
        "Acesse o site ou aplicativo da Enel e baixe a **fatura digital em PDF**."
    )
    st.info("💡 **Dica:** O sistema funciona melhor com o PDF original, não com fotos ou escaneamentos.")

with col_step2:
    st.subheader("2. Importe no Sistema")
    st.markdown(
        "Vá até a página **Importar Fatura** no menu lateral e arraste o arquivo para a área de upload."
    )

with col_step3:
    st.subheader("3. Desbloqueie (Se precisar)")
    st.markdown(
        "Se o PDF pedir senha, geralmente são os **5 primeiros dígitos do CPF** do titular da conta."
    )

st.divider()

st.header("📊 Entendendo os Dashboards")

with st.expander("⚖️ Taxômetro (Impostos vs. Energia)", expanded=True):
    st.markdown(
        """
        Este painel ajuda você a visualizar a **"mordida fiscal"** na sua conta.
        * **Energia Real:** O valor que efetivamente paga pelo produto energia.
        * **Impostos e Taxas:** Soma de ICMS, PIS/COFINS, Iluminação Pública e Bandeiras Tarifárias.
        * **Gráfico de Mosaico:** Quanto maior o quadrado, maior o impacto daquele item no valor final.
        """
    )

with st.expander("📉 Fluxo Financeiro"):
    st.markdown(
        """
        Aqui você acompanha a evolução dos pagamentos ao longo do tempo.
        * **Despesas (Vermelho):** Tudo que você pagou.
        * **Economia (Verde):** Créditos recebidos (ex: Energia Solar injetada, devoluções ou descontos).
        * **Ranking:** Lista ordenada do que mais pesou no seu bolso no mês selecionado.
        """
    )

with st.expander("🔌 Balanço Energético (kWh)"):
    st.markdown(
        """
        Focado no consumo físico e eficiência.
        * **Consumo da Rede:** O quanto você puxou da Enel.
        * **Geração Injetada:** Se você tem painéis solares, mostra quanto enviou para a rede.
        * **Eficiência (R$/kWh):** Monitora se o "preço unitário" da energia está subindo, independente do quanto você usa.
        """
    )

st.divider()

st.header("❓ Perguntas Frequentes (FAQ)")

faq_1, faq_2 = st.columns(2)

with faq_1:
    st.markdown("#### 🔒 Meus dados estão seguros?")
    st.markdown(
        "**Sim.** Todo o processamento é feito localmente na sua máquina (ou no servidor onde você hospedou). "
        "Nenhum dado é enviado para terceiros. O banco de dados fica salvo na pasta `data/database`."
    )

    st.markdown("#### 📄 O sistema não lê meu PDF!")
    st.markdown(
        "Verifique se:"
        "\n1. O arquivo é um PDF digital original (não escaneado)."
        "\n2. A senha (se houver) está correta."
        "\n3. O layout da fatura é da Enel (modelos muito antigos podem não ser reconhecidos)."
    )

with faq_2:
    st.markdown("#### ☀️ Tenho energia solar, funciona?")
    st.markdown(
        "**Sim!** O sistema detecta automaticamente linhas de 'Energia Injetada' e calcula seu saldo energético "
        "e a economia estimada baseada na tarifa cheia."
    )

    st.markdown("#### 🗑️ Como apagar dados errados?")
    st.markdown(
        "Na página **Importar Fatura**, role até o final para encontrar a **'Zona de Perigo'**. "
        "Lá você pode limpar todo o banco de dados e recomeçar."
    )
