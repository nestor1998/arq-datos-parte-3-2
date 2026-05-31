import streamlit as st
import pandas as pd
import requests
import re
from datetime import datetime, date
import os

LOG_FILE = "log_famosos.txt"


def escribir_log(leidos, procesados, duplicados, errores):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write("\n========================\n")
        f.write(f"Fecha y hora: {datetime.now()}\n")
        f.write(f"Registros leídos: {leidos}\n")
        f.write(f"Registros procesados: {procesados}\n")
        f.write(f"Duplicados eliminados: {duplicados}\n")
        f.write(f"Errores: {errores}\n")


def leer_txt(archivo):
    contenido = archivo.read().decode("utf-8", errors="ignore")
    lineas = [linea.strip() for linea in contenido.splitlines() if linea.strip()]

    datos = []

    for linea in lineas:
        linea = re.sub(r"^\d+\.\s*", "", linea)

        if " - " in linea:
            partes = linea.split(" - ", 1)
            nombre = partes[0].strip()
            fecha = partes[1].strip()

            datos.append({
                "nombre": nombre,
                "fecha_original": fecha
            })

    return pd.DataFrame(datos)


def calcular_edad_desde_fecha(fecha_nacimiento):
    hoy = date.today()
    edad = hoy.year - fecha_nacimiento.year

    if (hoy.month, hoy.day) < (fecha_nacimiento.month, fecha_nacimiento.day):
        edad -= 1

    return edad


def procesar_fecha(fecha_texto):
    texto = fecha_texto.strip().lower()

    if "a.c" in texto or "a.c." in texto:
        numeros = re.findall(r"\d+", texto)

        if len(numeros) >= 3:
            anio = int(numeros[0])
            mes = int(numeros[1])
            dia = int(numeros[2])

            return {
                "fecha_normalizada": f"{anio:04d}-{mes:02d}-{dia:02d} a.C.",
                "edad": date.today().year + anio,
                "tipo_fecha": "Exacta a.C."
            }

        elif len(numeros) == 1:
            anio = int(numeros[0])

            return {
                "fecha_normalizada": f"{anio:04d}-01-01 a.C.",
                "edad": date.today().year + anio,
                "tipo_fecha": "Aproximada a.C."
            }

    if "alrededor" in texto:
        numeros = re.findall(r"\d+", texto)

        if numeros:
            anio = int(numeros[0])

            return {
                "fecha_normalizada": f"{anio:04d}-01-01",
                "edad": date.today().year - anio,
                "tipo_fecha": "Aproximada"
            }

    formatos = [
        "%Y/%m/%d",
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y"
    ]

    for formato in formatos:
        try:
            fecha = datetime.strptime(fecha_texto, formato).date()

            return {
                "fecha_normalizada": fecha.strftime("%Y-%m-%d"),
                "edad": calcular_edad_desde_fecha(fecha),
                "tipo_fecha": "Exacta"
            }

        except:
            pass

    return {
        "fecha_normalizada": "No válida",
        "edad": None,
        "tipo_fecha": "Error"
    }


