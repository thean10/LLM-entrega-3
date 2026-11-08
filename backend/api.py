"""
API REST FastAPI para el Asistente de MIRA (CU-1).
Expone endpoints de conversación, inspección de casos, confirmación de acciones,
gestión de usuarios (tenants) y metadatos del corpus.
"""

import os
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from backend.assistant import MIRAAssistant
from mcp_server.db import MIRADataRepository, get_connection
from rag.corpus_inventory import CORPUS_INVENTORY

app = FastAPI(
    title="MIRA — Asistente del Operador de Revisión (CU-1)",
    description="Servidor con RAG, MCP propio, Aislamiento Multitenant y Validación de Reglas.",
    version="3.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

assistant = MIRAAssistant()
repo = MIRADataRepository()

class ChatRequest(BaseModel):
    query: str
    usuario_id: str = "U-01"
    org_id: str = "ORG-01"
    rol: str = "operador"
    confirmacion_accion: bool = False

class ConfirmActionRequest(BaseModel):
    caso_id: str
    documentos_solicitados: str
    motivo: str
    usuario_id: str = "U-01"

@app.get("/api/status")
def get_status():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM casos")
        total_casos = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM usuarios")
        total_usuarios = cur.fetchone()[0]

    return {
        "sistema": "MIRA Asistente CU-1",
        "version": "3.0.0",
        "estado": "operacional",
        "total_casos_db": total_casos,
        "total_usuarios_db": total_usuarios,
        "documentos_corpus": len(CORPUS_INVENTORY)
    }

@app.post("/api/chat")
def chat(req: ChatRequest):
    try:
        res = assistant.process_query(
            query=req.query,
            usuario_id=req.usuario_id,
            org_id=req.org_id,
            rol=req.rol,
            confirmacion_accion=req.confirmacion_accion
        )
        return res
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en el procesamiento del asistente: {str(e)}"
        )

@app.post("/api/chat/confirm_action")
def confirm_action(req: ConfirmActionRequest):
    try:
        res = assistant.process_query(
            query=f"solicitar antecedentes para {req.caso_id}",
            usuario_id=req.usuario_id,
            confirmacion_accion=True
        )
        return res
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al confirmar acción: {str(e)}"
        )

@app.get("/api/usuarios")
def list_users():
    with get_connection() as conn:
        cur = conn.cursor()
        cur.execute("""
            SELECT u.usuario_id, u.nombre, u.org_id, o.nombre as org_nombre, u.rol
            FROM usuarios u
            JOIN organizaciones o ON u.org_id = o.org_id
            ORDER BY u.org_id, u.usuario_id
        """)
        users = [dict(r) for r in cur.fetchall()]
        return {"usuarios": users}

@app.get("/api/casos")
def list_cases(usuario_id: Optional[str] = None):
    with get_connection() as conn:
        cur = conn.cursor()
        if usuario_id:
            user = repo.get_user(usuario_id)
            if not user:
                raise HTTPException(status_code=404, detail="Usuario no encontrado")
            cur.execute("""
                SELECT c.caso_id, c.org_id, o.nombre as org_nombre, c.tipo_proceso,
                       c.fecha_ingreso, c.estado, c.puntaje, c.decision_sugerida,
                       c.motivo_derivacion, c.vence_el
                FROM casos c
                JOIN organizaciones o ON c.org_id = o.org_id
                WHERE c.org_id = ?
                ORDER BY c.caso_id ASC
            """, (user["org_id"],))
        else:
            cur.execute("""
                SELECT c.caso_id, c.org_id, o.nombre as org_nombre, c.tipo_proceso,
                       c.fecha_ingreso, c.estado, c.puntaje, c.decision_sugerida,
                       c.motivo_derivacion, c.vence_el
                FROM casos c
                JOIN organizaciones o ON c.org_id = o.org_id
                ORDER BY c.caso_id ASC
            """)
        rows = [dict(r) for r in cur.fetchall()]
        return {"casos": rows}

@app.get("/api/corpus")
def get_corpus():
    return {"inventario": CORPUS_INVENTORY}

# Montar carpeta de evaluación para reportes JSON
eval_dir = os.path.join(os.path.dirname(__file__), "..", "evaluation")
if os.path.exists(eval_dir):
    app.mount("/evaluation", StaticFiles(directory=eval_dir), name="evaluation")

# Montar frontend estático si existe la carpeta
frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "dist")
if not os.path.exists(frontend_dir):
    frontend_dir = os.path.join(os.path.dirname(__file__), "..", "frontend", "public")

if os.path.exists(frontend_dir):
    app.mount("/", StaticFiles(directory=frontend_dir, html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.api:app", host="0.0.0.0", port=8000, reload=True)
