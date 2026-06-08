from nueveonce.app import app

# Wrapper mínimo para exponer `app` en la raíz del repositorio.
# Permite que WSGI/WSL/tests importen `from app import app`.
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
