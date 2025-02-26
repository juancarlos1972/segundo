import os.path
import base64
import json
import smtplib
import ssl
import random
import string
from datetime import date
import google.auth
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import streamlit as st
import time
import openai  # Importante

# Si modificas estos SCOPES, borra el archivo token.json
SCOPES = ['https://www.googleapis.com/auth/gmail.send']

# *** CONFIGURACIÓN DE OPENAI (REEMPLAZAR CON TU CLAVE REAL) ***
#openai.api_key = ""   Reemplaza con tu API key real

# *** FUNCIONES AUXILIARES (Gmail, JSON, etc.) ***
def obtener_credenciales():
    """Obtiene las credenciales para acceder a la API de Gmail."""
    creds = None
    if os.path.exists('token.json'):
        with open('token.json', 'r') as token:
            creds_info = json.load(token)
            creds = google.oauth2.credentials.Credentials.from_authorized_user_info(creds_info, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return creds

def enviar_correo_con_asunto_cuerpo(destinatario, asunto, cuerpo):
    """Envia un correo electrónico con un asunto y cuerpo especificados. Usado para notificaciones de registro."""
    creds = obtener_credenciales()
    try:
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEMultipart()
        message['to'] = destinatario
        message['subject'] = asunto

        message.attach(MIMEText(cuerpo, "plain"))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        mensaje_creado = {'raw': raw}
        mensaje_enviado = service.users().messages().send(userId="me", body=mensaje_creado).execute()
        return True  # Correo electrónico enviado exitosamente
    except HttpError as error:
        st.error(f"No se pudo enviar el correo electrónico: {error}")
        return False # Fallo al enviar el correo electrónico

def enviar_correo_creacion_grupo(destinatario, id_grupo, fecha_evento, fecha_max_inscripcion, presupuesto, aficiones, participantes):
    """Envia un correo electrónico cuando se crea un nuevo grupo."""
    creds = obtener_credenciales()
    try:
        service = build('gmail', 'v1', credentials=creds)
        message = MIMEMultipart()
        message['to'] = destinatario
        message['subject'] = "ID del Grupo Creado"

        # Crear el cuerpo del mensaje
        cuerpo = (
            f"Hola,\n\n"
            f"Se ha creado un nuevo grupo de juego con los siguientes detalles:\n\n"
            f"ID del Grupo: {id_grupo}\n"
            f"Fecha del Evento: {fecha_evento}\n"
            f"Fecha Máxima para Inscribirse: {fecha_max_inscripcion}\n"
            f"Presupuesto: {presupuesto} euros\n"
            f"Aficiones: {aficiones}\n\n"
            f"Participantes:\n"
        )
        for participante in participantes:
            cuerpo += f"- {participante}\n"

        cuerpo += "\nSaludos."

        message.attach(MIMEText(cuerpo, "plain"))
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
        mensaje_creado = {'raw': raw}
        mensaje_enviado = service.users().messages().send(userId="me", body=mensaje_creado).execute()
        #st.success(f"Correo electrónico enviado al organizador con el ID del grupo: {mensaje_enviado}")  <-- Eliminamos esta línea
        return True  # Indica que el correo se envió correctamente

    except HttpError as error:
        st.error(f"No se pudo enviar el correo electrónico: {error}")
        return False  # Indica que hubo un error al enviar el correo

# *** INTEGRACIÓN CON OPENAI (GPT) - NUEVA VERSIÓN ***
def obtener_ideas_de_regalo(presupuesto, intereses=None):
    """
    Genera ideas de regalos según un presupuesto y opcionalmente intereses específicos.
    """
    prompt = f"Dame 3 ideas de regalos originales y creativos por un precio máximo de {presupuesto} euros. "
    if intereses:
        prompt += f" La persona tiene interés en {intereses}."
    prompt += "Incluye una breve descripción y un precio aproximado para cada regalo. Formato: - Regalo (Precio): Descripción"

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": "Eres un experto en regalos que siempre da buenas ideas."},
                      {"role": "user", "content": prompt}]
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        print(f"Error al llamar a la API de OpenAI: {e}")
        return "No se pudieron obtener sugerencias de regalos de la IA."


