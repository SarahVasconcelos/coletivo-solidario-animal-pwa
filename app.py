import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'coletivo_animal_seguro_2026_x9k2m'

# Configuração da pasta de uploads de fotos
UPLOAD_FOLDER = 'static/uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Cria a pasta de uploads automaticamente se ela não existir
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Configuração de Cookies Seguros (RNF01)
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Strict'

# ---------------------------------------------------------
# INICIALIZAÇÃO DA BASE DE DADOS E DADOS SEMENTE (RNF01)
# ---------------------------------------------------------
def init_db():
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    # Tabela de Usuários / Voluntários
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS usuarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            senha_hash TEXT NOT NULL
        )
    ''')
    
    # Tabela de Lares Temporários (LT) - Minimização LGPD (Telefone + Bairro)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS lar_temporario (
            id_lar INTEGER PRIMARY KEY AUTOINCREMENT,
            nome_voluntario TEXT NOT NULL,
            contato_telefone TEXT NOT NULL,
            endereco_bairro TEXT NOT NULL,
            capacidade_maxima INTEGER NOT NULL,
            status_disponibilidade TEXT NOT NULL
        )
    ''')
    
    # Tabela de Animais (Relacionamento 1:N com lar_temporario)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS animais (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            especie TEXT NOT NULL,
            porte TEXT NOT NULL,
            sexo TEXT,
            idade_aproximada TEXT,
            status_saude TEXT NOT NULL,
            observacoes_clinicas TEXT,
            status_castracao TEXT NOT NULL,
            status_vacinacao TEXT NOT NULL,
            status_adocao TEXT NOT NULL,
            id_lar_temporario INTEGER,
            foto TEXT,
            FOREIGN KEY (id_lar_temporario) REFERENCES lar_temporario(id_lar)
        )
    ''')
    
    # Inserir usuário padrão se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM usuarios")
    if cursor.fetchone()[0] == 0:
        hash_senha = generate_password_hash("Voluntario123")
        cursor.execute("INSERT INTO usuarios (nome, email, senha_hash) VALUES (?, ?, ?)", 
                       ("Maria Silva (Embu)", "voluntario@coletivo.org", hash_senha))
        
    # Inserir Lar Temporário inicial padrão se a tabela estiver vazia
    cursor.execute("SELECT COUNT(*) FROM lar_temporario")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO lar_temporario (nome_voluntario, contato_telefone, endereco_bairro, capacidade_maxima, status_disponibilidade) 
            VALUES (?, ?, ?, ?, ?)
        ''', ("Maria Silva", "(11) 99999-8888", "Embu das Artes", 3, "Disponível"))
        
    conn.commit()
    conn.close()

init_db()

# ---------------------------------------------------------
# ROTAS DO SISTEMA
# ---------------------------------------------------------

# Rota Raiz: Redireciona para o login ou painel se já estiver autenticado
@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('painel'))

# RNF01: Autenticação (Login)
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        senha = request.form['senha']
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute("SELECT id, nome, senha_hash FROM usuarios WHERE email = ?", (email,))
        user = cursor.fetchone()
        conn.close()
        
        if user and check_password_hash(user[2], senha):
            session['usuario_id'] = user[0]
            session['usuario_nome'] = user[1]
            return redirect(url_for('painel'))
        else:
            return render_template('login.html', erro="E-mail ou senha incorretos.")
            
    return render_template('login.html')

# Rota de Encerramento de Sessão (Logout)
@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# Tela 1: Painel Inicial (Listagem de Animais)
@app.route('/painel')
def painel():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.id, a.nome, a.especie, a.status_saude, a.status_adocao, l.nome_voluntario, l.endereco_bairro, a.foto, a.porte, a.sexo, a.idade_aproximada 
        FROM animais a 
        LEFT JOIN lar_temporario l ON a.id_lar_temporario = l.id_lar
    ''')
    animais = cursor.fetchall()
    conn.close()
    
    return render_template('painel.html', animais=animais, usuario=session.get('usuario_nome'))

# Tela 2: Formulário de Cadastro
@app.route('/cadastro', methods=['GET', 'POST'])
def cadastro():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nome = request.form['nome']
        especie = request.form['especie']
        porte = request.form['porte']
        sexo = request.form['sexo']
        idade = request.form['idade']
        status_saude = request.form['status_saude']
        observacoes = request.form['observacoes']
        status_castracao = request.form['status_castracao']
        status_vacinacao = request.form['status_vacinacao']
        status_adocao = request.form['status_adocao']
        id_lar = request.form['id_lar']
        
        foto_filename = None
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto_filename = filename
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO animais (nome, especie, porte, sexo, idade_aproximada, status_saude, 
                                 observacoes_clinicas, status_castracao, status_vacinacao, status_adocao, id_lar_temporario, foto)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (nome, especie, porte, sexo, idade, status_saude, observacoes, status_castracao, status_vacinacao, status_adocao, id_lar, foto_filename))
        
        animal_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return redirect(url_for('confirmacao', id=animal_id))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT l.id_lar, l.nome_voluntario, l.endereco_bairro, l.capacidade_maxima,
               (SELECT COUNT(*) FROM animais a WHERE a.id_lar_temporario = l.id_lar) as total_ocupadas
        FROM lar_temporario l
        WHERE l.status_disponibilidade = 'Disponível'
    ''')
    lares_brutos = cursor.fetchall()
    conn.close()
    
    lares = []
    for lar in lares_brutos:
        id_lar, nome_vol, bairro, capacidade, ocupadas = lar
        vagas_livres = capacidade - ocupadas
        
        if vagas_livres > 0:
            texto_exibicao = f"{nome_vol} - {bairro} ({ocupadas} de {capacidade} vagas ocupadas - {vagas_livres} livres)"
            lares.append((id_lar, texto_exibicao))
            
    return render_template('cadastro.html', lares=lares)

