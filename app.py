import streamlit as st
import pandas as pd
import plotly.express as px
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import uuid

# --- 1. CONFIGURACIÓN DE PÁGINA (Debe ser lo primero) ---
st.set_page_config(page_title="Project Tracker Pro", layout="wide", page_icon="🚀")

# --- 2. SISTEMA DE LOGIN ---
def check_password():
    """Retorna `True` si el usuario tiene la contraseña correcta."""

    def password_entered():
        """Chequea si la contraseña ingresada es correcta."""
        if st.session_state["username"] in st.secrets["passwords"] and \
           st.session_state["password"] == st.secrets["passwords"][st.session_state["username"]]:
            st.session_state["password_correct"] = True
            # No guardamos la contraseña en session_state por seguridad
            del st.session_state["password"]  
        else:
            st.session_state["password_correct"] = False

    # Si ya validó correctamente, retornar True
    if st.session_state.get("password_correct", False):
        return True

    # Interfaz de Login
    col1, col2, col3 = st.columns([1,2,1])
    with col2:
        st.title("🔒 Acceso Restringido")
        st.markdown("Por favor, inicia sesión para acceder al tablero de gestión.")
        st.text_input("Usuario", key="username")
        st.text_input("Contraseña", type="password", on_change=password_entered, key="password")

        if "password_correct" in st.session_state:
            st.error("😕 Usuario o contraseña incorrectos")

    return False

# --- 3. APLICACIÓN PRINCIPAL (Protegida) ---
if check_password():

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
            # NOMBRE DE TU HOJA EN GOOGLE (Asegúrate que coincida)
            sheet = client.open("GestionProyecto").sheet1 
            data = sheet.get_all_records()
            
            if not data:
                return pd.DataFrame(columns=["id", "titulo", "responsable", "estado", "esfuerzo"])
                
            return pd.DataFrame(data)
        except Exception as e:
            st.error(f"Error al conectar con Google Sheets: {e}")
            return pd.DataFrame()

    def actualizar_tarea(id_tarea, nueva_columna, nuevo_valor):
        client = conectar_google_sheets()
        sheet = client.open("GestionProyecto").sheet1
        
        # Buscar la celda por ID
        cell = sheet.find(str(id_tarea))
        
        # Mapeo de columnas (Ajusta los índices si cambias el orden en Sheets)
        # id=1, titulo=2, responsable=3, estado=4, esfuerzo=5
        col_map = {"titulo": 2, "responsable": 3, "estado": 4, "esfuerzo": 5}
        
        if cell:
            sheet.update_cell(cell.row, col_map[nueva_columna], nuevo_valor)
            st.cache_data.clear() # Limpiar caché

    def crear_tarea(titulo, responsable, esfuerzo):
        client = conectar_google_sheets()
        sheet = client.open("GestionProyecto").sheet1
        nuevo_id = str(uuid.uuid4())[:8]
        fila = [nuevo_id, titulo, responsable, "Por Hacer", esfuerzo] 
        sheet.append_row(fila)
        st.cache_data.clear()

    # --- INTERFAZ DE USUARIO ---

    # Cargar datos
    df = cargar_datos()

    # Barra lateral (Sidebar)
    with st.sidebar:
        st.write(f"Hola, *{st.session_state['username']}* 👋")
        st.divider()
        st.header("⚡ Nueva Tarea")
        with st.form("add_task_form"):
            new_title = st.text_input("Título de la tarea")
            new_resp = st.selectbox("Responsable", ["Ana", "Carlos", "Luis", "Sofía", "Equipo"])
            new_effort = st.slider("Puntos de Esfuerzo", 1, 13, 5)
            submitted = st.form_submit_button("Añadir al Tablero")
            if submitted and new_title:
                crear_tarea(new_title, new_resp, new_effort)
                st.success("Tarea creada!")
                st.rerun()
                
        if st.button("Cerrar Sesión"):
            del st.session_state["password_correct"]
            st.rerun()

    # Título Principal
    st.title("🚀 Gestión de Proyectos")

    # Tabs de Navegación
    tab1, tab2 = st.tabs(["📋 Tablero Kanban", "📊 Dashboard de Impacto"])

    # --- VISTA 1: KANBAN ---
    with tab1:
        st.subheader("Flujo de Trabajo")
        
        col1, col2, col3 = st.columns(3)
        columnas_kanban = {
            "Por Hacer": (col1, "🔴", "#ffe6e6"),
            "En Progreso": (col2, "🟡", "#fff9c4"),
            "Hecho": (col3, "🟢", "#e8f5e9")
        }

        if not df.empty:
            for estado, (col_obj, icono, color_bg) in columnas_kanban.items():
                with col_obj:
                    st.markdown(f"<h3 style='text-align: center;'>{icono} {estado}</h3>", unsafe_allow_html=True)
                    st.markdown("---")
                    tareas_filtradas = df[df['estado'] == estado]
                    
                    for i, row in tareas_filtradas.iterrows():
                        # Tarjeta visual
                        with st.container(border=True):
                            st.markdown(f"**{row['titulo']}**")
                            st.caption(f"👤 {row['responsable']} | ⚙️ {row['esfuerzo']} pts")
                            
                            # Botones de Acción
                            c_izq, c_der = st.columns([1, 1])
                            
                            if estado == "Por Hacer":
                                if c_der.button("➡ Mover", key=f"next_{row['id']}"):
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
                                if c_izq.button("↩ Retomar", key=f"back_{row['id']}"):
                                    actualizar_tarea(row['id'], "estado", "En Progreso")
                                    st.rerun()
        else:
            st.info("No hay tareas aún. Usa la barra lateral para crear la primera.")

    # --- VISTA 2: DASHBOARD ---
    with tab2:
        if not df.empty:
            st.subheader("Métricas de Rendimiento")
            
            # KPIs Principales
            total_esfuerzo = df['esfuerzo'].sum()
            hecho_esfuerzo = df[df['estado'] == 'Hecho']['esfuerzo'].sum()
            avance = (hecho_esfuerzo / total_esfuerzo * 100) if total_esfuerzo > 0 else 0
            pendientes = len(df[df['estado'] != 'Hecho'])

            k1, k2, k3, k4 = st.columns(4)
            k1.metric("Progreso Global", f"{avance:.1f}%")
            k2.metric("Puntos Completados", hecho_esfuerzo)
            k3.metric("Tareas Pendientes", pendientes, delta_color="inverse")
            k4.metric("Carga Total", total_esfuerzo)
            
            st.divider()
            
            # Gráficos de Impacto
            g1, g2 = st.columns(2)
            
            with g1:
                st.markdown("##### 🧱 Carga de Trabajo por Responsable")
                fig_bar = px.bar(df, x="esfuerzo", y="responsable", color="estado", orientation='h',
                                 text_auto=True,
                                 color_discrete_map={"Por Hacer": "#ef553b", "En Progreso": "#fca311", "Hecho": "#00cc96"})
                st.plotly_chart(fig_bar, use_container_width=True)
                
            with g2:
                st.markdown("##### 🍩 Estado del Proyecto")
                fig_pie = px.pie(df, names="estado", values="esfuerzo", hole=0.5,
                                 color="estado",
                                 color_discrete_map={"Por Hacer": "#ef553b", "En Progreso": "#fca311", "Hecho": "#00cc96"})
                fig_pie.update_traces(textposition='inside', textinfo='percent+label')
                st.plotly_chart(fig_pie, use_container_width=True)
                
        else:
            st.warning("Añade datos para ver los gráficos.")
