<<<<<<< HEAD
from nueveonce.app import app

# Expose 'app' at package root for tests and WSGI servers.
=======
import os
import json
import re
import logging
import uuid
from datetime import datetime

from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(message)s")
logger = logging.getLogger("triage")

app = Flask(__name__, template_folder="templates")

# --- ESI Rules (EXACTAS - NO MODIFICAR) ---
ESI_RULES = {
    "1": {
        "categoria": "Rojo - Ambulancia",
        "palabras": [
            "dolor pecho", "paro cardíaco", "paro cardiaco", "no respira",
            "inconsciente", "convulsiones", "shock", "ahogo severo",
            "trauma grave", "hemorragia abundante", "pierde conocimiento",
            "accidente grave", "herida de bala", "apendicitis aguda",
        ],
        "canal": "ambulancia",
        "tiempo_minutos": 1,
        "color": "#EF4444",
    },
    "2": {
        "categoria": "Amarillo - Médico a domicilio",
        "palabras": [
            "fiebre alta 40", "dolor abdominal fuerte", "vómito sangre",
            "caída anciano", "quemadura", "dificultad moderada respirar",
            "alergia grave controlable", "deshidratación", "no puede caminar",
            "herida abierta", "presión alta 180", "diarrea intensa",
        ],
        "canal": "medico_domicilio",
        "tiempo_minutos": 240,
        "color": "#F59E0B",
    },
    "3": {
        "categoria": "Verde - Telemedicina",
        "palabras": [
            "resfriado", "tos seca", "dolor cabeza leve", "picazón",
            "consulta rutina", "receta médica", "duda medicamento",
            "malestar general leve", "sarpullido sin fiebre", "cansancio",
        ],
        "canal": "telemedicina",
        "tiempo_minutos": 1440,
        "color": "#10B981",
    },
}

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
GROQ_MODEL = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")
groq_client = None

if GROQ_API_KEY:
    try:
        from groq import Groq
        groq_client = Groq(api_key=GROQ_API_KEY)
        logger.info("Groq client initialized with model: %s", GROQ_MODEL)
    except Exception as e:
        logger.warning("Failed to init Groq: %s", e)

USE_GROQ = os.getenv("USE_GROQ", "").lower() in ("1", "true", "yes")

sessions_store: list[dict] = []
patients_store: dict[str, dict] = {}


def get_followup_questions(nivel: int, matched_phrase: str = "") -> list[str]:
    """Devuelve una lista de preguntas de filtrado según el nivel.

    - Nivel 1 (Rojo): máximo 2 preguntas cortas y directas.
    - Nivel 2 (Amarillo): 2 preguntas de filtrado.
    - Nivel 3 (Verde): 3 preguntas de filtro para telemedicina.
    """
    # Si tenemos una frase específica detectada, intentar preguntas más relevantes
    mp = (matched_phrase or "").lower()
    if nivel == 1:
        # Priorizar respiración/conciencia y una pregunta sobre localización o trauma
        if "dolor pecho" in mp or "paro" in mp or "no respira" in mp or "ahogo" in mp:
            return [
                "¿La persona está consciente? (sí/no)",
                "¿Respira normalmente o presenta dificultad respiratoria? (sí/no)",
            ]
        if "hemorragia" in mp or "herida" in mp or "trauma" in mp:
            return [
                "¿Hay sangrado abundante visible? (sí/no)",
                "¿La persona está consciente? (sí/no)",
            ]
        return [
            "¿La persona está consciente? (sí/no)",
            "¿La persona respira normalmente? (sí/no)",
        ]
    if nivel == 2:
        if "fiebre" in mp or "vómito sangre" in mp or "diarrea" in mp:
            return [
                "¿Qué temperatura aproximada tiene? (ej: 39°C)",
                "¿Presenta vómitos o diarrea persistente? (sí/no)",
            ]
        if "caída" in mp or "no puede caminar" in mp or "quemadura" in mp:
            return [
                "¿Puede movilizarse por su cuenta? (sí/no)",
                "¿Hay dolor intenso o pérdida de función? (sí/no)",
            ]
        return [
            "¿Tiene fiebre por encima de 38°C? (sí/no)",
            "¿Puede caminar o necesita ayuda para movilizarse? (sí/no)",
        ]
    # nivel 3
    if "tos" in mp or "resfriado" in mp or "dolor cabeza" in mp:
        return [
            "¿Cuánto tiempo lleva con estos síntomas? (ej: 2 días)",
            "¿Presenta fiebre actualmente? (sí/no)",
            "¿Tiene dificultad para respirar o dolor en el pecho? (sí/no)",
        ]
    return [
        "¿Cuánto tiempo lleva con estos síntomas? (ej: 2 días)",
        "¿Presenta fiebre actualmente? (sí/no)",
        "¿Afectan los síntomas su actividad diaria? (sí/no)",
    ]


