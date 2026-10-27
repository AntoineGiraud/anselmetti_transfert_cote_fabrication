import tempfile
from typing import Any, Dict, List, Optional

import networkx as nx
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from pyvis.network import Network


def init_default_data() -> None:
    """Initialise les données de démonstration dans le session_state."""
    if "df_cf" not in st.session_state:
        # CF = Cotes de Fabrication (Usinages)
        st.session_state.df_cf = pd.DataFrame(
            [
                {"id": "CF1", "surf_dep": "S1_brut", "surf_arr": "S2_usine", "nominale": 50.0, "it": 0.2},
                {"id": "CF2", "surf_dep": "S2_usine", "surf_arr": "S3_usine", "nominale": 20.0, "it": 0.15},
            ]
        )
    if "df_cc" not in st.session_state:
        # CC = Cotes Condition/Client (Le besoin)
        st.session_state.df_cc = pd.DataFrame(
            [
                {"id": "CC1_Client", "surf_A": "S1_brut", "surf_B": "S3_usine", "nominale_cible": 30.0, "it_max": 0.4},
            ]
        )

def build_graph(df_cf: pd.DataFrame) -> nx.Graph:
    """Construit un graphe non-orienté à partir des cotes de fabrication."""
    G = nx.Graph()
    for _, row in df_cf.iterrows():
        # L'arête contient les attributs de la cote
        G.add_edge(
            row["surf_dep"],
            row["surf_arr"],
            label=row["id"],
            it=row["it"],
            nominale=row["nominale"]
        )
    return G

def get_pyvis_html(G: nx.Graph) -> str:
    """Génère le rendu HTML interactif du graphe avec PyVis."""
    net = Network(height="400px", width="100%", bgcolor="#222222", font_color="white")
    net.from_nx(G)

    # Configuration physique pour un bel affichage
    net.repulsion(node_distance=150, central_gravity=0.2, spring_length=150, spring_strength=0.05)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as tmp_file:
        net.save_graph(tmp_file.name)
        with open(tmp_file.name, "r", encoding="utf-8") as f:
            return f.read()

def analyze_tolerance_chain(G: nx.Graph, surf_A: str, surf_B: str) -> Dict[str, Any]:
    """Trouve la chaîne de cotes entre deux surfaces et calcule la somme des IT."""
    try:
        # Algorithme du plus court chemin de Dijkstra/BFS
        path = nx.shortest_path(G, source=surf_A, target=surf_B)

        sum_it = 0.0
        chain_links: List[str] = []

        # Parcours des arêtes du chemin trouvé
        for i in range(len(path) - 1):
            u, v = path[i], path[i+1]
            edge_data = G.get_edge_data(u, v)
            sum_it += edge_data["it"]
            chain_links.append(f"{edge_data['label']} ({edge_data['it']}mm)")

        return {
            "success": True,
            "path": path,
            "sum_it": sum_it,
            "chain_links": chain_links
        }
    except nx.NetworkXNoPath:
        return {"success": False, "error": "Aucun lien de fabrication ne relie ces surfaces."}
    except nx.NodeNotFound as e:
        return {"success": False, "error": f"Surface manquante dans le graphe : {e}"}

# ==========================================
# Interface Streamlit
# ==========================================
st.set_page_config(page_title="Anselmetti Engine", layout="wide")
st.title("⚙️ Moteur de Transfert de Cotes (Anselmetti)")

init_default_data()

# 1. Zone de saisie (Data Engineering)
col1, col2 = st.columns(2)

with col1:
    st.subheader("🛠️ Cotes de Fabrication (CF)")
    st.write("Saisissez vos opérations d'usinage et leurs tolérances (IT).")
    df_cf_edited = st.data_editor(st.session_state.df_cf, num_rows="dynamic", key="editor_cf")

with col2:
    st.subheader("🎯 Cotes Fonctionnelles Client (CC)")
    st.write("Définissez les exigences du plan.")
    df_cc_edited = st.data_editor(st.session_state.df_cc, num_rows="dynamic", key="editor_cc")

st.divider()

# 2. Construction du Graphe
G = build_graph(df_cf_edited)

col_graph, col_analysis = st.columns([1, 1])

with col_graph:
    st.subheader("🕸️ Graphe de liaison des surfaces")
    if G.number_of_nodes() > 0:
        html_graph = get_pyvis_html(G)
        components.html(html_graph, height=410)
    else:
        st.info("Ajoutez des cotes de fabrication pour générer le graphe.")

# 3. Moteur d'Analyse (Calcul du transfert)
with col_analysis:
    st.subheader("🔍 Analyse des Transferts (Worst-Case)")

    for _, cc_row in df_cc_edited.iterrows():
        st.write(f"### Analyse de : **{cc_row['id']}**")
        st.caption(f"Chemin requis : {cc_row['surf_A']} ➔ {cc_row['surf_B']} | IT max autorisé : {cc_row['it_max']} mm")

        result = analyze_tolerance_chain(G, cc_row['surf_A'], cc_row['surf_B'])

        if result["success"]:
            it_calc = result["sum_it"]
            it_max = cc_row["it_max"]

            # Affichage de la chaîne trouvée
            st.write("🛣️ **Chaîne trouvée :** " + " ➔ ".join(result["path"]))
            st.write("🔗 **Détail :** " + " + ".join(result["chain_links"]))

            # Validation Anselmetti (IT calculé <= IT Client)
            delta = round(it_max - it_calc, 3)
            if it_calc <= it_max:
                st.success(f"✅ **TRANSFERT VALIDE** : L'IT cumulé ({it_calc:.3f} mm) respecte la limite de {it_max} mm. Marge de sécurité : {delta} mm.")
            else:
                st.error(f"❌ **TRANSFERT INVALIDE** : L'IT cumulé ({it_calc:.3f} mm) dépasse la limite de {it_max} mm ! (Dépassement : {abs(delta)} mm). Vos machines ne sont pas assez précises pour ce plan d'usinage.")
        else:
            st.warning(f"⚠️ {result['error']}")

        st.markdown("---")