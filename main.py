import customtkinter as ctk
from tkinter import messagebox, ttk
import sqlite3
import os
import webbrowser
import urllib.parse
from datetime import datetime, timedelta
import json
from PIL import Image
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import threading
import time
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURAÇÕES DE LICENÇA (NEXUS SEGURANÇA) ---
NOME_CLIENTE_BUSCA = "AUTO MECANICA" 
NOME_DA_PLANILHA_ONLINE = "NEXUS_CONTROLE" 

# --- DADOS DE PAGAMENTO (PIX) ---
DADOS_PIX = "\n\n💰 *DADOS PARA PAGAMENTO (PIX)*\n🔑 Chave: `54940819000168`\n👤 Nome: HENRIQUE DOS SANTOS\n🏦 Banco: NUBANK"

# --- CONFIGURAÇÃO VISUAL ---
COLOR_BG = "#0A0A0A"          
COLOR_CARD = "#1A1A1A"        
COLOR_RED_DEGRADE = "#8B0000" 
COLOR_RED_VIBRANT = "#FF0000" 
COLOR_TEXT = "#F2F2F2"        

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

NOME_OFICINA = "HENRIQUE AUTO MECÂNICA"
ENDERECO_OFICINA = "Rua Alcídes Silva, 85 - Limeira/SP"
TELEFONE_OFICINA = "(19) 98773-8915"
CAMINHO_DO_BANCO = "nexus_mecanica.db"


# ==========================================================
# 🚀 INICIALIZAÇÃO E MIGRAÇÃO AUTOMÁTICA DO BANCO SQLITE
# ==========================================================
def inicializar_banco():
    try:
        conexao = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conexao.cursor()
        
        # 1️⃣ CRIAÇÃO DAS TABELAS PADRÃO
        cursor.execute("CREATE TABLE IF NOT EXISTS catalogo_servicos (id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT)")
        cursor.execute("""CREATE TABLE IF NOT EXISTS clientes (
            id INTEGER PRIMARY KEY AUTOINCREMENT, nome TEXT, telefone TEXT, carro TEXT, 
            ano TEXT, motor TEXT, placa TEXT, endereco TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS historico_vendas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, placa TEXT, total REAL, data TEXT, pagamento TEXT, itens_detalhados TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS orçamentos_emitidos (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, telefone TEXT, carro TEXT, 
            placa TEXT, ano TEXT, motor TEXT, itens_json TEXT, mo REAL, total REAL, data TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS preventivas (
            id INTEGER PRIMARY KEY AUTOINCREMENT, cliente TEXT, servico TEXT, data_vencimento TEXT, placa TEXT, status TEXT)""")
        cursor.execute("""CREATE TABLE IF NOT EXISTS patio (
            id INTEGER PRIMARY KEY AUTOINCREMENT, data_entrada TEXT, cliente TEXT, carro TEXT, 
            placa TEXT, servicos_json TEXT, total_geral REAL)""")
        conexao.commit()

        # 2️⃣ INJEÇÃO AUTOMÁTICA DE COLUNAS FALTANTES (Migração Segura)
        alteracoes = [
            ("patio", "km", "TEXT DEFAULT '0'"),
            ("patio", "observacao", "TEXT DEFAULT ''"),
            ("orçamentos_emitidos", "km", "TEXT DEFAULT '0'"),
            ("historico_vendas", "km", "TEXT DEFAULT '0'"),
            ("historico_vendas", "observacao", "TEXT DEFAULT ''")
        ]
        for tabela, coluna, tipo in alteracoes:
            try:
                cursor.execute(f"ALTER TABLE {tabela} ADD COLUMN {coluna} {tipo}")
                conexao.commit()
                print(f"[NEXUS] Coluna '{coluna}' injetada na tabela '{tabela}'!")
            except sqlite3.OperationalError:
                pass
                
        conexao.close()
        print("[NEXUS] Banco de dados sincronizado e pronto!")
    except Exception as e:
        print(f"[NEXUS ERRO] Falha crítica ao inicializar/atualizar banco: {e}")

inicializar_banco()


# ==========================================================
# 🛡️ SEGURANÇA E LICENCIAMENTO ONLINE
# ==========================================================
def verificar_status_planilha():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name("nexus_token.json", scope)
        client = gspread.authorize(creds)
        planilha = client.open(NOME_DA_PLANILHA_ONLINE).sheet1
        registros = planilha.get_all_records()
        for linha in registros:
            cliente_planilha = str(linha.get('CLIENTE')).strip().upper()
            if cliente_planilha == NOME_CLIENTE_BUSCA.upper():
                return str(linha.get('STATUS')).strip().upper()
        return "NÃO ENCONTRADO"
    except Exception:
        return "ERRO_CONEXAO"

def monitor_de_seguranca():
    while True:
        time.sleep(60)
        status = verificar_status_planilha()
        if status != "PAGO":
            messagebox.showerror("🛡️ SEGURANÇA NEXUS AUTOMAÇÕES", 
                "⚠️ LICENÇA EXPIRADA\n\nO sistema será encerrado por segurança.\nContato: (19) 99005-3317")
            os._exit(0)