def evaluate_followups(session: dict) -> None:
    """Re-evalúa el nivel ESI usando sólo las palabras clave definidas en
    `ESI_RULES`, combinando los síntomas originales y las respuestas de
    follow-up. Si hay coincidencia en un nivel más crítico, se actualiza la
    sesión.

    Esta función es estricta: sólo considera coincidencias con las palabras
    exactas (con tolerancia de token parcial definida en `_palabras_en_texto`).
    """
    texto = session.get("sintomas", "") + " " + " ".join(
        [a.get("answer", "") for a in session.get("follow_up_answers", [])]
    )
    texto = normalizar(texto)

    for nivel in ["1", "2", "3"]:
        match, frase = _palabras_en_texto(ESI_RULES[nivel]["palabras"], texto)
        if match:
            rule = ESI_RULES[nivel]
            prev = session.get("nivel")
            session.update({
                "nivel": int(nivel),
                "categoria": rule["categoria"],
                "canal": rule["canal"],
                "tiempo_minutos": rule["tiempo_minutos"],
                "color": rule["color"],
                "justificacion": f"Coincidencia tras preguntas: '{frase}'",
                "fuente": "followup_keyword",
            })
            logger.info("Follow-up re-eval: session %s nivel %s -> %s", session.get("session_id"), prev, nivel)
            return

    # si no hay coincidencias, no cambiamos el nivel pero anotamos la fuente
    session["fuente"] = session.get("fuente", "") + "+followup_checked"



@app.route("/api/triage/answer", methods=["POST"])
def triage_answer():
    data = request.get_json() or {}
    session_id = data.get("session_id")
    answer = data.get("answer")
    if not session_id or answer is None:
        return jsonify({"error": "session_id y answer son requeridos"}), 400

    # buscar sesión
    for s in sessions_store:
        if s["session_id"] == session_id:
            # inicializar estructura si hace falta
            s.setdefault("follow_up_answers", [])
            s.setdefault("follow_up_index", 0)
            questions = s.get("follow_up_questions", [])

            # guardar respuesta
            s["follow_up_answers"].append({
                "question": questions[s["follow_up_index"]] if s["follow_up_index"] < len(questions) else "",
                "answer": answer,
                "timestamp": datetime.now().isoformat(),
            })
            s["follow_up_index"] += 1

            # decidir siguiente paso
            if s["follow_up_index"] >= len(questions):
                s["estado"] = "completado"
                # al terminar los follow-ups, re-evaluar estrictamente según palabras clave
                prev_nivel = s.get("nivel")
                evaluate_followups(s)
                # si está habilitado, intentar usar Groq alimentado con preguntas y respuestas
                if USE_GROQ and groq_client:
                    try:
                        groq_res = groq_classify_with_context(s.get("sintomas", ""), s.get("follow_up_answers", []))
                        # validar que la justificación contenga una frase reconocida
                        if groq_res and groq_res.get("matched_phrase"):
                            # aceptar resultado del modelo
                            s.update({
                                "nivel": groq_res["nivel"],
                                "categoria": groq_res["categoria"],
                                "canal": groq_res["canal"],
                                "tiempo_minutos": groq_res["tiempo_minutos"],
                                "color": groq_res.get("color", s.get("color")),
                                "justificacion": groq_res.get("justificacion", s.get("justificacion")),
                                "fuente": "groq_followup",
                                "matched_phrase": groq_res.get("matched_phrase"),
                                "used_groq": True,
                            })
                    except Exception:
                        logger.exception("Error usando Groq en follow-up, manteniendo evaluación por palabras clave.")

                # ejecutar acciones simuladas si cambió el nivel
                if s.get("nivel") != prev_nivel:
                    simulate_actions(s)
                return jsonify({"done": True, "session": s}), 200
            # devolver siguiente pregunta
            next_q = questions[s["follow_up_index"]]
            return jsonify({"done": False, "next_question": next_q, "session": s}), 200

    return jsonify({"error": "Sesión no encontrada"}), 404


