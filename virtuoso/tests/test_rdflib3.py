from __future__ import print_function
from builtins import range
from rdflib.graph import ConjunctiveGraph, Graph, Namespace
from rdflib.store import Store
from rdflib.plugin import get as plugin
from rdflib.namespace import RDF, RDFS, XSD, Namespace
from rdflib.term import URIRef, Literal, BNode, Variable
from datetime import datetime
from virtuoso.vstore import Virtuoso
from virtuoso.vsparql import Result
import os
import unittest

from math import sqrt

from nose.plugins.skip import SkipTest
from . import rdflib_connection

class Test00Plugin(unittest.TestCase):
    def test_get_plugin(self):
        V = plugin("Virtuoso", Store)
        assert V is Virtuoso

ex_subject = URIRef("http://example.org/")

test_statements = [
    (ex_subject, RDF["type"], RDFS["Resource"]),
    (BNode(), RDF["type"], RDFS["Resource"]),
    (ex_subject, RDF["type"], BNode()),
    (ex_subject, RDFS["label"], Literal("hello world")),
    (ex_subject, RDFS["comment"],
     Literal("Here we have a long comment to purposely overflow the inline RDF_QUAD limit. "
             "We keep talking and talking, but what are we saying? Precisely nothing the "
             "whole idea is to have a bunch of characters here. Blah blah, yadda yadda, "
             "etc. This is probably enough. Hopefully. One more sentence to make certain.")),
    (ex_subject, RDFS["label"], Literal(3)),
    (ex_subject, RDFS["label"], Literal(3.14, datatype=XSD.decimal)),
    (ex_subject, RDFS["label"], Literal(0.5, datatype=XSD.float)),
    (ex_subject, RDFS["label"], Literal(0.25, datatype=XSD.double)),
    #commented out the following line, as it seems to be broken
    #(ex_subject, RDFS["comment"], Literal(datetime.now())),
    (ex_subject, RDFS["comment"], Literal(datetime.now().date())),
    #commented out the following line, as it seems to be broken
    #(ex_subject, RDFS["comment"], Literal(datetime.now().time())),
    (ex_subject, RDFS["comment"], Literal("1970", datatype=XSD["gYear"])),
    (ex_subject, RDFS["label"], Literal("hello world", lang="en")),
    ]

## special test that will induce a namespace creation for testing of serialisation
ns_test = (URIRef("http://bnb.bibliographica.org/entry/GB8102507"), RDFS["label"], Literal("foo"))
test_statements.append(ns_test)

class Test00Open(unittest.TestCase):

    def test_open(self):
        store = Virtuoso(rdflib_connection)
        graph = Graph(store)
        result = graph.query("ASK { ?s ?p ?o }")
        assert not result

