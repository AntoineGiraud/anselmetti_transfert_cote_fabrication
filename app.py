import tempfile
import networkx as nx
import pandas as pd
import streamlit as st
import duckdb
import streamlit.components.v1 as components
from pyvis.network import Network


# ==========================================
# 1. Initialisation des données (Session State)
# ==========================================
def init_data():
    if "df_ressources" not in st.session_state:
        st.session_state.df_ressources = pd.DataFrame(
            [
                {
                    "id_ressource": "Moulage_Sable",
                    "type": "Fonderie",
                    "it_machine": 0.8,
                    "it_outil": 0.0,
                },
                {
                    "id_ressource": "Tour_Ebauche",
                    "type": "Tournage",
                    "it_machine": 0.1,
                    "it_outil": 0.05,
                },
                {
                    "id_ressource": "Tour_Finition",
                    "type": "Tournage",
                    "it_machine": 0.02,
                    "it_outil": 0.01,
                },
                {
                    "id_ressource": "Fraiseuse_Chanfrein",
                    "type": "Fraisage",
                    "it_machine": 0.05,
                    "it_outil": 0.02,
                },
            ]
        )

    if "df_gamme" not in st.session_state:
        st.session_state.df_gamme = pd.DataFrame(
            [
                {
                    "id_cf": "CF_Brut_G",
                    "surf_dep": "S_Brut_Gauche",
                    "surf_arr": "Plan_Symetrie",
                    "id_ressource": "Moulage_Sable",
                    "nominale": 10.0,
                },
                {
                    "id_cf": "CF_Brut_D",
                    "surf_dep": "Plan_Symetrie",
                    "surf_arr": "S_Brut_Droite",
                    "id_ressource": "Moulage_Sable",
                    "nominale": 10.0,
                },
                {
                    "id_cf": "CF_Tour_Eb",
                    "surf_dep": "Plan_Symetrie",
                    "surf_arr": "S_Ext_Ebauche",
                    "id_ressource": "Tour_Ebauche",
                    "nominale": 151.0,
                },
                {
                    "id_cf": "CF_Tour_Fin",
                    "surf_dep": "S_Ext_Ebauche",
                    "surf_arr": "S_Ext_Fini",
                    "id_ressource": "Tour_Finition",
                    "nominale": 150.0,
                },
                {
                    "id_cf": "CF_Chanfrein",
                    "surf_dep": "S_Ext_Fini",
                    "surf_arr": "S_Chanfrein",
                    "id_ressource": "Fraiseuse_Chanfrein",
                    "nominale": 2.0,
                },
            ]
        )

    if "df_client" not in st.session_state:
        st.session_state.df_client = pd.DataFrame(
            [
                {
                    "id_cc": "CC1_Largeur_Totale",
                    "surf_A": "S_Chanfrein",
                    "surf_B": "S_Brut_Gauche",
                    "nominale_cible": 140.0,
                    "it_max": 1.0,
                },
                {
                    "id_cc": "CC2_Symetrie_Fini",
                    "surf_A": "S_Ext_Fini",
                    "surf_B": "Plan_Symetrie",
                    "nominale_cible": 150.0,
                    "it_max": 0.1,
                },
            ]
        )