def normalizar(texto: str) -> str:
    texto = texto.lower().strip()
    for a, b in [["á", "a"], ["é", "e"], ["í", "i"], ["ó", "o"], ["ú", "u"], ["ü", "u"], ["ñ", "n"]]:
        texto = texto.replace(a, b)
    return re.sub(r"[^a-z0-9\s]", "", texto).strip()


def _match_palabra(palabra: str, token: str) -> bool:
    if palabra == token:
        return True
    if len(palabra) >= 6 and len(token) >= 6 and palabra[:5] == token[:5]:
        return True
    if len(palabra) >= 4 and len(token) >= 4 and palabra[:4] == token[:4]:
        return True
    return False


def _palabras_en_texto(palabras: list[str], texto: str) -> tuple[bool, str]:
    tokens_texto = texto.split()
    for frase in palabras:
        tokens_frase = frase.split()
        if len(tokens_frase) == 1:
            for tok in tokens_texto:
                # regla determinística: si la respuesta corresponde a una pregunta
                # crítica (conciencia / respiración) y es negativa, forzar Nivel 1
                try:
                    qidx = s["follow_up_index"] - 1
                    qtext = questions[qidx].lower() if 0 <= qidx < len(questions) else ""
                    ans_norm = normalizar(str(answer))
                    if any(k in qtext for k in ("consciente", "consciencia", "respira", "respirar")):
                        if ans_norm.startswith("no") or ans_norm in ("n", "sin"):
                            # forzar nivel 1
                            rule = ESI_RULES["1"]
                            s.update({
                                "nivel": 1,
                                "categoria": rule["categoria"],
                                "canal": rule["canal"],
                                "tiempo_minutos": rule["tiempo_minutos"],
                                "color": rule["color"],
                                "justificacion": f"Forzado por respuesta crítica: '{questions[qidx]}' -> '{answer}'",
                                "fuente": "forced_rule",
                                "derivation_reason": f"Respuesta crítica: {questions[qidx]} -> {answer}",
                            })
                            s["estado"] = "completado"
                            s["follow_up_index"] = len(questions)
                            simulate_actions(s)
                            return jsonify({"done": True, "session": s}), 200
                except Exception:
                    logger.exception("Error evaluando regla deterministica de follow-up")
                if _match_palabra(tokens_frase[0], tok):
                    return True, frase
        if len(tokens_frase) >= 2:
            coincidencias_parciales = 0
            for i, tok in enumerate(tokens_frase):
                for tok_texto in tokens_texto:
                    if _match_palabra(tok, tok_texto):
                        coincidencias_parciales += 1
                        break
            if coincidencias_parciales >= max(2, len(tokens_frase) - 1):
                return True, frase
            for start in range(len(tokens_texto) - len(tokens_frase) + 1):
                coinciden = sum(1 for i in range(len(tokens_frase))
                                if _match_palabra(tokens_frase[i], tokens_texto[start + i]))
                if coinciden / len(tokens_frase) >= 0.6:
                    return True, frase
    return False, ""