def generar_ideas_regalos(intereses, presupuesto):
    """Genera ideas de regalos basadas en los intereses y el presupuesto, usando OpenAI."""
    # *** OBTENER SUGERENCIAS DE LA IA ***
    sugerencias = obtener_ideas_de_regalo(presupuesto, intereses)

    # Formatear las sugerencias para el correo electrónico
    if sugerencias:
        # Ya vienen formateadas de la IA
        return sugerencias
    else:
        return "No se pudieron obtener sugerencias de regalos."

def realizar_sorteo(id_grupo):
    """Realiza el sorteo del amigo invisible, incluyendo al creador del grupo, guarda el resultado e incluye aficiones/preferencias."""
    try:
        with open("datos.json", "r", encoding='utf-8') as file:
            datos = json.load(file)
    except FileNotFoundError:
        st.error("Error: datos.json no se encuentra.")
        return
    except json.JSONDecodeError:
        st.error("Error: JSON inválido en datos.json.")
        return

    for grupo in datos.get("Grupos de Juego", []):
        if grupo["ID del Grupo"] == id_grupo:
            # ******************** NUEVA VERIFICACIÓN ********************
            if grupo.get("Sorteo Realizado", False):
                st.error("Ya se ha realizado el sorteo para este grupo. Pregunta al administrador del grupo.")
                time.sleep(10)
                st.session_state.page = 'menu'
                st.rerun()
                return
            # *********************************************************

            # Obtener los datos del creador del grupo
            creador = grupo["Detalles del Creador"]
            nombre_creador = creador["Nombre del Creador"]
            email_creador = creador["Email del Creador"]
            aficiones_creador = creador["Aficiones del Creador"]  # Obtener aficiones
            fecha_evento = creador["Fecha del Evento"] # Obtener fecha del evento
            total_presupuesto = creador["Total Presupuesto"] # Obtener presupuesto total

            # Crear una lista de participantes que incluya al creador
            participantes = [{"Nombre de Usuario": nombre_creador, "Email": email_creador, "Aficiones": aficiones_creador}]
            #Añadir participantes registrados.
            for p in grupo.get("Participantes", []):
                participantes.append({"Nombre de Usuario": p["Nombre de Usuario"], "Email": p["Email"], "Preferencias": p["Preferencias"]})

            if len(participantes) < 3:
                st.error("Se necesitan al menos 3 participantes para realizar el sorteo.")
                time.sleep(10)
                st.session_state.page = 'menu'
                st.rerun()
                return

            # Ensure no one is assigned to themselves
            givers = participantes[:]
            receivers = participantes[:]
            random.shuffle(receivers)

            # Ensure no one is assigned to themselves
            while any(giver["Nombre de Usuario"] == receiver["Nombre de Usuario"] for giver, receiver in zip(givers, receivers)):
                random.shuffle(receivers)

            assignments = {}
            for giver, receiver in zip(givers, receivers):
                assignments[giver["Nombre de Usuario"]] = {"regala_a": receiver["Nombre de Usuario"]}

            # Send emails
            errores_envio = False # Bandera para detectar si hubo algun error al enviar los correos
            for giver_name, assignment in assignments.items():
                receiver_name = assignment["regala_a"]
                giver_data = next(p for p in participantes if p["Nombre de Usuario"] == giver_name)
                receiver_data = next(p for p in participantes if p["Nombre de Usuario"] == receiver_name)

                giver_email = giver_data["Email"]
                receiver_email = receiver_data["Email"]

                # Obtener aficiones/preferencias del receptor para el correo
                receiver_interests = receiver_data.get("Aficiones", receiver_data.get("Preferencias", "No especificado"))

                # *** Generar ideas de regalos basadas en IA ***
                # Pasamos el presupuesto TOTAL del grupo, pero podríamos querer pasar un presupuesto individual por participante
                ideas_regalos = generar_ideas_regalos(receiver_interests, total_presupuesto)

                asunto = "Tu Amigo Invisible!"
                cuerpo = (f"Hola {giver_name},\n\n"
                          f"Eres el amigo invisible de: {receiver_name}\n\n"
                          f"Preferencias de {receiver_name}: {receiver_interests}\n\n"
                          f"Algunas ideas para regalarle, según sus gustos e intereses y respetando el presupuesto máximo de {total_presupuesto}€:\n{ideas_regalos}\n\n"
                          f"Fecha del Evento: {fecha_evento}\n"
                          f"Presupuesto Total: {total_presupuesto} euros\n\n"
                          f"¡Recuerda mantenerlo en secreto! 😉")

                if not enviar_correo_con_asunto_cuerpo(giver_email, asunto, cuerpo):
                    errores_envio = True # Si falla el envio, cambia la bandera
                    break # Sale del bucle para no seguir enviando correos si ya hubo un fallo

            # Prepare data for JSON file
            sorteo_data = {
                "Detalles del Grupo": {
                    "ID del Grupo": id_grupo,
                    "Aficiones del Creador": aficiones_creador,
                    "Fecha del Evento": fecha_evento,
                    "Presupuesto Total": total_presupuesto
                },
                "Participantes": []
            }

            for giver_name, assignment in assignments.items():
                receiver_name = assignment["regala_a"]
                giver_data = next(p for p in participantes if p["Nombre de Usuario"] == giver_name)
                receiver_data = next(p for p in participantes if p["Nombre de Usuario"] == receiver_name)

                participant_info = {
                    "Nombre": giver_name,
                    "Regala a": receiver_name,
                    "Aficiones/Preferencias": giver_data.get("Aficiones", giver_data.get("Preferencias", "No especificado"))
                }
                sorteo_data["Participantes"].append(participant_info)

            # Guardar los resultados en el archivo sorteos.json
            guardar_sorteo(id_grupo, sorteo_data)

            # ******************** MARCAR SORTEO COMO REALIZADO ********************
            grupo["Sorteo Realizado"] = True
            with open("datos.json", "w", encoding='utf-8') as file:
                json.dump(datos, file, indent=4, ensure_ascii=False)
            # *********************************************************

            # Mensaje de éxito y redirección al menú
            if not errores_envio: # Si no hubo errores al enviar los correos
              st.success("Sorteo realizado correctamente, suerte a los participantes!", icon="🎉")
            else:
              st.warning("Sorteo realizado, pero hubo errores al enviar algunos correos. Revisa la configuración de Gmail.", icon="⚠️")

            time.sleep(10)
            st.session_state.page = 'menu'
            st.rerun()
            return

    st.error("ID de grupo no encontrado. Por favor, verifica el ID e inténtalo de nuevo.")

