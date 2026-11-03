"""Mini-Projeto 03: Biblioteca escolar.
Gabriel Rafá Martins Freire — matrícula 20230145310.
Execute: python consultas.py
Dados fictícios. Os updates alteram somente uma cópia em memória.
"""
from pathlib import Path
from datetime import date
from rdflib import Graph, Namespace, RDF, RDFS, OWL, XSD, Literal, URIRef
from owlrl import DeductiveClosure, OWLRL_Semantics

EX = Namespace('https://example.org/biblioteca#')
BASE = Path(__file__).resolve().with_name('biblioteca.ttl')
PREFIXOS = '''PREFIX ex: <https://example.org/biblioteca#>
PREFIX rdf: <http://www.w3.org/1999/02/22-rdf-syntax-ns#>
PREFIX rdfs: <http://www.w3.org/2000/01/rdf-schema#>
PREFIX xsd: <http://www.w3.org/2001/XMLSchema#>
'''


def carregar(caminho=BASE):
    """Carrega a base original. RDFLib sozinho não executa raciocínio OWL."""
    return Graph().parse(caminho, format='turtle')


def copiar(g):
    novo = Graph()
    for prefixo, uri in g.namespaces():
        novo.bind(prefixo, uri)
    for tripla in g:
        novo.add(tripla)
    return novo


def curto(g, termo):
    if isinstance(termo, Literal):
        return termo.n3(g.namespace_manager)
    return g.namespace_manager.normalizeUri(termo)


def mostrar_triplas(g, triplas):
    linhas = sorted(tuple(curto(g, t) for t in tripla) for tripla in triplas)
    for linha in linhas:
        print(' | '.join(linha))
    print(f'Total: {len(linhas)} triplas')
    return linhas


def validar_base(g):
    """Verificações do conjunto de dados; não são restrições impostas por OWL."""
    classes = set(g.subjects(RDF.type, OWL.Class))
    objetos = set(g.subjects(RDF.type, OWL.ObjectProperty))
    dados = set(g.subjects(RDF.type, OWL.DatatypeProperty))
    individuos = set(g.subjects(RDF.type, OWL.NamedIndividual))
    assert len(classes) == 14 and len(objetos) == 10 and len(dados) == 9
    assert len(individuos) == 33 and len(g) >= 50
    assert (EX.Livro, RDFS.subClassOf, EX.ItemAcervo) in g
    assert (EX.ItemAcervo, RDFS.subClassOf, EX.Entidade) in g
    for prop in objetos | dados:
        assert len(list(g.objects(prop, RDFS.domain))) == 1
        assert len(list(g.objects(prop, RDFS.range))) == 1
    for pessoa in g.subjects(RDF.type, EX.Aluno):
        assert (pessoa, EX.matricula, None) in g
    codigos = list(g.objects(None, EX.codigoInventario))
    assert len(codigos) == len(set(codigos)) == 10
    for livro in g.subjects(EX.titulo, None):
        assert len(list(g.objects(livro, EX.codigoInventario))) == 1
        assert int(g.value(livro, EX.paginas)) > 0
    emprestados = []
    for emp in g.subjects(RDF.type, EX.Emprestimo):
        assert len(list(g.objects(emp, EX.itemEmprestado))) == 1
        assert g.value(emp, EX.dataEmprestimo).toPython() <= g.value(emp, EX.dataPrevista).toPython()
        if g.value(emp, EX.ativo).toPython():
            emprestados.append(g.value(emp, EX.itemEmprestado))
    assert len(emprestados) == len(set(emprestados))
    for pred in [EX.nome, EX.titulo, EX.codigoInventario, EX.matricula]:
        assert all(v.datatype == XSD.string for v in g.objects(None, pred))
    print(f'BASE: {len(classes)} classes; {len(objetos)} propriedades de objeto; '
          f'{len(dados)} de dados; {len(individuos)} indivíduos; {len(g)} triplas.')
    return dict(classes=len(classes), propriedades_objeto=len(objetos),
                propriedades_dados=len(dados), individuos=len(individuos), triplas=len(g))


def parte1(g):
    """Seis consultas por padrões. None é um curinga, não um valor do grafo."""
    # T1: sujeito fixo. Esperado: as 8 triplas declaradas do livro01.
    # T2: predicado fixo. Esperado: 10 relações livro -> autor.
    # T3: objeto fixo. Esperado: emprestimo01 -> emprestadoPara -> ana (1).
    # T4: predicado e objeto fixos. Esperado: os 6 alunos declarados.
    # T5: sujeito e predicado fixos. Esperado: autor1, autor do livro01 (1).
    # T6: predicado e objeto fixos. Esperado: livro08, livro09, livro10 (3).
    consultas = [
        ('T1', 'Dados do livro01 (sujeito fixo)', (EX.livro01, None, None), 8),
        ('T2', 'Relações de autoria (predicado fixo)', (None, EX.escritoPor, None), 10),
        ('T3', 'Quem se relaciona com Ana? (objeto fixo)', (None, None, EX.ana), 1),
        ('T4', 'Alunos declarados', (None, RDF.type, EX.Aluno), 6),
        ('T5', 'Autor do livro01', (EX.livro01, EX.escritoPor, None), 1),
        ('T6', 'Livros da estante infantil', (None, EX.guardadoEm, EX.estanteInfantil), 3),
    ]
    for numero, proposito, padrao, esperado in consultas:
        print(f'\n[{numero}] {proposito}. Esperado: {esperado} triplas.')
        resultados = list(g.triples(padrao))  # Consulta obrigatória com g.triples().
        assert len(resultados) == esperado, numero
        mostrar_triplas(g, resultados)


