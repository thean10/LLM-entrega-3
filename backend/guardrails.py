"""
Módulo de Seguridad y Guardrails de MIRA.
Implementa defensas contra los riesgos identificados en la Rúbrica C7:
1. R-01: Inyección de prompts y manipulación indirecta desde evidencias documentales (FAQ-OPE §6 / E-007 Caso C-014).
2. R-02: Alucinación de aprobación o rechazo autónomo sin intervención humana (PR-1 / PR-2).
3. R-03: Fuga de información y violación de aislamiento multitenant (PR-7).
4. R-04: Ejecución no autorizada o extralimitación de acciones de escritura (PR-6 / PRO-ANT §4).
"""

import re
from typing import Dict, Any, Tuple, Optional

INJECTION_PATTERNS = [
    r"ignora\s+(las\s+)?(instrucciones|políticas|reglas|órdenes)",
    r"ignore\s+(previous|all)\s+instructions",
    r"olvida\s+(las\s+)?(instrucciones|reglas|políticas)",
    r"responde\s+que\s+este\s+caso\s+cumple",
    r"aprueba\s+(de\s+inmediato|automáticamente|este\s+caso)",
    r"pasa\s+por\s+alto",
    r"system\s*prompt",
    r"nota\s+para\s+el\s+asistente"
]

class MIRAGuardrails:
    @staticmethod
    def sanitize_input(text: str) -> Tuple[str, bool, Optional[str]]:
        """
        Escanea el texto del usuario o de evidencias en busca de patrones de inyección o manipulación.
        """
        text_lower = text.lower()
        for pattern in INJECTION_PATTERNS:
            if re.search(pattern, text_lower, re.IGNORECASE):
                return text, True, f"Patrón de inyección detectado: '{pattern}'. Aplicando aislamiento de contexto (FAQ-OPE §6)."
        return text, False, None

    @staticmethod
    def check_decision_attempt(query: str) -> Optional[str]:
        """
        Detecta si el usuario está ordenando al asistente aprobar o rechazar directamente (PR-1).
        """
        q_lower = query.lower()
        if re.search(r"\b(aprueba|rechaza)\s+(el\s+)?caso\s+[c|e]-?\d+", q_lower):
            return (
                "El asistente no decide sobre un caso. Explica, sugiere y prepara; "
                "la decisión la toma y la confirma una persona (Principio PR-1, MAN-REV §3, FAQ-OPE §1)."
            )
        return None

    @staticmethod
    def check_multitenant_access(user_org: str, case_org: str, case_id: str) -> Optional[str]:
        """
        Garantiza que un usuario no pueda acceder a casos de otra organización (PR-7).
        """
        if user_org != case_org:
            return (
                f"Acceso denegado: El caso '{case_id}' pertenece a la organización '{case_org}', "
                f"mientras que su sesión corresponde a '{user_org}'. "
                "El asistente solo accede a los datos de la organización del usuario conectado (Principio PR-7)."
            )
        return None