def guardar_sorteo(id_grupo, sorteo_data):
    """Guarda los resultados del sorteo en el archivo sorteos.json, agrupados por ID de grupo."""
    filename = "sorteos.json"
    try:
        with open(filename, "r", encoding='utf-8') as file:
            sorteos = json.load(file)
    except FileNotFoundError:
        # Si el archivo no existe, crea un diccionario vacío
        sorteos = {}
    except json.JSONDecodeError:
        # Si el archivo está corrupto, crea un diccionario vacío
        sorteos = {}

    # Agrega o actualiza la información del sorteo para el ID de grupo actual
    sorteos[id_grupo] = sorteo_data

    # Guarda el diccionario actualizado en el archivo
    with open(filename, "w", encoding='utf-8') as file:
        json.dump(sorteos, file, indent=4, ensure_ascii=False)

def main():
    """Función principal de la aplicación."""
    # Crear archivo JSON al inicio
    if not os.path.exists("datos.json"):
        with open("datos.json", "w", encoding='utf-8') as file:
            json.dump({}, file, ensure_ascii=False)

    st.title("Menú Principal")

    if 'page' not in st.session_state:
        st.session_state.page = 'menu'

    if st.session_state.page == 'menu':
        mostrar_menu()
    elif st.session_state.page == 'crear_grupo':
        mostrar_formulario_crear_grupo()
    elif st.session_state.page == 'registrarse_grupo':
        mostrar_formulario_registrarse_grupo()
    elif st.session_state.page == 'ideas_regalar':
        mostrar_formulario_ideas_regalar()
    elif st.session_state.page == 'realizar_sorteo':
        mostrar_formulario_realizar_sorteo()

