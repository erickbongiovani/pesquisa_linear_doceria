CREATE TABLE insumos (
    id_insumo INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    custo_unit REAL NOT NULL,
    qntd_estoque REAL NOT NULL
);

CREATE TABLE produtos (
    id_produto INTEGER PRIMARY KEY AUTOINCREMENT,
    nome_prod TEXT NOT NULL,
    preco_venda REAL NOT NULL,
    demanda_max INTEGER NOT NULL,
    peso_unitario REAL NOT NULL,
);

CREATE TABLE receita (
    id_receita INTEGER PRIMARY KEY AUTOINCREMENT,
    produto_id INTEGER,
    insumo_id INTEGER,
    qntd_insumo REAL NOT NULL,
    FOREIGN KEY (produto_id) REFERENCES produtos(id_produto),
    FOREIGN KEY (insumo_id) REFERENCES insumos(id_insumo)
);

ALTER TABLE produtos ADD custo_prod REAL;
ALTER TABLE produtos ADD COLUMN tempo_processamento REAL DEFAULT 0.2;
ALTER TABLE produtos DROP COLUMN custo_prod;
ALTER TABLE produtos ADD COLUMN demanda_min INTEGER DEFAULT 0;
INSERT into produtos (id_produto, nome_prod, preco_venda, demanda_max, peso_unitario, tempo_processamento, demanda_min) VALUES (7, 'Bala Fini', 8.0, 30000, 0.3, 0.5, 15000);