def keyword_fallback(sintomas: str) -> dict:
    texto = normalizar(sintomas)
    for nivel in ["1", "2", "3"]:
        match, frase_match = _palabras_en_texto(ESI_RULES[nivel]["palabras"], texto)
        if match:
            rule = ESI_RULES[nivel]
            logger.info("Keyword match Nivel %s: '%s'", nivel, frase_match)
            return {
                "nivel": int(nivel),
                "categoria": rule["categoria"],
                "canal": rule["canal"],
                "tiempo_minutos": rule["tiempo_minutos"],
                "color": rule["color"],
                "justificacion": f"Coincidencia con palabra clave: '{frase_match}'",
                "fuente": "keyword",
                "matched_phrase": frase_match,
            }
    rule = ESI_RULES["3"]
    return {
        "nivel": 3,
        "categoria": rule["categoria"],
        "canal": rule["canal"],
        "tiempo_minutos": rule["tiempo_minutos"],
        "color": rule["color"],
        "justificacion": "No se detectaron palabras clave de alto riesgo.",
        "fuente": "keyword_default",
        "matched_phrase": "",
    }


def groq_classify(sintomas: str) -> dict | None:
    if not groq_client:
        return None

    rules_json = json.dumps(ESI_RULES, indent=2, ensure_ascii=False)

    system_prompt = f"""Eres un clasificador de triaje médico. Tu única función es asignar un nivel ESI según las reglas exactas definidas abajo. No puedes inventar niveles, canales ni categorías.

REGLAS EXACTAS — SOLO ESTOS 3 NIVELES EXISTEN:
{rules_json}

INSTRUCCIONES ESTRICTAS:
1. Lee los síntomas del paciente.
2. Busca coincidencias con las palabras clave de cada nivel, empezando por el Nivel 1 (más crítico).
3. Si hay coincidencia con palabras de Nivel 1 → clasifica como Nivel 1. Si no, prueba Nivel 2, luego Nivel 3.
4. Si no hay ninguna coincidencia con palabras clave, clasifica como Nivel 3 por defecto.
5. NUNCA devuelvas un nivel, categoría o canal que no esté en las reglas exactas de arriba.
6. RESPONDE ÚNICA Y EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO.
7. NO incluyas markdown, texto, explicaciones, comillas invertidas, ni nada fuera del JSON.

FORMATO DE RESPUESTA (exacto, JSON puro):
{{"nivel": <1|2|3>, "categoria": "<categoria exacta de las reglas>", "canal": "<canal exacto de las reglas>", "tiempo_minutos": <número exacto de las reglas>, "justificacion": "<explicación breve de qué palabras clave coincidieron>"}}"""

    try:
        resp = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Síntomas del paciente: {sintomas}"},
            ],
            model=GROQ_MODEL,
            temperature=0.1,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        logger.info("Groq response: %s", raw[:200])

        data = json.loads(raw)
        nivel = int(data.get("nivel", 3))
        nivel = max(1, min(3, nivel))

        rule = ESI_RULES.get(str(nivel), ESI_RULES["3"])
        # intentar extraer la frase coincidente de la justificacion
        just_text = data.get("justificacion", "") or sintomas
        match_phrase = ""
        m, frase = _palabras_en_texto(rule["palabras"], normalizar(just_text))
        if m:
            match_phrase = frase
        return {
            "nivel": nivel,
            "categoria": rule["categoria"],
            "canal": rule["canal"],
            "tiempo_minutos": rule["tiempo_minutos"],
            "color": rule["color"],
            "justificacion": data.get("justificacion", ""),
            "fuente": "groq",
            "matched_phrase": match_phrase,
        }
    except Exception as e:
        logger.warning("Groq API error: %s. Using keyword fallback.", e)
        return None