def mostrar_menu():
    """Muestra el menú principal de la aplicación."""
    if st.button("Crear Grupo de Juego"):
        st.session_state.page = 'crear_grupo'
    if st.button("Registrarse en Grupo Creado"):
        st.session_state.page = 'registrarse_grupo'
    if st.button("Ideas para Regalar"):
        st.session_state.page = 'ideas_regalar'
    if st.button("Realizar Sorteo Amigo Invisible"):
        st.session_state.page = 'realizar_sorteo'

def guardar_datos(data, category):
    """Guarda datos en el archivo JSON."""
    with open("datos.json", "r", encoding='utf-8') as file:
        datos = json.load(file)

    if category not in datos:
        datos[category] = []

    datos[category].append(data)

    with open("datos.json", "w", encoding='utf-8') as file:
        json.dump(datos, file, indent=4, ensure_ascii=False)

def guardar_datos_registro(id_grupo, data):
    """Guarda los datos de registro de un usuario en un grupo existente."""
    try:
        with open("datos.json", "r", encoding='utf-8') as file:
            datos = json.load(file)
    except FileNotFoundError:
        st.error("Error: datos.json no se encuentra.")
        return False
    except json.JSONDecodeError:
        st.error("Error: JSON inválido en datos.json.")
        return False

    # Verificar si el ID del grupo existe
    for grupo in datos.get("Grupos de Juego", []):
        if grupo["ID del Grupo"] == id_grupo:

            # **NUEVA VERIFICACIÓN: Comprobar si el sorteo ya se ha realizado**
            if grupo.get("Sorteo Realizado", False): # Usar .get() para evitar KeyError
                st.error(" lo sentimos no se puede registrar porque el sorteo ya se ha realizado.")
                return False  # No guardar los datos si el sorteo ya se ha realizado

            # **NUEVA VERIFICACIÓN: Verificar si el email ya está registrado (creador y participantes)**
            if grupo["Detalles del Creador"]["Email del Creador"] == data["Email"]:
                st.error("El email ya existe, por favor revise los datos.")
                return False  # No guardar los datos si el email es el mismo que el del creador

            if "Participantes" in grupo:
                for participante in grupo["Participantes"]:
                    if participante["Email"] == data["Email"]:
                        st.error("El email ya existe, por favor revise los datos.")
                        return False  # No guardar los datos si el email ya existe

            # Comprobar si la fecha actual es posterior a la fecha máxima de inscripción
            fecha_max_inscripcion_str = grupo["Fecha Máxima para Inscribirse"]
            fecha_max_inscripcion = date.fromisoformat(fecha_max_inscripcion_str)
            fecha_actual = date.today()

            if fecha_actual > fecha_max_inscripcion:
                st.error("Lo sentimos, la fecha límite para inscribirse en este grupo ha pasado.")
                return False  # No guardar los datos si la fecha ha pasado

            if "Participantes" not in grupo:
                grupo["Participantes"] = []
            grupo["Participantes"].append(data)

            # Enviar email al participante
            asunto_participante = "Registro Exitoso en el Grupo"
            fecha_evento = grupo["Detalles del Creador"]["Fecha del Evento"]
            total_presupuesto = grupo["Detalles del Creador"]["Total Presupuesto"]

            cuerpo_participante = (f"Te has registrado correctamente en el grupo con ID: {id_grupo}.\n"
                      f"Fecha del Evento: {fecha_evento}\n"
                      f"Presupuesto Total: {total_presupuesto} euros")

            if not enviar_correo_con_asunto_cuerpo(data["Email"], asunto_participante, cuerpo_participante):
                 st.error("Registro exitoso, pero hubo un error al enviar el correo electrónico al participante.")
                 return False

            # Enviar email al creador del grupo
            asunto_creador = "Nuevo Participante en tu Grupo"
            cuerpo_creador = (f"Un nuevo participante se ha registrado en tu grupo {id_grupo}:\n"
                              f"Nombre: {data['Nombre de Usuario']}\n"
                              f"Email: {data['Email']}")
            creador_email = grupo["Detalles del Creador"]["Email del Creador"]

            if not enviar_correo_con_asunto_cuerpo(creador_email, asunto_creador, cuerpo_creador):
               st.error(f"Registro exitoso, pero hubo un error al enviar el correo electrónico al creador del grupo.")
               return False

            try:
                with open("datos.json", "w", encoding='utf-8') as file:
                    json.dump(datos, file, indent=4, ensure_ascii=False)
            except Exception as e:
                st.error(f"Error al escribir en datos.json: {e}")
                return False

            st.success("Te has registrado correctamente y se ha enviado el correo electrónico.")
            return True # Registro exitoso

    st.error("ID de grupo no encontrado. Por favor, verifica el ID e inténtalo de nuevo.")
    return False  # ID de grupo no encontrado

