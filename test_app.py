import os
import pytest
from app import app, init_db
import sqlite3

@pytest.fixture
def client():
    """Configura o cliente de testes do Flask e garante um banco limpo."""
    app.config['TESTING'] = True
    app.config['WTF_CSRF_ENABLED'] = False
    init_db()
    
    # Garante que existe um lar temporário válido no banco para os testes de cadastro
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM lar_temporario")
    if cursor.fetchone()[0] == 0:
        cursor.execute('''
            INSERT INTO lar_temporario (nome_voluntario, contato_telefone, endereco_bairro, capacidade_maxima, status_disponibilidade) 
            VALUES (?, ?, ?, ?, ?)
        ''', ("Lar Teste", "(11) 98888-7777", "Centro", 5, "Disponível"))
        conn.commit()
    conn.close()

    with app.test_client() as client:
        yield client

def login_helper(client):
    """Função auxiliar para autenticar nos testes protegidos."""
    return client.post('/login', data={
        'email': 'voluntario@coletivo.org',
        'senha': 'Voluntario123'
    }, follow_redirects=True)

def test_manifest_json(client):
    """Testa a rota do PWA Manifest."""
    res = client.get('/manifest.json')
    assert res.status_code == 200
    data = res.get_json()
    assert data['name'] == "Coletivo Solidario Animal"

def test_index_redirect(client):
    """Testa se a raiz redireciona para login."""
    res = client.get('/', follow_redirects=False)
    assert res.status_code == 302

def test_login_sucesso_e_falha(client):
    """Testa o fluxo de login."""
    res_fail = client.post('/login', data={
        'email': 'errado@coletivo.org',
        'senha': 'errado'
    }, follow_redirects=True)
    assert res_fail.status_code == 200
    assert b"E-mail ou senha incorretos" in res_fail.data

    res_sucesso = login_helper(client)
    assert res_sucesso.status_code == 200

def test_painel_protegido_e_aberto(client):
    """Testa o acesso ao painel."""
    res_sem_login = client.get('/painel', follow_redirects=False)
    assert res_sem_login.status_code == 302

    login_helper(client)
    res_com_login = client.get('/painel')
    assert res_com_login.status_code == 200

def test_fluxo_crud_animal(client):
    """Testa o ciclo de vida completo de um animal: Cadastro, Confirmação, Termo, Edição e Exclusão."""
    login_helper(client)

    res_get_cad = client.get('/cadastro')
    assert res_get_cad.status_code == 200

    # Usando 'id_lar' exatamente como o app.py espera
    data_cadastro = {
        'nome': 'Bidu Teste',
        'especie': 'Cachorro',
        'porte': 'Médio',
        'sexo': 'Macho',
        'idade': '2 anos',
        'status_saude': 'Saudável',
        'observacoes': 'Dócil',
        'status_castracao': 'Sim',
        'status_vacinacao': 'Sim',
        'status_adocao': 'Disponível',
        'id_lar': '1'
    }
    
    res_post_cad = client.post('/cadastro', data=data_cadastro, follow_redirects=True)
    assert res_post_cad.status_code == 200

    # Busca o ID do animal cadastrado no banco para testar as próximas etapas
    conn = sqlite3.connect('database.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM animais WHERE nome = 'Bidu Teste'")
    animal_db = cursor.fetchone()
    conn.close()
    
    if animal_db:
        animal_id = animal_db[0]

        # Testar tela de Confirmação
        res_conf = client.get(f'/confirmacao/{animal_id}')
        assert res_conf.status_code == 200

        # Testar geração do Termo de Adoção
        res_termo = client.get(f'/termo/{animal_id}')
        assert res_termo.status_code == 200

        # Testar Edição (GET e POST)
        res_edit_get = client.get(f'/editar/{animal_id}')
        assert res_edit_get.status_code == 200

        data_edicao = {
            'nome': 'Bidu Atualizado',
            'especie': 'Cachorro',
            'porte': 'Médio',
            'sexo': 'Macho',
            'idade': '3 anos',
            'status_saude': 'Saudável',
            'observacoes': 'Atualizado com sucesso',
            'status_castracao': 'Sim',
            'status_vacinacao': 'Sim',
            'status_adocao': 'Adotado',
            'id_lar': '1',
            'foto_atual': ''
        }
        res_edit_post = client.post(f'/editar/{animal_id}', data=data_edicao, follow_redirects=True)
        assert res_edit_post.status_code == 200

        # Testar Exclusão
        res_exc = client.get(f'/excluir/{animal_id}', follow_redirects=True)
        assert res_exc.status_code == 200

def test_termo_animal_inexistente(client):
    """Testa animal inexistente gerando 404."""
    login_helper(client)
    res = client.get('/termo/99999')
    assert res.status_code == 404

def test_logout(client):
    """Testa o fluxo de logout."""
    login_helper(client)
    res = client.get('/logout', follow_redirects=True)
    assert res.status_code == 200