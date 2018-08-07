#!/usr/bin/env python
# -*- coding: utf-8 -*-
# Conexion y Consulta elastisearch
import sys

from elasticsearch import Elasticsearch
from pyspark import SparkConf, SparkContext
from pyspark.sql import SQLContext, HiveContext

# Crear la configuración de spark
conf = (SparkConf()
        .setAppName("summarize")
        .set("spark.executor.memory", "1g")
        .set("spark.yarn.appMasterEnv.PYSPARK_PYTHON", "/usr/bin/python")
        .set("spark.yarn.appMasterEnv.PYSPARK_DRIVER_PYTHON", "/usr/bin/python"))

# Crear el SparkContext con la configuración anterior
sc = SparkContext(conf=conf)

# Conectores SQL para trabajar en nuestro script
sqlContext = SQLContext(sc)
hiveContext = HiveContext(sc)

if len(sys.argv) != 7:
    errorMessage = "No se han introducido todos los argumentos requeridos o se han introducido de manera incorrecta\n"
    errArg1 = " Arg 1: Cadena de conexion donde leer el documento. IP. Ej: 172.22.248.206:9229 \n"
    errArg2 = " Arg 2: Cadena de conexion donde guardar el resúmen. IP. Ej: 172.22.248.206:9229 \n"
    errArg3 = " Arg 3: Indice de donde se lee el documento \n"
    errArg4 = " Arg 4: Indice de donde se guarda el resúmen del documento \n"
    errArg5 = " Arg 5: Nombre del documento o identificador. Ej: 03_002-008_14.PDF \n"
    errArg6 = " Arg 6: Nombre del criterio de busqueda, Ej: name, uuid o uri... \n"

    raise Exception(errorMessage + errArg1 + errArg2 + errArg3 + errArg4 + errArg5 + errArg6)


def conn_query(es_search_host, index_name, doc_name, criterion_name):
    #creamos la conexion a elasticsearch con el host de consulta
    try:
        es = Elasticsearch([es_search_host])
    except 'connection error':
        print("CONNECTION ERROR")
    try:
        # revisar indice para consulta. index="aeacus_kdd". uri:aeacus:fs#9e33cbdbd42b4ec98b1e8d2080d64ed4
        # lanzamos la consulta sobre elasticsearch con el criterio y nombre del documento que viene dado por parámetro en el script
        # por defecto en las consultas de elasticsearch el size = 10, si no lo modificamos sólo nos mostrará los 10 primero registros sobre nuestra consulta
        r = es.search(index=index_name, doc_type="document",
                      body={"size": 1000, "query": {"match": {criterion_name: doc_name}}},
                      sort="page")
        # recorremos todo el contenido de la consulta para poder alamcenar el texto completo en una sola lista
        txt = []
        for doc in r['hits']['hits']:
            txt.append(doc['_source']['content'])
        return txt
    except 'Warning':
        raise Exception("la consulta no se ha realizado de manera adecuada")


# Preprocesado basado en elastic search
def remove_accents(input_str, encoding="latin1"):
    try:
        input_str = unicode(input_str.decode(encoding))
    except UnicodeEncodeError:
        pass
    import unicodedata
    nfkd_form = unicodedata.normalize('NFKD', input_str)
    only_ascii = nfkd_form.encode('ASCII', 'ignore')
    return only_ascii


def del_page_num(txt):
    import re
    aux = re.findall(r"\b(\d{1,2}/\d{1,2})\b", txt)
    pattern = re.compile(r"\b(" + "|".join(aux) + ")\\W", re.I)
    return pattern.sub("", txt)


def del_strange_charact(txt):
    # Los textos de elastic search son una maravilla...
    prev_txt = ''
    while prev_txt != txt:
        prev_txt = txt
        txt = txt.replace(',.', ',')
        txt = txt.replace(', .', ',')
    return prev_txt


# Set de funciones para preprocessing para tokenizar correctamente
def reduce_concat(x, sep=""):
    return reduce(lambda s, y: s + sep + y, x)


def out_art(text):
    # Elimina el formato 1.2 que confunde al tokenizar frases
    import re
    auxexp = re.findall('[0-9]\.[0-9]', text)
    while len(auxexp) > 0:
        for expr in auxexp:
            auxexpr = expr.replace(".", "")
            text = text.replace(expr, auxexpr)
            auxexp = re.findall('[0-9]\.[0-9]', text)
    return text


