"""
Módulo de Indexación del RAG para MIRA (CU-1).
Implementa indexación reproducible y separada de la consulta.
Genera dos estrategias de fragmentación para el experimento comparativo:
- Estrategia A (Semántica por secciones Markdown)
- Estrategia B (Longitud fija con solapamiento)
"""

import os
import re
import json
from typing import List, Dict, Any

CORPUS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "Kit_Entrega_3_MIRA", "CU-1_operador_revision", "corpus"
)
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "indices")

def parse_header_metadata(markdown_text: str) -> Dict[str, str]:
    """
    Extrae la tabla de metadatos del encabezado Markdown del kit (antes de la primera sección ##).
    """
    metadata = {
        "codigo": "",
        "version": "",
        "estado": "",
        "vigencia": "",
        "responsable": ""
    }
    lines = markdown_text.splitlines()
    for line in lines:
        # Detenerse si ya empieza la primera sección ##
        if line.strip().startswith("##"):
            break
        if "|" in line:
            parts = [p.strip() for p in line.split("|") if p.strip()]
            if len(parts) >= 2:
                key = parts[0].lower().replace(":", "")
                val = parts[1]
                if ("código" in key or "codigo" in key) and not metadata["codigo"]:
                    metadata["codigo"] = val
                elif ("versión" in key or "version" in key) and not metadata["version"]:
                    metadata["version"] = val
                elif "estado" in key and not metadata["estado"]:
                    metadata["estado"] = val.replace("**", "").strip()
                elif "vigencia" in key and not metadata["vigencia"]:
                    metadata["vigencia"] = val
                elif "responsable" in key and not metadata["responsable"]:
                    metadata["responsable"] = val
    return metadata

def chunk_semantic(file_path: str) -> List[Dict[str, Any]]:
    """
    Estrategia A: Fragmentación semántica por secciones (H2/H3).
    Preserva tablas completas, títulos y cláusulas lógicas unificadas.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    metadata = parse_header_metadata(content)
    doc_code = metadata["codigo"] or filename.split("_")[0]
    doc_version = metadata["version"] or ("2" if "v2" in filename else "1")
    doc_estado = metadata["estado"] or ("Derogada" if "derogada" in filename else "Vigente")
    doc_vigencia = metadata["vigencia"]

    # Extraer título principal (H1)
    lines = content.splitlines()
    doc_title = lines[0].replace("#", "").strip() if lines else filename

    # Separar por secciones H2 (##)
    sections = re.split(r"\n(?=##\s+)", content)
    chunks = []

    for idx, sec in enumerate(sections):
        sec = sec.strip()
        if not sec:
            continue

        sec_lines = sec.splitlines()
        first_line = sec_lines[0].strip()

        # Si es el encabezado inicial previo a ## 1
        if not first_line.startswith("##"):
            seccion_num = "Intro"
            seccion_titulo = "Encabezado y Metadatos"
        else:
            sec_header = first_line.replace("##", "").strip()
            # Detectar número de sección si existe (ej. '1. Qué es una señal' o '¿Puedo pedirle...?')
            match_num = re.match(r"^(\d+)\.\s*(.*)", sec_header)
            if match_num:
                seccion_num = f"§{match_num.group(1)}"
                seccion_titulo = match_num.group(2)
            else:
                seccion_num = f"§{idx}"
                seccion_titulo = sec_header

        # Limpiar texto del fragmento
        body = "\n".join(sec_lines[1:]).strip() if first_line.startswith("##") else sec
        full_text = f"[{doc_code} v{doc_version} - {seccion_num} {seccion_titulo}]\n{body if body else sec}"

        words = len(full_text.split())
        approx_tokens = int(words * 1.3)

        fragment_id = f"{doc_code}-v{doc_version}-{seccion_num.replace('§', 'S')}"

        chunks.append({
            "fragment_id": fragment_id,
            "doc_codigo": doc_code,
            "doc_titulo": doc_title,
            "version": doc_version,
            "estado": doc_estado,
            "vigencia": doc_vigencia,
            "seccion_num": seccion_num,
            "seccion_titulo": seccion_titulo,
            "contenido": full_text,
            "palabras": words,
            "tokens_aprox": approx_tokens,
            "estrategia": "semantica"
        })

    return chunks

def chunk_fixed(file_path: str, chunk_size_words: int = 80, overlap_words: int = 15) -> List[Dict[str, Any]]:
    """
    Estrategia B: Fragmentación por ventana fija de tokens/palabras con solapamiento arbitrario.
    Ignora deliberadamente los límites de secciones y tablas.
    """
    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    filename = os.path.basename(file_path)
    metadata = parse_header_metadata(content)
    doc_code = metadata["codigo"] or filename.split("_")[0]
    doc_version = metadata["version"] or ("2" if "v2" in filename else "1")
    doc_estado = metadata["estado"] or ("Derogada" if "derogada" in filename else "Vigente")
    doc_vigencia = metadata["vigencia"]

    words = content.split()
    chunks = []
    chunk_idx = 0
    start = 0

    while start < len(words):
        end = min(start + chunk_size_words, len(words))
        chunk_words = words[start:end]
        body = " ".join(chunk_words)

        fragment_id = f"{doc_code}-v{doc_version}-F{chunk_idx:02d}"
        approx_tokens = int(len(chunk_words) * 1.3)

        chunks.append({
            "fragment_id": fragment_id,
            "doc_codigo": doc_code,
            "doc_titulo": doc_code,
            "version": doc_version,
            "estado": doc_estado,
            "vigencia": doc_vigencia,
            "seccion_num": f"Ventana-{chunk_idx}",
            "seccion_titulo": f"Bloque {chunk_idx}",
            "contenido": body,
            "palabras": len(chunk_words),
            "tokens_aprox": approx_tokens,
            "estrategia": "fija"
        })

        chunk_idx += 1
        if end >= len(words):
            break
        start += (chunk_size_words - overlap_words)

    return chunks

def build_indices():
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    all_files = [
        os.path.join(CORPUS_DIR, f)
        for f in os.listdir(CORPUS_DIR)
        if f.endswith(".md")
    ]

    semantic_chunks = []
    fixed_chunks = []

    for fpath in all_files:
        s_chunks = chunk_semantic(fpath)
        semantic_chunks.extend(s_chunks)

        f_chunks = chunk_fixed(fpath)
        fixed_chunks.extend(f_chunks)

    # Guardar índice semántico
    semantic_index_path = os.path.join(OUTPUT_DIR, "semantic_index.json")
    with open(semantic_index_path, "w", encoding="utf-8") as f:
        json.dump(semantic_chunks, f, ensure_ascii=False, indent=2)

    # Guardar índice fijo
    fixed_index_path = os.path.join(OUTPUT_DIR, "fixed_index.json")
    with open(fixed_index_path, "w", encoding="utf-8") as f:
        json.dump(fixed_chunks, f, ensure_ascii=False, indent=2)

    print(f"Indexación completada con éxito:")
    print(f" - Índice Semántico: {len(semantic_chunks)} fragmentos guardados en {semantic_index_path}")
    print(f" - Índice Longitud Fija: {len(fixed_chunks)} fragmentos guardados en {fixed_index_path}")

if __name__ == "__main__":
    build_indices()
