import speech_recognition as sr
import json
import time
import os
import glob
from gtts import gTTS
import difflib


DIRECTORIO_ACTUAL = os.path.dirname(os.path.abspath(__file__))
CARPETA_AUDIOS = os.path.join(DIRECTORIO_ACTUAL, "audios_generados")

if not os.path.exists(CARPETA_AUDIOS):
    os.makedirs(CARPETA_AUDIOS)

#limpiar y generar datos
def limpiar_audios():
    print(" Limpiando audios...")
    archivos = glob.glob(os.path.join(CARPETA_AUDIOS, "*.mp3"))
    for f in archivos:
        try: os.remove(f)
        except: pass

def cargar_guion(ruta_json):
    with open(os.path.join(DIRECTORIO_ACTUAL, ruta_json), "r", encoding="utf-8") as archivo:
        return json.load(archivo)

def pre_renderizar_audios(guion_datos):
    print("Generando la voz...")
    for avatar, dialogos in guion_datos.items():
        for frase_clave, datos in dialogos.items():
            texto = datos["texto"]
            datos["ruta_audio"] = "NONE"
            
            if texto.strip():
                nombre_limpio = avatar.replace(" ", "_")
                frase_limpia = frase_clave.replace(" ", "_").replace("?", "").replace("¿", "")
                ruta_audio = os.path.join(CARPETA_AUDIOS, f"resp_{nombre_limpio}_{frase_limpia}.mp3")
                
                # Solo genera el MP3 si no existe para ahorrar tiempo
                if not os.path.exists(ruta_audio):
                    tts = gTTS(text=texto, lang='es', tld='com.mx')
                    tts.save(ruta_audio)
                
                datos["ruta_audio"] = ruta_audio
    print("Voz generada exitosamente.")


def calcular_similitud(texto_usuario, frase_diccionario):
    return difflib.SequenceMatcher(None, texto_usuario, frase_diccionario).ratio()

def escuchar_y_procesar(guion_datos):
    r = sr.Recognizer()
    r.energy_threshold = 300  
    r.dynamic_energy_threshold = True 
    r.pause_threshold = 0.8 
    
    print("Cargando modelo Whisper...")
    
    with sr.Microphone(device_index=1) as source: 
        r.adjust_for_ambient_noise(source, duration=2)
        print("\n==================================================")
        print(" BIENVENIDO A TU CLASE DE ECONOMIA HABLA PARA CONTINUAR.")
        print(" Porfavor di: __INICIA LA CLASE__ para continuar.")
        print(" (Di 'apágate' para salir)")
        print("==================================================\n")

        while True:
            try:
                # 1. Escuchar al usuario
                audio = r.listen(source, timeout=5, phrase_time_limit=8)
                texto_crudo = r.recognize_whisper(audio, model="base", language="es").lower()
                texto_limpio = texto_crudo.replace("á","a").replace("é","e").replace("í","i").replace("ó","o").replace("ú","u").replace("¿","").replace("?","").strip()
                
                if texto_limpio:
                    # Imprimimos lo que el micrófono entendió
                    print(f"\n[Alumno]: {texto_limpio}")

                # 2. Comando de seguridad para apagar
                if "apagate" in texto_limpio or "termina la clase" in texto_limpio:
                    print("\n[Sistema]: Finalizando la clase. ¡Nos vemos!")
                    break

                # 3. Buscar la respuesta correcta en el JSON
                match_encontrado = False
                for avatar, dialogos in guion_datos.items():
                    for frase_clave, datos in dialogos.items():
                        
                        frase_limpia_diccionario = frase_clave.lower()
                        similitud = calcular_similitud(texto_limpio, frase_limpia_diccionario)
                        
                        # Si hay un match del 70% o más
                        if frase_limpia_diccionario in texto_limpio or similitud > 0.70:
                            
                            # Imprimir la respuesta 
                            nombre_profe = avatar.capitalize()
                            print(f"[{nombre_profe}]: {datos['texto']}")
                            
                            # Reproducir el audio
                            if datos["ruta_audio"] != "NONE":
                                # Este comando abre el reproductor de Windows de forma invisible y lo cierra al terminar
                                os.system(f'start /min "" "{datos["ruta_audio"]}"')
                            
                            # Dormir el programa el tiempo exacto que dura el audio para que el micro no capte la voz del mismo bot
                            tiempo_espera = max(3.0, len(datos["texto"]) / 14.0)
                            time.sleep(tiempo_espera)
                            
                            print("\n[Sistema]: Escuchando de nuevo...")
                            match_encontrado = True
                            break 
                    
                    if match_encontrado:
                        break 
                        
            
            except sr.WaitTimeoutError:
                pass # Si nadie habla en 5 segs, no hace nada y vuelve a escuchar
            except sr.UnknownValueError:
                pass # Si el audio fue puro ruido inentendible
            except Exception as e:
                pass

if __name__ == "__main__":
    try:
        limpiar_audios()
        mi_guion = cargar_guion("guion.json")
        pre_renderizar_audios(mi_guion)
        escuchar_y_procesar(mi_guion)
    except FileNotFoundError:
        print("Error: No se encontró el archivo guion.json en esta carpeta.")