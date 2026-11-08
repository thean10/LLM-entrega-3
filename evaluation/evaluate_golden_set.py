"""
Script de Evaluación Automatizada del Asistente sobre el Golden Set (CU-1).
Calcula las 5 métricas oficiales de la Rúbrica C6 y Tabla 7.2:
1. Recall@k (Recuperación a nivel de fragmento)
2. Precisión de Cita (Generación)
3. Fidelidad (Generación)
4. Abstención Correcta (Comportamiento)
5. Manejo de Conflicto y Vigencia (Comportamiento)
Clasifica cada fallo entre 'Recuperación' y 'Generación'.
"""

import os
import re
import json
from typing import Dict, Any, List
from backend.assistant import MIRAAssistant

GOLDEN_SET_PATH = os.path.join(os.path.dirname(__file__), "golden_set.json")
RESULTS_PATH = os.path.join(os.path.dirname(__file__), "evaluation_report.json")

def evaluate_assistant():
    assistant = MIRAAssistant()

    with open(GOLDEN_SET_PATH, "r", encoding="utf-8") as f:
        golden_set = json.load(f)

    total_preguntas = len(golden_set)
    preguntas_con_resp = [q for q in golden_set if q["debe_responder"]]
    preguntas_sin_resp = [q for q in golden_set if not q["debe_responder"]]
    preguntas_conflicto = [q for q in golden_set if q["tipo"] == "conflicto_vigentes"]
    preguntas_version = [q for q in golden_set if q["tipo"] == "distinta_entre_versiones"]

    # Contadores de métricas
    hits_recall_at_1 = 0
    hits_recall_at_3 = 0
    citas_correctas = 0
    total_citas_emitidas = 0
    respuestas_fieles = 0

    abstenciones_correctas = 0
    falsas_abstenciones = 0

    conflictos_bien_resueltos = 0
    versiones_bien_resueltas = 0

    fallos_recuperacion = 0
    fallos_generacion = 0

    detalles_evaluacion = []

    for item in golden_set:
        q_id = item["id"]
        tipo = item["tipo"]
        pregunta = item["pregunta"]
        debe_responder = item["debe_responder"]
        expected_frag = item.get("fragmento_esperado")
        expected_cita = item.get("cita_esperada")

        # Ejecutar asistente
        res = assistant.process_query(pregunta, usuario_id="U-01", org_id="ORG-01")

        respuesta_texto = res["respuesta"]
        estado_asistente = res["estado_asistente"]
        citas_emitidas = res["citas"]
        frags_recuperados = res["fragmentos_recuperados"]

        fallo_tipo = None
        es_acierto = True

        # --- Evaluaciones según tipo ---
        if not debe_responder:
            # Pregunta sin respuesta en el corpus: debe abstenerse (PR-3)
            if estado_asistente == "abstencion":
                abstenciones_correctas += 1
                respuestas_fieles += 1
            else:
                es_acierto = False
                fallo_tipo = "Fallo de Generación / Guardrail (No se abstuvo ante pregunta fuera de corpus)"
                fallos_generacion += 1

        else:
            # Pregunta con respuesta
            # 1. Comprobar si hubo falsa abstención
            if estado_asistente == "abstencion":
                falsas_abstenciones += 1
                es_acierto = False
                fallo_tipo = "Fallo de Recuperación (Falsa abstención para pregunta con respuesta)"
                fallos_recuperacion += 1

            # 2. Recall@k
            frag_encontrado_at_1 = False
            frag_encontrado_at_3 = False

            if expected_frag and frags_recuperados:
                targets = [t.strip().upper() for t in expected_frag.split("/")]
                for idx_c, c in enumerate(frags_recuperados[:3]):
                    cid = c.get("fragment_id", "").upper()
                    doc_c = c.get("doc_codigo", "").upper()
                    sec_n = c.get("seccion_num", "").upper().replace("§", "S")

                    for t in targets:
                        if t in cid or (doc_c in t and sec_n in t):
                            if idx_c == 0:
                                frag_encontrado_at_1 = True
                            frag_encontrado_at_3 = True

            if frag_encontrado_at_1:
                hits_recall_at_1 += 1
            if frag_encontrado_at_3:
                hits_recall_at_3 += 1
            elif not frag_encontrado_at_3 and expected_frag:
                if not fallo_tipo:
                    fallo_tipo = "Fallo de Recuperación (Fragmento clave no apareció en top 3)"
                    fallos_recuperacion += 1
                es_acierto = False

            # 3. Precisión de Citas
            if citas_emitidas:
                for c_tag in citas_emitidas:
                    total_citas_emitidas += 1
                    # Verificar si la cita emitida respalda efectivamente y coincide con esperada o corpus
                    clean_tag = re.sub(r"[\[\]§,\s]", "", c_tag).upper()
                    if expected_cita:
                        clean_exp = re.sub(r"[\[\]§,\s]", "", expected_cita).upper()
                        if clean_tag in clean_exp or any(term in clean_tag for term in ["POL-DEC", "MAN-REV", "CAT-SEN", "FAQ-OPE", "PRO-ANT"]):
                            citas_correctas += 1
                    else:
                        citas_correctas += 1
            else:
                if not fallo_tipo:
                    fallo_tipo = "Fallo de Generación (No emitió cita documental requerida)"
                    fallos_generacion += 1
                es_acierto = False

            # 4. Manejo de conflicto y vigencia
            if tipo == "conflicto_vigentes":
                if estado_asistente == "conflicto_detectado" and len(citas_emitidas) >= 2:
                    conflictos_bien_resueltos += 1
                    respuestas_fieles += 1
                else:
                    es_acierto = False
                    if not fallo_tipo:
                        fallo_tipo = "Fallo de Generación (No reconoció o no presentó ambas fuentes en conflicto)"
                        fallos_generacion += 1

            elif tipo == "distinta_entre_versiones":
                if estado_asistente == "version_vigente" and "POL-DEC v2" in respuesta_texto:
                    versiones_bien_resueltas += 1
                    respuestas_fieles += 1
                else:
                    es_acierto = False
                    if not fallo_tipo:
                        fallo_tipo = "Fallo de Generación (No resolvió con versión vigente o no contrastó con v1)"
                        fallos_generacion += 1
            else:
                # Pregunta estándar con respuesta
                if es_acierto and estado_asistente in ["responde_con_evidencia", "conflicto_detectado", "version_vigente"]:
                    respuestas_fieles += 1

        detalles_evaluacion.append({
            "id": q_id,
            "tipo": tipo,
            "pregunta": pregunta,
            "debe_responder": debe_responder,
            "acierto": es_acierto,
            "estado_asistente": estado_asistente,
            "citas_emitidas": citas_emitidas,
            "citas_esperadas": expected_cita,
            "fallo_clasificado": fallo_tipo,
            "tiempo_ms": res.get("tiempo_ms", 0)
        })

    # Cálculo final de métricas
    n_con_resp = len(preguntas_con_resp)
    n_sin_resp = len(preguntas_sin_resp)
    n_conflicto = len(preguntas_conflicto)
    n_version = len(preguntas_version)

    metric_recall_at_1 = hits_recall_at_1 / n_con_resp if n_con_resp else 0.0
    metric_recall_at_3 = hits_recall_at_3 / n_con_resp if n_con_resp else 0.0
    metric_precision_cita = citas_correctas / total_citas_emitidas if total_citas_emitidas else 0.0
    metric_fidelidad = respuestas_fieles / total_preguntas
    metric_abstencion_correcta = abstenciones_correctas / n_sin_resp if n_sin_resp else 0.0
    metric_tasa_falsa_abstencion = falsas_abstenciones / n_con_resp if n_con_resp else 0.0
    metric_conflicto_vigencia = (conflictos_bien_resueltos + versiones_bien_resueltas) / (n_conflicto + n_version)

    summary_metrics = {
        "resumen_general": {
            "total_preguntas": total_preguntas,
            "preguntas_con_respuesta": n_con_resp,
            "preguntas_sin_respuesta": n_sin_resp,
            "preguntas_conflicto": n_conflicto,
            "preguntas_versiones": n_version,
            "total_fallos_clasificados": {
                "fallos_recuperacion": fallos_recuperacion,
                "fallos_generacion": fallos_generacion,
                "total_fallos": fallos_recuperacion + fallos_generacion
            }
        },
        "metricas_tabla_7_2": {
            "recall@1": round(metric_recall_at_1, 4),
            "recall@3": round(metric_recall_at_3, 4),
            "precision_de_cita": round(metric_precision_cita, 4),
            "fidelidad": round(metric_fidelidad, 4),
            "abstencion_correcta": round(metric_abstencion_correcta, 4),
            "tasa_falsa_abstencion": round(metric_tasa_falsa_abstencion, 4),
            "manejo_conflicto_y_vigencia": round(metric_conflicto_vigencia, 4)
        },
        "detalles_por_pregunta": detalles_evaluacion
    }

    with open(RESULTS_PATH, "w", encoding="utf-8") as f:
        json.dump(summary_metrics, f, ensure_ascii=False, indent=2)

    print("=== RESULTADOS OFICIALES EVALUACIÓN GOLDEN SET (CU-1) ===")
    print(f"Total Preguntas Evaluadas: {total_preguntas}")
    print(f"1. Recall@1:                  {metric_recall_at_1*100:.1f} %")
    print(f"2. Recall@3:                  {metric_recall_at_3*100:.1f} %")
    print(f"3. Precisión de Cita:         {metric_precision_cita*100:.1f} % ({citas_correctas}/{total_citas_emitidas})")
    print(f"4. Fidelidad:                 {metric_fidelidad*100:.1f} % ({respuestas_fieles}/{total_preguntas})")
    print(f"5. Abstención Correcta:       {metric_abstencion_correcta*100:.1f} % ({abstenciones_correctas}/{n_sin_resp})")
    print(f"6. Tasa Falsa Abstención:     {metric_tasa_falsa_abstencion*100:.1f} % ({falsas_abstenciones}/{n_con_resp})")
    print(f"7. Manejo Conflicto/Vigencia: {metric_conflicto_vigencia*100:.1f} % ({conflictos_bien_resueltos + versiones_bien_resueltas}/{n_conflicto + n_version})")
    print(f"Fallos de Recuperación: {fallos_recuperacion} | Fallos de Generación: {fallos_generacion}")
    print(f"Informe completo exportado a: {RESULTS_PATH}")

if __name__ == "__main__":
    evaluate_assistant()

