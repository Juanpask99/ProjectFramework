import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid

# --- CONFIGURACIÓN DE PÁGINA ---
st.set_page_config(page_title="Project Tracker GSheets", layout="wide", page_icon="🚀")

# --- CONEXIÓN A GOOGLE SHEETS ---
@st.cache_resource
def conectar_google_sheets():
    # Definir el alcance de la API
    scope = ['https://www.googleapis.com/auth/spreadsheets', 'https://www.googleapis.com/auth/drive']
    
    # Cargar credenciales desde st.secrets
    creds_dict = dict(st.secrets["gcp_service_account"])
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
    
    # Autorizar cliente
    client = gspread.authorize(creds)
    return client

def cargar_datos():
    try:
        client = conectar_google_sheets()
        # REEMPLAZA "GestionProyecto" CON EL NOMBRE EXACTO DE TU HOJA EN GOOGLE
        sheet = client.open("ProjectFramework").sheet1 
        data = sheet.get_all_records()
        
        # Si la hoja está vacía, devolvemos estructura básica
        if not data:
            return pd.DataFrame(columns=["id", "titulo", "responsable", "estado", "esfuerzo"])
            
        return pd.DataFrame(data)
    except Exception as e:
        st.error(f"Error al conectar con Google Sheets: {e}")
        return pd.DataFrame()

def actualizar_tarea(id_tarea, nueva_columna, nuevo_valor):
    client = conectar_google_sheets()
    sheet = client.open("GestionProyecto").sheet1
    
    # Buscar la fila (gspread usa índice 1-based)
    # Asumimos que la columna 'id' está en la columna A (1)
    cell = sheet.find(str(id_tarea))
    
    # Mapeo de nombres de columna a índices numéricos
    # Ajusta estos índices según el orden de tus columnas en Sheets
    col_map = {"titulo": 2, "responsable": 3, "estado": 4, "esfuerzo": 5}
    
    if cell:
        sheet.update_cell(cell.row, col_map[nueva_columna], nuevo_valor)
        st.cache_data.clear() # Limpiar caché para refrescar

def crear_tarea(titulo, responsable, esfuerzo):
    client = conectar_google_sheets()
    sheet = client.open("GestionProyecto").sheet1
    nuevo_id = str(uuid.uuid4())[:8]
    # Asegúrate que el orden coincida con tus columnas en Sheets
    fila = [nuevo_id, titulo, responsable, "Por Hacer", esfuerzo] 
    sheet.append_row(fila)

# --- INTERFAZ DE USUARIO ---

# Cargar datos al inicio
df = cargar_datos()

# Barra lateral para añadir tareas
with st.sidebar:
    st.header("⚡ Nueva Tarea")
    with st.form("add_task_form"):
        new_title = st.text_input("Título")
        new_resp = st.selectbox("Responsable", ["Ana", "Carlos", "Luis", "Sofía"])
        new_effort = st.slider("Puntos de Esfuerzo", 1, 13, 5)
        submitted = st.form_submit_button("Añadir al Tablero")
        if submitted and new_title:
            crear_tarea(new_title, new_resp, new_effort)
            st.success("Tarea creada!")
            st.rerun()

# Navegación Superior
tab1, tab2 = st.tabs(["📋 Tablero Kanban", "📊 Dashboard de Impacto"])

# --- VISTA 1: KANBAN ---
with tab1:
    st.subheader("Flujo de Trabajo en Tiempo Real")
    
    col1, col2, col3 = st.columns(3)
    columnas_kanban = {
        "Por Hacer": (col1, "🔴"),
        "En Progreso": (col2, "🟡"),
        "Hecho": (col3, "🟢")
    }

    if not df.empty:
        for estado, (col_obj, icono) in columnas_kanban.items():
            with col_obj:
                st.markdown(f"### {icono} {estado}")
                st.markdown("---")
                tareas_filtradas = df[df['estado'] == estado]
                
                for i, row in tareas_filtradas.iterrows():
                    with st.container(border=True):
                        st.markdown(f"**{row['titulo']}**")
                        st.caption(f"👤 {row['responsable']} | ⚙️ {row['esfuerzo']} pts")
                        
                        # Botones de Acción (Mover Izquierda / Derecha)
                        c_izq, c_der = st.columns([1, 1])
                        
                        if estado == "Por Hacer":
                            if c_der.button("➡", key=f"next_{row['id']}"):
                                actualizar_tarea(row['id'], "estado", "En Progreso")
                                st.rerun()
                        
                        elif estado == "En Progreso":
                            if c_izq.button("⬅", key=f"prev_{row['id']}"):
                                actualizar_tarea(row['id'], "estado", "Por Hacer")
                                st.rerun()
                            if c_der.button("✅", key=f"fin_{row['id']}"):
                                actualizar_tarea(row['id'], "estado", "Hecho")
                                st.rerun()
                                
                        elif estado == "Hecho":
                            if c_izq.button("↩", key=f"back_{row['id']}"):
                                actualizar_tarea(row['id'], "estado", "En Progreso")
                                st.rerun()

# --- VISTA 2: DASHBOARD ---
with tab2:
    if not df.empty:
        st.title("Métricas de Rendimiento")
        
        # Métricas "Big Number"
        total_esfuerzo = df['esfuerzo'].sum()
        hecho_esfuerzo = df[df['estado'] == 'Hecho']['esfuerzo'].sum()
        avance = (hecho_esfuerzo / total_esfuerzo * 100) if total_esfuerzo > 0 else 0
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Progreso del Proyecto", f"{avance:.1f}%", delta=f"{hecho_esfuerzo} pts completados")
        kpi2.metric("Tareas Pendientes", len(df[df['estado'] != 'Hecho']), delta="Backlog activo", delta_color="inverse")
        kpi3.metric("Carga Total (Puntos)", total_esfuerzo)
        
        st.divider()
        
        # Gráficos de Impacto
        g1, g2 = st.columns(2)
        
        with g1:
            st.markdown("##### 🧱 Carga de Trabajo por Persona")
            # Gráfico de barras horizontal limpio
            fig_bar = px.bar(df, x="esfuerzo", y="responsable", color="estado", orientation='h',
                             title="Distribución de Esfuerzo", text_auto=True,
                             color_discrete_map={"Por Hacer": "#ff7f7f", "En Progreso": "#f4d35e", "Hecho": "#90ee90"})
            st.plotly_chart(fig_bar, use_container_width=True)
            
        with g2:
            st.markdown("##### 🍩 Estado General")
            # Donut Chart elegante
            fig_pie = px.pie(df, names="estado", values="esfuerzo", hole=0.5,
                             color="estado",
                             color_discrete_map={"Por Hacer": "#ff7f7f", "En Progreso": "#f4d35e", "Hecho": "#90ee90"})
            fig_pie.update_traces(textposition='inside', textinfo='percent+label')
            st.plotly_chart(fig_pie, use_container_width=True)
            
    else:
        st.warning("No hay datos en la hoja de cálculo todavía. ¡Añade una tarea en la barra lateral!")