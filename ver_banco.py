"""Diagnóstico (só leitura): mostra as tabelas, a versão da migração e os e-mails cadastrados.

Uso, na pasta do projeto, com o venv ativo:
    python ver_banco.py
Não altera o banco e não mostra senhas (só o e-mail das contas).
"""
import sqlite3
import sys

caminho = sys.argv[1] if len(sys.argv) > 1 else "reflex.db"
con = sqlite3.connect(f"file:{caminho}?mode=ro", uri=True)

tabelas = [r[0] for r in con.execute("select name from sqlite_master where type='table'")]
print("Banco:", caminho)
print("Tabelas:", tabelas)

if "alembic_version" in tabelas:
    print("Versão da migração:", [r[0] for r in con.execute("select version_num from alembic_version")])
else:
    print("Sem alembic_version: nenhuma migração aplicada neste arquivo.")

if "usuario" in tabelas:
    print("Contas cadastradas:", con.execute("select id, email from usuario").fetchall())
else:
    print("A tabela 'usuario' não existe: rode 'reflex db migrate' nesta pasta.")
