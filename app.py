import os

from sqlalchemy import create_engine, text
from flask import Flask, render_template, request, redirect, flash
from flask_session import Session
from tempfile import mkdtemp
from helpers import brl
from pulp import *

 
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
app = Flask(
    __name__,
    template_folder=os.path.join(BASE_DIR, 'templates'),
    static_folder=os.path.join(BASE_DIR, 'static'))

app.config['TEMPLATES_AUTO_RELOAD'] = True

app.jinja_env.filters['brl'] = brl

@app.after_request
def after_request(response):
    #Ensure responses aren't cached
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Expires'] = 0
    response.headers['Pragma'] = 'no-cache'
    return response

app.config['SESSION_FILE_DIR'] = mkdtemp()
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_TYPE'] = 'filesystem'
Session(app)

engine = create_engine('sqlite:///database.db')

def db_execute(query, **params):
    """Executa uma query SQL e retorna lista de dicts."""
    with engine.connect() as conn:
        result = conn.execute(text(query), params)
        if result.returns_rows:
            return [dict(row) for row in result.mappings()]
        conn.commit()
        return []

@app.route('/')
def index():
    return redirect('/otimizar')

@app.route('/insumos', methods=['GET', 'POST'])
def listar_insumos():
    if request.method == 'POST':
        nome = request.form.get('nome')
        custo = request.form.get('custo_unit')
        estoque = request.form.get('qntd_estoque')

        db_execute(
            'INSERT INTO insumos (nome, custo_unit, qntd_estoque) VALUES (:nome, :custo, :estoque)', nome=nome, custo=float(custo), estoque=float(estoque)
                   )
        return redirect('/insumos')
    lista_insumos = db_execute('SELECT * FROM insumos ORDER BY nome')
    return render_template('insumos.html', insumos=lista_insumos)

@app.route('/produtos', methods=['GET', 'POST'])
def listar_produtos():
    if request.method == 'POST':
        nome = request.form.get('nome_prod')
        preco = request.form.get('preco_venda')
        demanda = request.form.get('demanda_max')
        peso = request.form.get('peso_unit')
        db_execute(
            'INSERT INTO PRODUTOS (nome_prod, preco_venda, demanda_max, peso_unitario) VALUES (:nome, :preco, :demanda, :peso)', nome=nome, preco=float(preco), demanda=float(demanda), peso=float(peso)
        )
        return redirect('/produtos')
    lista_produtos = db_execute('SELECT * FROM produtos ORDER BY nome_prod')
    return render_template('produtos.html', produtos=lista_produtos)

@app.route('/receitas', methods=['GET', 'POST'])
def listar_receitas():
    if request.method == 'POST':
        produto = request.form.get('produto_id')
        insumo = request.form.get('insumo_id')
        qntd = request.form.get('qntd_insumo')
        if not produto or not insumo or not qntd:
            return 'Erro: Preencha todos os campos', 400
        db_execute('INSERT INTO receita (produto_id, insumo_id, qntd_insumo) VALUES (:produto, :insumo, :qntd)', produto=produto, insumo=insumo, qntd=float(qntd))
        return redirect('/receitas')

    produtos = db_execute('SELECT id_produto, nome_prod FROM produtos')
    insumos = db_execute('SELECT id_insumo, nome FROM insumos')
    receitas = db_execute('SELECT produtos.nome_prod AS nome_produto, insumos.nome AS nome_insumo, receita.qntd_insumo AS qntd_insumo, receita.id_receita AS id_receita FROM receita INNER JOIN produtos ON produtos.id_produto = receita.produto_id INNER JOIN insumos ON insumos.id_insumo = receita.insumo_id')
    return render_template('receitas.html', produtos=produtos, insumos=insumos, receitas=receitas)

