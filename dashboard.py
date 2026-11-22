from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots


st.set_page_config(
    page_title="Clima de Madrid y Londres",
    page_icon="🌦️",
    layout="wide",
)

CARPETA_DATA = Path(__file__).resolve().parent / "data"
RUTA_DATOS = CARPETA_DATA / "df_total.parquet"
COLORES = {"Madrid": "#d62728", "Londres": "#1f77b4"}
MESES = [
    "Ene", "Feb", "Mar", "Abr", "May", "Jun",
    "Jul", "Ago", "Sep", "Oct", "Nov", "Dic",
]


@st.cache_data
def cargar_datos(ruta: str) -> pd.DataFrame:
    """Carga el histórico meteorológico almacenado en formato Parquet."""
    return pd.read_parquet(ruta, engine="pyarrow")


st.title("Madrid y Londres: comparación climática")
st.markdown(
    "Explora la evolución histórica de las temperaturas y el perfil mensual "
    "de temperatura y precipitación de ambas ciudades."
)

if not RUTA_DATOS.is_file():
    st.error(
        f"No se encuentra {RUTA_DATOS}. Ejecuta primero `app.py` para generar "
        "los datos Parquet."
    )
    st.stop()

df_total = cargar_datos(str(RUTA_DATOS))
ciudades = ["Madrid", "Londres"]
datos = df_total[df_total["city"].isin(ciudades)].copy()

if datos.empty:
    st.error("El fichero Parquet no contiene datos de Madrid ni de Londres.")
    st.stop()

datos["fecha"] = pd.to_datetime(
    dict(year=datos["year"], month=datos["month"], day=1),
    errors="coerce",
)

# Presenta primero una instantánea histórica antes de las visualizaciones.
st.header("Resumen instantáneo")
resumen_ciudad = datos.groupby("city").agg(
    temperatura_media=("metrics.temperature.avg", "mean"),
    lluvia_total=("metrics.precipitation.avg", "sum"),
    registros=("month", "size"),
)
col_madrid, col_londres = st.columns(2)
for columna, ciudad in ((col_madrid, "Madrid"), (col_londres, "Londres")):
    if ciudad not in resumen_ciudad.index:
        columna.warning(f"No hay registros disponibles para {ciudad}.")
        continue
    resumen = resumen_ciudad.loc[ciudad]
    columna.metric(
        f"{ciudad} · temperatura media histórica",
        f"{resumen['temperatura_media']:.1f} °C",
    )
    columna.metric(
        f"{ciudad} · precipitación acumulada",
        f"{resumen['lluvia_total']:,.0f} mm",
    )
    columna.caption(f"{int(resumen['registros'])} registros mensuales")

if datos["fecha"].notna().any():
    st.caption(
        "Periodo de los datos: "
        f"{datos['fecha'].min():%m/%Y} – {datos['fecha'].max():%m/%Y}."
    )

# La banda muestra el rango mensual y la media como línea central.
st.header("Evolución de temperaturas · rango histórico mensual")
fig_evolucion = go.Figure()
for ciudad, color in COLORES.items():
    serie = (
        datos.loc[datos["city"] == ciudad]
        .dropna(
            subset=[
                "fecha",
                "metrics.temperature.min",
                "metrics.temperature.avg",
                "metrics.temperature.max",
            ]
        )
        .sort_values("fecha")
    )
    if serie.empty:
        continue

    fig_evolucion.add_trace(
        go.Scatter(
            x=serie["fecha"],
            y=serie["metrics.temperature.min"],
            mode="lines",
            line={"width": 0},
            showlegend=False,
            hoverinfo="skip",
            legendgroup=ciudad,
        )
    )
    fig_evolucion.add_trace(
        go.Scatter(
            x=serie["fecha"],
            y=serie["metrics.temperature.max"],
            mode="lines",
            line={"width": 0},
            fill="tonexty",
            fillcolor=(
                "rgba(214, 39, 40, 0.16)"
                if ciudad == "Madrid"
                else "rgba(31, 119, 180, 0.16)"
            ),
            name=f"{ciudad} · rango mín.–máx.",
            hovertemplate="%{x|%b %Y}<br>Máxima: %{y:.1f} °C<extra>"
            f"{ciudad}</extra>",
            legendgroup=ciudad,
        )
    )
    fig_evolucion.add_trace(
        go.Scatter(
            x=serie["fecha"],
            y=serie["metrics.temperature.avg"],
            mode="lines",
            line={"color": color, "width": 2.5},
            name=f"{ciudad} · media",
            hovertemplate="%{x|%b %Y}<br>Media: %{y:.1f} °C<extra>"
            f"{ciudad}</extra>",
            legendgroup=ciudad,
        )
    )

fig_evolucion.update_layout(
    height=500,
    hovermode="x unified",
    xaxis_title="Mes",
    yaxis_title="Temperatura (°C)",
    legend_title="Ciudad",
    margin={"t": 25, "r": 20, "b": 35, "l": 20},
)
st.plotly_chart(fig_evolucion, width="stretch")

