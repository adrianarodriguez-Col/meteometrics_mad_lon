from pathlib import Path

import pandas as pd
import requests

url_mad = "https://meteometrics.rlopez.org/historical-data/MAD"
url_lon = "https://meteometrics.rlopez.org/historical-data/LON"

try:
    response_madrid = requests.get(url_mad, timeout=15)
    response_madrid.raise_for_status()
    raw_data_madrid = response_madrid.json()

    response_londres = requests.get(url_lon, timeout=15)
    response_londres.raise_for_status()
    raw_data_londres = response_londres.json()

    df_madrid = pd.json_normalize(raw_data_madrid)
    df_madrid["city"] = "Madrid"

    df_londres = pd.json_normalize(raw_data_londres)
    df_londres["city"] = "Londres"

    df_combinado = pd.concat([df_madrid, df_londres], ignore_index=True)
    registros_iniciales = len(df_combinado)

    columnas_metricas = [
        "metrics.temperature.max",
        "metrics.temperature.avg",
        "metrics.temperature.min",
        "metrics.uv_index_max",
        "metrics.precipitation.avg",
    ]
    columnas_numericas = ["year", "month", *columnas_metricas]

    # 1. Normaliza comas decimales antes de convertir los valores.
    df_combinado[columnas_metricas] = df_combinado[columnas_metricas].replace(
        ",", ".", regex=True
    )

    # 2-3. Convierte todas las columnas numéricas y fuerza errores a nulos.
    df_combinado[columnas_numericas] = df_combinado[columnas_numericas].apply(
        pd.to_numeric, errors="coerce"
    )
    columnas_medicion = [
        "metrics.temperature.max",
        "metrics.temperature.avg",
        "metrics.temperature.min",
        "metrics.precipitation.avg",
    ]
    df_combinado[columnas_medicion] = df_combinado[columnas_medicion].astype(float)

    # 4. Trata el valor centinela como un dato ausente.
    df_combinado[columnas_numericas] = df_combinado[columnas_numericas].replace(
        -999.0, float("nan")
    )

    # 5-6. Conserva un registro por ciudad y mes y ordena cronológicamente.
    df_combinado = df_combinado.drop_duplicates(
        subset=["city", "year", "month"]
    ).sort_values(["city", "year", "month"]).reset_index(drop=True)

    # 7. Convierte Fahrenheit a Celsius e inches a milímetros de forma vectorizada.
    mascara_fahrenheit = df_combinado["metrics.temperature.unit"] == "F"
    columnas_temperatura = [
        "metrics.temperature.max",
        "metrics.temperature.avg",
        "metrics.temperature.min",
    ]
    df_combinado.loc[mascara_fahrenheit, columnas_temperatura] = (
        df_combinado.loc[mascara_fahrenheit, columnas_temperatura] - 32
    ) * 5 / 9
    df_combinado.loc[mascara_fahrenheit, "metrics.temperature.unit"] = "C"

    mascara_inches = df_combinado["metrics.precipitation.unit"] == "inches"
    df_combinado.loc[mascara_inches, "metrics.precipitation.avg"] = (
        df_combinado.loc[mascara_inches, "metrics.precipitation.avg"] * 25.4
    )
    df_combinado.loc[mascara_inches, "metrics.precipitation.unit"] = "mm"

    # Deriva el rango térmico y la lluvia acumulada respetando ciudad y año.
    df_combinado["thermal_range"] = (
        df_combinado["metrics.temperature.max"]
        - df_combinado["metrics.temperature.min"]
    )
    df_combinado["cumulative_rain_year"] = df_combinado.groupby(
        ["city", "year"]
    )["metrics.precipitation.avg"].cumsum()

    # Un índice mayor refleja más calor máximo combinado con menos lluvia.
    df_combinado["kpi.heat_stress_index"] = (
        df_combinado["metrics.temperature.max"]
        / (df_combinado["metrics.precipitation.avg"] + 1)
    )

    # Compara la temperatura media mensual con el historial de cada ciudad.
    temperatura_media = df_combinado["metrics.temperature.avg"]
    media_historica = df_combinado.groupby("city")[
        "metrics.temperature.avg"
    ].transform("mean")
    desviacion_historica = df_combinado.groupby("city")[
        "metrics.temperature.avg"
    ].transform("std")
    df_combinado["kpi.temp_zscore"] = (
        temperatura_media - media_historica
    ) / desviacion_historica

    # Resume el historial completo y los extremos absolutos por año y ciudad.
    resumen_ciudad = df_combinado.groupby("city").agg(
        temperatura_media_historica=("metrics.temperature.avg", "mean"),
        lluvia_total=("metrics.precipitation.avg", "sum"),
    )
    resumen_anual = df_combinado.groupby(["city", "year"]).agg(
        temperatura_maxima_absoluta=("metrics.temperature.max", "max"),
        temperatura_minima_absoluta=("metrics.temperature.min", "min"),
    )

    # Conserva el nombre solicitado para el DataFrame completo.
    df_total = df_combinado

    registros_finales = len(df_combinado)
    registros_borrados = registros_iniciales - registros_finales

    # Crea la carpeta de salida y guarda los tres DataFrames con PyArrow.
    carpeta_data = Path(__file__).resolve().parent / "data"
    carpeta_data.mkdir(parents=True, exist_ok=True)
    df_total.to_parquet(carpeta_data / "df_total.parquet", engine="pyarrow", index=False)
    resumen_ciudad.to_parquet(
        carpeta_data / "resumen_ciudad.parquet", engine="pyarrow", index=True
    )
    resumen_anual.to_parquet(
        carpeta_data / "resumen_anual.parquet", engine="pyarrow", index=True
    )

    # Guarda un resumen junto al script para dejar constancia de la limpieza.
    ruta_informe = Path(__file__).resolve().with_name("informe_limpieza.txt")
    ruta_informe.write_text(
        f"Registros iniciales: {registros_iniciales}\n"
        f"Registros borrados: {registros_borrados}\n"
        f"Registros finales: {registros_finales}\n",
        encoding="utf-8",
    )

    print(df_combinado)
    print(f"Informe de limpieza guardado en: {ruta_informe}")
    print("\nResumen por ciudad:")
    print(resumen_ciudad)
    print("\nResumen anual por ciudad:")
    print(resumen_anual)

except requests.exceptions.RequestException as e:
    print(f"Error en la petición: {e}")