def process_text(txt, outstopwords=True, outpunkt=True):
    # Funcion que elimina los acentos, stopwords, puntuaciones y convierte a minusculas

    # Quitamos acentos
    # texto = remove_accents(texto) # considerado en otro pretratado de texto
    # txt = remove_accents(text)

    # Pasamos a minuscula
    txt = txt.lower()

    # Eliminamos symbolos
    symbols = ['[', ']', '•', '^', '*', '/', '=']
    for symbol in symbols:
        txt = txt.replace(symbol, '')

    if outpunkt:
        # except '.'
        puntuations = [',', ':', ';', '(', ')', '?', '¿', '!', '¡', "'", '"']
        for puntuacion in puntuations:
            txt = txt.replace(puntuacion, '')

    # Hacemos algunas conversiones utiles
    prev_txt = ''
    while prev_txt != txt:
        prev_txt = txt
        txt = txt.replace('  ', ' ')  # Quitamos dobles espacios
        #    txt = txt.replace('. ', '.')  # Quitamos espacios despues de puntos
        #    txt = txt.replace(' .', '.')  # Quitamos espacios antes de puntos
        txt = txt.replace('\n\n', '\n')  # Quitamos dobles parrafos
        txt = txt.replace('\n \n', '\n')  # Quitamos dobles parrafos con espacio

    # Eliminamos stopwords
    if outstopwords:
        from nltk.corpus import stopwords
        stop_words = stopwords.words('spanish')
        for i in range(len(stop_words)):
            stop_words[i] = remove_accents(stop_words[i])

        txt_wd = txt.split(" ")
        txt_wd = [word for word in txt_wd if word not in stop_words]
        if len(txt_wd) > 0:
            txt = reduce_concat(txt_wd, sep=" ")
        else:
            txt = txt_wd
    return txt


def nonum(text):
    # Elimina ciertas expresiones que distorsionan la delimitacion de parrafos
    symbols = ['art.', ' art ', 'num.', 'i.', 'ii.', 'iii.', '.-']
    for symbol in symbols:
        text = text.replace(symbol, " ")  # Erease expresion
    return text


def outwords(text):
    # Dada una lista, elimina las palabras en un texto
    # Ampliar lista?
    word_list = ['ley', 'leyes', 'fj', 'derechos', 'derecho', 'justicia', ' ce ', 'LOTJ']
    for word in word_list:
        text = text.replace(word, "")  # Erease expresion
    return text


# Consiguiendo una tokenizacion "perfecta"
def sentences(text):
    # split en frases
    import pattern.es as pa
    parsed = pa.parse(text, tokenize=True, tags=0,
                      chunks=0, relations=0, lemmata=False, encoding='utf-8', tagset=None)
    bad_list = parsed.split('\n')
    ulist = [s.replace('&slash;', '/') for s in bad_list]  # edicion por mala codifiacion
    return [x.encode('utf-8') for x in ulist]


def preprosentence(txt):
    # Preprocesamiento previo a la metrica
    return del_strange_charact(nonum(outwords(process_text(out_art(txt)))))


def get_cosine(str1, str2):
    import re
    import math
    from collections import Counter
    comp = re.compile(r'\w+')
    str1 = preprosentence(str1)
    str2 = preprosentence(str2)
    words1 = comp.findall(str1)
    words2 = comp.findall(str2)
    vec1 = Counter(words1)
    vec2 = Counter(words2)
    intersection = set(vec1.keys()) & set(vec2.keys())
    numerator = sum([vec1[x] * vec2[x] for x in intersection])

    sum1 = sum([vec1[x] ** 2 for x in vec1.keys()])
    sum2 = sum([vec2[x] ** 2 for x in vec2.keys()])
    denominator = math.sqrt(sum1) * math.sqrt(sum2)

    if not denominator:
        return 0.0
    else:
        return float(numerator) / denominator


def connect(nodes):
    return [(start, end, get_cosine(start, end))
            for start in nodes
            for end in nodes
            if start is not end]


def rank(nodes, edges):
    import networkx as nx
    # el output es un dict de unos nodes y edges
    graph = nx.DiGraph()
    graph.add_nodes_from(nodes)
    graph.add_weighted_edges_from(edges)
    return nx.pagerank(graph)


