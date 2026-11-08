"""
Capa de acceso a datos para el servidor MCP de MIRA (CU-1).
Ejecuta exclusivamente consultas SQL parametrizadas escritas por el equipo.
Valida reglas de negocio del corpus (PRO-ANT, POL-DEC) y aislamiento multitenant (PR-7).
"""

import os
import sqlite3
from typing import Dict, Any, List, Optional
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "mira_cu1.db")

def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn

class MIRADataRepository:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path

    def get_user(self, usuario_id: str) -> Optional[Dict[str, Any]]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT usuario_id, nombre, org_id, rol FROM usuarios WHERE usuario_id = ?", (usuario_id,))
            row = cur.fetchone()
            return dict(row) if row else None

    def get_case(self, caso_id: str, usuario_id: Optional[str] = None) -> Dict[str, Any]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT c.caso_id, c.org_id, o.nombre AS org_nombre, c.tipo_proceso, c.fecha_ingreso,
                       c.estado, c.puntaje, c.decision_sugerida, c.motivo_derivacion,
                       c.operador_asignado, u.nombre AS operador_nombre, c.vence_el, c.version_flujo,
                       o.umbral_aprobacion, o.umbral_revision, o.plazo_resolucion_dias_habiles
                FROM casos c
                JOIN organizaciones o ON c.org_id = o.org_id
                LEFT JOIN usuarios u ON c.operador_asignado = u.usuario_id
                WHERE c.caso_id = ?
            """, (caso_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"Caso '{caso_id}' no encontrado en el sistema."}

            case_data = dict(row)

            # Validación de aislamiento multitenant (Principio PR-7)
            if usuario_id:
                user = self.get_user(usuario_id)
                if not user:
                    return {"error": f"Usuario '{usuario_id}' no existe en el sistema."}
                if user["rol"] != "admin_dprime" and user["org_id"] != case_data["org_id"]:
                    return {
                        "error": (
                            f"Acceso denegado: El caso '{caso_id}' pertenece a {case_data['org_nombre']} ({case_data['org_id']}), "
                            f"pero el usuario conectado pertenece a {user['org_id']}. "
                            "El operador solo puede acceder a casos de su propia organización (PR-7)."
                        ),
                        "bloqueado_por_politica": "PR-7"
                    }

            return case_data

    def list_signals(self, caso_id: str, usuario_id: Optional[str] = None) -> Dict[str, Any]:
        # Validar permisos sobre el caso primero
        case_info = self.get_case(caso_id, usuario_id)
        if "error" in case_info:
            return case_info

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT senal_id, caso_id, codigo, valor, minimo, bajo_minimo, es_fraude, activa, detalle
                FROM senales
                WHERE caso_id = ?
                ORDER BY es_fraude DESC, bajo_minimo DESC, senal_id ASC
            """, (caso_id,))
            rows = cur.fetchall()

            signals = [dict(r) for r in rows]
            fraud_signals = [s for s in signals if s["es_fraude"] == "sí" and s["activa"] == "sí"]
            below_min_signals = [s for s in signals if s["bajo_minimo"] == "sí"]

            return {
                "caso_id": caso_id,
                "total_senales": len(signals),
                "senales": signals,
                "resumen_alertas": {
                    "alertas_fraude_activas": len(fraud_signals),
                    "codigos_fraude": [s["codigo"] for s in fraud_signals],
                    "senales_bajo_minimo": len(below_min_signals),
                    "codigos_bajo_minimo": [f"{s['codigo']} ({s['valor']} < {s['minimo']})" for s in below_min_signals]
                }
            }

    def list_evidence(self, caso_id: str, usuario_id: Optional[str] = None) -> Dict[str, Any]:
        case_info = self.get_case(caso_id, usuario_id)
        if "error" in case_info:
            return case_info

        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT evidencia_id, caso_id, tipo, nombre_archivo, paginas, legible, texto_extraido
                FROM evidencias
                WHERE caso_id = ?
                ORDER BY evidencia_id ASC
            """, (caso_id,))
            rows = cur.fetchall()
            return {
                "caso_id": caso_id,
                "total_evidencias": len(rows),
                "evidencias": [dict(r) for r in rows]
            }

    def get_org_thresholds(self, org_id: str) -> Dict[str, Any]:
        with get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT org_id, nombre, industria, pais, umbral_aprobacion, umbral_revision,
                       plazo_resolucion_dias_habiles, plazo_antecedentes_dias_habiles
                FROM organizaciones
                WHERE org_id = ?
            """, (org_id,))
            row = cur.fetchone()
            if not row:
                return {"error": f"Organización '{org_id}' no encontrada."}

            cur.execute("""
                SELECT cambio_id, parametro, valor_anterior, valor_nuevo, autor, aprobador_1, aprobador_2, fecha
                FROM cambios_umbral
                WHERE org_id = ?
                ORDER BY fecha DESC
            """, (org_id,))
            cambios = [dict(r) for r in cur.fetchall()]

            org_data = dict(row)
            org_data["historial_cambios"] = cambios
            return org_data

    def create_antecedent_request(
        self,
        caso_id: str,
        documentos_solicitados: str,
        motivo: str,
        usuario_id: str,
        confirmado_por_humano: bool = False
    ) -> Dict[str, Any]:
        """
        Registra una solicitud de antecedentes validando estrictamente:
        1. Existencia del caso y usuario.
        2. Aislamiento multitenant (PR-7).
        3. Prohibición sobre casos ya aprobados automáticamente (PRO-ANT §4).
        4. Roles válidos: solo operador o supervisor (PRO-ANT §4).
        5. Límite de 2 solicitudes por operador; una 3ra exige rol de supervisor (PRO-ANT §4).
        6. Confirmación explícita humana antes de producir efectos (PR-6).
        """
        case_info = self.get_case(caso_id, usuario_id)
        if "error" in case_info:
            return case_info

        user = self.get_user(usuario_id)
        if not user:
            return {"error": f"Usuario '{usuario_id}' no existe en el sistema."}

        # Regla PRO-ANT §4: Solo operador o supervisor
        if user["rol"] not in ["operador", "supervisor"]:
            return {
                "error": f"El rol '{user['rol']}' no tiene permisos para solicitar antecedentes (PRO-ANT §4).",
                "bloqueado_por_politica": "PRO-ANT §4"
            }

        # Regla PRO-ANT §4: No se puede sobre caso aprobado automáticamente
        if case_info["estado"] == "aprobado_automatico":
            return {
                "error": (
                    f"No se puede solicitar antecedentes sobre el caso '{caso_id}' porque ya fue aprobado automáticamente. "
                    "Ese caso no vuelve a revisarse (PRO-ANT §4)."
                ),
                "bloqueado_por_politica": "PRO-ANT §4"
            }

        with get_connection() as conn:
            cur = conn.cursor()
            # Contar solicitudes previas del caso
            cur.execute("""
                SELECT COUNT(*) as total FROM solicitudes_antecedentes WHERE caso_id = ?
            """, (caso_id,))
            conteo = cur.fetchone()["total"]

            # Regla PRO-ANT §4: Máximo 2 solicitudes para un operador. La 3ra exige supervisor.
            if conteo >= 2 and user["rol"] != "supervisor":
                return {
                    "error": (
                        f"{caso_id} ya tiene {conteo} solicitudes registradas; "
                        "una tercera debe registrarla un supervisor (PRO-ANT §4)."
                    ),
                    "bloqueado_por_politica": "PRO-ANT §4",
                    "solicitudes_existentes": conteo,
                    "rol_actual": user["rol"]
                }

            # Principio PR-6: Las acciones con efecto requieren confirmación explícita
            if not confirmado_por_humano:
                return {
                    "requiere_confirmacion": True,
                    "mensaje": (
                        f"Para registrar la solicitud de antecedentes sobre {caso_id}, "
                        "se requiere confirmación explícita del operador (PR-6)."
                    ),
                    "resumen_accion": {
                        "caso_id": caso_id,
                        "documentos_solicitados": documentos_solicitados,
                        "motivo": motivo,
                        "usuario_id": usuario_id,
                        "operador_nombre": user["nombre"],
                        "solicitud_numero": conteo + 1
                    }
                }

            # Inserción parametrizada con confirmación
            nuevo_num = conteo + 1
            cur.execute("SELECT COUNT(*) as total_global FROM solicitudes_antecedentes")
            total_global = cur.fetchone()["total_global"] + 1
            solicitud_id = f"SA-{total_global:03d}"
            fecha_actual = datetime.now().strftime("%Y-%m-%d")

            cur.execute("""
                INSERT INTO solicitudes_antecedentes (solicitud_id, caso_id, usuario_id, fecha, documentos_solicitados, motivo, estado)
                VALUES (?, ?, ?, ?, ?, ?, 'pendiente')
            """, (solicitud_id, caso_id, usuario_id, fecha_actual, documentos_solicitados, motivo))

            # Actualizar estado del caso a 'solicitud_antecedentes' (PRO-ANT §3)
            cur.execute("""
                UPDATE casos SET estado = 'solicitud_antecedentes' WHERE caso_id = ?
            """, (caso_id,))

            conn.commit()

            return {
                "exito": True,
                "solicitud_id": solicitud_id,
                "caso_id": caso_id,
                "nuevo_estado_caso": "solicitud_antecedentes",
                "mensaje": f"Solicitud {solicitud_id} registrada con éxito. El caso {caso_id} pasó al estado 'solicitud_antecedentes' (PRO-ANT §3)."
            }

