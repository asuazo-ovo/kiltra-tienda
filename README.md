# Kiltra — tienda ficticia

Tienda web **ficticia** para el curso «Agentes de WhatsApp para Profesionales» de OVO Consulting: vitrina,
carro, pago simulado, seguimiento, panel y API (`/api/docs`). Clientes, pedidos y courier son inventados.
Nada se cobra ni se despacha.

- `tienda/`: la aplicación (FastAPI + SQLite). La base se crea desde `generador/caso.py` en cada arranque.
- `generador/`: el origen de los datos del caso (la foto del 29 de septiembre de 2026).
- `render.yaml`: el despliegue en Render (New → Blueprint).

Correr en local: `pip install -r tienda/requirements.txt`, y desde `tienda/`:
`python -m uvicorn app.main:app --port 8000`.

El código fuente vive en el vault de OVO (`10 - OVO/Propuestas exploratorias/Kiltra - demo ecommerce/`): este
repo se regenera desde ahí con `tienda/despliegue/armar_repo.py`. No se edita a mano.
