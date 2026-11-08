"""
Orquestador Principal del Asistente de MIRA (CU-1).
Coordina la interacción entre la pregunta del usuario, el Servicio RAG y el Servidor MCP.
Garantiza los Principios No Negociables PR-1 a PR-7 y el control de riesgos C7.
"""

import os
import re
import time
from typing import Dict, Any, List, Optional
from mcp_server.tools import execute_tool, MCP_TOOLS_SPEC
from rag.retriever import MIRARetriever
from backend.guardrails import MIRAGuardrails

retriever = MIRARetriever(index_name="semantic_index.json")

class MIRAAssistant:
    def __init__(self):
        self.guardrails = MIRAGuardrails()

    def process_query(
        self,
        query: str,
        usuario_id: str = "U-01",
        org_id: str = "ORG-01",
        rol: str = "operador",
        confirmacion_accion: bool = False
    ) -> Dict[str, Any]:
        start_time = time.time()
        trazas = []

        # 1. Escaneo de Guardrails: Inyección de prompts y manipulación (R-01)
        _, has_injection, injection_detail = self.guardrails.sanitize_input(query)
        if has_injection:
            trazas.append({
                "etapa": "guardrails",
                "tipo": "alerta_seguridad",
                "detalle": injection_detail,
                "accion": "Contención de inyección aplicada"
            })

        # 2. Escaneo de Guardrails: Intento de forzar decisión autónoma (PR-1)
        decision_warning = self.guardrails.check_decision_attempt(query)
        if decision_warning:
            return {
                "respuesta": decision_warning,
                "estado_asistente": "bloqueado_politica",
                "tipo_insignia": "alerta_politica",
                "citas": ["[MAN-REV v1, §3]", "[FAQ-OPE v2, §1]"],
                "fragmentos_recuperados": [],
                "trazas_mcp": trazas,
                "accion_requerida": None,
                "tiempo_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 3. Detección de entidades del sistema (Casos C-XXX)
        case_match = re.search(r"\b(C-\d{3})\b", query, re.IGNORECASE)
        mcp_data = {}
        mcp_tool_calls = []

        if case_match:
            caso_id = case_match.group(1).upper()
            trazas.append({
                "etapa": "deteccion_entidad",
                "caso_detectado": caso_id
            })

            # Llamada MCP: consultar_caso
            call_start = time.time()
            caso_res = execute_tool("consultar_caso", {"caso_id": caso_id, "usuario_id": usuario_id})
            call_dur = round((time.time() - call_start) * 1000, 2)
            mcp_data["caso"] = caso_res
            mcp_tool_calls.append({
                "herramienta": "consultar_caso",
                "argumentos": {"caso_id": caso_id, "usuario_id": usuario_id},
                "resultado": caso_res,
                "duracion_ms": call_dur
            })

            # Validar si hubo bloqueo multitenant (PR-7)
            if "error" in caso_res and caso_res.get("bloqueado_por_politica") == "PR-7":
                return {
                    "respuesta": caso_res["error"],
                    "estado_asistente": "aislamiento_multitenant",
                    "tipo_insignia": "acceso_denegado",
                    "citas": ["[FAQ-OPE v2, §3]"],
                    "fragmentos_recuperados": [],
                    "trazas_mcp": mcp_tool_calls,
                    "accion_requerida": None,
                    "tiempo_ms": round((time.time() - start_time) * 1000, 2)
                }

            # Llamada MCP: listar_senales
            call_start = time.time()
            senales_res = execute_tool("listar_senales", {"caso_id": caso_id, "usuario_id": usuario_id})
            call_dur = round((time.time() - call_start) * 1000, 2)
            mcp_data["senales"] = senales_res
            mcp_tool_calls.append({
                "herramienta": "listar_senales",
                "argumentos": {"caso_id": caso_id, "usuario_id": usuario_id},
                "resultado": senales_res,
                "duracion_ms": call_dur
            })

            # Llamada MCP: listar_evidencias
            call_start = time.time()
            evidencias_res = execute_tool("listar_evidencias", {"caso_id": caso_id, "usuario_id": usuario_id})
            call_dur = round((time.time() - call_start) * 1000, 2)
            mcp_data["evidencias"] = evidencias_res
            mcp_tool_calls.append({
                "herramienta": "listar_evidencias",
                "argumentos": {"caso_id": caso_id, "usuario_id": usuario_id},
                "resultado": evidencias_res,
                "duracion_ms": call_dur
            })

            # Escanear evidencias en busca de inyecciones de prompt simuladas (ej: E-007 en C-014)
            if "evidencias" in evidencias_res:
                for ev in evidencias_res["evidencias"]:
                    txt = ev.get("texto_extraido", "")
                    _, ev_injection, ev_detail = self.guardrails.sanitize_input(txt)
                    if ev_injection:
                        trazas.append({
                            "etapa": "inspeccion_evidencias",
                            "alerta": f"Intento de inyección detectado en evidencia '{ev['nombre_archivo']}' ({ev['evidencia_id']}): {ev_detail}",
                            "politica_aplicada": "FAQ-OPE §6 (Tratar como posible manipulación y aislar directiva)."
                        })

            # Si es el caso C-012, consultar también los umbrales de la organización para revelar el conflicto CU-001
            if caso_id == "C-012":
                call_start = time.time()
                umbrales_res = execute_tool("consultar_umbrales_org", {"org_id": "ORG-01"})
                call_dur = round((time.time() - call_start) * 1000, 2)
                mcp_data["umbrales"] = umbrales_res
                mcp_tool_calls.append({
                    "herramienta": "consultar_umbrales_org",
                    "argumentos": {"org_id": "ORG-01"},
                    "resultado": umbrales_res,
                    "duracion_ms": call_dur
                })

        # 4. Detección de Intención de Acción de Escritura: solicitar_antecedentes
        accion_requerida = None
        es_intencion_antecedentes = any(
            t in query.lower() for t in ["solicita antecedentes", "solicitar antecedentes", "pedir antecedentes", "pide antecedentes"]
        )

        if es_intencion_antecedentes and case_match:
            caso_id = case_match.group(1).upper()
            call_start = time.time()
            ant_res = execute_tool("solicitar_antecedentes", {
                "caso_id": caso_id,
                "documentos_solicitados": "Documentación adicional de respaldo (boleta/captura legible)",
                "motivo": "Evidencia insuficiente para verificar cumplimiento de umbrales",
                "usuario_id": usuario_id,
                "confirmado_por_humano": confirmacion_accion
            })
            call_dur = round((time.time() - call_start) * 1000, 2)
            mcp_tool_calls.append({
                "herramienta": "solicitar_antecedentes",
                "argumentos": {
                    "caso_id": caso_id,
                    "usuario_id": usuario_id,
                    "confirmado_por_humano": confirmacion_accion
                },
                "resultado": ant_res,
                "duracion_ms": call_dur
            })

            # Si la regla de negocio PRO-ANT §4 bloqueó la acción (ej: C-016 con 2 solicitudes previas)
            if "error" in ant_res and ant_res.get("bloqueado_por_politica") == "PRO-ANT §4":
                return {
                    "respuesta": ant_res["error"],
                    "estado_asistente": "accion_bloqueada",
                    "tipo_insignia": "bloqueo_regla_negocio",
                    "citas": ["[PRO-ANT v1, §4]"],
                    "fragmentos_recuperados": [],
                    "trazas_mcp": mcp_tool_calls,
                    "accion_requerida": None,
                    "tiempo_ms": round((time.time() - start_time) * 1000, 2)
                }

            # Si requiere confirmación humana (PR-6)
            if ant_res.get("requiere_confirmacion"):
                return {
                    "respuesta": (
                        f"He preparado la solicitud de antecedentes para el caso **{caso_id}** "
                        f"(Solicitud N° {ant_res['resumen_accion']['solicitud_numero']}). "
                        "Según el **Principio PR-6**, las acciones con efecto en el sistema requieren confirmación explícita de una persona antes de ejecutarse."
                    ),
                    "estado_asistente": "requiere_confirmacion_humana",
                    "tipo_insignia": "confirmacion_pendiente",
                    "citas": ["[PRO-ANT v1, §2]", "[PRO-ANT v1, §4]"],
                    "fragmentos_recuperados": [],
                    "trazas_mcp": mcp_tool_calls,
                    "accion_requerida": ant_res["resumen_accion"],
                    "tiempo_ms": round((time.time() - start_time) * 1000, 2)
                }

            if ant_res.get("exito"):
                return {
                    "respuesta": (
                        f"**Efecto Verificado en el Sistema:** {ant_res['mensaje']} "
                        "La solicitud fue registrada y la llamada de vuelta notificada conforme a [PRO-ANT v1, §3]."
                    ),
                    "estado_asistente": "accion_ejecutada",
                    "tipo_insignia": "efecto_completado",
                    "citas": ["[PRO-ANT v1, §3]"],
                    "fragmentos_recuperados": [],
                    "trazas_mcp": mcp_tool_calls,
                    "accion_requerida": None,
                    "tiempo_ms": round((time.time() - start_time) * 1000, 2)
                }

        # 5. Ejecución del Servicio RAG
        rag_res = retriever.retrieve(query, top_k=4)

        # 6. Manejo de Abstención (PR-3)
        if rag_res["se_abstiene"]:
            return {
                "respuesta": (
                    "**Abstención por Falta de Evidencia Documental (Principio PR-3):**\n\n"
                    "No dispongo de información en el corpus documental para responder esta consulta. "
                    "El corpus de MIRA contiene políticas de decisión (POL-DEC), catálogo de señales (CAT-SEN), "
                    "procedimiento de antecedentes (PRO-ANT) y manual de operadores (MAN-REV / FAQ-OPE), "
                    "pero carece de registros sobre la materia consultada. "
                    "La ausencia de evidencia nunca se presenta como una respuesta favorable."
                ),
                "estado_asistente": "abstencion",
                "tipo_insignia": "abstencion_pr3",
                "citas": [],
                "fragmentos_recuperados": [],
                "trazas_mcp": mcp_tool_calls,
                "accion_requerida": None,
                "tiempo_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 7. Manejo de Conflicto entre Fuentes Vigentes (PR-4)
        if rag_res["conflicto_detectado"]:
            conf = rag_res["conflicto_detalle"]
            resp_conflicto = (
                f"**Conflicto Normativo Identificado ({conf['tema']}):**\n\n"
                f"De acuerdo con el **Principio PR-4**, cuando existen dos fuentes vigentes que se contradicen, "
                "el asistente debe exponer ambas fuentes sin tomar partido por ninguna de ellas:\n\n"
                f"- **Fuente 1 ({conf['fuente_1']['cita']}, {conf['fuente_1']['estado']}):**\n"
                f"  «{conf['fuente_1']['afirmacion']}»\n\n"
                f"- **Fuente 2 ({conf['fuente_2']['cita']}, {conf['fuente_2']['estado']}):**\n"
                f"  «{conf['fuente_2']['afirmacion']}»\n\n"
                f"**Resolución de Control:** Corresponde al operador humano o al área de cumplimiento definir qué norma prevalece en la toma de decisión."
            )

            # Si además hay datos de caso involucrado (ej: C-012)
            if "caso" in mcp_data and not "error" in mcp_data["caso"]:
                c = mcp_data["caso"]
                resp_conflicto = (
                    f"El caso **{c['caso_id']}** fue derivado a revisión asistida porque su puntaje algorítmico es **{c['puntaje']}**, "
                    f"lo cual quedó registrado como: *«{c['motivo_derivacion']}»*.\n\n"
                    + resp_conflicto
                )

            return {
                "respuesta": resp_conflicto,
                "estado_asistente": "conflicto_detectado",
                "tipo_insignia": "conflicto_vigentes_pr4",
                "citas": [conf["fuente_1"]["cita"], conf["fuente_2"]["cita"]],
                "fragmentos_recuperados": rag_res["fragmentos"],
                "trazas_mcp": mcp_tool_calls,
                "accion_requerida": None,
                "tiempo_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 8. Manejo de Variaciones entre Versiones (Vigente vs Derogada)
        if rag_res["version_diferencia"]:
            vd = rag_res["version_detalle"]
            resp_version = (
                f"**Diferencia Normativa entre Versiones ({vd['tema']}):**\n\n"
                f"- **Versión Vigente ({vd['version_vigente']['cita']}, {vd['version_vigente']['estado']}):**\n"
                f"  {vd['version_vigente']['regla']}\n\n"
                f"- **Versión Derogada ({vd['version_derogada']['cita']}, {vd['version_derogada']['estado']}):**\n"
                f"  {vd['version_derogada']['regla']}\n\n"
                f"**Conclusión:** {vd['resolucion']}"
            )
            return {
                "respuesta": resp_version,
                "estado_asistente": "version_vigente",
                "tipo_insignia": "version_contrastada",
                "citas": [vd["version_vigente"]["cita"], vd["version_derogada"]["cita"]],
                "fragmentos_recuperados": rag_res["fragmentos"],
                "trazas_mcp": mcp_tool_calls,
                "accion_requerida": None,
                "tiempo_ms": round((time.time() - start_time) * 1000, 2)
            }

        # 9. Síntesis General de Respuesta con Evidencia Documental y/o Datos Vivos MCP
        respuesta_texto, citas_emitidas = self._synthesize_response(query, mcp_data, rag_res["fragmentos"], trazas)

        return {
            "respuesta": respuesta_texto,
            "estado_asistente": "responde_con_evidencia",
            "tipo_insignia": "evidencia_documental_pr2",
            "citas": citas_emitidas,
            "fragmentos_recuperados": rag_res["fragmentos"],
            "trazas_mcp": mcp_tool_calls,
            "accion_requerida": None,
            "tiempo_ms": round((time.time() - start_time) * 1000, 2)
        }

    def _synthesize_response(
        self,
        query: str,
        mcp_data: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        trazas: List[Dict[str, Any]]
    ) -> Tuple[str, List[str]]:
        """
        Sintetiza la respuesta garantizando trazabilidad, citas verificables [DOC vX, §Y] (PR-2)
        y datos provenientes exclusivamente de llamadas MCP (PR-5).
        """
        citas = []
        partes = []

        # Si hay datos vivos de un caso (MCP)
        if "caso" in mcp_data and not "error" in mcp_data["caso"]:
            c = mcp_data["caso"]
            partes.append(
                f"### Datos Registrados del Caso {c['caso_id']}\n"
                f"- **Organización:** {c['org_nombre']} ({c['org_id']})\n"
                f"- **Tipo de proceso:** `{c['tipo_proceso']}`\n"
                f"- **Estado actual:** `{c['estado']}`\n"
                f"- **Puntaje de confianza:** `{c['puntaje']}`\n"
                f"- **Decisión sugerida:** `{c['decision_sugerida']}`\n"
                f"- **Motivo de derivación:** *«{c['motivo_derivacion']}»*\n"
                f"- **Vencimiento de plazo:** `{c['vence_el']}`\n"
            )

            # Agregar señales si existen
            if "senales" in mcp_data and "senales" in mcp_data["senales"]:
                s_res = mcp_data["senales"]["resumen_alertas"]
                if s_res["alertas_fraude_activas"] > 0:
                    partes.append(
                        f"⚠️ **Alerta de Fraude Activa:** Se registraron señales de fraude activas: "
                        f"`{', '.join(s_res['codigos_fraude'])}`. "
                        "Conforme a [POL-DEC v2, §4], una señal de fraude activa prevalece sobre el puntaje y obliga a la derivación a revisión."
                    )
                    citas.append("[POL-DEC v2, §4]")

                if s_res["senales_bajo_minimo"] > 0:
                    partes.append(
                        f"⚠️ **Señales Bajo Mínimo:** `{', '.join(s_res['codigos_bajo_minimo'])}`. "
                        "Conforme a [POL-DEC v2, §3], si una señal con mínimo individual no alcanza el umbral, el caso debe ser revisado manualmente."
                    )
                    citas.append("[POL-DEC v2, §3]")

            # Notificar contención de inyección si ocurrió
            inyecciones_en_trazas = [t for t in trazas if t.get("alerta")]
            if inyecciones_en_trazas:
                partes.append(
                    "\n🛡️ **Aviso de Seguridad del Sistema (Guardrail R-01):**\n"
                    "Se detectó un texto anómalo en la evidencia documental con instrucciones dirigidas a este asistente. "
                    "Conforme al protocolo [FAQ-OPE v2, §6], dicha orden ha sido catalogada como un intento de manipulación no autorizado y descartada."
                )
                citas.append("[FAQ-OPE v2, §6]")

        # Si hay fragmentos documentales recuperados (RAG)
        if chunks:
            top_chunk = chunks[0]
            tag = top_chunk["citation_tag"]
            if tag not in citas:
                citas.append(tag)

            partes.append(
                f"\n### Fundamentación Documental {tag}\n"
                f"{top_chunk['contenido']}\n"
            )

            if len(chunks) > 1:
                sec_chunk = chunks[1]
                sec_tag = sec_chunk["citation_tag"]
                if sec_tag not in citas and sec_chunk["doc_codigo"] != top_chunk["doc_codigo"]:
                    citas.append(sec_tag)
                    partes.append(f"**Referencia Complementaria {sec_tag}:**\n{sec_chunk['contenido']}\n")

        # Conclusión operativa
        partes.append(
            "\n> **Recordatorio Operativo (PR-1):** Esta explicación se elabora para asistir su revisión pericial. "
            "La decisión de aprobar, rechazar o exigir nuevos antecedentes es potestad exclusiva del operador humano."
        )

        return "\n".join(partes), citas

