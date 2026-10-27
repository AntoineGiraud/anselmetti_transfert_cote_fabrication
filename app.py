import streamlit as st
import networkx as nx
from src.anselmetti_trf_cote import engine

st.set_page_config(page_title="Anselmetti Studio", layout="wide")
st.title("⚙️ Anselmetti Studio (Streamlit)")

st.info("""
**📖 Lexique métier :**
* **IT (Intervalle de Tolérance)** : Marge d'erreur géométrique acceptable.
* **CF (Cote de Fabrication)** : Dimension réalisée physiquement par la machine.
* **CC (Cote Condition)** : Exigence finale du plan client à vérifier.
""")

# ==========================================
# 1. Chargement & Édition des données (Pleine largeur)
# ==========================================
if "data_loaded" not in st.session_state:
    df_res, df_gamme, df_client = engine.get_initial_data()
    st.session_state.df_res, st.session_state.df_gamme, st.session_state.df_client = (
        df_res,
        df_gamme,
        df_client,
    )
    st.session_state.data_loaded = True

st.header("1. Paramétrage")
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
# 2. Moteur Métier (Calcul invisible)
# ==========================================
df_cf = engine.compute_cotes(st.session_state.df_gamme, st.session_state.df_res)
G = engine.build_graph(df_cf)

# Listes pour stocker les résultats et piloter l'affichage
failing_paths = []
results_ui = []

for _, cc_row in st.session_state.df_client.iterrows():
    try:
        path = nx.shortest_path(G, source=cc_row["surf_A"], target=cc_row["surf_B"])
        sum_it = sum(
            G.get_edge_data(path[i], path[i + 1])["it"] for i in range(len(path) - 1)
        )
        it_max = float(cc_row["it_max"])
        delta = round(it_max - sum_it, 4)

        if sum_it <= it_max:
            results_ui.append(
                {
                    "status": "success",
                    "title": f"✅ {cc_row['id_cc']} : VALIDE",
                    "path": path,
                    "it": sum_it,
                    "max": it_max,
                    "margin": delta,
                }
            )
        else:
            failing_paths.append(path)
            results_ui.append(
                {
                    "status": "error",
                    "title": f"❌ {cc_row['id_cc']} : INVALIDE",
                    "path": path,
                    "it": sum_it,
                    "max": it_max,
                    "margin": abs(delta),
                }
            )

    except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
        results_ui.append(
            {
                "status": "warning",
                "title": f"⚠️ {cc_row['id_cc']} : Erreur",
                "msg": str(e),
            }
        )

st.divider()
# ==========================================
# 3. Verdict & Détails analytiques
# ==========================================
st.header("2. Analyse & Visualisation")

# Création dynamique d'autant de colonnes qu'il y a de cotes client à vérifier
cols = st.columns(max(len(results_ui), 1))

for i, res in enumerate(results_ui):
    with cols[i]:
        if res["status"] in ["success", "error"]:
            chemin_str = " ➔ ".join(res["path"])

        if res["status"] == "success":
            st.success(
                f"**{res['title']}**\n\n"
                f"**Chemin :** `{chemin_str}`\n\n"
                f"IT Cumulé : **{res['it']} mm** / {res['max']} mm\n\n"
                f"Marge de sécurité : {res['margin']} mm"
            )
        elif res["status"] == "error":
            st.error(
                f"**{res['title']}**\n\n"
                f"**Chemin :** `{chemin_str}`\n\n"
                f"IT Cumulé : **{res['it']} mm** / {res['max']} mm\n\n"
                f"Dépassement : {res['margin']} mm"
            )
        else:
            st.warning(f"**{res['title']}**\n\n{res['msg']}")

# ==========================================
# 4. Graphes (Pleine largeur avec contrôles)
# ==========================================
st.write("")  # Espace
col_title, col_toggle = st.columns([3, 1])
with col_title:
    st.subheader("📊 Visualisation des transferts")
with col_toggle:
    # Option UI pour basculer le flowchart dynamiquement
    orientation = st.segmented_control(
        "Orientation", options=["LR", "TD"], default="LR", selection_mode="single"
    )

tab_flow, tab_seq = st.tabs(["🕸️ Anselmetti", "⏱️ Séquence"])

with tab_flow:
    # Le graphe prend désormais toute la largeur disponible sous les verdicts
    flowchart = engine.get_mermaid_flowchart(G, failing_paths, direction=orientation)
    st.markdown(f"```mermaid\n{flowchart}\n```")

with tab_seq:
    sequence = engine.get_mermaid_sequence(df_cf, failing_paths)
    st.markdown(f"```mermaid\n{sequence}\n```")