def groq_classify_with_context(sintomas: str, followups: list[dict]) -> dict | None:
    """Clasifica usando Groq alimentado con los síntomas y las preguntas/respuestas
    de follow-up para reducir alucinaciones. Devuelve el mismo formato que
    `groq_classify` o None si no está disponible.
    """
    if not groq_client:
        return None

    rules_json = json.dumps(ESI_RULES, indent=2, ensure_ascii=False)
    # construir bloque de Q&A
    qa_lines = []
    for i, qa in enumerate(followups):
        q = qa.get("question", "")
        a = qa.get("answer", "")
        qa_lines.append(f"Q{i+1}: {q} => A: {a}")
    qa_text = "\n".join(qa_lines)

    system_prompt = f"""Eres un clasificador de triaje médico. Tu única función es asignar un nivel ESI según las reglas exactas definidas abajo. No puedes inventar niveles, canales ni categorías.

REGLAS EXACTAS — SOLO ESTOS 3 NIVELES EXISTEN:
{rules_json}

INSTRUCCIONES ESTRICTAS:
1. Lee los síntomas y las preguntas/respuestas del follow-up.
2. Busca coincidencias con las palabras clave de cada nivel, empezando por el Nivel 1 (más crítico).
3. Si hay coincidencia con palabras de Nivel 1 → clasifica como Nivel 1. Si no, prueba Nivel 2, luego Nivel 3.
4. Si no hay ninguna coincidencia con palabras clave, clasifica como Nivel 3 por defecto.
5. NUNCA devuelvas un nivel, categoría o canal que no esté en las reglas exactas de arriba.
6. RESPONDE ÚNICA Y EXCLUSIVAMENTE CON UN OBJETO JSON VÁLIDO.
7. NO incluyas markdown, texto, explicaciones ni nada fuera del JSON.

ADICIONAL: A continuación tienes las preguntas y respuestas del follow-up (Q&A). Usa exclusivamente esa información y los síntomas para justificar la clasificación:
{qa_text}

FORMATO DE RESPUESTA (exacto, JSON puro):
{{"nivel": <1|2|3>, "categoria": "<categoria exacta>", "canal": "<canal exacto>", "tiempo_minutos": <número>, "justificacion": "<explicación breve de qué palabras clave coincidieron>"}}"""

    try:
        resp = groq_client.chat.completions.create(
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": f"Síntomas: {sintomas}"},
            ],
            model=GROQ_MODEL,
            temperature=0.05,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content.strip()
        logger.info("Groq followup response: %s", raw[:300])
        data = json.loads(raw)
        nivel = int(data.get("nivel", 3))
        nivel = max(1, min(3, nivel))
        rule = ESI_RULES.get(str(nivel), ESI_RULES["3"])
        just_text = data.get("justificacion", "") or sintomas
        match_phrase = ""
        m, frase = _palabras_en_texto(rule["palabras"], normalizar(just_text))
        if m:
            match_phrase = frase
        return {
            "nivel": nivel,
            "categoria": rule["categoria"],
            "canal": rule["canal"],
            "tiempo_minutos": rule["tiempo_minutos"],
            "color": rule["color"],
            "justificacion": data.get("justificacion", ""),
            "fuente": "groq",
            "matched_phrase": match_phrase,
        }
    except Exception as e:
        logger.warning("Groq followup error: %s", e)
        return None


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/patient", methods=["POST"])
def register_patient():
    data = request.get_json()
    if not data or not data.get("nombre"):
        return jsonify({"error": "Nombre del paciente requerido"}), 400

    nombre = data["nombre"].strip()
    paciente_id = uuid.uuid4().hex[:12]

    patients_store[paciente_id] = {
        "paciente_id": paciente_id,
        "nombre": nombre,
        "edad": data.get("edad", ""),
        "telefono": data.get("telefono", ""),
        "direccion": data.get("direccion", ""),
        "created_at": datetime.now().isoformat(),
    }
    logger.info("Paciente registrado: %s (%s)", nombre, paciente_id)
    return jsonify(patients_store[paciente_id]), 201


