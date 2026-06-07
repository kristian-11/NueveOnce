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

# NueveOnce - Triage ESI

Resumen
- Proyecto Flask que clasifica síntomas según reglas ESI (Emergency Severity Index).
- Soporta re-evaluación opcional con Groq (LLM) tras preguntas de follow-up si `USE_GROQ=true`.

Requisitos
- Python 3.10+
- (Opcional) Redis para caché

Instalación (Linux/macOS)
1. Crear y activar virtualenv:

```bash
python -m venv .venv
source .venv/bin/activate
```

2. Instalar dependencias:

```bash
pip install -r nueveonce/requirements.txt
```

Instalación (Windows PowerShell)
1. Crear y activar virtualenv:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

2. Instalar dependencias:

```powershell
pip install -r nueveonce/requirements.txt
```

Variables de entorno (recomendadas)
- `DATABASE_URL` — por ejemplo `sqlite:///./nueveonce.db` o una URL PostgreSQL.
- `USE_REDIS`=1 y `REDIS_URL` si quieres habilitar caching.
- `USE_GROQ`=1 y `GROQ_API_KEY` para usar Groq.
- `MAX_OUTPUT_TOKENS` para limitar la cantidad de tokens que aceptamos del LLM.

Inicializar la base de datos (local)

```bash
python nueveonce/scripts/init_db.py
```

Ejecutar la aplicación (desarrollo)

```bash
python nueveonce/app.py
```

Ejecutar tests

```bash
pytest -q
```

Endpoints principales
- `POST /api/triage` — responde con clasificación JSON.
- `POST /api/triage_stream` — streaming SSE (Server-Sent Events) para respuestas incrementales.

Despliegue en Vercel
- Este repositorio incluye `vercel.json` para una configuración básica con `@vercel/python`.
- Pasos rápidos:
	1. Conectar el repositorio en Vercel (GitHub integration).
	2. Asegurarte que la variable de entorno `GROQ_API_KEY` se guarda en el dashboard de Vercel (si la usas).
	3. Vercel detectará `vercel.json` y construirá el proyecto; el endpoint expuesto será el que declare `routes`.
- Nota: También hay un `Procfile` para despliegues alternativos con Gunicorn.

Seguridad y producción
- Use PostgreSQL en `DATABASE_URL` y ajuste `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` según carga.
- No cachee información sensible en Redis sin cifrado/TTL apropiado.
- Controle `MAX_OUTPUT_TOKENS` y valide estrictamente la salida del LLM con `nueveonce/schemas.py`.

Notas técnicas
- El sistema prioriza reglas ESI (`ESI_RULES`) basado en palabras clave; Groq se usa sólo como re-evaluación y su salida se valida contra el esquema esperado para evitar alucinaciones.

Contribuyendo
- Crear una rama, abrir un PR hacia `main`, y la CI ejecutará tests en la rama `feature/refactor-llm-optimizations`.

Licencia
- (Añade la licencia si lo deseas)
