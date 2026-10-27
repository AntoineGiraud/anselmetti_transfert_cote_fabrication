import networkx as nx
import pandas as pd
import streamlit as st
import duckdb
import streamlit.components.v1 as components
from pyvis.network import Network


# ==========================================
# 1. Moteur Data (DuckDB)
# ==========================================
@st.cache_resource
def init_db():
    conn = duckdb.connect(database=":memory:")

    # Table des Ressources (Machines & Outils)
    conn.execute("""
        CREATE TABLE ressources (
            id_ressource VARCHAR PRIMARY KEY,
            type VARCHAR,
            it_machine DOUBLE,
            it_outil DOUBLE
        );

        INSERT INTO ressources VALUES
            ('Moulage_Sable', 'Fonderie', 0.8, 0.0),
            ('Tour_Ebauche', 'Tournage', 0.1, 0.05),
            ('Tour_Finition', 'Tournage', 0.02, 0.01),
            ('Fraiseuse_Chanfrein', 'Fraisage', 0.05, 0.02);
    """)

    # Table de la Gamme (Cotes de Fabrication)
    conn.execute("""
        CREATE TABLE gamme_usinage (
            id_cf VARCHAR PRIMARY KEY,
            surf_dep VARCHAR,
            surf_arr VARCHAR,
            id_ressource VARCHAR,
            nominale DOUBLE,
            FOREIGN KEY(id_ressource) REFERENCES ressources(id_ressource)
        );

        -- Cas : Flasque ronde moulée (ep: 20mm, dia: 300mm), avec reprise chanfrein
        INSERT INTO gamme_usinage VALUES
            ('CF_Brut_G', 'S_Brut_Gauche', 'Plan_Symetrie', 'Moulage_Sable', 10.0),
            ('CF_Brut_D', 'Plan_Symetrie', 'S_Brut_Droite', 'Moulage_Sable', 10.0),
            ('CF_Tour_Eb', 'Plan_Symetrie', 'S_Ext_Ebauche', 'Tour_Ebauche', 151.0),
            ('CF_Tour_Fin', 'S_Ext_Ebauche', 'S_Ext_Fini', 'Tour_Finition', 150.0),
            ('CF_Chanfrein', 'S_Ext_Fini', 'S_Chanfrein', 'Fraiseuse_Chanfrein', 2.0);
    """)

    # Vue analytique : Jointure et calcul dynamique de l'IT
    conn.execute("""
        CREATE VIEW v_cotes_fabrication AS
        SELECT
            g.id_cf as id,
            g.surf_dep,
            g.surf_arr,
            g.nominale,
            g.id_ressource,
            (r.it_machine + r.it_outil) AS it_calcule
        FROM gamme_usinage g
        JOIN ressources r ON g.id_ressource = r.id_ressource;
    """)

    return conn


# ==========================================
# 2. Logique Graphe & Analyse
# ==========================================
def build_graph(df_cf: pd.DataFrame) -> nx.Graph:
    G = nx.Graph()
    for _, row in df_cf.iterrows():
        # L'IT utilisé est désormais celui calculé par SQL
        G.add_edge(
            row["surf_dep"], row["surf_arr"], label=row["id"], it=row["it_calcule"]
        )
    return G


def get_pyvis_html(G: nx.Graph) -> str:
    net = Network(height="400px", width="100%", bgcolor="#222222", font_color="white")
    net.from_nx(G)
    # Mise en évidence du plan de symétrie (nœud virtuel)
    for node in net.nodes:
        if "Symetrie" in node["id"]:
            node["color"] = "#ff4b4b"
            node["shape"] = "diamond"
            node["size"] = 25
    return net.generate_html()


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
        return {"success": True, "path": path, "sum_it": sum_it, "links": links}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ==========================================
# 3. Interface Streamlit
# ==========================================
st.set_page_config(page_title="Anselmetti DB Engine", layout="wide")
conn = init_db()

st.title("⚙️ Moteur de Transfert Anselmetti (DuckDB Powered)")

# Récupération des tables via SQL
df_ressources = conn.execute("SELECT * FROM ressources").df()
df_cf_dynamique = conn.execute("SELECT * FROM v_cotes_fabrication").df()

col1, col2 = st.columns(2)
with col1:
    st.subheader("🏭 Parc Machines & Outils (Ressources)")
    st.dataframe(df_ressources, use_container_width=True, hide_index=True)

with col2:
    st.subheader("📋 Gamme d'Usinage (IT calculé via vue SQL)")
    st.dataframe(df_cf_dynamique, use_container_width=True, hide_index=True)

st.divider()

G = build_graph(df_cf_dynamique)
col_graph, col_analysis = st.columns(2)

with col_graph:
    st.subheader("🕸️ Graphe de liaison (Plan de symétrie en rouge)")
    components.html(get_pyvis_html(G), height=410)

with col_analysis:
    st.subheader("🎯 Vérification Besoin Client")
    st.write(
        "Test : Respect de la distance entre le Chanfrein et le Brut opposé (Ex: IT max = 1.0mm)"
    )

    # Simulation d'une requête client
    surf_client_A = "S_Chanfrein"
    surf_client_B = "S_Brut_Gauche"
    it_client_max = 1.0

    result = analyze_chain(G, surf_client_A, surf_client_B)

    if result["success"]:
        st.write("🛣️ **Chemin :** " + " ➔ ".join(result["path"]))
        st.write("🔗 **Opérations :** " + " + ".join(result["links"]))

        delta = round(it_client_max - result["sum_it"], 3)
        if result["sum_it"] <= it_client_max:
            st.success(
                f"✅ **VALIDE** : IT Cumulé ({result['sum_it']} mm) <= IT Max ({it_client_max} mm). Marge : {delta}mm"
            )
        else:
            st.error(
                f"❌ **INVALIDE** : IT Cumulé ({result['sum_it']} mm) > IT Max ({it_client_max} mm)."
            )