@app.route("/api/triage", methods=["POST"])
def triage():
    data = request.get_json()
    if not data or not data.get("sintomas"):
        return jsonify({"error": "Campo 'sintomas' requerido"}), 400

    sintomas = data["sintomas"].strip()
    if len(sintomas) < 3:
        return jsonify({"error": "Describe tus síntomas con más detalle"}), 400

    paciente_id = data.get("paciente_id", "")
    paciente = patients_store.get(paciente_id, {})
    nombre = paciente.get("nombre", data.get("nombre", "Anónimo"))

    # Clasificación estricta usando únicamente `ESI_RULES`.
    # NO se consultará Groq/LLM: usamos el fallback por palabras clave que
    # retorna Nivel 1/2/3 o Nivel 3 por defecto si no hay coincidencias.
    keyword_result = keyword_fallback(sintomas)
    result = keyword_result
    logger.info("Clasificación estricta aplicada (ESI_RULES) -> Nivel %s", result.get("nivel"))

    session_id = uuid.uuid4().hex[:12]
    timestamp = datetime.now().isoformat()

    session = {
        "session_id": session_id,
        "paciente_id": paciente_id,
        "nombre": nombre,
        "edad": paciente.get("edad", ""),
        "sintomas": sintomas,
        "nivel": result["nivel"],
        "categoria": result["categoria"],
        "canal": result["canal"],
        "tiempo_minutos": result["tiempo_minutos"],
        "color": result["color"],
        "justificacion": result["justificacion"],
        "fuente": result["fuente"],
        "estado": "pendiente",
        "follow_up_questions": get_followup_questions(result["nivel"], result.get("matched_phrase", "")) if result.get("nivel") else [],
        "follow_up_index": 0,
        "follow_up_answers": [],
        "timestamp": timestamp,
    }

    sessions_store.append(session)
    logger.info("Nuevo triaje | Nivel %d | %s | %s", result["nivel"], result["categoria"], nombre)

    simulate_actions(session)

    return jsonify(session), 201


@app.route("/api/sessions", methods=["GET"])
def get_sessions():
    paciente_id = request.args.get("paciente_id", "")
    nivel = request.args.get("nivel")
    estado = request.args.get("estado")
    result = list(reversed(sessions_store))
    if paciente_id:
        result = [s for s in result if s.get("paciente_id") == paciente_id]
    if nivel:
        result = [s for s in result if str(s["nivel"]) == nivel]
    if estado:
        result = [s for s in result if s.get("estado") == estado]
    return jsonify({"total": len(result), "sesiones": result})


@app.route("/api/sessions/<session_id>", methods=["GET"])
def get_session(session_id: str):
    for s in sessions_store:
        if s["session_id"] == session_id:
            return jsonify(s)
    return jsonify({"error": "Sesión no encontrada"}), 404


def simulate_actions(session: dict):
    nivel = session["nivel"]
    sid = session["session_id"]
    logger.info("=" * 50)
    logger.info("NOTIFICACIONES - Sesión %s", sid)
    logger.info("=" * 50)
    if nivel == 1:
        logger.info("🔥 [ALERTA] Nivel 1 - ROJO")
        logger.info("🚑 [SIM] Ambulancia medicalizada despachada")
        logger.info("📱 [SIM] SMS: Unidad en camino. < 1 min")
    elif nivel == 2:
        logger.info("⚠️  [ALERTA] Nivel 2 - AMARILLO")
        logger.info("👨‍⚕️ [SIM] Médico domiciliario asignado")
        logger.info("📱 [SIM] SMS: Médico en camino. Máx 4 horas")
    else:
        logger.info("🟢 [AVISO] Nivel 3 - VERDE")
        logger.info("📹 [SIM] Enlace de videollamada generado")
        logger.info("📱 [SIM] SMS: Enlace de telemedicina enviado")
    logger.info("=" * 50)


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
    logger.info("🚀 NueveOnce - TriageBot")
    logger.info("   http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)

>>>>>>> origin/main
