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
