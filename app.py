import streamlit as st
import networkx as nx

# Importation de ton cœur métier factorisé
from src.anselmetti_trf_cote import engine

st.set_page_config(page_title="Anselmetti Studio", layout="wide")
st.title("⚙️ Anselmetti Studio (Streamlit)")

# ==========================================
# 1. Initialisation des données
# ==========================================
if "data_loaded" not in st.session_state:
    df_res, df_gamme, df_client = engine.get_initial_data()
    st.session_state.df_res = df_res
    st.session_state.df_gamme = df_gamme
    st.session_state.df_client = df_client
    st.session_state.data_loaded = True

# ==========================================
# 2. Interface de Paramétrage (Édition)
# ==========================================
st.header("1. Paramètres")
tab_res, tab_gamme, tab_client = st.tabs(["🏭 Ressources", "📋 Gamme", "🎯 Client"])

with tab_res:
    st.session_state.df_res = st.data_editor(
        st.session_state.df_res, num_rows="dynamic", use_container_width=True
    )
with tab_gamme:
    st.session_state.df_gamme = st.data_editor(
        st.session_state.df_gamme, num_rows="dynamic", use_container_width=True
    )
with tab_client:
    st.session_state.df_client = st.data_editor(
        st.session_state.df_client, num_rows="dynamic", use_container_width=True
    )

# ==========================================
# 3. Moteur Métier (Calculs & Graphe)
# ==========================================
df_cf = engine.compute_cotes(st.session_state.df_gamme, st.session_state.df_res)
G = engine.build_graph(df_cf)

st.divider()

# ==========================================
# 4. Analyse et Visualisation
# ==========================================
st.header("2. Analyse & Validation")

col_analysis, col_viz = st.columns([1, 1.2])
failing_paths = []

with col_analysis:
    st.subheader("🔍 Contrôle des Cotes")

    for _, cc_row in st.session_state.df_client.iterrows():
        try:
            path = nx.shortest_path(G, source=cc_row["surf_A"], target=cc_row["surf_B"])
            sum_it = sum(
                G.get_edge_data(path[i], path[i + 1])["it"]
                for i in range(len(path) - 1)
            )
            it_max = float(cc_row["it_max"])
            delta = round(it_max - sum_it, 4)

            chemin_str = " ➔ ".join(path)

            # Utilisation de st.success / st.error comme équivalent de mo.callout
            if sum_it <= it_max:
                st.success(
                    f"**✅ {cc_row['id_cc']} : VALIDE**\n\n"
                    f"**Chemin** : `{chemin_str}`\n\n"
                    f"**IT Cumulé : {round(sum_it, 3)} mm** (Max toléré : {it_max} mm) | Marge : {delta} mm"
                )
            else:
                failing_paths.append(path)
                st.error(
                    f"**❌ {cc_row['id_cc']} : INVALIDE**\n\n"
                    f"**Chemin** : `{chemin_str}`\n\n"
                    f"**IT Cumulé : {round(sum_it, 3)} mm** (Max toléré : {it_max} mm) | Dépassement : {abs(delta)} mm"
                )

        except nx.NetworkXNoPath:
            st.warning(
                f"**⚠️ {cc_row['id_cc']} : Chemin introuvable**\n\n"
                f"Aucun lien continu entre `{cc_row['surf_A']}` et `{cc_row['surf_B']}`."
            )
        except nx.NodeNotFound as e:
            st.warning(f"**⚠️ {cc_row['id_cc']} : Erreur**\n\nSurface manquante : {e}")

with col_viz:
    st.subheader("📊 Visualisation Mermaid")
    tab_flow, tab_seq = st.tabs(["🕸️ Anselmetti", "⏱️ Séquence"])

    with tab_flow:
        st.markdown(
            f"```mermaid\n{engine.get_mermaid_flowchart(G, failing_paths)}\n```"
        )
    with tab_seq:
        st.markdown(
            f"```mermaid\n{engine.get_mermaid_sequence(df_cf, failing_paths)}\n```"
        )