# ==========================================
# 2. Logique Graphe & Analyse
# ==========================================
def build_graph(df_cf: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, row in df_cf.iterrows():
        # En cas d'erreur de frappe sur la ressource, on sécurise avec un IT par défaut à 99
        it_val = row["it_calcule"] if pd.notna(row["it_calcule"]) else 99.9
        G.add_edge(row["surf_dep"], row["surf_arr"], label=row["id"], it=it_val)
    return G


def get_pyvis_html(G: nx.Graph) -> str:
    net = Network(height="450px", width="100%", bgcolor="#222222", font_color="white")
    net.from_nx(G)
    for node in net.nodes:
        if "Symetrie" in node["id"]:
            node["color"] = "#ff4b4b"
            node["shape"] = "diamond"
            node["size"] = 25

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.save_graph(tmp_file.name)
        with open(tmp_file.name, "r", encoding="utf-8") as f:
            return f.read()


def analyze_chain(G: nx.Graph, surf_A: str, surf_B: str):
    try:
        path = nx.shortest_path(G, source=surf_A, target=surf_B)
        sum_it = sum(
            G.get_edge_data(path[i], path[i + 1])["it"] for i in range(len(path) - 1)
        )
        links = [
            f"{G.get_edge_data(path[i], path[i + 1])['label']} ({G.get_edge_data(path[i], path[i + 1])['it']}mm)"
            for i in range(len(path) - 1)
        ]
        return {
            "success": True,
            "path": path,
            "sum_it": round(sum_it, 4),
            "links": links,
        }
    except nx.NetworkXNoPath:
        return {
            "success": False,
            "error": "Rupture de chaîne : aucun lien continu entre ces surfaces.",
        }
    except nx.NodeNotFound as e:
        return {"success": False, "error": f"Surface {e} introuvable dans la gamme."}


# ==========================================
# 3. Interface Streamlit
# ==========================================
st.set_page_config(page_title="Anselmetti Studio", layout="wide")
init_data()

st.title("⚙️ Anselmetti Studio : Transfert de Cotes")

# -- ZONE D'ÉDITION DES DONNÉES --
st.header("1. Paramétrage (Édition libre)")
tab1, tab2, tab3 = st.tabs(
    [
        "🏭 Ressources (Machines/Outils)",
        "📋 Gamme d'Usinage (Cotes Fab)",
        "🎯 Cotes Client (Besoins)",
    ]
)

with tab1:
    res_edited = st.data_editor(
        st.session_state.df_ressources,
        num_rows="dynamic",
        key="ed_res",
        use_container_width=True,
    )
with tab2:
    gamme_edited = st.data_editor(
        st.session_state.df_gamme,
        num_rows="dynamic",
        key="ed_gamme",
        use_container_width=True,
    )
with tab3:
    client_edited = st.data_editor(
        st.session_state.df_client,
        num_rows="dynamic",
        key="ed_client",
        use_container_width=True,
    )

# -- CALCUL DUCKDB A LA VOLÉE --
# DuckDB lit directement les variables res_edited et gamme_edited
query = """
    SELECT
        g.id_cf as id,
        g.surf_dep,
        g.surf_arr,
        g.nominale,
        g.id_ressource,
        (r.it_machine + r.it_outil) AS it_calcule
    FROM gamme_edited g
    LEFT JOIN res_edited r ON g.id_ressource = r.id_ressource
"""
df_cf_dynamique = duckdb.query(query).df()

st.divider()

# -- ZONE D'ANALYSE --
st.header("2. Analyse & Validation")
G = build_graph(df_cf_dynamique)
col_graph, col_analysis = st.columns([1, 1.2])

with col_graph:
    st.subheader("🕸️ Graphe de liaison")
    if G.number_of_nodes() > 0:
        components.html(get_pyvis_html(G), height=460)
    else:
        st.info("Graphe vide. Ajoutez des cotes de fabrication.")

with col_analysis:
    st.subheader("🔍 Contrôle des Cotes Client")

    for _, cc_row in client_edited.iterrows():
        with st.expander(
            f"Analyse : {cc_row['id_cc']} ({cc_row['surf_A']} ➔ {cc_row['surf_B']})",
            expanded=True,
        ):
            it_max = float(cc_row["it_max"])
            result = analyze_chain(G, cc_row["surf_A"], cc_row["surf_B"])

            if result["success"]:
                st.markdown(f"**Chemin :** `{' ➔ '.join(result['path'])}`")
                st.caption(f"**Opérations :** {' + '.join(result['links'])}")

                it_calc = result["sum_it"]
                delta = round(it_max - it_calc, 4)

                if it_calc <= it_max:
                    st.success(
                        f"✅ **VALIDE** | IT Cumulé: **{it_calc} mm** (Max: {it_max} mm) | Marge: {delta} mm"
                    )
                else:
                    st.error(
                        f"❌ **INVALIDE** | IT Cumulé: **{it_calc} mm** (Max: {it_max} mm) | Dépassement: {abs(delta)} mm"
                    )
            else:
                st.warning(f"⚠️ {result['error']}")