# Oito consultas SPARQL de leitura. Executadas na base explícita, sem inferência.
LEITURAS = [
    ('S1', 'Catálogo com autores, ordenado por título', '''
SELECT DISTINCT ?titulo ?autor WHERE {
  ?livro rdf:type/rdfs:subClassOf* ex:Livro ; ex:titulo ?titulo ; ex:escritoPor ?a .
  ?a ex:nome ?autor .
} ORDER BY ?titulo
''', 10),  # Esperado: 10 linhas. O caminho inclui subclasses de Livro.
    ('S2', 'Leituras curtas: até 120 páginas', '''
SELECT ?titulo ?paginas WHERE {
  ?livro ex:titulo ?titulo ; ex:paginas ?paginas .
  FILTER(?paginas <= 120)
} ORDER BY ?paginas ?titulo
''', 4),  # Esperado: 48, 64, 80 e 120 páginas.
    ('S3', 'Quantidade de exemplares por autor', '''
SELECT ?autor (COUNT(?livro) AS ?quantidade) WHERE {
  ?livro ex:escritoPor ?a . ?a ex:nome ?autor .
} GROUP BY ?autor ORDER BY DESC(?quantidade) ?autor
''', 4),  # Esperado: Clara 3, Paulo 3, Helena 2 e Miguel 2.
    ('S4', 'Ana está com o livro01 em um empréstimo ativo?', '''
ASK { ?emp a ex:Emprestimo ; ex:emprestadoPara ex:ana ;
      ex:itemEmprestado ex:livro01 ; ex:ativo true . }
''', True),  # Esperado: True, por emprestimo01.
    ('S5', 'Construir um grafo pessoa -> estaCom -> livro', '''
CONSTRUCT { ?pessoa ex:estaCom ?livro . }
WHERE { ?emp a ex:Emprestimo ; ex:emprestadoPara ?pessoa ;
        ex:itemEmprestado ?livro ; ex:ativo true . }
''', 5),  # Esperado: grafo separado com 5 triplas; não altera g.
    ('S6', 'Empréstimos vencidos na data fixa 03/11/2026', '''
SELECT ?emp ?pessoa ?titulo ?prazo WHERE {
  ?emp a ex:Emprestimo ; ex:emprestadoPara ?p ; ex:itemEmprestado ?livro ;
       ex:dataPrevista ?prazo ; ex:ativo true .
  ?p ex:nome ?pessoa . ?livro ex:titulo ?titulo .
  FILTER(?prazo < "2026-11-03"^^xsd:date)
} ORDER BY ?prazo
''', 2),  # Esperado: emprestimo04 (28/10) e emprestimo02 (30/10).
    ('S7', 'Livros cuja estante habitual fica na biblioteca central', '''
SELECT ?titulo WHERE {
  ?livro ex:titulo ?titulo ; ex:guardadoEm/ex:pertenceBiblioteca ex:central .
} ORDER BY ?titulo
''', 8),  # Esperado: todos exceto livro04 e livro07. Caminho explícito, sem OWL.
    ('S8', 'Exemplares sem empréstimo ativo registrado', '''
SELECT ?livro ?titulo WHERE {
  ?livro ex:titulo ?titulo .
  FILTER NOT EXISTS { ?emp ex:itemEmprestado ?livro ; ex:ativo true . }
} ORDER BY ?livro
''', 5),  # Esperado: livro02, 04, 06, 09, 10. Ausência no cadastro, não verdade OWL.
]


def parte2(g):
    for numero, proposito, consulta, esperado in LEITURAS:
        print(f'\n[{numero}] {proposito}')
        resultado = g.query(PREFIXOS + consulta)
        if resultado.type == 'ASK':
            print('Resposta:', bool(resultado.askAnswer))
            assert bool(resultado.askAnswer) == esperado
        elif resultado.type == 'CONSTRUCT':
            mostrar_triplas(resultado.graph, resultado.graph)
            assert len(resultado.graph) == esperado
            assert not list(g.triples((None, EX.estaCom, None)))
        else:
            linhas = list(resultado)
            print(' | '.join(str(v) for v in resultado.vars))
            for linha in linhas:
                print(' | '.join(curto(g, valor) for valor in linha))
            print('Total:', len(linhas), 'linhas')
            assert len(linhas) == esperado, numero
            if numero == 'S2':
                assert [int(linha.paginas) for linha in linhas] == [48, 64, 80, 120]
            if numero == 'S3':
                assert sorted(int(linha.quantidade) for linha in linhas) == [2, 2, 3, 3]
            if numero == 'S6':
                assert [linha.emp for linha in linhas] == [EX.emprestimo04, EX.emprestimo02]
            if numero == 'S8':
                assert {linha.livro for linha in linhas} == {EX.livro02,EX.livro04,EX.livro06,EX.livro09,EX.livro10}