def generar_id_grupo():
    """Genera un ID de grupo aleatorio."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=5))

def mostrar_formulario_crear_grupo():
    """Muestra el formulario para crear un nuevo grupo."""
    st.header("CREAR GRUPO DE JUEGO")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    nombre_creador = st.text_input("Nombre del Creador del Grupo")
    email_creador = st.text_input("Email del Creador")
    aficiones_creador = st.text_area("Aficiones o Gustos")
    fecha_evento = st.date_input("Fecha del Evento")
    fecha_max_inscripcion = st.date_input("Fecha Máxima para Inscribirse")
    total_presupuesto = st.number_input("Total Presupuesto", min_value=0)

    if st.button("Crear el Grupo de Juego"):
        if not nombre_creador or not email_creador or not aficiones_creador or not fecha_evento or not fecha_max_inscripcion or total_presupuesto == 0:
            st.error("Por favor, completa todos los campos antes de enviar.")
        else:
            id_grupo = generar_id_grupo()
            data = {
                "ID del Grupo": id_grupo,
                "Fecha Máxima para Inscribirse": fecha_max_inscripcion.strftime("%Y-%m-%d"),
                "Detalles del Creador": {
                    "Nombre del Creador": nombre_creador,
                    "Email del Creador": email_creador,
                    "Aficiones del Creador": aficiones_creador,
                    "Fecha del Evento": fecha_evento.strftime("%Y-%m-%d"),
                    "Total Presupuesto": total_presupuesto
                },
                "Participantes": []
            }
            guardar_datos(data, "Grupos de Juego")
            enviar_correo_creacion_grupo(email_creador, id_grupo, fecha_evento.strftime("%Y-%m-%d"), fecha_max_inscripcion.strftime("%Y-%m-%d"), total_presupuesto, aficiones_creador, data["Participantes"])

            # Mostrar mensaje de éxito en la interfaz de Streamlit y esperar 10 segundos
            st.success("El grupo se ha creado correctamente")
            time.sleep(10)

            # Volver al menú
            st.session_state.page = 'menu'
            st.rerun()

def mostrar_formulario_registrarse_grupo():
    """Muestra el formulario para registrarse en un grupo existente."""
    st.header("Registrarse en Grupo Creado")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()

    # Mostrar la fecha actual en la parte superior izquierda de la pantalla
    st.text(f"Fecha actual: {date.today().strftime('%Y-%m-%d')}")

    id_grupo = st.text_input("ID del Grupo")
    nombre_usuario = st.text_input("Nombre de Usuario")
    email = st.text_input("Email")
    preferencias = st.text_area("Preferencias")

    if st.button("Enviar"):
        if not id_grupo or not nombre_usuario or not email or not preferencias:
            st.error("Por favor, completa todos los campos antes de enviar.")
        else:
            data = {
                "Nombre de Usuario": nombre_usuario,
                "Email": email,
                "Preferencias": preferencias
            }
            if guardar_datos_registro(id_grupo, data):
                st.success("¡Participante añadido al grupo correctamente!")
                time.sleep(10)  # Mostrar el mensaje durante 10 segundos
                st.session_state.page = 'menu'
                st.rerun()

def mostrar_formulario_ideas_regalar():
    """Muestra el formulario para obtener ideas para regalar."""
    st.header("Ideas para Regalar")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    destinatario = st.text_input("Para quién es el regalo")
    presupuesto = st.number_input("Presupuesto", min_value=0)
    intereses = st.text_area("Intereses de la persona")

    if st.button("Obtener Ideas"):
        if not destinatario or presupuesto <= 0 or not intereses:
            st.error("Por favor, completa todos los campos antes de enviar.")
        else:
            data = {
                "Destinatario": destinatario,
                "Presupuesto": presupuesto,
                "Intereses": intereses
            }
            guardar_datos(data, "Ideas para Regalar")
            st.success("Datos guardados correctamente")
            st.session_state.page = 'menu'

def mostrar_formulario_realizar_sorteo():
    """Muestra el formulario para realizar el sorteo."""
    st.header("Realizar Sorteo Amigo Invisible")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()

    id_grupo = st.text_input("ID del Grupo para el Sorteo")
    email_usuario = st.text_input("Ingrese su Email para verificar autorización")  # Campo para que el usuario ingrese su email

    if st.button("Realizar Sorteo"):
        # Verificar si el ID del grupo existe y obtener el email del creador
        email_creador = None
        try:
            with open("datos.json", "r", encoding='utf-8') as file:
                datos = json.load(file)
        except FileNotFoundError:
            st.error("Error: datos.json no se encuentra.")
            return
        except json.JSONDecodeError:
            st.error("Error: JSON inválido en datos.json.")
            return

        for grupo in datos.get("Grupos de Juego", []):
            if grupo["ID del Grupo"] == id_grupo:
                email_creador = grupo["Detalles del Creador"]["Email del Creador"]
                break

        if not email_creador:
            st.error("ID de grupo no encontrado. Por favor, verifica el ID e inténtalo de nuevo.")
            return

        # Verificar si el email ingresado coincide con el del creador del grupo
        if email_usuario == email_creador:
            realizar_sorteo(id_grupo)  # Realizar el sorteo si el email coincide
            st.session_state.page = 'menu'
            st.rerun()
        else:
            # Mostrar mensaje de error y no redirigir al menú principal
            st.error("Lo siento, pero no tienes permiso para realizar este sorteo. Por favor, contacta con el administrador del grupo.")
            return  # Sale de la función sin realizar el sorteo ni redirigir

def guardar_datos(data, category):
    """Guarda datos en el archivo JSON."""
    with open("datos.json", "r", encoding='utf-8') as file:
        datos = json.load(file)

    if category not in datos:
        datos[category] = []

    datos[category].append(data)

    with open("datos.json", "w", encoding='utf-8') as file:
        json.dump(datos, file, indent=4, ensure_ascii=False)

def guardar_datos_registro(id_grupo, data):
    """Guarda los datos de registro de un usuario en un grupo existente."""
    try:
        with open("datos.json", "r", encoding='utf-8') as file:
            datos = json.load(file)
    except FileNotFoundError:
        st.error("Error: datos.json no se encuentra.")
        return False
    except json.JSONDecodeError:
        st.error("Error: JSON inválido en datos.json.")
        return False

    # Verificar si el ID del grupo existe
    for grupo in datos.get("Grupos de Juego", []):
        if grupo["ID del Grupo"] == id_grupo:

            # **NUEVA VERIFICACIÓN: Comprobar si el sorteo ya se ha realizado**
            if grupo.get("Sorteo Realizado", False): # Usar .get() para evitar KeyError
                st.error("No se puede registrar porque el sorteo ya se ha realizado.")
                return False  # No guardar los datos si el sorteo ya se ha realizado

            # **NUEVA VERIFICACIÓN: Verificar si el email ya está registrado (creador y participantes)**
            if grupo["Detalles del Creador"]["Email del Creador"] == data["Email"]:
                st.error("El email ya existe, por favor revise los datos.")
                return False  # No guardar los datos si el email es el mismo que el del creador

            if "Participantes" in grupo:
                for participante in grupo["Participantes"]:
                    if participante["Email"] == data["Email"]:
                        st.error("El email ya existe, por favor revise los datos.")
                        return False  # No guardar los datos si el email ya existe

            # Comprobar si la fecha actual es posterior a la fecha máxima de inscripción
            fecha_max_inscripcion_str = grupo["Fecha Máxima para Inscribirse"]
            fecha_max_inscripcion = date.fromisoformat(fecha_max_inscripcion_str)
            fecha_actual = date.today()

            if fecha_actual > fecha_max_inscripcion:
                st.error("Lo sentimos, la fecha límite para inscribirse en este grupo ha pasado.")
                return False  # No guardar los datos si la fecha ha pasado

            if "Participantes" not in grupo:
                grupo["Participantes"] = []
            grupo["Participantes"].append(data)

            # Enviar email al participante
            asunto_participante = "Registro Exitoso en el Grupo"
            fecha_evento = grupo["Detalles del Creador"]["Fecha del Evento"]
            total_presupuesto = grupo["Detalles del Creador"]["Total Presupuesto"]

            cuerpo_participante = (f"Te has registrado correctamente en el grupo con ID: {id_grupo}.\n"
                      f"Fecha del Evento: {fecha_evento}\n"
                      f"Presupuesto Total: {total_presupuesto} euros")

            if not enviar_correo_con_asunto_cuerpo(data["Email"], asunto_participante, cuerpo_participante):
                 st.error("Registro exitoso, pero hubo un error al enviar el correo electrónico al participante.")
                 return False

            # Enviar email al creador del grupo
            asunto_creador = "Nuevo Participante en tu Grupo"
            cuerpo_creador = (f"Un nuevo participante se ha registrado en tu grupo {id_grupo}:\n"
                              f"Nombre: {data['Nombre de Usuario']}\n"
                              f"Email: {data['Email']}")
            creador_email = grupo["Detalles del Creador"]["Email del Creador"]

            if not enviar_correo_con_asunto_cuerpo(creador_email, asunto_creador, cuerpo_creador):
               st.error(f"Registro exitoso, pero hubo un error al enviar el correo electrónico al creador del grupo.")
               return False

            try:
                with open("datos.json", "w", encoding='utf-8') as file:
                    json.dump(datos, file, indent=4, ensure_ascii=False)
            except Exception as e:
                st.error(f"Error al escribir en datos.json: {e}")
                return False

            st.success("Te has registrado correctamente y se ha enviado el correo electrónico.")
            return True # Registro exitoso

    st.error("ID de grupo no encontrado. Por favor, verifica el ID e inténtalo de nuevo.")
    return False  # ID de grupo no encontrado

def generar_id_grupo():
    """Genera un ID de grupo aleatorio."""
    return ''.join(random.choices(string.ascii_letters + string.digits, k=5))

def mostrar_formulario_crear_grupo():
    """Muestra el formulario para crear un nuevo grupo."""
    st.header("CREAR GRUPO DE JUEGO")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    nombre_creador = st.text_input("Nombre del Creador del Grupo")
    email_creador = st.text_input("Email del Creador")
    aficiones_creador = st.text_area("Aficiones o Gustos")
    fecha_evento = st.date_input("Fecha del Evento")
    fecha_max_inscripcion = st.date_input("Fecha Máxima para Inscribirse")
    total_presupuesto = st.number_input("Total Presupuesto", min_value=0)

    if st.button("Crear el Grupo de Juego"):
        if not nombre_creador or not email_creador or not aficiones_creador or not fecha_evento or not fecha_max_inscripcion or total_presupuesto == 0:
            st.error("Por favor, completa todos los campos antes de enviar.")
        else:
            id_grupo = generar_id_grupo()
            data = {
                "ID del Grupo": id_grupo,
                "Fecha Máxima para Inscribirse": fecha_max_inscripcion.strftime("%Y-%m-%d"),
                "Detalles del Creador": {
                    "Nombre del Creador": nombre_creador,
                    "Email del Creador": email_creador,

                    "Aficiones del Creador": aficiones_creador,
                    "Fecha del Evento": fecha_evento.strftime("%Y-%m-%d"),
                    "Total Presupuesto": total_presupuesto
                },
                "Participantes": []
            }
            guardar_datos(data, "Grupos de Juego")
            enviar_correo_creacion_grupo(email_creador, id_grupo, fecha_evento.strftime("%Y-%m-%d"), fecha_max_inscripcion.strftime("%Y-%m-%d"), total_presupuesto, aficiones_creador, data["Participantes"])

            # Mostrar mensaje de éxito en la interfaz de Streamlit y esperar 10 segundos
            st.success("El grupo se ha creado correctamente")
            time.sleep(10)

            # Volver al menú
            st.session_state.page = 'menu'
            st.rerun()

def mostrar_formulario_registrarse_grupo():
    """Muestra el formulario para registrarse en un grupo existente."""
    st.header("Registrarse en Grupo Creado")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()

    # Mostrar la fecha actual en la parte superior izquierda de la pantalla
    st.text(f"Fecha actual: {date.today().strftime('%Y-%m-%d')}")

    id_grupo = st.text_input("ID del Grupo")
    nombre_usuario = st.text_input("Nombre de Usuario")
    email = st.text_input("Email")
    preferencias = st.text_area("Preferencias")

    if st.button("Enviar"):
        if not id_grupo or not nombre_usuario or not email or not preferencias:
            st.error("Por favor, completa todos los campos antes de enviar.")
        else:
            data = {
                "Nombre de Usuario": nombre_usuario,
                "Email": email,
                "Preferencias": preferencias
            }
            if guardar_datos_registro(id_grupo, data):
                st.success("¡Participante añadido al grupo correctamente!")
                time.sleep(10)  # Mostrar el mensaje durante 10 segundos
                st.session_state.page = 'menu'
                st.rerun()

def mostrar_formulario_ideas_regalar():
    """Muestra el formulario para obtener ideas para regalar."""
    st.header("Ideas para Regalar")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()
    destinatario = st.text_input("Para quién es el regalo")
    presupuesto = st.number_input("Presupuesto", min_value=0)
    intereses = st.text_area("Intereses de la persona")

    if st.button("Obtener Ideas"):
        if not destinatario or presupuesto <= 0 or not intereses:
            st.error("Por favor, completa todos los campos antes de enviar.")
        else:
            data = {
                "Destinatario": destinatario,
                "Presupuesto": presupuesto,
                "Intereses": intereses
            }
            guardar_datos(data, "Ideas para Regalar")
            st.success("Datos guardados correctamente")
            st.session_state.page = 'menu'

def mostrar_formulario_realizar_sorteo():
    """Muestra el formulario para realizar el sorteo."""
    st.header("Realizar Sorteo Amigo Invisible")
    if st.button("Volver al Menú Principal"):
        st.session_state.page = 'menu'
        st.rerun()

    id_grupo = st.text_input("ID del Grupo para el Sorteo")
    email_usuario = st.text_input("Ingrese su Email para verificar autorización")  # Campo para que el usuario ingrese su email

    if st.button("Realizar Sorteo"):
        # Verificar si el ID del grupo existe y obtener el email del creador
        email_creador = None
        try:
            with open("datos.json", "r", encoding='utf-8') as file:
                datos = json.load(file)
        except FileNotFoundError:
            st.error("Error: datos.json no se encuentra.")
            return
        except json.JSONDecodeError:
            st.error("Error: JSON inválido en datos.json.")
            return

        for grupo in datos.get("Grupos de Juego", []):
            if grupo["ID del Grupo"] == id_grupo:
                email_creador = grupo["Detalles del Creador"]["Email del Creador"]
                break

        if not email_creador:
            st.error("ID de grupo no encontrado. Por favor, verifica el ID e inténtalo de nuevo.")
            return

        # Verificar si el email ingresado coincide con el del creador del grupo
        if email_usuario == email_creador:
            realizar_sorteo(id_grupo)  # Realizar el sorteo si el email coincide
            st.session_state.page = 'menu'
            st.rerun()
        else:
            # Mostrar mensaje de error y no redirigir al menú principal
            st.error("Lo siento, pero no tienes permiso para realizar este sorteo. Por favor, contacta con el administrador del grupo.")
            return  # Sale de la función sin realizar el sorteo ni redirigir

if __name__ == "__main__":
    main()