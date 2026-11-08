"""
Definición de Contratos y Esquemas de Herramientas del Servidor MCP de MIRA.
Sigue estrictamente la especificación del Model Context Protocol (MCP).
"""

from typing import Dict, Any, List
from mcp_server.db import MIRADataRepository

repo = MIRADataRepository()

MCP_TOOLS_SPEC = [
    {
        "name": "consultar_caso",
        "description": (
            "Consulta los datos vivos y estado de un caso en la base de datos de MIRA: "
            "organización, tipo de proceso, estado, puntaje algorítmico, decisión sugerida, "
            "motivo de derivación, operador asignado y fecha de vencimiento. "
            "Respeta aislamiento multitenant según el usuario conectado (PR-7)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "caso_id": {
                    "type": "string",
                    "description": "Identificador único del caso (ej: 'C-011', 'C-012')."
                },
                "usuario_id": {
                    "type": "string",
                    "description": "Identificador del usuario conectado para validar pertenencia de organización (ej: 'U-01')."
                }
            },
            "required": ["caso_id"]
        }
    },
    {
        "name": "listar_senales",
        "description": (
            "Obtiene el desglose de todas las señales analíticas asociadas a un caso específico: "
            "código de señal, valor numérico, mínimo requerido, si está bajo su mínimo, "
            "si es señal de fraude y si se encuentra activa con su detalle de hallazgo."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "caso_id": {
                    "type": "string",
                    "description": "Identificador único del caso (ej: 'C-012', 'C-013')."
                },
                "usuario_id": {
                    "type": "string",
                    "description": "Identificador del usuario que realiza la consulta."
                }
            },
            "required": ["caso_id"]
        }
    },
    {
        "name": "listar_evidencias",
        "description": (
            "Consulta las piezas documentales y capturas adjuntas a un caso: "
            "nombre del archivo, tipo (pdf/imagen), número de páginas, legibilidad "
            "y transcripción del texto extraído."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "caso_id": {
                    "type": "string",
                    "description": "Identificador único del caso (ej: 'C-011', 'C-014')."
                },
                "usuario_id": {
                    "type": "string",
                    "description": "Identificador del usuario conectado."
                }
            },
            "required": ["caso_id"]
        }
    },
    {
        "name": "consultar_umbrales_org",
        "description": (
            "Consulta los umbrales vigentes configurados para una organización cliente "
            "(umbral de aprobación, umbral de revisión, plazos hábiles) y su historial "
            "de modificaciones con sus respectivos aprobadores."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "org_id": {
                    "type": "string",
                    "description": "Código de la organización (ej: 'ORG-01', 'ORG-02', 'ORG-03')."
                }
            },
            "required": ["org_id"]
        }
    },
    {
        "name": "solicitar_antecedentes",
        "description": (
            "Registra formalmente una solicitud de antecedentes sobre un caso en revisión. "
            "Aplica las reglas de negocio de PRO-ANT §4 (máx 2 solicitudes para operador, "
            "tercera requiere supervisor, prohibido en aprobados automáticos) y el Principio PR-6 "
            "(requiere confirmación explícita del humano antes de persistir en la base de datos)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "caso_id": {
                    "type": "string",
                    "description": "Identificador del caso sobre el que se solicitan antecedentes."
                },
                "documentos_solicitados": {
                    "type": "string",
                    "description": "Detalle comprensible de los documentos o capturas requeridas."
                },
                "motivo": {
                    "type": "string",
                    "description": "Justificación no técnica del motivo por el cual la evidencia actual es insuficiente."
                },
                "usuario_id": {
                    "type": "string",
                    "description": "Identificador del operador o supervisor que emite la solicitud."
                },
                "confirmado_por_humano": {
                    "type": "boolean",
                    "description": "Indica si el operador humano ya confirmó la ejecución de la acción en la interfaz."
                }
            },
            "required": ["caso_id", "documentos_solicitados", "motivo", "usuario_id"]
        }
    }
]

def execute_tool(name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
    """
    Despachador central de ejecución de herramientas MCP.
    """
    if name == "consultar_caso":
        return repo.get_case(arguments.get("caso_id"), arguments.get("usuario_id"))
    elif name == "listar_senales":
        return repo.list_signals(arguments.get("caso_id"), arguments.get("usuario_id"))
    elif name == "listar_evidencias":
        return repo.list_evidence(arguments.get("caso_id"), arguments.get("usuario_id"))
    elif name == "consultar_umbrales_org":
        return repo.get_org_thresholds(arguments.get("org_id"))
    elif name == "solicitar_antecedentes":
        return repo.create_antecedent_request(
            caso_id=arguments.get("caso_id"),
            documentos_solicitados=arguments.get("documentos_solicitados"),
            motivo=arguments.get("motivo"),
            usuario_id=arguments.get("usuario_id"),
            confirmado_por_humano=arguments.get("confirmado_por_humano", False)
        )
    else:
        return {"error": f"Herramienta MCP '{name}' desconocida."}