class Test01Store(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.store = Virtuoso(rdflib_connection)
        cls.identifier = URIRef("http://example2.org/")
        cls.graph = Graph(cls.store, identifier=cls.identifier)
        cls.graph.remove((None, None, None))

    @classmethod
    def tearDown(cls):
        cls.graph.remove((None, None, None))
        cls.store.close()

    def test_01_query(self):
        g = ConjunctiveGraph(self.store)
        count = 0
        for statement in g.triples((None, None, None)):
            count += 1
            break
        assert count == 1, "Should have found at least one triple"

    def test_02_contexts(self):
        g = ConjunctiveGraph(self.store)
        for c in g.contexts():
            assert isinstance(c, Graph)
            break

    def test_03_construct(self):
        self.graph.add(test_statements[0])
        q = "CONSTRUCT { ?s ?p ?o } WHERE { GRAPH %s { ?s ?p ?o } }" % (self.graph.identifier.n3(),)
        result = self.store.query(q)
        assert isinstance(result.graph, Graph)
        assert test_statements[0] in result
        self.graph.remove(test_statements[0])

    def test_04_ask(self):
        arg = (self.graph.identifier.n3(),)
        assert not self.graph.query("ASK FROM %s WHERE { ?s ?p ?o }" % arg)
        self.graph.add(test_statements[0])
        assert self.graph.query("ASK FROM %s WHERE { ?s ?p ?o }" % arg)
        self.graph.remove(test_statements[0])
        assert not self.graph.query("ASK FROM %s WHERE { ?s ?p ?o }" % arg)

    def test_05_select(self):
        for statement in test_statements:
            self.graph.add(statement)
        q = "SELECT DISTINCT ?s FROM %(g)s WHERE { ?s %(t)s ?o }" % {
            "t": RDF["type"].n3(), "g": self.graph.identifier.n3()}
        results = list(self.graph.query(q))
        assert len(results) == 2, results
        assert results[0][0] == ex_subject
        assert results[0]['s'] == ex_subject
        assert results[0].s == ex_subject
        self.graph.remove((None, None, None))

    def test_06_construct(self):
        for statement in test_statements:
            self.graph.add(statement)
        q = "CONSTRUCT { ?s %(t)s ?o } FROM %(g)s WHERE { ?s %(t)s ?o }" % {
            "t": RDF["type"].n3(), "g": self.graph.identifier.n3()}
        result = self.graph.query(q)
        assert isinstance(result.graph, Graph)
        assert len(result) == 3
        self.graph.remove((None, None, None))

    def test_07_select(self):
        for statement in test_statements:
            self.graph.add(statement)
        q = "SELECT ?s ?p ?o WHERE { ?s ?p ?o }"
        results = list(self.graph.query(q))
        assert set(results) == set(test_statements)

    def test_08_serialize(self):
        self.graph.add(ns_test)
        self.graph.serialize(format="n3")

    def test_09_multiple_results(self):
        # This fails on virtuoso 7. 
        # https://github.com/maparent/virtuoso-python/issues/2
        # https://github.com/openlink/virtuoso-opensource/issues/127
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.A, RDFS.subClassOf, TST.B))
        self.graph.add((TST.B, RDFS.subClassOf, TST.C))
        self.graph.add((TST.C, RDFS.subClassOf, TST.D))
        self.graph.add((TST.D, RDFS.subClassOf, TST.TOP))
        result = self.graph.query("""SELECT DISTINCT ?class
            WHERE {
                ?class rdfs:subClassOf+ %s .
                %s rdfs:subClassOf+ ?class .
            }""" % (TST.TOP.n3(), TST.A.n3()))
        result = list(result)
        print(result)
        if not len(result):
            # This should be a xFail, but nosetests does not offer this.
            raise SkipTest

    def test_10_oount(self):
        statements = [s for s in test_statements if s[0]== ex_subject]
        for statement in statements:
            self.graph.add(statement)
        result = self.graph.query("""SELECT COUNT(?o) 
            WHERE {<http://example.org/> ?p ?o}""")
        result = next(iter(result))[0]
        assert int(result) == len(statements)

    def test_11_base(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query("""BASE <http://example.com/ns/>
            SELECT * { ?s <b> ?o }""")
        assert result.type == "SELECT", result.type
        assert len(result) == 1

    def test_11_empty_prefix(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query("""PREFIX : <http://example.com/ns/>
            SELECT * { ?s :b ?o }""")
        assert result.type == "SELECT", result.type
        assert len(result) == 1

    def test_12_ask(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query("ASK { ?s ?p ?o }")
        assert result.type == "ASK", result.type
        assert result

    def test_13_initNs(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query(
            "SELECT * { ?s tst:b ?o }",
            initNs = { "tst": "http://example.com/ns/" },
        )

    def test_14_initBindings(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query(
            "SELECT * { ?s ?p ?o }",
            initBindings = {
                "p": TST.b,
                Variable("o"): TST.c,
            },
        )
        assert result.type == "SELECT", result.type
        assert len(result) == 1

    def test_15_prepared_qyery(self):
        from rdflib.plugins.sparql.processor import prepareQuery
        pquery = prepareQuery("SELECT * { ?s <b> tst:c }",
                              { "tst": "http://example.com/ns/" },
                              "http://example.com/ns/")

        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query(pquery)
        assert result.type == "SELECT", result.type
        assert len(result) == 1

    def test_16_triple_pattern(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        for s, p, o in self.graph.triples((None, TST.b, None)):
            assert s == TST.a, repr(s)
            assert p == TST.b, repr(p)
            assert o == TST.c, repr(o)

    def test_17_query_nase(self):
        TST=Namespace('http://example.com/ns/')
        self.graph.add((TST.a, TST.b, TST.c))
        self.graph.add((TST.d, TST.e, TST.f))
        result = self.graph.query("SELECT * { ?s <b> ?o }",
                                  base=TST[""])
        assert result.type == "SELECT", result.type
        assert len(result) == 1

    def test_18_construct_bnode(self):
        result = self.graph.query("CONSTRUCT { [] rdf:value 42 } {}")
        assert type(list(result.graph)[0][0]) is BNode

    def test_19_addN_1_graph(self):
        quads = ( (s, p, o, self.graph) for s,p,o in test_statements )
        self.store.addN(quads)
        assert len(self.graph) == len(test_statements), len(self.graph)

    def test_20_rollback(self):
        quads = ( (s, p, o, self.graph) for s,p,o in test_statements )
        self.store.transaction()
        self.store.addN(quads)
        assert len(self.graph) == len(test_statements), len(self.graph)
        self.store.rollback()
        assert len(self.graph) == 0

    def test_21_commit(self):
        quads = ( (s, p, o, self.graph) for s,p,o in test_statements )
        self.store.transaction()
        self.store.addN(quads)
        assert len(self.graph) == len(test_statements), len(self.graph)
        self.store.commit()
        assert len(self.graph) == len(test_statements), len(self.graph)

    def test_22_intertwined_queries(self):
        ex = Namespace('http://example.org/')
        for i in range(10):
            self.graph.add((ex.root, ex.p, ex['r%s'%i]))
            self.graph.add((ex['r%s'%i], ex.value, Literal(i)))

        bag = set()
        q1 = 'PREFIX ex: <http://example.org/>\n SELECT * { ex:root ex:p ?x }'
        q2 = 'PREFIX ex: <http://example.org/>\n SELECT * { ?x ex:value ?y }'
        for tpl1 in self.store.query(q1):
            x = tpl1[0]
            for tpl2 in self.store.query(q2, initBindings={'x': x}):
                bag.add(int(tpl2[1]))
        assert len(bag) == 10, len(bag)
        assert bag == set(range(10)), bag

    def test_23_interwined_queries_in_transaction(self):
        self.store.transaction()
        try:
            self.test_22_intertwined_queries()
        finally:
            self.store.rollback()

    def test_24_result_bindings(self):
        b = list(self.graph.query('SELECT (1 as ?x) {}'))
        assert b[0][0] == Literal(1)
        assert b[0]['x'] == Literal(1)
        assert b[0][Variable('x')] == Literal(1)
        b = self.graph.query('SELECT (1 as ?x) {}').bindings
        assert b[0][Variable('x')] == Literal(1)
        assert b[0]['x'] == Literal(1)

    def test_25_first_cell_empty(self):
        b = list(self.graph.query('''select ?x ?y { 
             values (?x ?y) {(1 undef) (undef 2) (3 undef)}}'''))
        assert len(b) == 3, len(b)
        assert b[0]['x'] == Literal(1)
        assert b[0]['y'] == None
        assert b[1]['x'] == None
        assert b[1]['y'] == Literal(2)
        assert b[2]['x'] == Literal(3)
        assert b[2]['y'] == None

    def test_26_decimal(self):
        for lexval in [ "3.14", "1234.56789", ".5" ]:
            b = list(self.graph.query('''select (%s as ?x) {}''' % lexval))
            assert len(b) == 1, len(b)
            assert b[0]['x'] == Literal(lexval, datatype=XSD.decimal), b[0]['x']

    def test_27_float(self):
        # this one produces a binary encoded float
        b = list(self.graph.query('''select ("0.5"^^xsd:float as ?x) {}''',
                                  initNs={'xsd': XSD }))
        assert len(b) == 1, len(b)
        assert b[0]['x'] == Literal(0.5, datatype=XSD.float), repr(b[0]['x'])
        assert b[0]['x'].datatype == XSD.float

    def test_27_float_bis(self):
        # this one produces a string encoded float
        lit = Literal(0.5, datatype=XSD.float)
        self.graph.add((ex_subject, RDFS.label, lit))
        b = list(self.graph.query('''select ?x { [ rdfs:label ?x ] }'''))
        assert len(b) == 1, len(b)
        assert b[0]['x'] == lit, repr(b[0]['x'])
        assert b[0]['x'].datatype == XSD.float

    def test_28_double(self):
        # this one produces a binary encoded float
        b = list(self.graph.query('''select (314e-2 as ?x) {}''',
                                  initNs={'xsd': XSD }))
        assert len(b) == 1, len(b)
        assert b[0]['x'] == Literal(3.14, datatype=XSD.double), b[0]['x']
        assert b[0]['x'].datatype == XSD.double

    def test_28_double_bis(self):
        # this one produces a string encoded double
        lit = Literal(0.5, datatype=XSD.double)
        self.graph.add((ex_subject, RDFS.label, lit))
        b = list(self.graph.query('''select ?x { [ rdfs:label ?x ] }'''))
        assert len(b) == 1, len(b)
        assert b[0]['x'] == lit, repr(b[0]['x'])
        assert b[0]['x'].datatype == XSD.double

    def test_29_int(self):
        b = list(self.graph.query('''select (42 as ?x) {}'''))
        assert len(b) == 1, len(b)
        assert b[0]['x'] == Literal(42), b[0]['x']

    def test_30_addN_many(self):
        how_many = 5000
        many_quads = ( (RDFS.label, RDFS.label, Literal(i), self.graph)
                         for i in range(how_many) )
        self.graph.addN(many_quads)
        assert len(self.graph) == how_many

    def test_99_deadlock(self):
        os.environ["VSTORE_DEBUG"] = "TRUE"
        dirname = os.path.dirname(__file__)
        fixture = os.path.join(dirname, "fixture1.rdf")
        self.graph.parse(fixture)
        for statement in self.graph.triples((None, None, None)):
            pass
        self.graph.remove((None, None, None))

    def add_remove(self, statement):
        # add and check presence
        self.graph.add(statement)
        self.store.commit()

        assert statement in self.graph, "%s not found" % (statement,)

        # check that we really got back what we asked for
        for x in self.graph.triples(statement):
            assert statement == x, "Round-trip mismatch:\n\t%s\n\t%s" % (statement, x)

        # delete and check absence
        self.graph.remove(statement)
        self.store.commit()

        assert statement not in self.graph, "%s found" % (statement,)

class Test02Contexts(unittest.TestCase):
    @classmethod
    def setUp(cls):
        cls.store = Virtuoso(rdflib_connection)
        cls.id1 = URIRef("http://example2.org/g1")
        cls.g1 = Graph(cls.store, identifier=cls.id1)
        cls.g1.remove((None, None, None))
        cls.id2 = URIRef("http://example2.org/g2")
        cls.g2 = Graph(cls.store, identifier=cls.id2)
        cls.g2.remove((None, None, None))

        cls.tst = TST = Namespace('http://example.com/ns/')
        cls.g1.add((TST.g0, RDF.type, TST.Graph))
        cls.g1.add((TST.g1, RDF.type, TST.Graph))
        cls.g2.add((TST.g0, RDF.type, TST.Graph))
        cls.g2.add((TST.g2, RDF.type, TST.Graph))


    @classmethod
    def tearDown(cls):
        cls.g1.remove((None, None, None))
        cls.g2.remove((None, None, None))
        cls.store.close()

    def test_union(self):
        TST = self.tst

        res0 = list(self.store.triples((TST.g0, None, None), None))
        assert len(res0) >= 1, len(res0)
        assert [ g.identifier for g in res0[0][1] ][0] in { self.id1, self.id2 }

        res1 = list(self.store.triples((TST.g1, None, None), None))
        assert len(res1) == 1, len(res1)
        assert [ g.identifier for g in res1[0][1] ] == [self.id1]

        res2 = list(self.store.triples((TST.g2, None, None), None))
        assert len(res2) == 1, len(res2)
        assert [ g.identifier for g in res2[0][1] ] == [self.id2]

    def test_single_context(self):
        TST = self.tst

        res0 = list(self.store.triples((TST.g0, None, None), self.g1))
        assert len(res0) == 1, len(res0)
        assert [ g.identifier for g in res0[0][1] ] == [self.id1]

        res1 = list(self.store.triples((TST.g1, None, None), self.g1))
        assert len(res1) == 1, len(res1)
        assert [ g.identifier for g in res1[0][1] ] == [self.id1]

        res2 = list(self.store.triples((TST.g2, None, None), self.g1))
        assert len(res2) == 0, len(res2)

    def test_single_graph(self):
        res = self.g1.query("SELECT DISTINCT ?g { GRAPH ?g { ?s ?p ?o } }")
        res = list(res)
        assert [ t[0] for t in res ] == [ self.g1.identifier ], res

    def test_single_triple(self):
        TST = self.tst

        res0 = list(self.store.triples((TST.g0, RDF.type, TST.Graph), self.g1))
        assert len(res0) == 1, len(res0)
        assert [ g.identifier for g in res0[0][1] ] == [self.id1]


# make separate tests for each of the test statements so that we don't
# get flooded with unreadable and irrelevant log messages if one fails
def _mk_add_remove(name, s):
    def _f(self):
        self.add_remove(s)
    _f.__name__ = name
    return _f
for i in range(len(test_statements)):
    attr = "test_%02d_add_remove" % (i + 80)
    setattr(Test01Store, attr, _mk_add_remove(attr, test_statements[i]))

if __name__ == '__main__':
    suite = unittest.TestLoader().loadTestsFromTestCase(Test00Plugin)
    unittest.TextTestRunner(verbosity=2).run(suite)

    suite = unittest.TestLoader().loadTestsFromTestCase(Test01Store)
    unittest.TextTestRunner(verbosity=2).run(suite)
