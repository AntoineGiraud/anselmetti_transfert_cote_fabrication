import pandas as pd
import networkx as nx
import duckdb


def get_initial_data():
    """Renvoie les DataFrames par défaut (Ressources, Gamme, Client)."""
    df_res = pd.DataFrame(
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
                "it_machine": 0.05,
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
    df_gamme = pd.DataFrame(
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
    df_client = pd.DataFrame(
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
    return df_res, df_gamme, df_client


def compute_cotes(df_gamme: pd.DataFrame, df_res: pd.DataFrame) -> pd.DataFrame:
    """Calcule l'IT dynamique via DuckDB."""
    return duckdb.query("""
        SELECT
            g.id_cf as id, g.surf_dep, g.surf_arr, g.nominale, g.id_ressource,
            ROUND((r.it_machine + r.it_outil), 3) AS it_calcule
        FROM df_gamme g
        LEFT JOIN df_res r ON g.id_ressource = r.id_ressource
    """).df()


def build_graph(df_cf: pd.DataFrame) -> nx.Graph:
    """Construit le graphe Anselmetti."""
    G = nx.Graph()
    for _, row in df_cf.iterrows():
        it_val = row["it_calcule"] if pd.notna(row["it_calcule"]) else 99.9
        G.add_edge(row["surf_dep"], row["surf_arr"], label=row["id"], it=it_val)
    return G


def get_mermaid_flowchart(
    G: nx.Graph, failing_paths: list, direction: str = "LR"
) -> str:
    lines = [f"graph {direction}"]
    for node in G.nodes():
        if "Symetrie" in str(node):
            lines.append(
                f'    {node}{{"{node}"}}\n    style {node} fill:#2196f3,color:#fff,stroke:#333'
            )
        else:
            lines.append(f'    {node}["{node}"]')

    for i, (u, v, data) in enumerate(list(G.edges(data=True))):
        lines.append(f'    {u} -- "{data["label"]} ({data["it"]:.3g}mm)" --- {v}')
        is_failing = any(
            any(
                (u == path[j] and v == path[j + 1])
                or (v == path[j] and u == path[j + 1])
                for j in range(len(path) - 1)
            )
            for path in failing_paths
        )
        if is_failing:
            lines.append(f"    linkStyle {i} stroke:#ff4b4b,stroke-width:4px;")
    return "\n".join(lines)


def get_mermaid_sequence(df_cf: pd.DataFrame, failing_paths: list) -> str:
    seq_lines = ["sequenceDiagram\n    autonumber"]
    for surf in pd.concat([df_cf["surf_dep"], df_cf["surf_arr"]]).unique():
        seq_lines.append(f"    participant {surf}")

    for _, row in df_cf.iterrows():
        it = (
            round(row.get("it_calcule", 0), 3)
            if pd.notna(row.get("it_calcule"))
            else "N/A"
        )
        is_failing_op = any(
            any(
                (row["surf_dep"] == path[j] and row["surf_arr"] == path[j + 1])
                or (row["surf_arr"] == path[j] and row["surf_dep"] == path[j + 1])
                for j in range(len(path) - 1)
            )
            for path in failing_paths
        )
        marker = "🔴 " if is_failing_op else ""
        seq_lines.append(
            f"    {row['surf_dep']}->>{row['surf_arr']}: {marker}{row['id']} (IT: {it})"
        )
    return "\n".join(seq_lines)
