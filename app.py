import os
import logging
from nueveonce.app import app

# Configuración básica de logging para el wrapper
logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(name)s | %(message)s")
logger = logging.getLogger("nueveonce-wrapper")

if __name__ == "__main__":
    # Ejecuta la app desde la raíz si se desea (útil en desarrollo)
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")
    logger.info("🚀 NueveOnce - TriageBot Wrapper Starting")
    logger.info("   Endpoint: http://localhost:%d", port)
    app.run(host="0.0.0.0", port=port, debug=debug)
