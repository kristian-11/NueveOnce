<<<<<<< HEAD
# NueveOnce - Triage Backend (MVP)

Instrucciones rápidas para desarrollo y pruebas.

Requisitos:
- Python 3.10+
- (Opcional) Redis para caché

Instalación:

```bash
python -m venv .venv
. .venv/bin/activate   # o PowerShell: . .venv\Scripts\Activate.ps1
pip install -r nueveonce/requirements.txt
```

Variables de entorno recomendadas:
- `DATABASE_URL` (ej: `sqlite:///./nueveonce.db` o PostgreSQL URL)
- `USE_REDIS`=1 y `REDIS_URL` si quieres caching
- `USE_GROQ`=1 y `GROQ_API_KEY` si tienes acceso a Groq
- `MAX_OUTPUT_TOKENS` para limitar salida LLM

Inicializar DB (local):

```bash
python nueveonce/scripts/init_db.py
```

Ejecutar la aplicación:

```bash
python nueveonce/app.py
```

Ejecutar tests:

```bash
pytest -q
```

Endpoints principales:
- `POST /api/triage` -> respuesta JSON
- `POST /api/triage_stream` -> streaming SSE (Server-Sent Events)

Seguridad y producción:
- Configure `DATABASE_URL` a PostgreSQL y ajuste `DB_POOL_SIZE`.
- No cachee información sensible en Redis sin cifrado/TTL apropiado.
- Asegure el acceso al endpoint LLM y use timeouts/quotas.
=======
NueveOnce - Triage ESI

Resumen
- Proyecto Flask que clasifica síntomas según reglas ESI estrictas.
- El backend puede usar Groq (LLM) para re-evaluar tras preguntas de follow-up si `USE_GROQ=true`.

Variables de entorno (.env)
- `USE_GROQ=true` — habilita la llamada al modelo Groq en la re-evaluación (ya está por defecto).
- `GROQ_API_KEY` — clave de la API Groq (dejar vacío para no usar Groq).
- `GROQ_MODEL` — modelo a usar (por defecto `llama-3.3-70b-versatile`).
- `PORT`, `DEBUG` — puerto y modo debug.

Instalación y ejecución (Windows Powershell)
1. Crear y activar un virtualenv (si no existe):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r nueveonce/requirements.txt
```

3. Editar `.env` en `nueveonce/.env` para añadir `GROQ_API_KEY` si quieres usar Groq.

4. Ejecutar la aplicación:

```powershell
# desde la carpeta del workspace
.\.venv\Scripts\python.exe nueveonce/app.py
```

Pruebas rápidas (Powershell)
- Registrar paciente:

```powershell
$body = @{nombre='test'} | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/patient' -Method Post -Body $body -ContentType 'application/json'
```

- Enviar triage:

```powershell
$body = @{sintomas='dolor pecho'; paciente_id=''} | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/triage' -Method Post -Body $body -ContentType 'application/json' | ConvertTo-Json -Depth 6
```

- Responder follow-up (usar `session_id` devuelto):

```powershell
$body = @{session_id='<SESSION_ID>'; answer='si'} | ConvertTo-Json -Compress
Invoke-RestMethod -Uri 'http://127.0.0.1:5000/api/triage/answer' -Method Post -Body $body -ContentType 'application/json'
```

Notas
- El sistema prioriza `ESI_RULES` (clasificación por palabras clave). Cuando `USE_GROQ=true` y `GROQ_API_KEY` esté definida, Groq se consultará tras completar los follow-ups y su salida será aceptada sólo si contiene una coincidencia con las palabras clave (evita alucinaciones).
- Revisa `nueveonce/app.py` para cambiar la lógica o los criterios de verificación si necesitas mayor/menor sensibilidad.
>>>>>>> origin/main
