# NueveOnce - Triage ESI

Resumen
- Proyecto Flask que clasifica síntomas según reglas ESI (Emergency Severity Index).
- Soporta re-evaluación opcional con Groq (LLM) tras preguntas de follow-up si `USE_GROQ=true`.

Requisitos
- Python 3.10+
- (Opcional) Redis para caché

Instalación
1. Crear y activar virtualenv:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # o .\.venv\Scripts\Activate.ps1 en Windows
   ```

2. Instalar dependencias:
   ```bash
   pip install -r requirements.txt
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
python app.py
```

Ejecutar tests
```bash
pytest -q
```

Endpoints principales
- `POST /api/triage` — responde con clasificación JSON y preguntas de seguimiento.
- `POST /api/triage/answer` — envía respuestas a las preguntas de seguimiento.
- `POST /api/triage_stream` — streaming SSE para respuestas incrementales.

Despliegue en Vercel
- Este repositorio incluye `vercel.json` para una configuración básica con `@vercel/python`.
- Pasos rápidos:
  1. Conectar el repositorio en Vercel.
  2. Guardar `GROQ_API_KEY` en el dashboard de Vercel.

Seguridad y producción
- Use PostgreSQL en `DATABASE_URL` y ajuste `DB_POOL_SIZE`/`DB_MAX_OVERFLOW` según carga.
- Controle `MAX_OUTPUT_TOKENS` y valide estrictamente la salida del LLM con `nueveonce/schemas.py`.

Notas técnicas
- El sistema prioriza reglas ESI basadas en palabras clave; Groq se usa como re-evaluación y su salida se valida contra el esquema esperado.
