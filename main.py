import speech_recognition as sr
import json
import time
import os
from gtts import gTTS
import socket
import glob
import threading
import difflib

DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
CARPETA_AUDIOS = os.path.join(DIRECTORIO_ACTUAL, "audios_generados")

if not os.path.exists(CARPETA_AUDIOS):
    os.makedirs(CARPETA_AUDIOS)

IP_UNITY = "127.0.0.1"
PUERTO_UNITY = 5005
cable_udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

bloqueo_cooldown = False

def limpiar_audios():
    print("[1/4] Limpiando audios de clases anteriores...")
    archivos = glob.glob(os.path.join(CARPETA_AUDIOS, "*.mp3"))
    for f in archivos:
        try: os.remove(f)
        except: pass
    print("Limpieza terminada.")

def guion(ruta_json):
    ruta_completa = os.path.join(DIRECTORIO_ACTUAL, ruta_json)
    with open(ruta_completa, "r", encoding="utf-8") as archivo:
        return json.load(archivo)

def pre_renderizar_audios(guion_datos):
    print("[2/4] Pre-renderizando voz del profesor...")
    for avatar, dialogos in guion_datos.items():
        for frase_clave, datos in dialogos.items():
            texto = datos["texto"]
            datos["ruta_audio"] = "NONE"
            
            if texto.strip():
                nombre_limpio = avatar.replace(" ", "_")
                frase_limpia = frase_clave.replace(" ", "_").replace("?", "").replace("¿", "")
                ruta_audio = os.path.join(CARPETA_AUDIOS, f"resp_{nombre_limpio}_{frase_limpia}.mp3")
                
                # Solo genera el audio si no existe, acelera el arranque
                if not os.path.exists(ruta_audio):
                    print(f"Generando voz para: '{frase_clave}'")
                    tts = gTTS(text=texto, lang='es', tld='com.mx')
                    tts.save(ruta_audio)
                
                datos["ruta_audio"] = ruta_audio
    print("Audios listos para Unity.")

def enviar_orden_unity(avatar, ruta_audio, accion, longitud_texto):
    global bloqueo_cooldown
    mensaje = f"{avatar}|{ruta_audio}|{accion}"
    cable_udp.sendto(mensaje.encode('utf-8'), (IP_UNITY, PUERTO_UNITY))
    print(f"\n[UNITY] Animación ejecutada: {accion}")
    
    # LOGICA NUEVA: Calculo estimado de tiempo hablado (14 caracteres por segundo aprox)
    # Así no usamos un sleep fijo de 5s, el profe espera exactamente lo que dura su línea.
    tiempo_espera = max(3.0, len(longitud_texto) / 14.0)
    time.sleep(tiempo_espera)
    
    bloqueo_cooldown = False
    print("\n>>> PROFESOR ESCUCHANDO DE NUEVO <<<")

def calcular_similitud(texto_usuario, frase_diccionario):
    return difflib.SequenceMatcher(None, texto_usuario, frase_diccionario).ratio()

def escuchar_y_procesar(guion_datos):
    global bloqueo_cooldown
    r = sr.Recognizer()

    # LOGICA NUEVA: Calibración dinámica para que NO se trabe el bucle
    r.energy_threshold = 300  
    r.dynamic_energy_threshold = True # Permite adaptarse al ruido del salón/cuarto
    r.pause_threshold = 0.8 # Responde más rápido cuando el usuario termina de hablar
    
    print("[3/4] Cargando modelo Whisper...")
    
    with sr.Microphone(device_index=1) as source: 
        print("[4/4] Ajustando sonido del ambiente...")
        r.adjust_for_ambient_noise(source, duration=2)
        print("====== SISTEMA LISTO. DILE AL PROFE QUE INICIE ======")

        while True:
            try:
                if not bloqueo_cooldown:
                    # Timeout de 5s: Si nadie habla, el loop se reinicia limpio sin crashear
                    audio = r.listen(source, timeout=5, phrase_time_limit=8)
                    
                    texto_crudo = r.recognize_whisper(audio, model="base", language="es").lower()
                    texto_limpio = texto_crudo.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("¿","").replace("?","").replace("¡","").replace("!","").replace(",","").replace(".","").strip()
                    
                    print(f"Alumno dijo: '{texto_limpio}'")

                    if "apagate" in texto_limpio or "termina la clase" in texto_limpio:
                        cable_udp.sendto("sistema|NONE|apagar_todo".encode('utf-8'), (IP_UNITY, PUERTO_UNITY))
                        break

                    match_encontrado = False
                    for avatar, dialogos in guion_datos.items():
                        for frase_clave, datos in dialogos.items():
                            
                            frase_limpia_diccionario = frase_clave.lower()
                            similitud = calcular_similitud(texto_limpio, frase_limpia_diccionario)
                            
                            # Subimos el umbral a 0.70 para que en los quiz no agarre respuestas al azar
                            if frase_limpia_diccionario in texto_limpio or similitud > 0.70:
                                print(f"*** Match detectado: '{frase_clave}' ***")
                                
                                bloqueo_cooldown = True
                                hilo = threading.Thread(target=enviar_orden_unity, args=(avatar, datos["ruta_audio"], datos["accion"], datos["texto"]))
                                hilo.start()
                                
                                match_encontrado = True
                                break
                        if match_encontrado:
                            break
            
            # Estas excepciones atrapan los tiempos muertos para que el While siga rodando perfecto
            except sr.WaitTimeoutError:
                pass
            except sr.UnknownValueError:
                pass
            except Exception as e:
                pass
            
if __name__ == "__main__":
    try:
        limpiar_audios()
        mi_guion = guion("guion.json")
        pre_renderizar_audios(mi_guion)
        escuchar_y_procesar(mi_guion)
    except FileNotFoundError:
        print("No se encontró el archivo guion.json.")