@app.route('/otimizar', methods=['GET', 'POST'])
def otimizar():
    if request.method == 'POST':
        # Essa query calcula a margem e traz as restrições de cada produto
        query_pulp = """
                     SELECT p.id_produto, \
                            p.nome_prod, \
                            p.preco_venda, \
                            p.demanda_max, \
                            p.tempo_processamento, \
                            p.demanda_min, \
                            SUM(r.qntd_insumo * i.custo_unit) AS custo_total, \
                            (p.preco_venda - SUM(r.qntd_insumo * i.custo_unit)) AS margem_lucro
                     FROM produtos p
                            JOIN receita r ON p.id_produto = r.produto_id
                            JOIN insumos i ON r.insumo_id = i.id_insumo
                     GROUP BY p.id_produto \
                     """
        dados_produtos = db_execute(query_pulp)
        dados_estoque = db_execute('SELECT * FROM insumos')
        problema = pulp.LpProblem('Otimizar_Mix', LpMaximize)
        lista_ids = [item['id_produto'] for item in dados_produtos]
        tempo_disponivel = 14400 * 3 * 0.8
        minhas_variaveis = pulp.LpVariable.dicts('Prefixo_Variavel', indices=lista_ids, lowBound=0, cat='Integer')
        # 3. Adiciona a Função Objetivo ao problema
        problema += pulp.lpSum([
            produto['margem_lucro'] * minhas_variaveis[produto['id_produto']]
            for produto in dados_produtos
        ]), "Lucro_Total_Projetado"

        problema += (pulp.lpSum([(linha['tempo_processamento']) * minhas_variaveis[linha['id_produto']]
                                 for linha in dados_produtos]) <= tempo_disponivel), 'Restrição de tempo'
        for linha in dados_produtos:
            id_produto = linha['id_produto']
            problema += ((minhas_variaveis[id_produto]) <= linha['demanda_max']), f'DemMax_{id_produto}'
            problema += ((minhas_variaveis[id_produto]) >= linha['demanda_min']), f'DemMin_{id_produto}'

        for linha in dados_estoque:
            id_insumo = linha['id_insumo']
            estoque_disponivel = linha['qntd_estoque']
            uso_receita = db_execute('SELECT produto_id, qntd_insumo FROM receita WHERE insumo_id = :id', id = id_insumo)
            if uso_receita:
                problema += (pulp.lpSum([
                    minhas_variaveis[receita['produto_id']] * receita['qntd_insumo']
                    for receita in uso_receita]) <= estoque_disponivel), f'QntdEstoque_{id_insumo}'
        problema.solve()
        status = LpStatus[problema.status]
        if status == 'Infeasible':
            gargalos = []
            # Essa query calcula o consumo minimo de cada insumo baseado na demanda minima de cada produto
            consumo_minimo = db_execute('SELECT id_insumo, SUM(produtos.demanda_min * receita.qntd_insumo) AS consumo_min_insumo FROM produtos INNER JOIN receita ON produtos.id_produto = receita.produto_id INNER JOIN insumos ON insumos.id_insumo = receita.insumo_id GROUP BY id_insumo')
            for linha in consumo_minimo:
                id_insumo = linha['id_insumo']
                consumo_min = linha['consumo_min_insumo']
                qntd_estoque = db_execute('SELECT nome, qntd_estoque FROM insumos WHERE id_insumo = :id', id=id_insumo)
                deficit = consumo_min - qntd_estoque[0]['qntd_estoque']
                if consumo_min > qntd_estoque[0]['qntd_estoque']:
                    gargalos.append({
                        'nome': qntd_estoque[0]['nome'],
                        'consumo_min': consumo_min,
                        'estoque': qntd_estoque[0]['qntd_estoque'],
                        'deficit': deficit
                    })
            tempo_minimo = db_execute('SELECT id_produto, SUM(produtos.demanda_min * produtos.tempo_processamento) AS tempo_minimo FROM produtos')
            for linha in tempo_minimo:
                tempo_min = linha['tempo_minimo']
                tempo_disponivel = 14400 * 3 * 0.8
                deficit_tempo = tempo_min - tempo_disponivel
                if deficit_tempo > 0:
                    gargalos.append({
                        'nome': 'Tempo de produção',
                        'consumo_min': tempo_min,
                        'estoque': tempo_disponivel,
                        'deficit': deficit_tempo
                    })
            return render_template('otimizar.html', gargalos=gargalos, status=status)

        plano_prod = []
        lucro_total_estimado = 0
        for dados in dados_produtos:
            id_produto = dados['id_produto']
            qntd_otima = minhas_variaveis[id_produto].varValue or 0
            nome_prod = dados['nome_prod']
            if qntd_otima > 0:
                lucro_item = dados['margem_lucro'] * qntd_otima
                lucro_total_estimado += lucro_item
                plano_prod.append([nome_prod, qntd_otima])
        return render_template('otimizar.html', plano_prod=plano_prod, status=status, lucro_total_estimado=lucro_total_estimado)
    return render_template('otimizar.html')


if __name__ == '__main__':
    app.run(debug=True)
