
"""
╔══════════════════════════════════════════════════════════════╗
║   DATABASE — SQLite Thread-Safe (WAL mode + threading lock) ║
╚══════════════════════════════════════════════════════════════╝
"""

import os
import sqlite3
import threading
from datetime import datetime

DB_PATH = os.environ.get("DB_PATH", "atendimentos.db")
_lock = threading.Lock()

def _get_conn():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")
    return conn

def init_db():
    with _lock:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS atendimentos (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                atendente           TEXT    NOT NULL,
                data_atendimento    TEXT    NOT NULL,
                numero_pedido       TEXT    NOT NULL UNIQUE,
                nome_cliente        TEXT    NOT NULL,
                valor_pedido        REAL    NOT NULL,
                email_cliente       TEXT,
                arquivo_comprovante TEXT,
                data_hora_registro  TEXT    NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS vendedores (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                nome       TEXT    NOT NULL UNIQUE,
                criado_em  TEXT    NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS pagamentos (
                id                  INTEGER PRIMARY KEY AUTOINCREMENT,
                numero_os           TEXT    NOT NULL,
                atendente           TEXT    NOT NULL,
                data_pagamento      TEXT    NOT NULL,
                nome_cliente        TEXT    NOT NULL,
                valor_produto       REAL    NOT NULL,
                valor_entrada       REAL    NOT NULL DEFAULT 0,
                valor_saldo         REAL    NOT NULL DEFAULT 0,
                tipo_pagamento      TEXT    NOT NULL,
                arquivo_comprovante TEXT    NOT NULL,
                data_hora_registro  TEXT    NOT NULL
            )
        """)
        conn.commit()
        conn.close()

init_db()

# ══════════════════════════════════════════════════════════════
# ATENDIMENTOS
# ══════════════════════════════════════════════════════════════

def salvar_atendimento(dados: dict):
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO atendimentos
                    (atendente, data_atendimento, numero_pedido, nome_cliente,
                     valor_pedido, email_cliente, arquivo_comprovante, data_hora_registro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (dados["atendente"], dados["data_atendimento"], dados["numero_pedido"],
                  dados["nome_cliente"], dados["valor_pedido"], dados.get("email_cliente", ""),
                  dados.get("arquivo_comprovante", ""), dados["data_hora_registro"]))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Número de pedido '{dados['numero_pedido']}' já existe.")
        finally:
            conn.close()

def carregar_atendimentos() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM atendimentos ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def atualizar_atendimento(id_: int, dados: dict):
    with _lock:
        conn = _get_conn()
        conn.execute("""
            UPDATE atendimentos SET atendente=?, data_atendimento=?, numero_pedido=?,
                nome_cliente=?, valor_pedido=?, email_cliente=? WHERE id=?
        """, (dados["atendente"], dados["data_atendimento"], dados["numero_pedido"],
              dados["nome_cliente"], dados["valor_pedido"], dados.get("email_cliente", ""), id_))
        conn.commit()
        conn.close()

def contar_atendimentos() -> int:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM atendimentos").fetchone()[0]
    conn.close()
    return total

def obter_valor_total() -> float:
    conn = _get_conn()
    val = conn.execute("SELECT COALESCE(SUM(valor_pedido), 0) FROM atendimentos").fetchone()[0]
    conn.close()
    return float(val)

def estatisticas_por_atendente() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT atendente, COUNT(*) AS total_atendimentos,
               SUM(valor_pedido) AS valor_total, AVG(valor_pedido) AS valor_medio
        FROM atendimentos GROUP BY atendente ORDER BY total_atendimentos DESC
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def estatisticas_por_periodo() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT data_atendimento AS periodo, COUNT(*) AS total, SUM(valor_pedido) AS valor
        FROM atendimentos GROUP BY data_atendimento ORDER BY data_atendimento
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def evolucao_por_vendedor() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("""
        SELECT atendente, data_atendimento AS periodo, COUNT(*) AS total, SUM(valor_pedido) AS valor
        FROM atendimentos GROUP BY atendente, data_atendimento ORDER BY data_atendimento
    """).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def limpar_todos_dados():
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM atendimentos")
        conn.commit()
        conn.close()

# ══════════════════════════════════════════════════════════════
# VENDEDORES
# ══════════════════════════════════════════════════════════════

def listar_vendedores() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM vendedores ORDER BY nome").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def cadastrar_vendedor(nome: str):
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("INSERT INTO vendedores (nome, criado_em) VALUES (?, ?)",
                         (nome, datetime.now().strftime("%d/%m/%Y %H:%M:%S")))
            conn.commit()
        except sqlite3.IntegrityError:
            raise ValueError(f"Vendedor '{nome}' já existe.")
        finally:
            conn.close()

def excluir_vendedor(id_: int):
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM vendedores WHERE id = ?", (id_,))
        conn.commit()
        conn.close()

# ══════════════════════════════════════════════════════════════
# PAGAMENTOS
# ══════════════════════════════════════════════════════════════

def salvar_pagamento(dados: dict):
    with _lock:
        conn = _get_conn()
        try:
            conn.execute("""
                INSERT INTO pagamentos
                    (numero_os, atendente, data_pagamento, nome_cliente, valor_produto,
                     valor_entrada, valor_saldo, tipo_pagamento, arquivo_comprovante, data_hora_registro)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (dados["numero_os"], dados["atendente"], dados["data_pagamento"], dados["nome_cliente"],
                  dados["valor_produto"], dados["valor_entrada"], dados["valor_saldo"],
                  dados["tipo_pagamento"], dados["arquivo_comprovante"], dados["data_hora_registro"]))
            conn.commit()
        finally:
            conn.close()

def carregar_pagamentos() -> list[dict]:
    conn = _get_conn()
    rows = conn.execute("SELECT * FROM pagamentos ORDER BY id DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]

def contar_pagamentos() -> int:
    conn = _get_conn()
    total = conn.execute("SELECT COUNT(*) FROM pagamentos").fetchone()[0]
    conn.close()
    return total

def atualizar_pagamento(id_: int, dados: dict):
    with _lock:
        conn = _get_conn()
        conn.execute("""
            UPDATE pagamentos SET
                numero_os      = ?,
                atendente      = ?,
                data_pagamento = ?,
                nome_cliente   = ?,
                valor_produto  = ?,
                valor_entrada  = ?,
                valor_saldo    = ?,
                tipo_pagamento = ?
            WHERE id = ?
        """, (dados["numero_os"], dados["atendente"], dados["data_pagamento"], dados["nome_cliente"],
              dados["valor_produto"], dados["valor_entrada"], dados["valor_saldo"],
              dados["tipo_pagamento"], id_))
        conn.commit()
        conn.close()

def excluir_pagamento(id_: int):
    with _lock:
        conn = _get_conn()
        conn.execute("DELETE FROM pagamentos WHERE id = ?", (id_,))
        conn.commit()
        conn.close()