# ==========================================
# NOVA ROTA: Cadastro de Novo Lar Temporário
# ==========================================
@app.route('/novo_lar', methods=['GET', 'POST'])
def novo_lar():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    if request.method == 'POST':
        nome_voluntario = request.form['nome_voluntario']
        contato_telefone = request.form['contato_telefone']
        endereco_bairro = request.form['endereco_bairro']
        capacidade_maxima = int(request.form['capacidade_maxima'])
        status_disponibilidade = request.form['status_disponibilidade']
        
        conn = sqlite3.connect('database.db')
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO lar_temporario (nome_voluntario, contato_telefone, endereco_bairro, capacidade_maxima, status_disponibilidade)
            VALUES (?, ?, ?, ?, ?)
        ''', (nome_voluntario, contato_telefone, endereco_bairro, capacidade_maxima, status_disponibilidade))
        
        conn.commit()
        conn.close()
        
        return redirect(url_for('cadastro'))
        
    return render_template('novo_lar.html', usuario=session.get('usuario_nome'))

# Tela 3: Confirmação e Emissão do Termo
@app.route('/confirmacao/<int:id>')
def confirmacao(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, nome, especie, status_adocao FROM animais WHERE id = ?", (id,))
    animal = cursor.fetchone()
    conn.close()
    
    return render_template('confirmacao.html', animal=animal)

# Rota para Geração do Termo de Adoção e Responsabilidade
@app.route('/termo/<int:id>')
def gerar_termo(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute('''
        SELECT a.nome, a.especie, a.porte, a.sexo, a.idade_aproximada, a.status_saude, 
               a.observacoes_clinicas, a.status_castracao, a.status_vacinacao, a.status_adocao, 
               a.foto, l.nome_voluntario, l.endereco_bairro
        FROM animais a
        LEFT JOIN lar_temporario l ON a.id_lar_temporario = l.id_lar
        WHERE a.id = ?
    ''', (id,))
    animal = cursor.fetchone()
    conn.close()
    
    if not animal:
        return "Animal não encontrado", 404
        
    return render_template('termo.html', animal=animal)

# Rota para Excluir Cadastro de Animal
@app.route('/excluir/<int:id>')
def excluir(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM animais WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    
    return redirect(url_for('painel'))

# Tela 4: Edição de Animal
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar(id):
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.form['nome']
        especie = request.form['especie']
        porte = request.form['porte']
        sexo = request.form['sexo']
        idade = request.form['idade']
        status_saude = request.form['status_saude']
        observacoes = request.form['observacoes']
        status_castracao = request.form['status_castracao']
        status_vacinacao = request.form['status_vacinacao']
        status_adocao = request.form['status_adocao']
        id_lar = request.form['id_lar']
        
        foto_filename = request.form.get('foto_atual')
        if 'foto' in request.files:
            file = request.files['foto']
            if file and file.filename != '' and allowed_file(file.filename):
                filename = secure_filename(file.filename)
                file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
                foto_filename = filename

        cursor.execute('''
            UPDATE animais 
            SET nome = ?, especie = ?, porte = ?, sexo = ?, idade_aproximada = ?, 
                status_saude = ?, observacoes_clinicas = ?, status_castracao = ?, 
                status_vacinacao = ?, status_adocao = ?, id_lar_temporario = ?, foto = ?
            WHERE id = ?
        ''', (nome, especie, porte, sexo, idade, status_saude, observacoes, 
              status_castracao, status_vacinacao, status_adocao, id_lar, foto_filename, id))
        
        conn.commit()
        conn.close()
        return redirect(url_for('painel'))
        
    cursor.execute("SELECT * FROM animais WHERE id = ?", (id,))
    animal = cursor.fetchone()
    
    cursor.execute('''
        SELECT l.id_lar, l.nome_voluntario, l.endereco_bairro, l.capacidade_maxima,
               (SELECT COUNT(*) FROM animais a WHERE a.id_lar_temporario = l.id_lar) as total_ocupadas
        FROM lar_temporario l
        WHERE l.status_disponibilidade = 'Disponível'
    ''')
    lares_brutos = cursor.fetchall()
    conn.close()
    
    lares = []
    for lar in lares_brutos:
        id_lar, nome_vol, bairro, capacidade, ocupadas = lar
        vagas_livres = capacidade - ocupadas
        if vagas_livres > 0 or id_lar == animal[11]:
            texto_exibicao = f"{nome_vol} - {bairro} ({ocupadas} de {capacidade} vagas ocupadas - {vagas_livres} livres)"
            lares.append((id_lar, texto_exibicao))

    return render_template('editar.html', animal=animal, lares=lares)

# ==========================================
# ROTAS DE CONFIGURAÇÃO PWA (Manifest e SW)
# ==========================================
@app.route('/manifest.json')
def manifest():
    return app.send_static_file('manifest.json')

@app.route('/sw.js')
def service_worker():
    return app.send_static_file('sw.js')

if __name__ == '__main__':
    app.run(debug=True, port=5002)