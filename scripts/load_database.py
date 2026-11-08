"""
Script para inicializar y cargar la base de datos SQLite desde CU-1_datos.xlsx.
Asegura tipos correctos, claves foráneas e integridad referencial.
"""

import os
import sqlite3
import openpyxl

EXCEL_PATH = os.path.join(
    os.path.dirname(__file__), "..", "Kit_Entrega_3_MIRA", "CU-1_operador_revision", "datos", "CU-1_datos.xlsx"
)
DB_PATH = os.path.join(os.path.dirname(__file__), "..", "database", "mira_cu1.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("PRAGMA foreign_keys = ON;")

    # 1. organizaciones
    cur.execute("""
    CREATE TABLE organizaciones (
        org_id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        industria TEXT NOT NULL,
        pais TEXT NOT NULL,
        umbral_aprobacion REAL NOT NULL,
        umbral_revision REAL NOT NULL,
        plazo_resolucion_dias_habiles INTEGER NOT NULL,
        plazo_antecedentes_dias_habiles INTEGER NOT NULL
    );
    """)

    # 2. usuarios
    cur.execute("""
    CREATE TABLE usuarios (
        usuario_id TEXT PRIMARY KEY,
        nombre TEXT NOT NULL,
        org_id TEXT NOT NULL,
        rol TEXT NOT NULL,
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id)
    );
    """)

    # 3. casos
    cur.execute("""
    CREATE TABLE casos (
        caso_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        tipo_proceso TEXT NOT NULL,
        fecha_ingreso TEXT NOT NULL,
        estado TEXT NOT NULL,
        puntaje REAL,
        decision_sugerida TEXT,
        motivo_derivacion TEXT,
        operador_asignado TEXT,
        vence_el TEXT,
        version_flujo TEXT,
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id),
        FOREIGN KEY (operador_asignado) REFERENCES usuarios(usuario_id)
    );
    """)

    # 4. senales
    cur.execute("""
    CREATE TABLE senales (
        senal_id TEXT PRIMARY KEY,
        caso_id TEXT NOT NULL,
        codigo TEXT NOT NULL,
        valor REAL,
        minimo REAL,
        bajo_minimo TEXT,
        es_fraude TEXT NOT NULL,
        activa TEXT,
        detalle TEXT,
        FOREIGN KEY (caso_id) REFERENCES casos(caso_id)
    );
    """)

    # 5. evidencias
    cur.execute("""
    CREATE TABLE evidencias (
        evidencia_id TEXT PRIMARY KEY,
        caso_id TEXT NOT NULL,
        tipo TEXT NOT NULL,
        nombre_archivo TEXT NOT NULL,
        paginas INTEGER,
        legible TEXT,
        texto_extraido TEXT,
        FOREIGN KEY (caso_id) REFERENCES casos(caso_id)
    );
    """)

    # 6. solicitudes_antecedentes
    cur.execute("""
    CREATE TABLE solicitudes_antecedentes (
        solicitud_id TEXT PRIMARY KEY,
        caso_id TEXT NOT NULL,
        usuario_id TEXT NOT NULL,
        fecha TEXT NOT NULL,
        documentos_solicitados TEXT NOT NULL,
        motivo TEXT NOT NULL,
        estado TEXT NOT NULL,
        FOREIGN KEY (caso_id) REFERENCES casos(caso_id),
        FOREIGN KEY (usuario_id) REFERENCES usuarios(usuario_id)
    );
    """)

    # 7. cambios_umbral
    cur.execute("""
    CREATE TABLE cambios_umbral (
        cambio_id TEXT PRIMARY KEY,
        org_id TEXT NOT NULL,
        parametro TEXT NOT NULL,
        valor_anterior REAL NOT NULL,
        valor_nuevo REAL NOT NULL,
        autor TEXT NOT NULL,
        aprobador_1 TEXT,
        aprobador_2 TEXT,
        fecha TEXT NOT NULL,
        FOREIGN KEY (org_id) REFERENCES organizaciones(org_id),
        FOREIGN KEY (autor) REFERENCES usuarios(usuario_id)
    );
    """)

    # Cargar datos desde el Excel
    wb = openpyxl.load_workbook(EXCEL_PATH)
    tables = [
        "organizaciones",
        "usuarios",
        "casos",
        "senales",
        "evidencias",
        "solicitudes_antecedentes",
        "cambios_umbral",
    ]

    for table in tables:
        ws = wb[table]
        rows = list(ws.iter_rows(values_only=True))
        if not rows:
            continue
        headers = [str(c) for c in rows[0]]
        placeholders = ", ".join(["?"] * len(headers))
        sql = f"INSERT INTO {table} ({', '.join(headers)}) VALUES ({placeholders})"

        count = 0
        for r in rows[1:]:
            if all(c is None for c in r):
                continue
            cur.execute(sql, r)
            count += 1
        print(f"Cargada tabla '{table}': {count} registros.")

    conn.commit()
    conn.close()
    print(f"Base de datos SQLite generada con éxito en: {DB_PATH}")

if __name__ == "__main__":
    init_db()

