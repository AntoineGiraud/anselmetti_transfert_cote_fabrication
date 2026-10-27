import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell(hide_code=True)
def imports():
    import marimo as mo
    import networkx as nx
    from src.anselmetti_trf_cote import engine

    return engine, mo, nx


@app.cell(hide_code=True)
def init_data(engine):
    df_res, df_gamme, df_client = engine.get_initial_data()
    return df_client, df_gamme, df_res


@app.cell
def ui_components(df_client, df_gamme, df_res, mo):
    ui_res = mo.ui.data_editor(df_res)
    ui_gamme = mo.ui.data_editor(df_gamme)
    ui_client = mo.ui.data_editor(df_client)
    mo.ui.tabs({"🏭 Ressources": ui_res, "📋 Gamme": ui_gamme, "🎯 Client": ui_client})
    return ui_client, ui_gamme, ui_res


@app.cell(hide_code=True)
def logic_engine(engine, ui_gamme, ui_res):
    df_cf = engine.compute_cotes(ui_gamme.value, ui_res.value)
    G = engine.build_graph(df_cf)
    return G, df_cf


@app.cell(hide_code=True)
def ui_analysis(G, mo, nx, ui_client):
    failing_paths = []
    results_ui = []

    for _, cc_row in ui_client.value.iterrows():
        try:
            path = nx.shortest_path(G, source=cc_row["surf_A"], target=cc_row["surf_B"])
            sum_it = sum(G.get_edge_data(path[i], path[i+1])["it"] for i in range(len(path)-1))
            it_max = float(cc_row["it_max"])
            delta = round(it_max - sum_it, 4)

            if sum_it <= it_max:
                results_ui.append(mo.callout(mo.md(f"**Chemin** : `{' ➔ '.join(path)}`\n\n**IT Cumulé : {round(sum_it, 3)} mm** (Max toléré : {it_max} mm) | Marge : {delta} mm"), kind="success", title=f"✅ {cc_row['id_cc']} : VALIDE"))
            else:
                failing_paths.append(path)
                results_ui.append(mo.callout(mo.md(f"**Chemin** : `{' ➔ '.join(path)}`\n\n**IT Cumulé : {round(sum_it, 3)} mm** (Max toléré : {it_max} mm) | Dépassement : {abs(delta)} mm"), kind="danger", title=f"❌ {cc_row['id_cc']} : INVALIDE"))
        except (nx.NetworkXNoPath, nx.NodeNotFound) as e:
            results_ui.append(mo.callout(mo.md(f"Erreur de résolution de graphe : {e}"), kind="warn", title=f"⚠️ {cc_row['id_cc']}"))

    analysis_output = mo.vstack(results_ui) if results_ui else mo.md("Aucune analyse.")
    analysis_output
    return (failing_paths,)


@app.cell(hide_code=True)
def render_mermaid(G, df_cf, engine, failing_paths, mo):
    flowchart = engine.get_mermaid_flowchart(G, failing_paths)
    sequence = engine.get_mermaid_sequence(df_cf, failing_paths)

    mo.ui.tabs({
        "🕸️ Anselmetti": mo.mermaid(flowchart),
        "⏱️ Séquence": mo.mermaid(sequence),
    })
    return


if __name__ == "__main__":
    app.run()
