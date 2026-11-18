import sqlite3
import firebase_admin
from firebase_admin import credentials, firestore

# Inicializa o Firebase com o seu token/credencial
if not firebase_admin._apps:
  cred = credentials.Certificate("nexus_token.json")
  firebase_admin.initialize_app(cred)

db = firestore.client()

# Conecta ao seu banco SQLite local
conexao = sqlite3.connect("nexus_mecanica.db")
conexao.row_factory = sqlite3.Row
cursor = conexao.cursor()


def migrar_tabela(nome_tabela, nome_colecao):
  print(f"🔄 Migrando tabela '{nome_tabela}'...")
  cursor.execute(f"SELECT * FROM {nome_tabela}")
  linhas = cursor.fetchall()

  count = 0
  for linha in linhas:
    dados = dict(linha)
    # Remove o ID numérico antigo para o Firebase gerar IDs seguros na nuvem
    if "id" in dados:
      reg_id = str(dados["id"])
      del dados["id"]
      db.collection(nome_colecao).document(reg_id).set(dados)
    else:
      db.collection(nome_colecao).add(dados)
    count += 1

  print(f"✅ {count} registros enviados para a coleção '{nome_colecao}'!\n")


try:
  migrar_tabela("clientes", "clientes")
  migrar_tabela("historico_vendas", "historico_vendas")
  migrar_tabela("catalogo_servicos", "catalogo_servicos")
  migrar_tabela("patio", "patio")
  migrar_tabela("preventivas", "preventivas")
  print("🚀 MIGRAÇÃO CONCLUÍDA COM SUCESSO PARA O FIREBASE!")
except Exception as e:
  print(f"❌ Erro na migração: {e}")

conexao.close()