medias_ciudad = resumen_ciudad["temperatura_media"]
if {"Madrid", "Londres"}.issubset(medias_ciudad.index):
    diferencia_temperatura = medias_ciudad["Madrid"] - medias_ciudad["Londres"]
    ciudad_mas_calida = "Madrid" if diferencia_temperatura > 0 else "Londres"
    st.markdown(
        "**Interpretación:** La línea central representa la temperatura media "
        "mensual y la banda, el intervalo entre las temperaturas mínima y "
        "máxima. En este histórico, "
        f"{ciudad_mas_calida} tiene una media superior por "
        f"{abs(diferencia_temperatura):.1f} °C. La amplitud de cada banda ayuda "
        "a identificar los meses con mayor oscilación térmica."
    )
else:
    st.markdown(
        "**Interpretación:** Las bandas muestran el rango mensual entre "
        "mínimas y máximas; las líneas muestran las medias. Se necesitan "
        "datos de ambas ciudades para compararlas."
    )

# Usa dos radares para que temperatura y lluvia mantengan sus propias unidades.
st.header("Perfil climático mensual · radar")
perfil_mensual = (
    datos.groupby(["city", "month"], as_index=False)
    .agg(
        temperatura_media=("metrics.temperature.avg", "mean"),
        precipitacion_media=("metrics.precipitation.avg", "mean"),
    )
)
fig_radar = make_subplots(
    rows=1,
    cols=2,
    specs=[[{"type": "polar"}, {"type": "polar"}]],
    subplot_titles=("Temperatura media (°C)", "Precipitación media (mm)"),
)
for ciudad, color in COLORES.items():
    perfil = (
        perfil_mensual[perfil_mensual["city"] == ciudad]
        .set_index("month")
        .reindex(range(1, 13))
    )
    meses_cerrados = MESES + [MESES[0]]
    temperaturas = perfil["temperatura_media"].tolist()
    precipitaciones = perfil["precipitacion_media"].tolist()
    fig_radar.add_trace(
        go.Scatterpolar(
            r=temperaturas + temperaturas[:1],
            theta=meses_cerrados,
            mode="lines+markers",
            line={"color": color, "width": 2},
            name=ciudad,
            legendgroup=ciudad,
            connectgaps=False,
            hovertemplate="%{theta}<br>%{r:.1f} °C<extra>" f"{ciudad}</extra>",
        ),
        row=1,
        col=1,
    )
    fig_radar.add_trace(
        go.Scatterpolar(
            r=precipitaciones + precipitaciones[:1],
            theta=meses_cerrados,
            mode="lines+markers",
            line={"color": color, "width": 2},
            name=ciudad,
            legendgroup=ciudad,
            showlegend=False,
            connectgaps=False,
            hovertemplate="%{theta}<br>%{r:.1f} mm<extra>" f"{ciudad}</extra>",
        ),
        row=1,
        col=2,
    )

fig_radar.update_layout(
    height=520,
    margin={"t": 65, "r": 45, "b": 25, "l": 45},
    legend_title="Ciudad",
)
st.plotly_chart(fig_radar, width="stretch")

if {"Madrid", "Londres"}.issubset(medias_ciudad.index):
    mensual_precipitacion = perfil_mensual.groupby("city")[
        "precipitacion_media"
    ].mean()
    ciudad_mas_lluviosa = (
        "Madrid"
        if mensual_precipitacion.get("Madrid", 0)
        > mensual_precipitacion.get("Londres", 0)
        else "Londres"
    )
    mes_mas_calido = (
        perfil_mensual.loc[
            perfil_mensual.groupby("city")["temperatura_media"].idxmax()
        ][["city", "month"]]
        .set_index("city")["month"]
        .to_dict()
    )
    detalle_mes = ", ".join(
        f"{ciudad} en {MESES[int(mes) - 1]}"
        for ciudad, mes in mes_mas_calido.items()
        if pd.notna(mes)
    )
    diferencia_lluvia = abs(
        mensual_precipitacion.get("Madrid", 0)
        - mensual_precipitacion.get("Londres", 0)
    )
    st.markdown(
        "**Interpretación:** El radar de la izquierda compara la temperatura "
        "media de cada mes y el de la derecha la precipitación media mensual; "
        "separarlos evita mezclar escalas distintas. Los meses más cálidos "
        f"del histórico son {detalle_mes}. En promedio mensual, "
        f"{ciudad_mas_lluviosa} registra más precipitación, con una diferencia "
        f"de {diferencia_lluvia:.1f} mm."
    )
else:
    st.markdown(
        "**Interpretación:** Cada radar muestra la evolución de los 12 meses "
        "para la variable indicada. Se necesitan datos de ambas ciudades para "
        "comparar sus perfiles."
    )
