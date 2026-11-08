"""
Inventario Oficial del Corpus Documental de MIRA (CU-1: Asistente del operador de revisión).
Cumple con la sección 4.1 y la Rúbrica C3.
"""

CORPUS_INVENTORY = [
    {
        "id": "CAT-SEN",
        "titulo": "Catálogo de señales de MIRA",
        "origen": "kit",
        "archivo": "CAT-SEN_catalogo_senales.md",
        "version": "3",
        "estado": "Vigente",
        "vigencia": "Desde el 1 de septiembre de 2026",
        "responsable": "Equipo de Ingeniería de Modelos, DPRIME",
        "palabras": 564,
        "tokens_aprox": 733,
        "descripcion": "Define señales documentales, metadatos, biométricas, cruce de fuentes y señales de fraude."
    },
    {
        "id": "FAQ-OPE",
        "titulo": "Preguntas frecuentes de operadores",
        "origen": "kit",
        "archivo": "FAQ-OPE_preguntas_frecuentes_operadores.md",
        "version": "2",
        "estado": "Vigente",
        "vigencia": "Desde el 1 de octubre de 2026",
        "responsable": "Equipo de Soporte y Operación, DPRIME",
        "palabras": 287,
        "tokens_aprox": 373,
        "descripcion": "Respuestas directas sobre el alcance del asistente, roles, manipulación de documentos y corrección de datos."
    },
    {
        "id": "MAN-REV",
        "titulo": "Manual de revisión asistida para operadores",
        "origen": "kit",
        "archivo": "MAN-REV_manual_revision_asistida.md",
        "version": "1",
        "estado": "Vigente",
        "vigencia": "Desde el 15 de julio de 2026",
        "responsable": "Equipo de Soporte y Operación, DPRIME",
        "palabras": 455,
        "tokens_aprox": 591,
        "descripcion": "Describe flujo de revisión en bandeja, decisiones de operador (aprobar, rechazar, antecedentes) y plazos."
    },
    {
        "id": "POL-DEC-v1",
        "titulo": "Política de decisión y umbrales (v1)",
        "origen": "kit",
        "archivo": "POL-DEC_v1_derogada.md",
        "version": "1",
        "estado": "Derogada",
        "vigencia": "2 de marzo de 2026 al 31 de agosto de 2026 (Reemplazada por v2)",
        "responsable": "Dirección de Producto, DPRIME",
        "palabras": 269,
        "tokens_aprox": 349,
        "descripcion": "Versión obsoleta donde señales de fraude restaban 20 puntos y cualquier diseñador cambiaba umbrales."
    },
    {
        "id": "POL-DEC-v2",
        "titulo": "Política de decisión y umbrales (v2)",
        "origen": "kit",
        "archivo": "POL-DEC_v2_vigente.md",
        "version": "2",
        "estado": "Vigente",
        "vigencia": "Desde el 1 de septiembre de 2026 (Reemplaza a v1)",
        "responsable": "Dirección de Producto, DPRIME, con revisión de Cumplimiento",
        "palabras": 528,
        "tokens_aprox": 686,
        "descripcion": "Política vigente: mínimos por señal (DOC_AUT >= 70, etc.), fraude prevalece sobre puntaje, doble aprobación supervisores."
    },
    {
        "id": "PRO-ANT",
        "titulo": "Procedimiento de solicitud de antecedentes",
        "origen": "kit",
        "archivo": "PRO-ANT_solicitud_antecedentes.md",
        "version": "1",
        "estado": "Vigente",
        "vigencia": "Desde el 15 de julio de 2026",
        "responsable": "Equipo de Soporte y Operación, DPRIME",
        "palabras": 353,
        "tokens_aprox": 458,
        "descripcion": "Normas para pedir antecedentes: contenido, límites de operador (máx 2; 3ra por supervisor) y plazos."
    }
]