def obtener_imagen_wikipedia(nombre):
    if "cache_imagenes" not in st.session_state:
        st.session_state["cache_imagenes"] = {}

    if nombre in st.session_state["cache_imagenes"]:
        return st.session_state["cache_imagenes"][nombre]

    headers = {
        "User-Agent": "ProyectoFamososStreamlit/1.0"
    }

    try:
        search_url = "https://en.wikipedia.org/w/api.php"

        params = {
            "action": "query",
            "list": "search",
            "srsearch": nombre,
            "format": "json",
            "utf8": 1
        }

        respuesta = requests.get(search_url, params=params, headers=headers, timeout=10)
        data = respuesta.json()

        if "query" not in data or len(data["query"]["search"]) == 0:
            resultado = {
                "imagen_url": "",
                "fuente_imagen": "No encontrada",
                "fecha_captura": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            }

            st.session_state["cache_imagenes"][nombre] = resultado
            return resultado

        titulo = data["query"]["search"][0]["title"]

        summary_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{titulo.replace(' ', '_')}"

        respuesta_summary = requests.get(summary_url, headers=headers, timeout=10)
        data_summary = respuesta_summary.json()

        imagen = ""

        if "originalimage" in data_summary:
            imagen = data_summary["originalimage"]["source"]
        elif "thumbnail" in data_summary:
            imagen = data_summary["thumbnail"]["source"]

        fuente = data_summary.get("content_urls", {}).get("desktop", {}).get(
            "page",
            f"https://en.wikipedia.org/wiki/{titulo.replace(' ', '_')}"
        )

        resultado = {
            "imagen_url": imagen,
            "fuente_imagen": fuente,
            "fecha_captura": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        st.session_state["cache_imagenes"][nombre] = resultado
        return resultado

    except Exception as e:
        resultado = {
            "imagen_url": "",
            "fuente_imagen": f"Error al consultar API: {e}",
            "fecha_captura": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }

        st.session_state["cache_imagenes"][nombre] = resultado
        return resultado


def procesar_famosos(df):
    antes = len(df)

    df = df.drop_duplicates(subset=["nombre"])
    duplicados = antes - len(df)

    resultados = []
    errores = 0

    for _, row in df.iterrows():
        nombre = row["nombre"]
        fecha_original = row["fecha_original"]

        datos_fecha = procesar_fecha(fecha_original)

        if datos_fecha["tipo_fecha"] == "Error":
            errores += 1

        resultados.append({
            "nombre": nombre,
            "fecha_original": fecha_original,
            "fecha_normalizada": datos_fecha["fecha_normalizada"],
            "edad": datos_fecha["edad"],
            "tipo_fecha": datos_fecha["tipo_fecha"]
        })

    df_resultado = pd.DataFrame(resultados)

    if not df_resultado.empty:
        df_resultado = df_resultado.sort_values("nombre").reset_index(drop=True)

    return df_resultado, duplicados, errores


st.set_page_config(page_title="Famosos y Fechas", layout="wide")

st.title("Sistema de Fechas de Nacimiento de Famosos")

st.info("Sube un archivo TXT con famosos y fechas de nacimiento.")

archivo = st.file_uploader(
    "Cargar archivo TXT de famosos",
    type=["txt"]
)

if archivo is not None:
    if st.button("Procesar archivo"):
        df_original = leer_txt(archivo)
        df_procesado, duplicados, errores = procesar_famosos(df_original)

        st.session_state["df_famosos"] = df_procesado
        st.session_state["leidos"] = len(df_original)
        st.session_state["duplicados"] = duplicados
        st.session_state["errores"] = errores

        escribir_log(
            len(df_original),
            len(df_procesado),
            duplicados,
            errores
        )

        st.success("Archivo procesado correctamente.")


if "df_famosos" in st.session_state:
    df = st.session_state["df_famosos"]

    st.subheader("Resumen del proceso")

    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Registros leídos", st.session_state["leidos"])
    col2.metric("Procesados", len(df))
    col3.metric("Duplicados eliminados", st.session_state["duplicados"])
    col4.metric("Errores", st.session_state["errores"])

    st.subheader("Lista de famosos procesados")

    buscar = st.text_input("Buscar famoso:")

    df_mostrar = df.copy()

    if buscar:
        df_mostrar = df_mostrar[
            df_mostrar["nombre"].str.contains(buscar, case=False, na=False)
        ]

    df_mostrar = df_mostrar.sort_values("nombre").reset_index(drop=True)
    df_mostrar.index = range(1, len(df_mostrar) + 1)

    st.dataframe(df_mostrar, use_container_width=True)

    st.subheader("Seleccionar famoso para ver imagen")

    famoso = st.selectbox(
        "Selecciona un famoso:",
        df["nombre"].tolist()
    )

    if famoso:
        fila = df[df["nombre"] == famoso].iloc[0]

        st.write(f"Nombre: {fila['nombre']}")
        st.write(f"Fecha de nacimiento: {fila['fecha_normalizada']}")
        st.write(f"Edad: {fila['edad']}")

        if st.button("Ver imagen"):
            imagen_data = obtener_imagen_wikipedia(famoso)

            st.session_state["imagen_actual"] = imagen_data
            st.session_state["famoso_actual"] = famoso

        if (
            "imagen_actual" in st.session_state
            and "famoso_actual" in st.session_state
            and st.session_state["famoso_actual"] == famoso
        ):
            imagen_data = st.session_state["imagen_actual"]

            if imagen_data["imagen_url"]:
                st.write("Imagen:")
                st.image(
                    imagen_data["imagen_url"],
                    width=350
                )

                st.write(f"Fuente de imagen: {imagen_data['fuente_imagen']}")
                st.write(f"Fecha de captura desde API: {imagen_data['fecha_captura']}")
            else:
                st.warning("No se encontró imagen para este famoso.")
                st.write(f"Detalle: {imagen_data['fuente_imagen']}")

    st.subheader("Descargas")

    txt_salida = df.to_string(index=False)

    st.download_button(
        label="Descargar TXT procesado",
        data=txt_salida,
        file_name="famosos_procesados.txt",
        mime="text/plain"
    )

    csv_salida = df.to_csv(index=False, encoding="utf-8-sig")




if os.path.exists(LOG_FILE):
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        contenido_log = f.read()

    st.download_button(
        label="Descargar log",
        data=contenido_log,
        file_name="log_famosos.txt",
        mime="text/plain"
    )

    with st.expander("Ver log"):
        st.text(contenido_log)