# ==========================================================
# 🏎️ CLASSE PRINCIPAL DO SISTEMA
# ==========================================================
class SistemaOficina(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(f"{NOME_OFICINA} - GESTÃO & WHATSAPP 🏎️")
        self.geometry("1300x850")
        self.configure(fg_color=COLOR_BG)
        
        self.base_path = os.getcwd()
        for pasta in ["SAIDAS", "ORÇAMENTO", "FECHAMENTO_MENSAL"]:
            path = os.path.join(self.base_path, pasta)
            if not os.path.exists(path): 
                os.makedirs(path)
        
        self.entradas = [] 
        self.carregar_dados()
        self.carregar_patio_do_banco()
        self.setup_ui()

    def carregar_dados(self):
        conexao = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conexao.cursor()
        cursor.execute("SELECT nome FROM catalogo_servicos ORDER BY nome ASC")
        self.servicos_cadastrados = [r[0] for r in cursor.fetchall()]
        cursor.execute("SELECT nome, telefone, carro, ano, motor, placa, endereco FROM clientes ORDER BY nome ASC")
        self.clientes_cadastrados = [
            {"nome": r[0], "tel": r[1], "carro": r[2], "ano": r[3], "motor": r[4], "placa": r[5], "end": r[6]} 
            for r in cursor.fetchall()
        ]
        conexao.close()

    def carregar_patio_do_banco(self):
        self.entradas = []
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("SELECT data_entrada, cliente, carro, placa, km, servicos_json, total_geral, observacao FROM patio")
        for r in cursor.fetchall():
            try:
                servs = json.loads(r[5]) if r[5] else []
            except Exception:
                servs = []
            self.entradas.append({
                "data_entrada": r[0], 
                "cliente": r[1], 
                "carro": r[2], 
                "placa": r[3], 
                "km": r[4] if r[4] else "0", 
                "servicos": servs, 
                "servicos_json": r[5],
                "total_geral": r[6] if r[6] else 0.0,
                "observacao": r[7] if r[7] else ""
            })
        conn.close()

    def enviar_whatsapp(self, telefone, mensagem):
        if not telefone: 
            return
        telefone_limpo = "".join(filter(str.isdigit, str(telefone)))
        if not telefone_limpo.startswith("55") and len(telefone_limpo) >= 10:
            telefone_limpo = "55" + telefone_limpo
        texto = urllib.parse.quote(mensagem)
        link = f"https://web.whatsapp.com/send?phone={telefone_limpo}&text={texto}"
        webbrowser.open(link)

    # ==========================================================
    # 📄 GERADOR DE PDF PROFISSIONAL (CABEÇALHO CLARO + KM BLINDADO)
    # ==========================================================
    def gerar_pdf_mecanica(self, arquivo, cl_nome, placa, itens, mo, total, km, tipo="ORÇAMENTO", pagamento="N/A", observacao=""):
        c = canvas.Canvas(arquivo, pagesize=A4)
        largura, altura = A4 

        caminho_fonte_henrique = os.path.join(os.path.dirname(os.path.abspath(__file__)), "Satisfy-Regular.ttf")
        if os.path.exists(caminho_fonte_henrique):
            try:
                pdfmetrics.registerFont(TTFont('HenriqueFonteManuscrita', caminho_fonte_henrique))
                fonte_henrique = 'HenriqueFonteManuscrita'
            except Exception:
                fonte_henrique = "Helvetica-BoldOblique"
        else:
            fonte_henrique = "Helvetica-BoldOblique"

        # ─── 1. CABEÇALHO CLARO E CLEAN ───
        c.setFillColor(colors.HexColor("#F4F4F4"))
        c.rect(0, altura - 90, largura, 90, fill=1, stroke=0)

        c.setFillColor(colors.HexColor("#111111"))
        c.setFont(fonte_henrique, 36)
        c.drawString(40, altura - 52, "Henrique")

        c.setFillColor(colors.HexColor("#CC0000"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(42, altura - 68, "AUTO MECÂNICA")

        c.setFillColor(colors.HexColor("#111111"))
        c.setFont("Helvetica-Bold", 10)
        c.drawRightString(largura - 40, altura - 38, NOME_OFICINA)
        
        c.setFillColor(colors.HexColor("#444444"))
        c.setFont("Helvetica", 8)
        c.drawRightString(largura - 40, altura - 53, ENDERECO_OFICINA)
        c.drawRightString(largura - 40, altura - 65, f"CONTATO: {TELEFONE_OFICINA}")

        c.setStrokeColor(colors.HexColor("#CC0000"))
        c.setLineWidth(3)
        c.line(0, altura - 90, largura, altura - 90)

        c.setStrokeColor(colors.black)
        c.setLineWidth(1)
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.black)
        
        c.rect(160, altura - 120, 10, 10)
        c.drawString(175, altura - 118, "AVALIAÇÃO / ORÇAMENTO")
        
        c.rect(340, altura - 120, 10, 10)
        c.drawString(355, altura - 118, "ORDEM DE SERVIÇO / RECIBO")
        
        c.drawString(161 if tipo == "ORÇAMENTO" else 341, altura - 118, "X")

        # ─── 2. BUSCA TRIANGULADA DE DADOS DO CLIENTE, VEÍCULO E KM ───
        tel_cl = ""
        carro_cl = "N/A"
        ano_cl = "N/A"
        km_patio = None

        if self.clientes_cadastrados:
            cl_found = next((cl for cl in self.clientes_cadastrados if str(cl.get('nome', '')).strip().upper() == str(cl_nome).strip().upper()), None)
            if cl_found:
                tel_cl = cl_found.get('tel', '')
                carro_cl = cl_found.get('carro', 'N/A')
                ano_cl = cl_found.get('ano', 'N/A')

        if self.entradas:
            ent_found = next((e for e in self.entradas if str(e.get('placa', '')).strip().upper() == str(placa).strip().upper()), None)
            if ent_found:
                if not tel_cl: tel_cl = ent_found.get('telefone', '')
                if carro_cl == "N/A": carro_cl = ent_found.get('carro', 'N/A')
                if ano_cl == "N/A": ano_cl = ent_found.get('ano', 'N/A')
                if ent_found.get('km'): km_patio = ent_found.get('km')

        if not tel_cl or carro_cl == "N/A":
            try:
                conn_pdf = sqlite3.connect(CAMINHO_DO_BANCO)
                cursor_pdf = conn_pdf.cursor()
                cursor_pdf.execute("SELECT telefone, carro, ano FROM clientes WHERE placa = ? OR nome = ? LIMIT 1", (placa, cl_nome))
                res_db = cursor_pdf.fetchone()
                if res_db:
                    if res_db[0] and not tel_cl: tel_cl = res_db[0]
                    if res_db[1] and carro_cl == "N/A": carro_cl = res_db[1]
                    if res_db[2] and ano_cl == "N/A": ano_cl = res_db[2]
                conn_pdf.close()
            except Exception:
                pass

        # ─── 3. PREENCHIMENTO DOS DADOS DO VEÍCULO / CLIENTE ───
        y_top = altura - 140
        c.setFont("Helvetica-Bold", 9)
        c.line(40, y_top, largura - 40, y_top)

        c.drawString(45, y_top - 15, f"NOME: {str(cl_nome).upper()}")
        c.drawString(420, y_top - 15, f"FONE: {tel_cl}")
        c.line(40, y_top - 25, largura - 40, y_top - 25)

        km_final = km if km and str(km).strip().lower() not in ['none', '', '0'] else km_patio
        km_formatado = "0" if not km_final or str(km_final).strip().lower() == 'none' else str(km_final)

        c.drawString(45, y_top - 40, f"VEÍCULO: {str(carro_cl).upper()}")
        c.drawString(260, y_top - 40, f"ANO: {str(ano_cl).upper()}")
        c.drawString(360, y_top - 40, f"PLACA: {str(placa).upper()}")
        c.drawString(490, y_top - 40, f"KM: {km_formatado}")
        c.line(40, y_top - 50, largura - 40, y_top - 50)

        c.drawString(45, y_top - 65, f"DATA: {datetime.now().strftime('%d/%m/%Y')}")
        c.drawString(200, y_top - 65, f"HORA: {datetime.now().strftime('%H:%M')}")
        c.drawString(400, y_top - 65, f"PAGAMENTO: {str(pagamento).upper()}")
        c.line(40, y_top - 75, largura - 40, y_top - 75)

        # ─── 4. TABELA DE SERVIÇOS E PEÇAS ───
        y = y_top - 105
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.lightgrey)
        c.rect(40, y, 415, 18, fill=1)
        c.rect(455, y, 100, 18, fill=1)
        c.setFillColor(colors.black)
        c.drawString(50, y + 5, "DESCRIÇÃO DOS SERVIÇOS / PEÇAS")
        c.drawString(485, y + 5, "PREÇO (R$)")
        y -= 18

        total_pecas = 0.0
        for item in itens:
            if isinstance(item, dict):
                nome_servico = item.get('nome', '')
                valor_total_item = float(item.get('valor', 0))
                qtd = float(item.get('qtd', 1))
                valor_unit = float(item.get('unit', valor_total_item))
            elif isinstance(item, (list, tuple)) and len(item) >= 4:
                nome_servico = item[0]
                valor_unit = float(item[1])
                qtd = float(item[2])
                valor_total_item = float(item[3])
            else:
                continue

            if "MÃO DE OBRA" in nome_servico.upper() or "MAO DE OBRA" in nome_servico.upper(): 
                continue

            c.setFont("Helvetica", 9)
            c.rect(40, y, 415, 18)
            c.rect(455, y, 100, 18)

            desc = nome_servico
            if qtd >= 1: 
                desc += f" ({int(qtd)} UN x R$ {valor_unit:.2f})"

            c.drawString(45, y + 5, desc[:85])
            c.drawRightString(545, y + 5, f"{valor_total_item:.2f}")
            total_pecas += valor_total_item
            y -= 18

            if y < 220: 
                c.showPage()
                y = altura - 50
                c.setFont("Helvetica", 9)

        # ─── 5. QUADRO DE OBSERVAÇÕES TÉCNICAS ───
        y_obs = 180
        obs_texto = str(observacao).strip() if observacao else ""

        if obs_texto:
            c.setFont("Helvetica-Bold", 9)
            c.setFillColor(colors.HexColor("#CC0000"))
            c.drawString(45, y_obs + 22, "OBSERVAÇÕES TÉCNICAS / RECADO AO CLIENTE:")

            c.setFont("Helvetica-Bold", 8)
            c.setFillColor(colors.black)
            c.setStrokeColor(colors.black)
            c.setLineWidth(0.8)
            c.rect(40, y_obs - 15, 515, 32)

            c.drawString(45, y_obs + 5, obs_texto[:110])
            if len(obs_texto) > 110:
                c.drawString(45, y_obs - 8, obs_texto[110:220])

        # ─── 6. BLOCO DE FECHAMENTO ───
        y_totais = 130
        c.setFillColor(colors.black)
        c.setFont("Helvetica-Bold", 10)
        c.drawString(45, y_totais, f"TOTAL PEÇAS: R$ {total_pecas:.2f}")
        c.drawString(220, y_totais, f"MÃO DE OBRA: R$ {float(mo):.2f}")

        c.setFont("Helvetica-Bold", 12)
        c.drawRightString(545, y_totais, f"TOTAL GERAL: R$ {float(total):.2f}")

        y_assinatura = 60
        c.setLineWidth(0.5)
        c.setStrokeColor(colors.black)
        c.line(50, y_assinatura, 250, y_assinatura)
        c.line(340, y_assinatura, 540, y_assinatura)

        c.setFont("Helvetica", 9)
        c.drawCentredString(150, y_assinatura - 12, "Mecânica Responsável")
        c.drawCentredString(440, y_assinatura - 12, "Assinatura do Cliente")

        c.showPage()
        c.save()

    # ==========================================================
    # 🎨 ESTRUTURA VISUAL DA INTERFACE (SIDEBAR + WORKSPACE)
    # ==========================================================
    def setup_ui(self):
        self.sidebar = ctk.CTkFrame(self, width=240, corner_radius=0, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_RED_DEGRADE)
        self.sidebar.pack(side="left", fill="y")
        
        try:
            caminho_logo = os.path.join(os.path.dirname(__file__), "logo.png")
            img_logo = Image.open(caminho_logo)
            self.logo_image = ctk.CTkImage(light_image=img_logo, dark_image=img_logo, size=(160, 160))
            self.logo_label = ctk.CTkLabel(self.sidebar, image=self.logo_image, text="")
            self.logo_label.pack(pady=(30, 20))
        except Exception:
            self.logo_label = ctk.CTkLabel(self.sidebar, text="HENRIQUE\nAUTO MECÂNICA", font=("Segoe UI", 20, "bold"), text_color=COLOR_RED_VIBRANT)
            self.logo_label.pack(pady=(30, 20))

        menu_items = [
            ("🏠 Painel Geral", self.tela_inicial), 
            ("📝 Novo Orçamento", self.tela_gerar_orcamento), 
            ("📋 Orçamentos Salvos", self.tela_ver_orcamentos), 
            ("👥 Clientes", self.tela_cadastrar_cliente), 
            ("🛠️ Catálogo", self.tela_servicos), 
            ("🚗 Entrada Direta", self.tela_entrada), 
            ("💰 Financeiro", self.tela_financeiro), 
            ("🔍 Histórico", self.tela_busca_historico), 
            ("✅ Saída/Recibo", self.tela_saida)
        ]
        for text, cmd in menu_items:
            btn = ctk.CTkButton(self.sidebar, text=text, command=cmd, fg_color="transparent", text_color=COLOR_TEXT, hover_color=COLOR_RED_DEGRADE, anchor="w", height=45, font=("Segoe UI", 13, "bold"))
            btn.pack(fill="x", padx=15, pady=5)

        self.workspace = ctk.CTkFrame(self, corner_radius=15, fg_color=COLOR_CARD, border_width=1, border_color="#333333")
        self.workspace.pack(side="right", fill="both", expand=True, padx=20, pady=20)
        
        self.header = ctk.CTkFrame(self.workspace, height=80, fg_color="transparent")
        self.header.pack(fill="x", padx=20, pady=10)
        
        self.lbl_titulo_aba = ctk.CTkLabel(self.header, text="PAINEL DE CONTROLE", font=("Segoe UI", 26, "bold"), text_color=COLOR_TEXT)
        self.lbl_titulo_aba.pack(side="left", pady=10)
        
        self.main_frame = ctk.CTkFrame(self.workspace, fg_color="transparent")
        self.main_frame.pack(fill="both", expand=True, padx=20, pady=10)

        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=COLOR_CARD, foreground="white", fieldbackground=COLOR_CARD, rowheight=35, borderwidth=0)
        style.configure("Treeview.Heading", background=COLOR_RED_DEGRADE, foreground="white", font=("Segoe UI", 11, "bold"))
        style.map("Treeview", background=[('selected', COLOR_RED_VIBRANT)])
        
        self.tela_inicial()

    def limpar_tela(self, titulo):
        self.lbl_titulo_aba.configure(text=titulo)
        for widget in self.main_frame.winfo_children(): 
            widget.destroy()

    # ==========================================================
    # 🏠 TELA INICIAL (PÁTIO)
    # ==========================================================
    def tela_inicial(self):
        self.limpar_tela("🚗 VEÍCULOS NO PÁTIO")
        
        alertas = self.checar_alertas_preventiva()
        if alertas:
            f_alerta = ctk.CTkFrame(self.main_frame, fg_color="#330000", border_width=2, border_color=COLOR_RED_VIBRANT)
            f_alerta.pack(fill="x", pady=(0, 15), padx=5)
            ctk.CTkLabel(f_alerta, text="🚨 ALERTAS DE MANUTENÇÃO PREVENTIVA", font=("Segoe UI", 13, "bold"), text_color=COLOR_RED_VIBRANT).pack(pady=5)
            for msg in alertas: 
                ctk.CTkLabel(f_alerta, text=msg, font=("Segoe UI", 12), text_color="white").pack()

        f_botoes = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_botoes.pack(fill="x", pady=15, side="bottom")

        ctk.CTkButton(
            f_botoes, 
            text="✏️ EDITAR SERVIÇOS / KM / MO", 
            fg_color="#004466",
            hover_color="#006699",
            height=42,
            font=("Segoe UI", 12, "bold"),
            command=self.abrir_janela_edicao
        ).pack(side="left", padx=10, expand=True, fill="x")

        ctk.CTkButton(
            f_botoes, 
            text="❌ REMOVER DO PÁTIO", 
            fg_color="#660000", 
            hover_color="#990000",
            height=42,
            font=("Segoe UI", 12, "bold"),
            command=lambda: self.cancelar_patio(self.tree)
        ).pack(side="left", padx=10, expand=True, fill="x")

        cols = ("Entrada", "Cliente", "Veículo", "Placa", "KM", "Subtotal")
        self.tree = ttk.Treeview(self.main_frame, columns=cols, show='headings')
        for c in cols:
            self.tree.heading(c, text=c)
            self.tree.column(c, width=130, anchor="center")
        self.tree.pack(fill="both", expand=True, padx=5, pady=5)

        for e in self.entradas: 
            self.tree.insert("", "end", values=(
                e['data_entrada'], 
                e['cliente'], 
                e['carro'], 
                e['placa'], 
                e.get('km', '0'), 
                f"R$ {e['total_geral']:.2f}"
            ))

    # ==========================================================
    # 📝 NOVO ORÇAMENTO (COM BOTÃO FIXO NO RODAPÉ)
    # ==========================================================
    def tela_gerar_orcamento(self):
        self.limpar_tela("📝 NOVO ORÇAMENTO")
        self.pecas_orc = []

        # 1. Card Superior de Inputs e Adição (side="top")
        f_topo_container = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_topo_container.pack(fill="x", pady=5, side="top")

        f = ctk.CTkFrame(f_topo_container, fg_color="#252525")
        f.pack(fill="x", pady=5, padx=5)

        self.cb_o_cl = ctk.CTkComboBox(f, values=["AVULSO"] + [c['nome'] for c in self.clientes_cadastrados], width=250, command=self.preencher_orc)
        self.cb_o_cl.grid(row=0, column=0, padx=10, pady=15)

        self.en_o_ca = ctk.CTkEntry(f, placeholder_text="Veículo", width=150)
        self.en_o_ca.grid(row=0, column=1, padx=5)

        self.en_o_pl = ctk.CTkEntry(f, placeholder_text="Placa", width=100)
        self.en_o_pl.grid(row=0, column=2, padx=5)

        self.en_o_km = ctk.CTkEntry(f, placeholder_text="Km do Veículo", width=150)
        self.en_o_km.grid(row=1, column=0, padx=10, pady=(0, 15))

        self.en_o_mo = ctk.CTkEntry(f, placeholder_text="Mão de Obra R$", width=150)
        self.en_o_mo.grid(row=1, column=1, padx=5, pady=(0, 15))

        f_item = ctk.CTkFrame(f_topo_container, fg_color="transparent")
        f_item.pack(fill="x", pady=5)

        self.cb_item_n = ctk.CTkComboBox(f_item, values=self.servicos_cadastrados, width=220)
        self.cb_item_n.grid(row=0, column=0, padx=5)

        self.en_item_v = ctk.CTkEntry(f_item, placeholder_text="R$ Unit.", width=100)
        self.en_item_v.grid(row=0, column=1, padx=5)

        self.en_item_qtd = ctk.CTkEntry(f_item, placeholder_text="Qtd", width=60)
        self.en_item_qtd.insert(0, "1")
        self.en_item_qtd.grid(row=0, column=2, padx=5)

        ctk.CTkButton(f_item, text="ADD", fg_color=COLOR_RED_DEGRADE, width=60, command=self.add_orc).grid(row=0, column=3, padx=5)
        ctk.CTkButton(f_item, text="REMOVER ITEM", fg_color="#660000", hover_color="#990000", width=140, command=self.remover_item_orcamento).grid(row=0, column=4, padx=5)

        f_oleo_o = ctk.CTkFrame(f_topo_container, fg_color="transparent")
        f_oleo_o.pack(fill="x", pady=5)

        self.cb_tipo_oleo_o = ctk.CTkComboBox(f_oleo_o, values=["Mineral", "Semissintético", "Sintético"], width=150)
        self.cb_tipo_oleo_o.set("Tipo de Óleo")
        self.cb_tipo_oleo_o.grid(row=0, column=0, padx=10)

        self.cb_visco_oleo_o = ctk.CTkComboBox(f_oleo_o, values=["5W30", "5W40", "10W30", "10W40", "15W40", "0W20", "20W50"], width=120)
        self.cb_visco_oleo_o.set("Viscosidade")
        self.cb_visco_oleo_o.grid(row=0, column=1, padx=5)

        self.cb_marca_oleo_o = ctk.CTkComboBox(f_oleo_o, values=["Mobil", "Castrol", "Shell", "Petronas", "Motul", "Lubrax", "Ipiranga", "Idmitsu", "Havoline", "Valvoline", "Bardahl"], width=150)
        self.cb_marca_oleo_o.set("Marca")
        self.cb_marca_oleo_o.grid(row=0, column=2, padx=5)

        # 2. Botão de Salvar Fixado no Rodapé (side="bottom" para NUNCA sumir ao maximizar)
        f_acoes_orc = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_acoes_orc.pack(fill="x", pady=(10, 15), padx=10, side="bottom")

        ctk.CTkButton(
            f_acoes_orc,
            text="💾 SALVAR ORÇAMENTO, GERAR PDF E WHATSAPP",
            fg_color=COLOR_RED_VIBRANT,
            height=45,
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            command=self.salvar_e_enviar_orcamento
        ).pack(fill="x")

        # 3. Tabela Central (Ocupa o espaço intermediário flexível)
        f_tabela_orc = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_tabela_orc.pack(fill="both", expand=True, pady=5, padx=10, side="top")

        cols = ("SERV", "UNIT", "QTD", "TOTAL")
        self.tree_o = ttk.Treeview(f_tabela_orc, columns=cols, show='headings')
        self.tree_o.heading("SERV", text="ITEM / SERVIÇO")
        self.tree_o.heading("UNIT", text="VALOR UNIT.")
        self.tree_o.heading("QTD", text="QTD")
        self.tree_o.heading("TOTAL", text="TOTAL ITEM")
        self.tree_o.column("SERV", width=400)
        self.tree_o.column("UNIT", width=120, anchor="center")
        self.tree_o.column("QTD", width=80, anchor="center")
        self.tree_o.column("TOTAL", width=120, anchor="center")
        
        scrollbar_orc = ttk.Scrollbar(f_tabela_orc, orient="vertical", command=self.tree_o.yview)
        self.tree_o.configure(yscrollcommand=scrollbar_orc.set)
        
        self.tree_o.pack(side="left", fill="both", expand=True)
        scrollbar_orc.pack(side="right", fill="y")

    def add_orc(self):
        try:
            v_unit = float(self.en_item_v.get().replace(",", "."))
            qtd = float(self.en_item_qtd.get().replace(",", "."))
            v_total = v_unit * qtd
            serv_nome = self.cb_item_n.get().upper()
            if "ÓLEO" in serv_nome or "OLEO" in serv_nome:
                det = []
                if self.cb_tipo_oleo_o.get() != "Tipo de Óleo": det.append(self.cb_tipo_oleo_o.get())
                if self.cb_visco_oleo_o.get() != "Viscosidade": det.append(self.cb_visco_oleo_o.get())
                if self.cb_marca_oleo_o.get() != "Marca": det.append(self.cb_marca_oleo_o.get())
                if det: serv_nome += f" ({' - '.join(det)})"
            self.pecas_orc.append({"nome": serv_nome, "valor": v_total, "unit": v_unit, "qtd": qtd})
            self.tree_o.insert("", "end", values=(serv_nome, f"R$ {v_unit:.2f}", int(qtd) if qtd.is_integer() else qtd, f"R$ {v_total:.2f}"))
            self.en_item_v.delete(0, 'end')
            self.en_item_qtd.delete(0, 'end')
            self.en_item_qtd.insert(0, "1")
        except Exception: 
            messagebox.showerror("Erro", "Valor ou Quantidade inválidos!")

    def salvar_e_enviar_orcamento(self):
        try:
            km_veiculo = self.en_o_km.get().strip() or "0"
            mo = float(self.en_o_mo.get().replace(",", ".") or 0)
            total = mo + sum(p['valor'] for p in self.pecas_orc)
            cl_nome = self.cb_o_cl.get().upper()
            ca = self.en_o_ca.get().upper()
            pl = self.en_o_pl.get().upper()
            
            cliente_info = next((c for c in self.clientes_cadastrados if c['nome'] == cl_nome), None)
            telefone = cliente_info['tel'] if cliente_info else ""
            
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO orçamentos_emitidos (cliente, telefone, carro, placa, km, itens_json, mo, total, data) VALUES (?,?,?,?,?,?,?,?,?)", 
                           (cl_nome, telefone, ca, pl, km_veiculo, json.dumps(self.pecas_orc, ensure_ascii=False), mo, total, datetime.now().strftime("%d/%m/%Y %H:%M")))
            conn.commit()
            conn.close()
            
            dir_orc = os.path.join(self.base_path, "ORÇAMENTO")
            nome_arq = f"Orcamento_{pl}_{datetime.now().strftime('%H%M%S')}.pdf"
            caminho_completo = os.path.join(dir_orc, nome_arq)
            
            self.gerar_pdf_mecanica(caminho_completo, cl_nome, pl, self.pecas_orc, mo, total, km=km_veiculo, tipo="ORÇAMENTO")
            
            try: 
                os.startfile(caminho_completo)
            except Exception: 
                pass
            
            msg = f"🏎️ *{NOME_OFICINA}*\n📍 {ENDERECO_OFICINA}\n\n✅ *ORÇAMENTO: {pl}*\n👤 Cliente: {cl_nome}\n🚗 Veículo: {ca} | KM: {km_veiculo}\n-----------------------------------\n"
            for p in self.pecas_orc: 
                msg += f"• {p['nome']}: {int(p['qtd'])} UN x R$ {p['unit']:.2f} = R$ {p['valor']:.2f}\n"
            msg += f"• Mão de Obra: R$ {mo:.2f}\n-----------------------------------\n💰 *TOTAL: R$ {total:.2f}*{DADOS_PIX}\n\n📄 _PDF detalhado enviado._"
            
            if telefone: 
                self.enviar_whatsapp(telefone, msg)
            self.tela_ver_orcamentos()
        except Exception as e: 
            messagebox.showerror("Erro", f"Falha ao salvar orçamento: {e}")

    # ==========================================================
    # 🚗 ENTRADA DIRETA NO PÁTIO (COM PERSISTÊNCIA NO SQLITE E KM)
    # ==========================================================
    def tela_entrada(self):
        self.limpar_tela("📥 ENTRADA DIRETA")
        self.servicos_entrada_atual = []

        f = ctk.CTkFrame(self.main_frame, fg_color="#252525")
        f.pack(fill="x", pady=10, padx=10)

        self.cb_cl_ent = ctk.CTkComboBox(f, values=[c['nome'] for c in self.clientes_cadastrados], width=250, command=self.preencher_ent_direta)
        self.cb_cl_ent.grid(row=0, column=0, padx=10, pady=15)

        self.en_ent_ca = ctk.CTkEntry(f, placeholder_text="Veículo", width=150)
        self.en_ent_ca.grid(row=0, column=1, padx=5)

        self.en_ent_pl = ctk.CTkEntry(f, placeholder_text="Placa", width=100)
        self.en_ent_pl.grid(row=0, column=2, padx=5)

        self.en_ent_km = ctk.CTkEntry(f, placeholder_text="Km do Veículo", width=150)
        self.en_ent_km.grid(row=1, column=0, padx=10, pady=(0, 15))

        self.en_ent_mo = ctk.CTkEntry(f, placeholder_text="Mão de Obra R$", width=150)
        self.en_ent_mo.insert(0, "0")
        self.en_ent_mo.grid(row=1, column=1, padx=5, pady=(0, 15))

        self.en_ent_obs = ctk.CTkEntry(f, placeholder_text="Observação Técnica (Opcional)", width=250)
        self.en_ent_obs.grid(row=1, column=2, padx=5, pady=(0, 15))

        f_add = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_add.pack(fill="x", pady=5)

        self.cb_sv_ent = ctk.CTkComboBox(f_add, values=self.servicos_cadastrados, width=220)
        self.cb_sv_ent.grid(row=0, column=0, padx=5)

        self.en_p_ent = ctk.CTkEntry(f_add, placeholder_text="R$ Unit.", width=100)
        self.en_p_ent.grid(row=0, column=1, padx=5)

        self.en_qtd_ent = ctk.CTkEntry(f_add, placeholder_text="Qtd", width=60)
        self.en_qtd_ent.insert(0, "1")
        self.en_qtd_ent.grid(row=0, column=2, padx=5)

        ctk.CTkButton(f_add, text="ADD", fg_color=COLOR_RED_DEGRADE, width=60, command=self.add_ent_direta).grid(row=0, column=3, padx=5)
        ctk.CTkButton(f_add, text="REMOVER ITEM", fg_color="#660000", hover_color="#990000", width=140, command=self.remover_item_entrada).grid(row=0, column=4, padx=5)

        f_oleo_ent = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_oleo_ent.pack(fill="x", pady=5)

        self.cb_tipo_oleo_ent = ctk.CTkComboBox(f_oleo_ent, values=["Mineral", "Semissintético", "Sintético"], width=150)
        self.cb_tipo_oleo_ent.set("Tipo de Óleo")
        self.cb_tipo_oleo_ent.grid(row=0, column=0, padx=10)

        self.cb_visco_oleo_ent = ctk.CTkComboBox(f_oleo_ent, values=["5W30", "5W40", "10W30", "10W40", "15W40", "0W20", "20W50"], width=120)
        self.cb_visco_oleo_ent.set("Viscosidade")
        self.cb_visco_oleo_ent.grid(row=0, column=1, padx=5)

        self.cb_marca_oleo_ent = ctk.CTkComboBox(f_oleo_ent, values=["Mobil", "Castrol", "Shell", "Petronas", "Motul", "Lubrax", "Ipiranga", "Idmitsu", "Havoline", "Valvoline", "Bardahl"], width=150)
        self.cb_marca_oleo_ent.set("Marca")
        self.cb_marca_oleo_ent.grid(row=0, column=2, padx=5)

        cols = ("SERV", "UNIT", "QTD", "TOTAL")
        self.tree_ent = ttk.Treeview(self.main_frame, columns=cols, show='headings', height=6)
        self.tree_ent.heading("SERV", text="ITEM / SERVIÇO")
        self.tree_ent.heading("UNIT", text="VALOR UNIT.")
        self.tree_ent.heading("QTD", text="QTD")
        self.tree_ent.heading("TOTAL", text="TOTAL ITEM")
        self.tree_ent.column("SERV", width=400)
        self.tree_ent.column("UNIT", width=120, anchor="center")
        self.tree_ent.column("QTD", width=80, anchor="center")
        self.tree_ent.column("TOTAL", width=120, anchor="center")
        self.tree_ent.pack(fill="x", pady=10)

        ctk.CTkButton(
            self.main_frame,
            text="✅ CONFIRMAR ENTRADA NO PÁTIO",
            fg_color=COLOR_RED_VIBRANT,
            height=42,
            font=("Segoe UI", 12, "bold"),
            command=self.salvar_entrada_patio
        ).pack(fill="x", padx=10, pady=10)

    def add_ent_direta(self):
        try: 
            v_unit = float(self.en_p_ent.get().replace(",", "."))
            qtd = float(self.en_qtd_ent.get().replace(",", "."))
            v_total = v_unit * qtd
            serv_nome = self.cb_sv_ent.get().upper()
            if "ÓLEO" in serv_nome or "OLEO" in serv_nome:
                det = []
                if self.cb_tipo_oleo_ent.get() != "Tipo de Óleo": det.append(self.cb_tipo_oleo_ent.get())
                if self.cb_visco_oleo_ent.get() != "Viscosidade": det.append(self.cb_visco_oleo_ent.get())
                if self.cb_marca_oleo_ent.get() != "Marca": det.append(self.cb_marca_oleo_ent.get())
                if det: serv_nome += f" ({' - '.join(det)})"
            self.servicos_entrada_atual.append({"nome": serv_nome, "valor": v_total, "unit": v_unit, "qtd": qtd})
            self.tree_ent.insert("", "end", values=(serv_nome, f"R$ {v_unit:.2f}", int(qtd) if qtd.is_integer() else qtd, f"R$ {v_total:.2f}"))
            self.en_p_ent.delete(0, 'end')
            self.en_qtd_ent.delete(0, 'end')
            self.en_qtd_ent.insert(0, "1")
        except Exception: 
            messagebox.showerror("Erro", "Valor ou Quantidade inválidos!")

    def salvar_entrada_patio(self):
        cliente = self.cb_cl_ent.get().strip().upper()
        veiculo = self.en_ent_ca.get().strip().upper()
        placa = self.en_ent_pl.get().strip().upper()
        obs = self.en_ent_obs.get().strip()
        
        if not cliente or not placa:
            messagebox.showwarning("Atenção", "Preencha pelo menos Cliente e Placa!")
            return

        km_digitado = self.en_ent_km.get().strip()
        km_salvar = km_digitado if km_digitado != "" else "0"

        try:
            mo_valor = float(self.en_ent_mo.get().replace(",", ".")) if self.en_ent_mo.get() else 0.0
        except ValueError:
            mo_valor = 0.0

        if mo_valor > 0:
            if not any(i['nome'] == "MÃO DE OBRA" for i in self.servicos_entrada_atual):
                self.servicos_entrada_atual.append({
                    "nome": "MÃO DE OBRA", 
                    "valor": mo_valor, 
                    "unit": mo_valor, 
                    "qtd": 1
                })

        total_calculado = sum(item['valor'] for item in self.servicos_entrada_atual)
        data_agora = datetime.now().strftime('%d/%m/%Y %H:%M')
        servs_json = json.dumps(self.servicos_entrada_atual, ensure_ascii=False)

        try:
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO patio (data_entrada, cliente, carro, placa, km, servicos_json, total_geral, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (data_agora, cliente, veiculo or "N/A", placa, km_salvar, servs_json, total_calculado, obs))
            conn.commit()
            conn.close()
        except Exception as err:
            print(f"[NEXUS] Erro ao gravar entrada no SQLite: {err}")

        self.carregar_patio_do_banco()
        messagebox.showinfo("Sucesso", f"Veículo {veiculo} ({placa}) deu entrada no pátio!\nKM Registrado: {km_salvar}")
        self.tela_inicial()

    # ==========================================================
    # ✅ SAÍDA E RECIBO FINAL (KM + HISTÓRICO + WHATSAPP)
    # ==========================================================
    def fin(self):
        selecionado = self.cb_s.get()
        if "(" not in selecionado: 
            messagebox.showwarning("Atenção", "Selecione um veículo na lista!")
            return
            
        placa = selecionado.split("(")[-1].replace(")", "").strip()
        entrada = next((e for e in self.entradas if e['placa'] == placa), None)
        
        if not entrada:
            messagebox.showerror("Erro", "Veículo não encontrado!")
            return

        dados_servicos = entrada.get('servicos') or entrada.get('servicos_json') or []
        if isinstance(dados_servicos, str):
            try:
                servicos = json.loads(dados_servicos)
            except Exception:
                servicos = []
        else:
            servicos = list(dados_servicos)

        texto_itens_servicos = ""
        mo_valor = 0.0
        total_pecas = 0.0
        
        for item in servicos:
            if isinstance(item, dict):
                nome = item.get('nome', '').upper()
                valor = float(item.get('valor', 0))
                qtd = int(item.get('qtd', 1))
                unitario = float(item.get('unit', valor / qtd if qtd > 0 else valor))
            else:
                nome = str(item[0]).upper()
                valor = float(item[3] if len(item) >= 4 else item[1])
                qtd = int(item[2] if len(item) >= 3 else 1)
                unitario = float(item[1] if len(item) >= 2 else valor)
            
            if "MÃO DE OBRA" in nome or "MAO DE OBRA" in nome:
                mo_valor += valor
            else:
                total_pecas += valor
                texto_itens_servicos += f"* {nome}: {qtd} UN x R$ {unitario:.2f} = R$ {valor:.2f}\n"

        total_geral = total_pecas + mo_valor
        if total_geral == 0 and entrada.get('total_geral', 0) > 0:
            total_geral = float(entrada.get('total_geral'))

        cliente = entrada.get('cliente', 'CLIENTE').upper()
        km = str(entrada.get('km') or entrada.get('Km') or '0').strip()
        carro = entrada.get('carro', 'VEÍCULO').upper()
        observacao_veiculo = str(entrada.get('observacao', '')).strip()

        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        
        cursor.execute("SELECT observacao, km FROM patio WHERE placa = ? LIMIT 1", (placa,))
        res_patio = cursor.fetchone()
        if res_patio:
            if not observacao_veiculo and res_patio[0]:
                observacao_veiculo = str(res_patio[0]).strip()
            if (not km or km in ['0', 'None', '']) and res_patio[1]:
                km = str(res_patio[1]).strip()

        if not km or km.lower() in ['none', '']:
            km = '0'

        cursor.execute("SELECT telefone FROM clientes WHERE placa = ? OR nome = ? LIMIT 1", (placa, cliente))
        res_tel = cursor.fetchone()
        telefone = res_tel[0] if res_tel else ""

        dir_saida = os.path.join(self.base_path, "SAIDAS")
        data_hora = datetime.now().strftime("%d-%m-%Y_%H-%M-%S")
        nome_arquivo = f"Recibo_{placa}_{data_hora}.pdf"
        caminho_completo = os.path.join(dir_saida, nome_arquivo)
        
        try:
            forma_pagamento = self.metodo.get().upper()
            self.gerar_pdf_mecanica(
                caminho_completo, 
                cliente, 
                placa, 
                servicos, 
                mo_valor, 
                total_geral, 
                km, 
                "RECIBO", 
                forma_pagamento,
                observacao=observacao_veiculo
            )

            data_hoje = datetime.now().strftime("%d/%m/%Y %H:%M")
            cursor.execute("""
                INSERT INTO historico_vendas (cliente, placa, total, data, pagamento, itens_detalhados, km, observacao)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (cliente, placa, total_geral, data_hoje, forma_pagamento, json.dumps(servicos, ensure_ascii=False), km, observacao_veiculo))

            cursor.execute("DELETE FROM patio WHERE placa = ?", (placa,))
            conn.commit()
            conn.close()

            self.carregar_patio_do_banco()
            try: 
                os.startfile(caminho_completo)
            except Exception: 
                pass

            messagebox.showinfo("Sucesso", f"Saída concluída!\nKM Registrado: {km}\nPDF gerado e gravado no Histórico!")

            if telefone:
                texto_obs_wa = f"\n📝 *Observações:* {observacao_veiculo}\n" if observacao_veiculo else ""
                mensagem_wa = (
                    f"🏎️💨 *{NOME_OFICINA}*\n"
                    f"📍 {ENDERECO_OFICINA}\n\n"
                    f"✅ *RECIBO DE SAÍDA: {placa}*\n"
                    f"👤 Cliente: {cliente}\n"
                    f"🚗 Veículo: {carro} | KM: {km}\n"
                    f"-----------------------------------\n"
                    f"{texto_itens_servicos}"
                    f"* Mão de Obra: R$ {mo_valor:.2f}\n"
                    f"-----------------------------------\n"
                    f"💰 *TOTAL: R$ {total_geral:.2f}*\n"
                    f"💳 Forma de Pagamento: *{forma_pagamento}*"
                    f"{texto_obs_wa}"
                    f"{DADOS_PIX}"
                )
                self.enviar_whatsapp(telefone, mensagem_wa)

            self.tela_inicial()
        except Exception as e:
            if conn: conn.close()
            messagebox.showerror("Erro no PDF", f"Falha ao processar finalização:\n{e}")

    def preencher_ent_direta(self, e):
        c = next((cl for cl in self.clientes_cadastrados if cl['nome'] == e), None)
        if c: 
            self.en_ent_ca.delete(0, 'end')
            self.en_ent_ca.insert(0, c['carro'])
            self.en_ent_pl.delete(0, 'end')
            self.en_ent_pl.insert(0, c['placa'])

    # ==========================================================
    # 💰 DASHBOARD FINANCEIRO E FECHAMENTO
    # ==========================================================
    def tela_financeiro(self):
        self.limpar_tela("💰 DASHBOARD FINANCEIRO")
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        mes_atual = datetime.now().strftime("%m/%Y")
        cursor.execute("SELECT total, itens_detalhados FROM historico_vendas WHERE data LIKE ?", (f"%{mes_atual}%",))
        vendas = cursor.fetchall()
        total_mes = sum(v[0] for v in vendas if v[0])
        contagem_servicos = {}
        
        for v in vendas:
            if v[1]:
                itens = json.loads(v[1])
                for it in itens:
                    nome = it['nome'].split('(')[0].strip()
                    contagem_servicos[nome] = contagem_servicos.get(nome, 0) + 1
                    
        mais_realizados = sorted(contagem_servicos.items(), key=lambda x: x[1], reverse=True)[:5]
        
        f_resumo = ctk.CTkFrame(self.main_frame, fg_color=COLOR_CARD, border_width=1, border_color=COLOR_RED_DEGRADE)
        f_resumo.pack(fill="x", pady=10, padx=10)
        ctk.CTkLabel(f_resumo, text=f"FATURAMENTO {mes_atual}", font=("Segoe UI", 16, "bold")).pack(pady=5)
        ctk.CTkLabel(f_resumo, text=f"R$ {total_mes:.2f}", font=("Segoe UI", 32, "bold"), text_color=COLOR_RED_VIBRANT).pack(pady=10)
        
        ctk.CTkLabel(self.main_frame, text="📊 SERVIÇOS MAIS PROCURADOS (TOP 5)", font=("Segoe UI", 14, "bold")).pack(pady=15)
        for serv, qtd in mais_realizados:
            f_item = ctk.CTkFrame(self.main_frame, fg_color="#252525", height=40)
            f_item.pack(fill="x", pady=2, padx=50)
            ctk.CTkLabel(f_item, text=f"🛠️ {serv}", font=("Segoe UI", 12)).pack(side="left", padx=20)
            ctk.CTkLabel(f_item, text=f"{qtd}x Realizados", font=("Segoe UI", 12, "bold"), text_color=COLOR_RED_VIBRANT).pack(side="right", padx=20)
            
        ctk.CTkButton(self.main_frame, text="📄 GERAR FECHAMENTO MENSAL (PDF)", fg_color="#006600", height=50, command=self.gerar_pdf_fechamento).pack(pady=30)
        conn.close()

    def gerar_pdf_fechamento(self):
        try:
            mes_ref = datetime.now().strftime("%m/%Y")
            arquivo = os.path.join(self.base_path, "FECHAMENTO_MENSAL", f"Fechamento_{mes_ref.replace('/','_')}.pdf")
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            cursor.execute("SELECT data, cliente, placa, total, pagamento FROM historico_vendas WHERE data LIKE ? ORDER BY data ASC", (f"%{mes_ref}%",))
            vendas = cursor.fetchall()
            
            c = canvas.Canvas(arquivo, pagesize=A4)
            c.setFont("Helvetica-Bold", 16)
            c.drawCentredString(300, 780, NOME_OFICINA)
            c.setFont("Helvetica", 9)
            c.drawCentredString(300, 765, ENDERECO_OFICINA)
            c.line(50, 755, 550, 755)
            c.setFont("Helvetica-Bold", 14)
            c.drawCentredString(300, 735, f"FECHAMENTO MENSAL - {mes_ref}")
            
            y = 690
            c.setFont("Helvetica-Bold", 10)
            c.drawString(50, y, "DATA")
            c.drawString(130, y, "CLIENTE")
            c.drawString(300, y, "PLACA")
            c.drawString(380, y, "PGTO")
            c.drawString(480, y, "VALOR")
            y -= 20
            c.setFont("Helvetica", 9)
            total_geral = 0
            
            for v in vendas:
                if y < 50: 
                    c.showPage()
                    y = 750
                c.drawString(50, y, str(v[0])[:10])
                c.drawString(130, y, str(v[1])[:25])
                c.drawString(300, y, str(v[2]))
                c.drawString(380, y, str(v[4]))
                c.drawString(480, y, f"R$ {float(v[3]):.2f}")
                total_geral += float(v[3])
                y -= 15
                
            c.line(50, y, 550, y)
            c.setFont("Helvetica-Bold", 14)
            c.drawString(300, y-30, f"TOTAL ACUMULADO: R$ {total_geral:.2f}")
            c.save()
            conn.close()
            os.startfile(arquivo)
            messagebox.showinfo("Nexus", "Relatório Mensal gerado!")
        except Exception as e: 
            messagebox.showerror("Erro", f"Falha: {e}")

    # ==========================================================
    # ✅ TELA DE SAÍDA E ALERTAS
    # ==========================================================
    def tela_saida(self):
        self.limpar_tela("✅ BAIXAR SAÍDA")
        if not self.entradas: 
            ctk.CTkLabel(self.main_frame, text="PÁTIO VAZIO", font=("Segoe UI", 14)).pack(pady=50)
            return
        self.cb_s = ctk.CTkComboBox(self.main_frame, values=[f"{e['cliente']} ({e['placa']})" for e in self.entradas], width=400)
        self.cb_s.pack(pady=20)
        self.metodo = ctk.StringVar(value="PIX")
        f = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f.pack(pady=10)
        for m in ["Dinheiro", "PIX", "Cartão"]: 
            ctk.CTkRadioButton(f, text=m, variable=self.metodo, value=m).pack(side="left", padx=15)
        ctk.CTkButton(self.main_frame, text="FINALIZAR E GERAR RECIBO", fg_color="#006600", height=50, command=self.fin).pack(pady=20)

    def checar_alertas_preventiva(self):
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("SELECT cliente, servico, data_vencimento, placa FROM preventivas WHERE status = 'ATIVO'")
        alertas = []
        hoje = datetime.now()
        margem = hoje + timedelta(days=5)
        for cl, sv, dv, pl in cursor.fetchall():
            try:
                dt = datetime.strptime(dv, "%d/%m/%Y")
                if dt <= margem: 
                    alertas.append(f"⚠️ {cl} ({pl}) - {sv} VENCE EM: {dv}")
            except Exception: 
                pass
        conn.close()
        return alertas

    def preencher_orc(self, e):
        c = next((cl for cl in self.clientes_cadastrados if cl['nome'] == e), None)
        if c: 
            self.en_o_ca.delete(0, 'end')
            self.en_o_ca.insert(0, c['carro'])
            self.en_o_pl.delete(0, 'end')
            self.en_o_pl.insert(0, c['placa'])

    # ==========================================================
    # 📋 ORÇAMENTOS SALVOS
    # ==========================================================
    def tela_ver_orcamentos(self):
        self.limpar_tela("📋 ORÇAMENTOS PENDENTES")
        cols = ("ID", "Cliente", "Veículo", "Placa", "KM", "Total R$")
        self.tree_orc_salvos = ttk.Treeview(self.main_frame, columns=cols, show='headings')
        for c in cols:
            self.tree_orc_salvos.heading(c, text=c)
            self.tree_orc_salvos.column(c, width=120, anchor="center")
        self.tree_orc_salvos.pack(fill="both", expand=True, pady=10)
        
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("SELECT id, cliente, carro, placa, km, total FROM orçamentos_emitidos")
        for r in cursor.fetchall():
            self.tree_orc_salvos.insert("", "end", values=(r[0], r[1], r[2], r[3], r[4] or '0', f"R$ {float(r[5]):.2f}"))
        conn.close()
        
        btn_f = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        btn_f.pack(fill="x", pady=10)
        ctk.CTkButton(btn_f, text="✅ ENTRADA EM PÁTIO", fg_color="#006600", height=40, command=self.converter_orcamento_em_patio).pack(side="left", expand=True, padx=10, fill="x")
        ctk.CTkButton(btn_f, text="🗑️ EXCLUIR", fg_color="#660000", height=40, command=self.excluir_orcamento).pack(side="left", expand=True, padx=10, fill="x")

    def converter_orcamento_em_patio(self):
        sel = self.tree_orc_salvos.selection()
        if not sel: 
            return
        id_orc = self.tree_orc_salvos.item(sel)['values'][0]
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("SELECT cliente, carro, placa, km, itens_json, mo, total FROM orçamentos_emitidos WHERE id=?", (id_orc,))
        res = cursor.fetchone()
        if res:
            cl, ca, pl, km_orc, it_j, mo, tot = res
            itens = json.loads(it_j)
            if mo and float(mo) > 0:
                itens.append({"nome": "MÃO DE OBRA", "valor": float(mo), "unit": float(mo), "qtd": 1})
            data_entrada = datetime.now().strftime("%d/%m/%Y %H:%M")
            cursor.execute("INSERT INTO patio (data_entrada, cliente, carro, placa, km, servicos_json, total_geral) VALUES (?,?,?,?,?,?,?)", 
                           (data_entrada, cl, ca, pl, km_orc or '0', json.dumps(itens, ensure_ascii=False), tot))
            cursor.execute("DELETE FROM orçamentos_emitidos WHERE id=?", (id_orc,))
            conn.commit()
            conn.close()
            self.carregar_patio_do_banco()
            self.tela_inicial()

    # ==========================================================
    # 👥 CADASTRO DE CLIENTES (LAYOUT EM CARD PROFISSIONAL)
    # ==========================================================
    def tela_cadastrar_cliente(self):
        self.limpar_tela("👥 CADASTRO DE CLIENTES & VEÍCULOS")

        f_card = ctk.CTkFrame(self.main_frame, fg_color="#1E1E1E", border_width=1, border_color="#333333", corner_radius=12)
        f_card.pack(fill="x", pady=15, padx=20)

        ctk.CTkLabel(
            f_card, 
            text="📋 INFORMAÇÕES DO CLIENTE E VEÍCULO", 
            font=("Segoe UI", 14, "bold"), 
            text_color="#FFFFFF"
        ).pack(anchor="w", pady=(15, 10), padx=20)

        f_form = ctk.CTkFrame(f_card, fg_color="transparent")
        f_form.pack(fill="x", pady=10, padx=20)

        config_campos = [
            ("👤 Nome Completo:", "Ex: João da Silva", 0, 0, 320, "Nome"),
            ("📱 WhatsApp / Tel:", "Ex: (19) 98773-8915", 1, 0, 220, "WhatsApp"),
            ("🚗 Veículo / Modelo:", "Ex: Gol 1.0 G6", 0, 1, 320, "Carro"),
            ("🏷️ Placa do Veículo:", "Ex: ABC1D23", 1, 1, 220, "Placa"),
            ("📅 Ano Fabricação:", "Ex: 2018/2019", 0, 2, 180, "Ano"),
            ("⚙️ Motorização:", "Ex: 1.0 12V Flex", 1, 2, 220, "Motor"),
            ("📍 Endereço Completo:", "Ex: Rua Alcídes Silva, 85 - Limeira/SP", 0, 3, 560, "Endereço"),
        ]

        self.ents = {}

        for rotulo, placeholder, col, lin, largura, chave in config_campos:
            f_campo = ctk.CTkFrame(f_form, fg_color="transparent")
            if chave == "Endereço":
                f_campo.grid(row=lin, column=0, columnspan=2, sticky="w", pady=8, padx=5)
            else:
                f_campo.grid(row=lin, column=col, sticky="w", pady=8, padx=5)

            ctk.CTkLabel(f_campo, text=rotulo, font=("Segoe UI", 11, "bold"), text_color="#AAAAAA").pack(anchor="w", pady=(0, 2))
            entry = ctk.CTkEntry(f_campo, width=largura, height=35, placeholder_text=placeholder, font=("Segoe UI", 12), corner_radius=6)
            entry.pack(fill="x")
            self.ents[chave] = entry

        f_botoes = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_botoes.pack(fill="x", pady=20, padx=20)

        ctk.CTkButton(
            f_botoes, 
            text="💾 SALVAR CLIENTE E VEÍCULO", 
            fg_color=COLOR_RED_VIBRANT, 
            hover_color="#AA0000",
            height=45, 
            font=("Segoe UI", 13, "bold"),
            corner_radius=8,
            command=self.salvar_c
        ).pack(fill="x")

    def salvar_c(self):
        nome = self.ents['Nome'].get().strip().upper()
        if not nome:
            messagebox.showwarning("Atenção", "O Nome do cliente é obrigatório!")
            return
        d = (
            nome, 
            self.ents['WhatsApp'].get().strip(), 
            self.ents['Carro'].get().strip().upper(), 
            self.ents['Ano'].get().strip(), 
            self.ents['Motor'].get().strip().upper(), 
            self.ents['Placa'].get().strip().upper(), 
            self.ents['Endereço'].get().strip().upper()
        )
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO clientes (nome, telefone, carro, ano, motor, placa, endereco) VALUES (?,?,?,?,?,?,?)", d)
        conn.commit()
        conn.close()
        self.carregar_dados()
        messagebox.showinfo("Sucesso", f"Cliente {nome} cadastrado com sucesso!")
        self.tela_inicial()

    # ==========================================================
    # 🛠️ CATÁLOGO DE SERVIÇOS (COM BOTÃO FIXO NO RODAPÉ)
    # ==========================================================
    def tela_servicos(self):
        self.limpar_tela("🛠️ CATÁLOGO DE SERVIÇOS E PEÇAS")

        f_card_add = ctk.CTkFrame(self.main_frame, fg_color="#1E1E1E", border_width=1, border_color="#333333", corner_radius=10)
        f_card_add.pack(fill="x", pady=10, padx=15, side="top")

        ctk.CTkLabel(
            f_card_add, 
            text="➕ ADICIONAR NOVO SERVIÇO / ITEM AO CATÁLOGO", 
            font=("Segoe UI", 12, "bold"), 
            text_color="#FFFFFF"
        ).pack(anchor="w", pady=(10, 5), padx=15)

        f_inputs = ctk.CTkFrame(f_card_add, fg_color="transparent")
        f_inputs.pack(fill="x", pady=(0, 10), padx=15)

        self.en_sv_n = ctk.CTkEntry(
            f_inputs, 
            placeholder_text="Digite o nome do serviço ou peça...", 
            width=450, 
            height=38,
            font=("Segoe UI", 12)
        )
        self.en_sv_n.pack(side="left", fill="x", expand=True, padx=(0, 10))

        ctk.CTkButton(
            f_inputs, 
            text="💾 SALVAR ITEM", 
            fg_color=COLOR_RED_VIBRANT, 
            hover_color="#AA0000",
            height=38, 
            width=130,
            font=("Segoe UI", 11, "bold"),
            command=self.save_sv
        ).pack(side="right")

        f_acoes = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_acoes.pack(fill="x", pady=(10, 15), padx=15, side="bottom")

        ctk.CTkButton(
            f_acoes, 
            text="🗑️ EXCLUIR ITEM SELECIONADO DO CATÁLOGO", 
            fg_color="#660000", 
            hover_color="#990000",
            height=45, 
            font=("Segoe UI", 12, "bold"),
            corner_radius=8,
            command=self.excluir_servico_catalogo
        ).pack(fill="x")

        f_tabela_frame = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_tabela_frame.pack(fill="both", expand=True, pady=5, padx=15, side="top")

        ctk.CTkLabel(f_tabela_frame, text="📋 ITENS E SERVIÇOS CADASTRADOS", font=("Segoe UI", 12, "bold")).pack(anchor="w", pady=(0, 5))

        cols = ("ID", "NOME")
        self.tree_servicos = ttk.Treeview(f_tabela_frame, columns=cols, show='headings')
        self.tree_servicos.heading("ID", text="ID")
        self.tree_servicos.heading("NOME", text="DESCRIÇÃO DO SERVIÇO / ITEM")
        self.tree_servicos.column("ID", width=70, anchor="center")
        self.tree_servicos.column("NOME", width=550, anchor="w")

        scrollbar = ttk.Scrollbar(f_tabela_frame, orient="vertical", command=self.tree_servicos.yview)
        self.tree_servicos.configure(yscrollcommand=scrollbar.set)
        
        self.tree_servicos.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome FROM catalogo_servicos ORDER BY nome ASC")
        for row in cursor.fetchall():
            self.tree_servicos.insert("", "end", values=row)
        conn.close()

    def save_sv(self):
        if self.en_sv_n.get().strip(): 
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            cursor.execute("INSERT INTO catalogo_servicos (nome) VALUES (?)", (self.en_sv_n.get().strip().upper(),))
            conn.commit()
            conn.close()
            self.carregar_dados()
            self.tela_servicos()

    def excluir_servico_catalogo(self):
        selecionado = self.tree_servicos.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um item da tabela para excluir!")
            return

        item_vals = self.tree_servicos.item(selecionado[0], "values")
        item_id = item_vals[0]
        item_nome = item_vals[1]

        if messagebox.askyesno("Confirmar Exclusão", f"Deseja realmente remover o item abaixo do catálogo?\n\n'{item_nome}'"):
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM catalogo_servicos WHERE id = ?", (item_id,))
            conn.commit()
            conn.close()
            self.carregar_dados()
            messagebox.showinfo("Sucesso", "Item removido do catálogo!")
            self.tela_servicos()

    # ==========================================================
    # 🔍 HISTÓRICO DE PASSAGENS
    # ==========================================================
    def tela_busca_historico(self):
        self.limpar_tela("🔍 BUSCA NO HISTÓRICO")
        f_busca = ctk.CTkFrame(self.main_frame, fg_color="transparent")
        f_busca.pack(pady=10)
        
        self.en_b = ctk.CTkEntry(f_busca, width=400, placeholder_text="Busque por Nome do Cliente ou Placa...")
        self.en_b.grid(row=0, column=0, padx=10)
        
        cols = ("CLIENTE", "PLACA", "PASSAGENS")
        self.tree_h = ttk.Treeview(self.main_frame, columns=cols, show='headings')
        self.tree_h.heading("CLIENTE", text="CLIENTE")
        self.tree_h.heading("PLACA", text="PLACA")
        self.tree_h.heading("PASSAGENS", text="PASSAGENS NA OFICINA")
        self.tree_h.column("CLIENTE", width=400)
        self.tree_h.column("PLACA", width=150, anchor="center")
        self.tree_h.column("PASSAGENS", width=150, anchor="center")
        self.tree_h.pack(fill="both", expand=True, pady=10)
        
        def buscar():
            for i in self.tree_h.get_children():
                self.tree_h.delete(i)
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            t = f"%{self.en_b.get()}%"
            cursor.execute("SELECT cliente, placa, COUNT(*) FROM historico_vendas WHERE cliente LIKE ? OR placa LIKE ? GROUP BY cliente, placa ORDER BY cliente ASC", (t, t))
            for r in cursor.fetchall():
                self.tree_h.insert("", "end", values=r)
            conn.close()
            
        ctk.CTkButton(f_busca, text="BUSCAR", fg_color=COLOR_RED_DEGRADE, command=buscar).grid(row=0, column=1)
        ctk.CTkButton(self.main_frame, text="VER TODAS AS ENTRADAS DESTE CLIENTE", fg_color=COLOR_RED_VIBRANT, height=45, command=self.abrir_detalhes_agrupados).pack(pady=10)

    def abrir_detalhes_agrupados(self):
        sel = self.tree_h.selection()
        if not sel: 
            return
        cl_nome, pl_selecionada = self.tree_h.item(sel)['values'][0], self.tree_h.item(sel)['values'][1]
        conn = sqlite3.connect(CAMINHO_DO_BANCO)
        cursor = conn.cursor()
        cursor.execute("SELECT data, total, pagamento, itens_detalhados, km FROM historico_vendas WHERE cliente=? AND placa=? ORDER BY id DESC", (cl_nome, pl_selecionada))
        passagens = cursor.fetchall()
        conn.close()
        
        if passagens:
            janela = ctk.CTkToplevel(self)
            janela.title(f"HISTÓRICO: {cl_nome} - {pl_selecionada}")
            janela.geometry("800x600")
            janela.configure(fg_color=COLOR_BG)
            ctk.CTkLabel(janela, text="HISTÓRICO COMPLETO DO VEÍCULO", font=("Segoe UI", 20, "bold"), text_color=COLOR_RED_VIBRANT).pack(pady=15)
            f_container = ctk.CTkScrollableFrame(janela, fg_color=COLOR_CARD, border_width=1, border_color="#333333")
            f_container.pack(fill="both", expand=True, padx=20, pady=10)
            
            for data, total, pag, itens_json, km_hist in passagens:
                f_passagem = ctk.CTkFrame(f_container, fg_color="#252525", border_width=1, border_color=COLOR_RED_DEGRADE)
                f_passagem.pack(fill="x", pady=10, padx=5)
                ctk.CTkLabel(f_passagem, text=f"📅 DATA: {data}  |  🚗 KM: {km_hist or '0'}  |  💰 TOTAL: R$ {total:.2f}  |  💳 PGTO: {pag}", font=("Segoe UI", 12, "bold"), text_color="white").pack(pady=5, padx=10, anchor="w")
                itens = json.loads(itens_json) if itens_json else []
                txt_itens = "Peças/Serviços: " + ", ".join([f"{i['nome']} (R$ {i['valor']:.2f})" for i in itens])
                lbl_itens = ctk.CTkLabel(f_passagem, text=txt_itens, font=("Segoe UI", 11), text_color="#AAAAAA", wraplength=700, justify="left")
                lbl_itens.pack(pady=5, padx=10, anchor="w")

    def excluir_orcamento(self):
        sel = self.tree_orc_salvos.selection()
        if sel: 
            id_orc = self.tree_orc_salvos.item(sel)['values'][0]
            conn = sqlite3.connect(CAMINHO_DO_BANCO)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM orçamentos_emitidos WHERE id=?", (id_orc,))
            conn.commit()
            conn.close()
            self.tela_ver_orcamentos()

    def cancelar_patio(self, tree):
        sel = tree.selection()
        if sel: 
            pl = tree.item(sel)['values'][3]
            if messagebox.askyesno("Confirmar", f"Remover {pl} do pátio?"):
                conn = sqlite3.connect(CAMINHO_DO_BANCO)
                cursor = conn.cursor()
                cursor.execute("DELETE FROM patio WHERE placa=?", (pl,))
                conn.commit()
                conn.close()
                self.carregar_patio_do_banco()
                self.tela_inicial()

    def remover_item_orcamento(self):
        selecionado = self.tree_o.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um item para remover.")
            return
        item_id = selecionado[0]
        index = self.tree_o.index(item_id)
        self.tree_o.delete(item_id)
        if 0 <= index < len(self.pecas_orc):
            del self.pecas_orc[index]

    def remover_item_entrada(self):
        selecionado = self.tree_ent.selection()
        if not selecionado:
            messagebox.showwarning("Aviso", "Selecione um item para remover.")
            return
        item_id = selecionado[0]
        index = self.tree_ent.index(item_id)
        self.tree_ent.delete(item_id)
        if 0 <= index < len(self.servicos_entrada_atual):
            del self.servicos_entrada_atual[index]

    # ==========================================================
    # ✏️ JANELA DE EDIÇÃO DE SERVIÇOS E KM NO PÁTIO
    # ==========================================================
    def abrir_janela_edicao(self):
        selecionado = self.tree.selection()
        if not selecionado:
            messagebox.showwarning("Atenção", "Selecione um veículo no pátio!")
            return
        
        item = self.tree.item(selecionado)
        valores_linha = item.get('values', [])
        placa = valores_linha[3] if len(valores_linha) > 3 else ""
        entrada = next((e for e in self.entradas if e['placa'] == placa), None)
        
        if entrada:
            janela = ctk.CTkToplevel(self)
            janela.title(f"Nexus Pro - Edição: {placa}")
            janela.geometry("700x700")
            janela.attributes("-topmost", True)
            
            ctk.CTkLabel(janela, text=f"🔧 Ajustes Técnicos & Orçamento: {placa}", font=("Segoe UI", 20, "bold")).pack(pady=5)

            f_km = ctk.CTkFrame(janela, fg_color="#2B2B2B", corner_radius=10)
            f_km.pack(fill="x", padx=15, pady=3, ipady=3)
            
            ctk.CTkLabel(f_km, text="🚗 Quilometragem (KM):", font=("Segoe UI", 12, "bold")).pack(side="left", padx=15)
            self.en_km_edicao = ctk.CTkEntry(f_km, width=150, placeholder_text="Ex: 45000")
            self.en_km_edicao.pack(side="left", padx=10)
            self.en_km_edicao.insert(0, str(entrada.get('km', '0')))

            ctk.CTkLabel(janela, text="📋 Serviços salvos no Veículo:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(5, 0))
            
            cols_ex = ("SERV", "UNIT", "QTD", "TOTAL")
            tree_existentes = ttk.Treeview(janela, columns=cols_ex, show='headings', height=4)
            for c in cols_ex: 
                tree_existentes.heading(c, text=c) 
                tree_existentes.column(c, width=150, anchor="center")
            tree_existentes.pack(fill="x", padx=15, pady=3)

            raw_servicos = entrada.get('servicos') or entrada.get('servicos_json') or []
            servicos_atuais = json.loads(raw_servicos) if isinstance(raw_servicos, str) else list(raw_servicos)

            def atualizar_tabela_existentes():
                for i in tree_existentes.get_children():
                    tree_existentes.delete(i)
                for s in servicos_atuais:
                    nome_s = s.get('nome', '')
                    val_s = float(s.get('unit', s.get('valor', 0)))
                    qtd_s = float(s.get('qtd', 1))
                    tot_s = float(s.get('valor', val_s * qtd_s))
                    tree_existentes.insert("", "end", values=(nome_s, f"R$ {val_s:.2f}", int(qtd_s) if qtd_s.is_integer() else qtd_s, f"R$ {tot_s:.2f}"))

            atualizar_tabela_existentes()

            f_acoes_existentes = ctk.CTkFrame(janela, fg_color="transparent")
            f_acoes_existentes.pack(fill="x", padx=15, pady=3)

            def excluir_servico_selecionado():
                selecionado_tree = tree_existentes.selection()
                if not selecionado_tree:
                    messagebox.showwarning("Atenção", "Selecione o serviço que deseja excluir!")
                    return
                item_sel = tree_existentes.item(selecionado_tree)
                nome_alvo = item_sel['values'][0]
                if messagebox.askyesno("Confirmar", f"Remover '{nome_alvo}'?"):
                    nonlocal servicos_atuais
                    removido = False
                    novos = []
                    for s in servicos_atuais:
                        if not removido and s.get('nome', '') == nome_alvo:
                            removido = True
                            continue
                        novos.append(s)
                    servicos_atuais = novos
                    atualizar_tabela_existentes()

            def ajustar_valor_servico():
                selecionado_tree = tree_existentes.selection()
                if not selecionado_tree:
                    messagebox.showwarning("Atenção", "Selecione o serviço para ajustar o valor!")
                    return
                item_sel = tree_existentes.item(selecionado_tree)
                nome_alvo = item_sel['values'][0]
                dialogo = ctk.CTkInputDialog(text=f"Novo valor unitário (R$) para '{nome_alvo}':", title="Ajustar Valor")
                novo_valor_str = dialogo.get_input()
                if novo_valor_str:
                    try:
                        novo_valor = float(novo_valor_str.replace(',', '.'))
                        for s in servicos_atuais:
                            if s.get('nome', '') == nome_alvo:
                                q = float(s.get('qtd', 1))
                                s['unit'] = novo_valor
                                s['valor'] = novo_valor * q
                        atualizar_tabela_existentes()
                    except ValueError:
                        messagebox.showerror("Erro", "Digite um valor numérico válido!")

            ctk.CTkButton(f_acoes_existentes, text="✏️ AJUSTAR VALOR", fg_color="#1f538d", hover_color="#14375e", width=200, height=30, command=ajustar_valor_servico).pack(side="left", padx=5)
            ctk.CTkButton(f_acoes_existentes, text="🗑️ EXCLUIR SERVIÇO", fg_color="#b30000", hover_color="#800000", width=200, height=30, command=excluir_servico_selecionado).pack(side="left", padx=5)

            ctk.CTkLabel(janela, text="➕ Adicionar novos itens/serviços:", font=("Segoe UI", 12, "bold")).pack(anchor="w", padx=15, pady=(5, 0))
            f_add = ctk.CTkFrame(janela, fg_color="#2B2B2B", corner_radius=10)
            f_add.pack(fill="x", pady=3, padx=15, ipady=5)

            self.cb_sv_ed = ctk.CTkComboBox(f_add, values=self.servicos_cadastrados, width=250)
            self.cb_sv_ed.grid(row=0, column=0, padx=10, pady=5)

            self.en_p_ed = ctk.CTkEntry(f_add, placeholder_text="R$ Unit.", width=100)
            self.en_p_ed.grid(row=0, column=1, padx=5)

            self.en_qtd_ed = ctk.CTkEntry(f_add, placeholder_text="Qtd", width=60)
            self.en_qtd_ed.insert(0, "1")
            self.en_qtd_ed.grid(row=0, column=2, padx=5)

            def add_item_edicao_local():
                try:
                    v_unit = float(self.en_p_ed.get().replace(",", "."))
                    qtd = float(self.en_qtd_ed.get().replace(",", "."))
                    v_total = v_unit * qtd
                    serv_nome = self.cb_sv_ed.get().upper()
                    servicos_atuais.append({"nome": serv_nome, "valor": v_total, "unit": v_unit, "qtd": qtd})
                    atualizar_tabela_existentes()
                    self.en_p_ed.delete(0, 'end')
                    self.en_qtd_ed.delete(0, 'end')
                    self.en_qtd_ed.insert(0, "1")
                except Exception:
                    messagebox.showerror("Erro", "Verifique valor e quantidade!")

            ctk.CTkButton(f_add, text="ADICIONAR", fg_color=COLOR_RED_DEGRADE, width=100, height=30, command=add_item_edicao_local).grid(row=0, column=3, padx=10)

            def salvar_com_km():
                novo_km = self.en_km_edicao.get().strip() or "0"
                t_geral = sum(float(s.get('valor', 0)) for s in servicos_atuais)
                servs_json = json.dumps(servicos_atuais, ensure_ascii=False)
                
                conn = sqlite3.connect(CAMINHO_DO_BANCO)
                cursor = conn.cursor()
                cursor.execute("UPDATE patio SET km = ?, servicos_json = ?, total_geral = ? WHERE placa = ?", (novo_km, servs_json, t_geral, placa))
                conn.commit()
                conn.close()
                
                self.carregar_patio_do_banco()
                messagebox.showinfo("Sucesso", "Alterações salvas no banco de dados!")
                janela.destroy()
                self.tela_inicial()

            ctk.CTkButton(janela, text="💾 SALVAR ALTERAÇÕES E ATUALIZAR", fg_color=COLOR_RED_VIBRANT, height=45, command=salvar_com_km).pack(side="top", pady=15, fill="x", padx=15)


# ==========================================================
# 🚦 INICIALIZAÇÃO DO APLICATIVO
# ==========================================================
def iniciar_sistema():
    status_inicial = verificar_status_planilha()
    if status_inicial == "PAGO":
        threading.Thread(target=monitor_de_seguranca, daemon=True).start() 
        app = SistemaOficina()
        app.mainloop()
    else:
        root_erro = ctk.CTk()
        root_erro.withdraw()
        messagebox.showerror("🛡️ ACESSO NEGADO", "⚠️ SISTEMA BLOQUEADO\nWhatsApp: (19) 99005-3317")
        os._exit(0)

if __name__ == "__main__":
    iniciar_sistema()