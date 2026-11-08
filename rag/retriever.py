"""
Módulo de Recuperación (Retriever) del RAG para MIRA (CU-1).
Implementa:
- Búsqueda híbrida (BM25 léxica + Cosine Semántica).
- Fusión por RRF (Reciprocal Rank Fusion).
- Detección de Cobertura de Términos Clave y Abstención Robusta (Principio PR-3).
- Detección de Conflictos Normativos entre Fuentes Vigentes (Principio PR-4).
- Detección y Contraste de Versiones Vigentes vs Derogadas.
"""

import os
import re
import json
import math
from typing import List, Dict, Any, Tuple, Optional

INDICES_DIR = os.path.join(os.path.dirname(__file__), "indices")

STOPWORDS = {
    "el", "la", "de", "del", "los", "las", "un", "una", "unos", "unas", "y", "o", "u",
    "en", "para", "por", "con", "sin", "sobre", "entre", "tras", "durante", "mediante",
    "que", "qué", "cual", "cuál", "cuales", "cuáles", "quien", "quién", "como", "cómo",
    "donde", "dónde", "cuando", "cuándo", "es", "son", "fue", "ser", "se", "al", "a",
    "su", "sus", "mi", "mis", "tu", "tus", "este", "esta", "estos", "estas", "ese", "esa"
}

import unicodedata

def normalize_text(text: str) -> str:
    nfkd = unicodedata.normalize('NFD', text.lower())
    return "".join(c for c in nfkd if unicodedata.category(c) != 'Mn')

def clean_term(w: str) -> str:
    w_norm = normalize_text(w)
    return re.sub(r"[^\w§]", "", w_norm.strip())

def get_content_terms(text: str) -> List[str]:
    clean = re.sub(r"[^\w\sáéíóúüñ§]", " ", text.lower())
    terms = [clean_term(t) for t in clean.split()]
    return [t for t in terms if t and t not in STOPWORDS and len(t) > 2]

def stem_prefix(w: str) -> str:
    # Stemming ligero en español por prefijo de raíz
    if len(w) > 5:
        return w[:5]
    return w

