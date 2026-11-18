import sqlite3

def atualizar_banco():
    conn = sqlite3.connect("nexus_mecanica.db")
    cursor = conn.cursor()
    
    tabelas_a_alterar = ["patio", "orçamentos_emitidos"]
    
    for tabela in tabelas_a_alterar:
        try:
            cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN km TEXT")
            conn.commit()
            print(f"✅ Coluna 'km' criada na tabela '{tabela}' com sucesso!")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                print(f"ℹ️ A coluna 'km' já existia na tabela '{tabela}'.")
            else:
                print(f"❌ Erro ao atualizar tabela '{tabela}': {e}")
    
    conn.close()

if __name__ == "__main__":
    print("Iniciando a atualização do banco...")
    atualizar_banco()
    input("\nAtualização concluída! Pressione ENTER para fechar...")