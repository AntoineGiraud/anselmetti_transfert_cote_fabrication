import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def imports():
    import marimo as mo
    import pandas as pd
    import networkx as nx
    import duckdb

    return duckdb, mo, nx, pd


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    # ⚙️ Anselmetti Studio (Marimo)
    ## 1. Paramètres
    """)
    return


@app.cell(hide_code=True)
def init_data(pd):
    # Données par défaut
    df_res_init = pd.DataFrame(
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

    df_gamme_init = pd.DataFrame(
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

    df_client_init = pd.DataFrame(
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
    return df_client_init, df_gamme_init, df_res_init


@app.cell
def ui_components(df_client_init, df_gamme_init, df_res_init, mo):
    # Création des tableaux éditables (équivalent de st.data_editor)
    # L'argument `label` n'est pas strict, on va les mettre dans des onglets.
    ui_res = mo.ui.data_editor(df_res_init)
    ui_gamme = mo.ui.data_editor(df_gamme_init)
    ui_client = mo.ui.data_editor(df_client_init)

    # Création des onglets
    mo.ui.tabs({"🏭 Ressources": ui_res, "📋 Gamme": ui_gamme, "🎯 Client": ui_client})
    return ui_client, ui_gamme, ui_res


@app.cell(hide_code=True)
def _(mo):
    mo.md(r"""
    ## 2. Analyse
    """)
    return


@app.cell(hide_code=True)
def logic_engine(duckdb, nx, pd, ui_gamme, ui_res):
    # Récupération des DataFrames modifiés par l'utilisateur
    res_edited = ui_res.value
    gamme_edited = ui_gamme.value

    # ⚠️ Pro-tip Pyodide/WASM :
    # Si DuckDB pose un problème de compilation C++ dans le navigateur,
    # tu peux remplacer cette requête par un `pd.merge()` natif très facilement.
    df_cf = duckdb.query("""
        SELECT
            g.id_cf as id, g.surf_dep, g.surf_arr, g.nominale, g.id_ressource,
            ROUND((r.it_machine + r.it_outil), 3) AS it_calcule
        FROM gamme_edited g
        LEFT JOIN res_edited r ON g.id_ressource = r.id_ressource
    """).df()

    # Construction du graphe (réexécuté automatiquement si df_cf change)
    G = nx.Graph()
    for _, _row in df_cf.iterrows():
        it_val = _row["it_calcule"] if pd.notna(_row["it_calcule"]) else 99.9
        G.add_edge(_row["surf_dep"], _row["surf_arr"], label=_row["id"], it=it_val)
    return G, df_cf


@app.cell(hide_code=True)
def ui_analysis(G, mo, nx, ui_client):
    client_edited = ui_client.value
    results_ui = []

    # NOUVEAU : On stocke une liste de tous les chemins invalides
    failing_paths = []

    for _, cc_row in client_edited.iterrows():
        try:
            path = nx.shortest_path(G, source=cc_row["surf_A"], target=cc_row["surf_B"])
            sum_it = sum(
                G.get_edge_data(path[i], path[i + 1])["it"]
                for i in range(len(path) - 1)
            )

            it_max = float(cc_row["it_max"])
            delta = round(it_max - sum_it, 4)

            if sum_it <= it_max:
                kind = "success"
                title = f"✅ {cc_row['id_cc']} : VALIDE"
                detail = f"**IT Cumulé : {round(sum_it, 3)} mm** (Max toléré : {it_max} mm) | Marge : {delta} mm"
            else:
                kind = "danger"
                title = f"❌ {cc_row['id_cc']} : INVALIDE"
                detail = f"**IT Cumulé : {round(sum_it, 3)} mm** (Max toléré : {it_max} mm) | Dépassement : {abs(delta)} mm"

                # On sauvegarde ce chemin précis car il est en erreur
                failing_paths.append(path)

            content = mo.md(f"""
            - **Chemin** : `{" ➔ ".join(path)}`
            - {detail}
            """)
            results_ui.append(mo.callout(content, kind=kind, title=title))

        except nx.NetworkXNoPath:
            results_ui.append(
                mo.callout(
                    mo.md(
                        f"Aucun lien continu entre `{cc_row['surf_A']}` et `{cc_row['surf_B']}`."
                    ),
                    kind="warn",
                    title=f"⚠️ {cc_row['id_cc']} : Chemin introuvable",
                )
            )
        except nx.NodeNotFound as e:
            results_ui.append(
                mo.callout(
                    mo.md(f"Surface manquante : {e}"),
                    kind="warn",
                    title=f"⚠️ {cc_row['id_cc']} : Erreur",
                )
            )

    # L'astuce Marimo : on met le composant UI dans une variable,
    # et on retourne les DEUX variables pour exporter la donnée ET l'affichage
    analysis_output = mo.vstack(results_ui) if results_ui else mo.md("Aucune analyse.")
    analysis_output
    return (failing_paths,)


@app.cell(hide_code=True)
def render_mermaid(G, df_cf, failing_paths, mo, pd):
    # Fonction de génération Flowchart
    lines = ["graph LR"]
    for _node in G.nodes():
        if "Symetrie" in str(_node):
            lines.append(f'    {_node}{{"{_node}"}}')
            lines.append(f"    style {_node} fill:#ff4b4b,color:#fff,stroke:#333")
        else:
            lines.append(f'    {_node}["{_node}"]')

    edges_list = list(G.edges(data=True))
    for i, (u, v, data) in enumerate(edges_list):
        lines.append(f'    {u} -- "{data["label"]} ({data["it"]:.3g}mm)" --- {v}')

        # On vérifie si l'arête fait partie d'UN des chemins en erreur
        is_failing = False
        for _path in failing_paths:
            if any(
                (u == _path[j] and v == _path[j + 1])
                or (v == _path[j] and u == _path[j + 1])
                for j in range(len(_path) - 1)
            ):
                is_failing = True
                break

        # Si oui, on la colore en ROUGE
        if is_failing:
            lines.append(f"    linkStyle {i} stroke:#ff4b4b,stroke-width:4px;")

    mermaid_flow = "\n".join(lines)

    # Fonction de génération Sequence
    seq_lines = ["sequenceDiagram", "    autonumber"]
    for surf in pd.concat([df_cf["surf_dep"], df_cf["surf_arr"]]).unique():
        seq_lines.append(f"    participant {surf}")
    for _, row in df_cf.iterrows():
        it = round(row.get("it_calcule", 0), 3) if pd.notna(row.get("it_calcule")) else "N/A"

        # Vérification : cette opération appartient-elle à une chaîne en erreur ?
        is_failing_op = False
        for _path in failing_paths:
            if any((row['surf_dep'] == _path[j] and row['surf_arr'] == _path[j + 1]) or
                   (row['surf_arr'] == _path[j] and row['surf_dep'] == _path[j + 1])
                   for j in range(len(_path) - 1)):
                is_failing_op = True
                break

        # Ajout du marqueur visuel sur le libellé de la flèche
        marker = "🔴 " if is_failing_op else ""
        seq_lines.append(f"    {row['surf_dep']}->>{row['surf_arr']}: {marker}{row['id']} (IT: {it})")

    mermaid_seq = "\n".join(seq_lines)

    # CORRECTION MARIMO : On retourne directement l'objet UI sans mot-clé `return` vide à la fin
    mermaid_ui = mo.ui.tabs(
        {
            "🕸️ Anselmetti": mo.mermaid(f"{mermaid_flow}"),
            "⏱️ Séquence": mo.mermaid(f"{mermaid_seq}"),
        }
    )
    mermaid_ui
    return


if __name__ == "__main__":
    app.run()