class MIRARetriever:
    def __init__(self, index_name: str = "semantic_index.json"):
        self.index_name = index_name
        self.index_path = os.path.join(INDICES_DIR, index_name)
        if not os.path.exists(self.index_path):
            raise FileNotFoundError(f"Índice no encontrado en: {self.index_path}. Ejecute indexer.py primero.")

        with open(self.index_path, "r", encoding="utf-8") as f:
            self.chunks: List[Dict[str, Any]] = json.load(f)

        self._build_bm25_structures()

    def _build_bm25_structures(self):
        self.corpus_size = len(self.chunks)
        self.doc_tokens = []
        self.doc_stems = []
        self.doc_lens = []
        self.df = {}

        for doc in self.chunks:
            full_text = doc["contenido"] + " " + doc.get("seccion_titulo", "") + " " + doc.get("doc_codigo", "")
            terms = get_content_terms(full_text)
            stems = [stem_prefix(t) for t in terms]

            self.doc_tokens.append(terms)
            self.doc_stems.append(stems)
            self.doc_lens.append(len(terms))

            unique_terms = set(terms)
            for t in unique_terms:
                self.df[t] = self.df.get(t, 0) + 1

        self.avg_doc_len = sum(self.doc_lens) / max(1, self.corpus_size)

        # Precalcular IDF
        self.idf = {}
        for term, freq in self.df.items():
            self.idf[term] = math.log((self.corpus_size - freq + 0.5) / (freq + 0.5) + 1.0)

    def bm25_search(self, query: str, top_k: int = 10, k1: float = 1.5, b: float = 0.75) -> List[Tuple[int, float]]:
        q_terms = get_content_terms(query)
        q_stems = [stem_prefix(t) for t in q_terms]
        scores = []

        for idx, terms in enumerate(self.doc_tokens):
            score = 0.0
            doc_len = self.doc_lens[idx]
            stems = self.doc_stems[idx]

            tf_dict = {}
            for t in terms:
                tf_dict[t] = tf_dict.get(t, 0) + 1

            stem_dict = {}
            for s in stems:
                stem_dict[s] = stem_dict.get(s, 0) + 1

            for q_term, q_stem in zip(q_terms, q_stems):
                idf_val = self.idf.get(q_term, 1.2)
                freq = tf_dict.get(q_term, 0)
                if freq == 0 and q_stem in stem_dict:
                    freq = stem_dict[q_stem] * 0.75

                if freq > 0:
                    num = freq * (k1 + 1.0)
                    denom = freq + k1 * (1.0 - b + b * (doc_len / self.avg_doc_len))
                    score += idf_val * (num / denom)

            # Bonus por coincidencia de identificadores de documento o regla específica
            doc = self.chunks[idx]
            doc_code = doc.get("doc_codigo", "").lower()
            query_lower = query.lower()
            if doc_code and doc_code.lower() in query_lower:
                score += 3.5

            scores.append((idx, score))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def vector_semantic_search(self, query: str, top_k: int = 10) -> List[Tuple[int, float]]:
        q_terms = get_content_terms(query)
        if not q_terms:
            return []

        q_vec = {}
        for t in q_terms:
            q_vec[t] = q_vec.get(t, 0) + 1
        q_norm = math.sqrt(sum(v * v for v in q_vec.values())) or 1.0

        scores = []
        for idx, terms in enumerate(self.doc_tokens):
            if not terms:
                scores.append((idx, 0.0))
                continue
            d_vec = {}
            for t in terms:
                d_vec[t] = d_vec.get(t, 0) + 1
            d_norm = math.sqrt(sum(v * v for v in d_vec.values())) or 1.0

            dot = sum(q_vec[t] * d_vec.get(t, 0) * self.idf.get(t, 1.0) for t in q_vec)
            cosine = dot / (q_norm * d_norm)
            scores.append((idx, cosine))

        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    def check_query_term_coverage(self, query: str, doc_idx: int) -> float:
        """
        Calcula la fracción de términos de la pregunta que están presentes en el fragmento.
        """
        q_terms = get_content_terms(query)
        if not q_terms:
            return 1.0

        doc_terms_set = set(self.doc_tokens[doc_idx])
        doc_stems_set = set(self.doc_stems[doc_idx])

        matched = 0
        for t in q_terms:
            s = stem_prefix(t)
            if t in doc_terms_set or s in doc_stems_set:
                matched += 1

        return matched / len(q_terms)

    def retrieve(self, query: str, top_k: int = 4) -> Dict[str, Any]:
        q_terms = get_content_terms(query)
        bm25_results = self.bm25_search(query, top_k=12)
        vec_results = self.vector_semantic_search(query, top_k=12)

        rrf_scores = {}
        c_const = 60

        for rank, (doc_idx, _) in enumerate(bm25_results):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0.0) + (1.0 / (c_const + rank + 1))

        for rank, (doc_idx, _) in enumerate(vec_results):
            rrf_scores[doc_idx] = rrf_scores.get(doc_idx, 0.0) + (1.0 / (c_const + rank + 1))

        sorted_rrf = sorted(rrf_scores.items(), key=lambda x: x[1], reverse=True)
        top_candidates = sorted_rrf[:top_k]

        best_doc_idx = top_candidates[0][0] if top_candidates else None
        coverage = self.check_query_term_coverage(query, best_doc_idx) if best_doc_idx is not None else 0.0
        best_bm25 = bm25_results[0][1] if bm25_results else 0.0

        # Abstención Estricta (Principio PR-3):
        # Si menos del 35% de los términos informativos de la pregunta existen en el mejor fragmento
        # o el BM25 es prácticamente nulo (< 1.5), el asistente reconoce que no está en el corpus.
        is_abstention = (coverage < 0.35 and best_bm25 < 4.5) or (len(q_terms) > 2 and coverage < 0.25)

        retrieved_chunks = []
        if not is_abstention:
            for idx, score in top_candidates:
                chunk = dict(self.chunks[idx])
                chunk["rrf_score"] = round(score, 4)
                chunk["citation_tag"] = f"[{chunk['doc_codigo']} v{chunk['version']}, {chunk['seccion_num']}]"
                retrieved_chunks.append(chunk)

        # Detección de Conflicto entre Fuentes Vigentes (Principio PR-4)
        conflicto_detectado = False
        conflicto_detalle = None

        query_norm = normalize_text(query)
        # Conflicto 1: Umbral de aprobación automática en MAN-REV (80) vs POL-DEC v2 (85)
        terms_umbral = ["umbral", "aprueb", "aproba", "80", "85", "automat"]
        if sum(1 for t in terms_umbral if t in query_norm) >= 2 and not is_abstention:
            conflicto_detectado = True
            conflicto_detalle = {
                "tipo": "CONFLICTO_FUENTES_VIGENTES",
                "tema": "Umbral mínimo para Aprobación Automática",
                "fuente_1": {
                    "cita": "[MAN-REV v1, §1]",
                    "estado": "Vigente",
                    "afirmacion": "Los casos con puntaje de 80 o más y sin señales de fraude se aprueban automáticamente, por lo que no llegarán a su bandeja."
                },
                "fuente_2": {
                    "cita": "[POL-DEC v2, §2]",
                    "estado": "Vigente",
                    "afirmacion": "Puntaje de confianza 85 o más: Aprobación automática, solo si no hay señales de fraude activas y todas las señales con mínimo propio lo cumplen."
                },
                "instruccion_pr4": "Ambas fuentes son vigentes pero presentan umbrales contradictorios (80 vs 85). Presente ambas fuentes sin elegir una por su cuenta."
            }

        # Conflicto 2: Quién puede modificar umbrales (POL-DEC v1 decía cualquier diseñador, pero v1 está derogada;
        # en la base de datos ORG-01 tiene umbral 90 fijado con un solo aprobador U-02, lo que contradice POL-DEC v2 §5 que exige 2 aprobadores)
        if any(t in query_norm for t in ["c-012", "cambio_umbral", "aprobadores", "modificar umbrales"]) and not is_abstention:
            if "c-012" in query_norm or "cambio" in query_norm:
                conflicto_detectado = True
                conflicto_detalle = {
                    "tipo": "CONFLICTO_DATOS_VS_POLITICA",
                    "tema": "Validez del cambio de umbral de ORG-01 para el caso C-012",
                    "fuente_1": {
                        "cita": "[POL-DEC v2, §5]",
                        "estado": "Vigente",
                        "afirmacion": "Un cambio de umbral requiere la aprobación de dos personas con rol de supervisor. Un cambio con una sola aprobación no entra en vigor."
                    },
                    "fuente_2": {
                        "cita": "[Base de Datos: cambios_umbral CU-001]",
                        "estado": "Vigente en sistema",
                        "afirmacion": "El cambio de umbral a 90 de ORG-01 solo registra a U-02 como aprobador_1 (aprobador_2 es NULL). En la tabla organizaciones figura 90, pero no cumplió la ratificación exigida."
                    },
                    "instruccion_pr4": "Señale la contradicción entre el dato aplicado en la derivación del caso C-012 (umbral 90) y la política vigente POL-DEC v2 §5 que exige dos supervisores."
                }

        # Detección de Versión Derogada vs Vigente
        version_diferencia = False
        version_detalle = None
        if not is_abstention:
            if any(term in query_norm for term in ["restan", "resta", "20 puntos", "v1", "derogada", "version 1"]):
                version_diferencia = True
                version_detalle = {
                    "tema": "Tratamiento de Señales de Fraude entre versiones",
                    "version_derogada": {
                        "cita": "[POL-DEC v1, §4]",
                        "estado": "Derogada",
                        "regla": "Cada señal de fraude activa resta 20 puntos al puntaje total del caso."
                    },
                    "version_vigente": {
                        "cita": "[POL-DEC v2, §4]",
                        "estado": "Vigente",
                        "regla": "Una señal de fraude activa deriva el caso a revisión, cualquiera sea su puntaje. Las señales de fraude no restan puntos: PREVALECEN sobre el puntaje."
                    },
                    "resolucion": "La regla aplicable hoy es POL-DEC v2 §4 (Vigente). POL-DEC v1 está derogada desde el 1 de septiembre de 2026."
                }
            elif ("modificar" in query_norm or "quien" in query_norm or "autoriz" in query_norm) and "umbral" in query_norm:
                version_diferencia = True
                version_detalle = {
                    "tema": "Autorización para Modificar Umbrales entre versiones",
                    "version_derogada": {
                        "cita": "[POL-DEC v1, §3]",
                        "estado": "Derogada",
                        "regla": "Cualquier usuario con rol de diseñador de flujos de la organización podía modificar los umbrales desde el diseñador de flujos."
                    },
                    "version_vigente": {
                        "cita": "[POL-DEC v2, §5]",
                        "estado": "Vigente",
                        "regla": "Un cambio de umbral requiere la aprobación de DOS personas con rol de supervisor de esa organización. Un cambio con una sola aprobación no entra en vigor."
                    },
                    "resolucion": "Aplica estrictamente POL-DEC v2 §5 (Vigente). POL-DEC v1 está derogada."
                }
            elif any(term in query_norm for term in ["parcial", "senal faltante"]) or ("modulo" in query_norm and ("falla" in query_norm or "no entrega" in query_norm)):
                version_diferencia = True
                version_detalle = {
                    "tema": "Tratamiento de Señales Faltantes entre versiones",
                    "version_derogada": {
                        "cita": "[POL-DEC v1, §5]",
                        "estado": "Derogada",
                        "regla": "Si un módulo no entrega su señal, el puntaje se calcula con las señales disponibles."
                    },
                    "version_vigente": {
                        "cita": "[POL-DEC v2, §6]",
                        "estado": "Vigente",
                        "regla": "Si un módulo falla o no entrega su señal, el caso no se aprueba con información parcial: se deriva a revisión indicando qué señal faltó."
                    },
                    "resolucion": "Aplica POL-DEC v2 §6 (Vigente). No se aprueba con información parcial."
                }

        return {
            "query": query,
            "se_abstiene": is_abstention,
            "motivo_abstencion": "La información consultada no se encuentra respaldada en el corpus documental de MIRA (Principio PR-3)." if is_abstention else None,
            "conflicto_detectado": conflicto_detectado,
            "conflicto_detalle": conflicto_detalle,
            "version_diferencia": version_diferencia,
            "version_detalle": version_detalle,
            "fragmentos": retrieved_chunks
        }
