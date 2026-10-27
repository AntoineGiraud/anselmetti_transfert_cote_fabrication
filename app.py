import networkx as nx
import pandas as pd
import streamlit as st
import duckdb


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
# 2. Moteur Graphe & Mermaid
# ==========================================
def build_graph(df_cf: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, row in df_cf.iterrows():
        it_val = row["it_calcule"] if pd.notna(row["it_calcule"]) else 99.9
        G.add_edge(row["surf_dep"], row["surf_arr"], label=row["id"], it=it_val)
    return G


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
        return {"success": False, "error": f"Surface {e} introuvable."}


def get_mermaid_flowchart(G: nx.Graph, critical_path: list = None) -> str:
    """Génère le graphe Anselmetti avec coloration du chemin de cotes."""
    lines = ["graph BT"]

    # Définition des noeuds (Sécurisés avec des guillemets "")
    for node in G.nodes():
        if "Symetrie" in str(node):
            # En f-string Python, {{ devient { pour générer le losange Mermaid
            lines.append(f'    {node}{{"{node}"}}')
            lines.append(
                f"    style {node} fill:#ff4b4b,color:#fff,stroke:#333,stroke-width:2px"
            )
        else:
            lines.append(f'    {node}["{node}"]')

    # Définition des arêtes
    edges_list = list(G.edges(data=True))
    for i, (u, v, data) in enumerate(edges_list):
        label = f"{data['label']} (IT: {data['it']:.3g}mm)"

        # Syntaxe Mermaid robuste : A -- "texte" --- B
        lines.append(f'    {u} -- "{label}" --- {v}')

        # Coloration du chemin trouvé en rouge
        if critical_path:
            is_in_path = any(
                (u == critical_path[j] and v == critical_path[j + 1])
                or (v == critical_path[j] and u == critical_path[j + 1])
                for j in range(len(critical_path) - 1)
            )
            if is_in_path:
                lines.append(f"    linkStyle {i} stroke:#ff4b4b,stroke-width:3px;")

    return "\n".join(lines)


def get_mermaid_sequence(df_gamme: pd.DataFrame) -> str:
    """Génère la chronologie de la gamme d'usinage."""
    lines = ["sequenceDiagram", "    autonumber"]

    surfaces = pd.concat([df_gamme["surf_dep"], df_gamme["surf_arr"]]).unique()
    for surf in surfaces:
        lines.append(f"    participant {surf}")

    for _, row in df_gamme.iterrows():
        it = (
            round(row.get("it_calcule", 0), 3)
            if pd.notna(row.get("it_calcule"))
            else "N/A"
        )
        lines.append(
            f"    {row['surf_dep']}->>{row['surf_arr']}: {row['id']} (IT: {it})"
        )

    return "\n".join(lines)


# ==========================================
# 3. Interface Streamlit
# ==========================================
st.set_page_config(page_title="Anselmetti Studio", layout="wide")
init_data()

st.title("⚙️ Anselmetti Studio : Transfert de Cotes")

# -- 1. ZONE D'ÉDITION --
st.header("1. Paramétrage (Édition libre)")
tab_res, tab_gamme, tab_client = st.tabs(
    [
        "🏭 Ressources (Machines/Outils)",
        "📋 Gamme d'Usinage (Cotes Fab)",
        "🎯 Cotes Client (Besoins)",
    ]
)

with tab_res:
    res_edited = st.data_editor(
        st.session_state.df_ressources,
        num_rows="dynamic",
        key="ed_res",
        use_container_width=True,
    )
with tab_gamme:
    gamme_edited = st.data_editor(
        st.session_state.df_gamme,
        num_rows="dynamic",
        key="ed_gamme",
        use_container_width=True,
    )
with tab_client:
    client_edited = st.data_editor(
        st.session_state.df_client,
        num_rows="dynamic",
        key="ed_client",
        use_container_width=True,
    )

# -- CALCUL DUCKDB --
df_cf_dynamique = duckdb.query("""
    SELECT
        g.id_cf as id, g.surf_dep, g.surf_arr, g.nominale, g.id_ressource,
        ROUND((r.it_machine + r.it_outil), 3) AS it_calcule
    FROM gamme_edited g
    LEFT JOIN res_edited r ON g.id_ressource = r.id_ressource
""").df()

st.divider()

# -- 2. ZONE D'ANALYSE & VISUALISATION --
st.header("2. Analyse & Validation")
G = build_graph(df_cf_dynamique)

col_viz, col_analysis = st.columns([1.2, 1])

with col_analysis:
    st.subheader("🔍 Contrôle des Cotes")

    active_path = None
    for _, cc_row in client_edited.iterrows():
        with st.expander(
            f"Analyse : {cc_row['id_cc']} ({cc_row['surf_A']} ➔ {cc_row['surf_B']})",
            expanded=True,
        ):
            it_max = float(cc_row["it_max"])
            result = analyze_chain(G, cc_row["surf_A"], cc_row["surf_B"])

            if result["success"]:
                # Sauvegarde du dernier chemin réussi pour l'afficher sur le graphe
                active_path = result["path"]

                st.markdown(f"**Chemin :** `{' ➔ '.join(result['path'])}`")
                st.caption(f"**Détail :** {' + '.join(result['links'])}")

                it_calc = result["sum_it"]
                delta = round(it_max - it_calc, 4)

                if it_calc <= it_max:
                    st.success(
                        f"✅ **VALIDE** | IT Cumulé: **{it_calc} mm** (Max: {it_max}) | Marge: {delta} mm"
                    )
                else:
                    st.error(
                        f"❌ **INVALIDE** | IT Cumulé: **{it_calc} mm** (Max: {it_max}) | Dépassement: {abs(delta)} mm"
                    )
            else:
                st.warning(f"⚠️ {result['error']}")

with col_viz:
    tab_flow, tab_seq = st.tabs(["🕸️ Graphe Anselmetti", "⏱️ Diagramme de Séquence"])

    with tab_flow:
        st.caption(
            "Le tracé vectoriel des transferts. Le dernier chemin analysé est surligné en rouge."
        )
        if G.number_of_nodes() > 0:
            mermaid_flow = get_mermaid_flowchart(G, active_path)
            st.markdown(f"```mermaid\n{mermaid_flow}\n```")
        else:
            st.info("Graphe vide.")

    with tab_seq:
        st.caption("Chronologie de la gamme d'usinage surface par surface.")
        if not df_cf_dynamique.empty:
            mermaid_seq = get_mermaid_sequence(df_cf_dynamique)
            st.markdown(f"```mermaid\n{mermaid_seq}\n```")
        else:
            st.info("Gamme vide.")