def get_phrase(nodes, frases, texto_paginas):
    # Primero, acotamos las frases segun su aparicion en el texto
    nod = []
    for node in nodes:
        if node not in nod:
            nod.append(node)

    indice_frase = []
    c = 0
    for i in nod:
        c += 1
        if c < 2:
            indice_frase.append((0, len(i), i))
        else:
            indice_frase.append((indice_frase[c - 2][1] + 1, indice_frase[c - 2][1] + len(i), i))
    # Segundo, buscamos las frases ordenadas por score en que acotacion esta segun el resultado anterior
    frases_acotadas = []
    for j in frases:
        for i in indice_frase:
            if i[2] == j:
                frases_acotadas.append(i[0:2])
    # Tercero, tenemos las paginas acotadas
    # indice de paginas

    indices = []
    c = 0
    for i in texto_paginas:
        c += 1
        if c < 2:
            indices.append((0, len(i), c))
        else:
            indices.append((indices[c - 2][1] + 1, indices[c - 2][1] + len(i), c))

    # cuarto, buscamos dentro de los rangos encontrados
    localizacion = []
    no_encontradas = []
    for ind in frases_acotadas:
        encontrada = False
        for ind_pag in indices:
            if ind[0] >= ind_pag[0] and ind[1] <= ind_pag[1] and not encontrada:
                localizacion.append(ind_pag[2])
                encontrada = True
            elif (ind[0] >= ind_pag[0] and ind[0] <= ind_pag[1]) and (ind[1] > ind_pag[1]) and not encontrada:
                localizacion.append((ind_pag[2], ind_pag[2] + 1))
                encontrada = True
        if not encontrada:
            localizacion.append(indices[-1][-1])
    return localizacion


def summarize(es_search_host, search_index, doc_name, criterion_name):
    text = ""
    try:
        text = conn_query(es_search_host, search_index, doc_name, criterion_name)
    except TypeError as e:
        print(e)
    txt_junto = ''
    for i in text:
        txt_junto += i
    txt = del_page_num(txt_junto)
    nodes = sentences(txt)
    edges = connect(nodes)
    scores = rank(nodes, edges)
    phrases = sorted(scores, key=scores.get, reverse=True)
    scroll = []

    for key in phrases:
        if key in nodes:
            try:
                scroll.append(float(nodes.index(key)) / len(nodes) * 100)
            except:
                pass

    vec_list = (phrases, get_phrase(nodes, phrases, text), sorted(scores.values(), reverse=True), scroll)
    print(vec_list)
    return vec_list

# vec_list = (phrases, get_phrase(nodes, phrases, text), sorted(scores.values(), reverse=True), scroll)
def load_data_into_es(newesconn, INDEX_NAME, TYPE_NAME, name, vec_list):
    bulk_data = []
    print("Comienza la carga de datos en ES")
    i = 1
    filename = name
	# De vec_list obtenemos cuatro listas con las frases, el resultado de la función get_phrase, los scores y el scroll
    datas=zip(vec_list[0],vec_list[1],vec_list[2],vec_list[3])
	#Vamos a preparar los datos procedentes del resultado de la ejecución del algoritmo para su subida a elasticsearch
    for data in datas:
        print("vamos a ir viendo data")
        print(data[0])
        index_id = filename + "_" + str(i)
        data_dict = {
            "file": filename,
            "phrase": unicode(data[0], "utf-8"),
            "page": data[1],
            "score": data[2],
            "scroll": data[3]
        }
        doc = {
            "index": {
                "_index": INDEX_NAME,
                "_type": TYPE_NAME,
                "_id": index_id
            }
        }
        bulk_data.append(doc)
        bulk_data.append(data_dict)
        i = i + 1

    # bulk index the data
    print("bulk indexing...")
	# Hacemos la carga masiva de datos
    newesconn.bulk(index=INDEX_NAME, body=bulk_data, refresh=True, request_timeout=60)
    print("Finalizada la carga de datos")


