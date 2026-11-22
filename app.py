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

    registros_finales = len(df_combinado)
    registros_borrados = registros_iniciales - registros_finales

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

except requests.exceptions.RequestException as e:
    print(f"Error en la petición: {e}")