def demonstrar_updates(original):
    """S9–S11: todos na mesma cópia da base original, sem salvar sobre o .ttl."""
    g = copiar(original)
    antes = set(original)
    print('\n[S9] INSERT DATA: registrar empréstimo temporário do livro10 para Elisa.')
    print('ANTES: triplas do emprestimo06 =', len(list(g.triples((EX.emprestimo06, None, None)))))
    g.update(PREFIXOS + '''INSERT DATA {
      ex:emprestimo06 a ex:Emprestimo ; ex:emprestadoPara ex:elisa ;
          ex:itemEmprestado ex:livro10 ; ex:registradoEm ex:central ;
          ex:dataEmprestimo "2026-11-03"^^xsd:date ;
          ex:dataPrevista "2026-11-17"^^xsd:date ; ex:ativo true .
    }''')
    # Esperado: 7 novas triplas; ASK muda de falso (registro ausente) para verdadeiro.
    mostrar_triplas(g, g.triples((EX.emprestimo06, None, None)))
    existe = bool(g.query(PREFIXOS + 'ASK { ex:emprestimo06 ex:itemEmprestado ex:livro10 }').askAnswer)
    print('DEPOIS: registro existe?', existe, '| Triplas adicionadas:', len(g)-len(original))
    assert existe and len(g) == len(original)+7

    print('\n[S10] DELETE WHERE: apagar o registro temporário criado em S9.')
    print('ANTES: triplas do emprestimo06 =', len(list(g.triples((EX.emprestimo06, None, None)))))
    g.update(PREFIXOS + 'DELETE WHERE { ex:emprestimo06 ?p ?o . }')
    # Esperado: zero triplas do registro e grafo igual ao original.
    print('DEPOIS: triplas do emprestimo06 =', len(list(g.triples((EX.emprestimo06, None, None)))))
    assert set(g) == antes

    print('\n[S11] DELETE/INSERT: renovar o prazo do empréstimo de Ana.')
    print('ANTES:', g.value(EX.emprestimo01, EX.dataPrevista))
    g.update(PREFIXOS + '''
DELETE { ex:emprestimo01 ex:dataPrevista ?antiga . }
INSERT { ex:emprestimo01 ex:dataPrevista "2026-11-24"^^xsd:date . }
WHERE  { ex:emprestimo01 ex:dataPrevista ?antiga ; ex:ativo true . }
''')
    # Esperado: remover 17/11 e inserir 24/11, sem deixar dois prazos.
    print('DEPOIS:', g.value(EX.emprestimo01, EX.dataPrevista))
    assert list(g.objects(EX.emprestimo01, EX.dataPrevista)) == [Literal('2026-11-24', datatype=XSD.date)]
    assert (EX.emprestimo01, EX.dataPrevista, Literal('2026-11-17', datatype=XSD.date)) not in g
    assert set(original) == antes
    print('Base original preservada; os updates ocorreram apenas em memória.')
    return g


def demonstrar_owl(original):
    """Demonstra inferências OWL-RL numa cópia independente, sem updates."""
    inferido = copiar(original)
    exemplos = [
        ('I1: hierarquia de classes', (EX.livro01, RDF.type, EX.Livro)),
        ('I2: inverseOf', (EX.autor1, EX.autorDe, EX.livro01)),
        ('I3: subpropriedades + transitividade', (EX.livro01, EX.localizadoEm, EX.central)),
        ('I4: simetria da parceria', (EX.anexo, EX.parceiraDe, EX.central)),
    ]
    for _, tripla in exemplos:
        assert tripla not in original
    DeductiveClosure(OWLRL_Semantics).expand(inferido)
    for nome, tripla in exemplos:
        print(f'\n[{nome}] ANTES: {tripla in original} | DEPOIS: {tripla in inferido}')
        mostrar_triplas(inferido, [tripla])
        assert tripla in inferido
    # Disjunção: nenhum indivíduo desta base pode ser simultaneamente Livro e Pessoa/Local.
    for classe in [EX.Pessoa, EX.Local]:
        assert not (set(inferido.subjects(RDF.type, EX.Livro)) & set(inferido.subjects(RDF.type, classe)))
    print('\nFuncionalidade: cada registro tem um único item; cada exemplar tem um código.')
    print('Disjunção: não há Livro simultaneamente Pessoa ou Local nesta base.')
    print('OWL não é um formulário validador: domain/range inferem tipos; funcionalidade não é chave única.')
    return inferido


def main():
    g = carregar()
    validar_base(g)
    parte1(g)
    parte2(g)
    demonstrar_updates(g)
    demonstrar_owl(g)
    print('\nTODAS AS CONSULTAS E VERIFICAÇÕES FORAM CONCLUÍDAS.')


if __name__ == '__main__':
    main()