def load_summary_into_elastic(es_load_host, load_index, doc_name, vec_list):
    INDEX_NAME = load_index
	# Creamos la conexion a elasticsearch con el host de carga. Aquí es donde cargaremos el resultado de la ejecución del algoritmo anterior
    try:
        newesconn = Elasticsearch([es_load_host])
    except 'connection error':
        print("CONNECTION ERROR")
    TYPE_NAME = 'summary'
    # Vamos a comprobar si el índice existe en elasticsearch, de no ser así lo creamos en la sentencia "else"
    if newesconn.indices.exists(INDEX_NAME):
        pass
    else:
        # Configuracion de particion de indices y replicacion
        request_body = {
            "settings": {
                "number_of_shards": 1,
                "number_of_replicas": 0
            }
        }

        # OJO, sólo si no existe o se ha borrado
        print('')
        print("Creando el indice '%s'..." % INDEX_NAME)
        response_create_index = newesconn.indices.create(index=INDEX_NAME, body=request_body)
        print("response: '%s'" % response_create_index)
        print('')

    try:
        # Habrá que buscar los _id asociados al nombre del documento y borrar todos si existen
        # antes de cargar de nuevo los datos en ES
	    # Con la siguiente consulta buscamos todos los registros que cumplan que el campo "file" coincide con 
	    # la variable doc_name, que viene dada como parámetro a la función
        scroll = newesconn.search(index=INDEX_NAME, doc_type=TYPE_NAME,
                                  body={"size": 1000, "query": {"match": {"file": doc_name}}})
        bulk = ""
	    # En hits_number almacenamos el número de registros de la anterior consulta
        hits_number = scroll['hits'][u'total']
	    # Si el número de registros es distinto de cero creamos el bulk para el borrado de datos masivo
        if hits_number != 0:
            for result in scroll['hits']['hits']:
                bulk = bulk + '{ "delete" : { "_index" : "' + str(result['_index']) + '", "_type" : "' + str(
                    result['_type']) + '", "_id" : "' + str(result['_id']) + '" } }\n'
            newesconn.bulk(body=bulk)
    except:
        print("No hay datos para borrar asociados al documento")
	# Ejecutamos la función load_data_into_es que cargará el resumen en elasticsearch
	# Para no crear dos veces el conector, se lo pasaremos por parámetro
    load_data_into_es(newesconn, INDEX_NAME, TYPE_NAME, doc_name, vec_list)
    

def response_summarize(es_search_host, search_index, es_load_host, load_index, doc_name, criterion_name):
    summaries = summarize(es_search_host, search_index, doc_name, criterion_name)
    print(summaries)
    load_summary_into_elastic(es_load_host, load_index, doc_name, summaries)
    print("Finalizado el proceso de generación de resúmen")


# if __name__ == "__main__":
# res(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])

def load_execution_result_into_elastic(es__host2, INDEX_NAME, script_name, arguments, resultado_ejecucion):
    import time
    import datetime
    try:
        es = Elasticsearch([es__host2])
    except 'connection error':
        print("CONNECTION ERROR")
    ts = time.time()
	# Vamos a tomar el datetime para tener guardado el momento de la ejecución
	# Además lo añadiremos al id, ya que este ha de ser único
    st_field = datetime.datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
    st_index = datetime.datetime.fromtimestamp(ts).strftime('%Y%m%d%H%M%S')
    # INDEX_NAME = 'pruebas'
    TYPE_NAME = 'akd_result'
    bulk_data = []
    index_id = str(script_name) + str("_") + str(st_index)
    data_dict = {
        "script_name": script_name,
        "arguments": arguments,
        "resultado": resultado_ejecucion,
        "time_stamp": str(st_field)
    }
    doc = {
        "index": {
            "_index": INDEX_NAME,
            "_type": TYPE_NAME,
            "_id": index_id
        }
    }
    bulk_data.append(doc)
    bulk_data.append(data_dict)
    es = Elasticsearch(hosts=[es__host2])
    res = es.bulk(index=INDEX_NAME, body=bulk_data, refresh=True, request_timeout=60)
    return res


if __name__ == "__main__":
    script_name="summarize.py"
    # Preparamos en un string los argumentos recibidos para la función de resultado
    arguments = str(sys.argv[1]) + str("|") + str(sys.argv[2] + str("|") + sys.argv[3]) + str("|") + str(
        sys.argv[4] + str("|") + sys.argv[5]) + str("|") + str(sys.argv[6])
    try:
        # Comenzamos la ejecución
        response_summarize(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6])
		# En caso de que la ejecución haya sido satisfactoria cargamos en la variable "resultado" el valor success
        load_execution_result_into_elastic(sys.argv[3], sys.argv[4], script_name, arguments, "success")
    # print(res(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5], sys.argv[6]))
    except:
		# En caso de que la ejecución no haya sido satisfactoria cargamos en la variable "resultado" el valor failure
        error_control = load_execution_result_into_elastic(sys.argv[3], sys.argv[4], script_name, arguments, "failure")
        print(error_control)

