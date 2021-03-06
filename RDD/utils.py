import psycopg2 as p
import pandas as pd
from pprint import pprint
dbname= 'aeacus_kdd' #aeacus_kdd
dbuser= 'aeacus'
dbpass= 'aeacus##sij2016'
host= '172.22.248.221'
port = '5432'

class DBConn:
    def __init__(self,dbname,dbuser,dbpass,host,port):
        con_str = str('dbname='+'\''+dbname+'\''+' user='+'\''+dbuser+'\''+' host='+'\''+host+'\''+' password='+'\''+dbpass+'\''+' port='+'\''+port+'\'')
        pprint("Conectando a: [%s]..." % con_str)
        try:
            self.connection = p.connect(con_str)
            self.connection.autocommit = True
            self.cursor = self.connection.cursor()
            pprint("Conectado")
        
        except (Exception, p.DatabaseError) as error:
            pprint(error) 
        
    def insert_record(self, table, rows, values):
        # Inserta Registros en la tabla indicada.
        concat=lambda x: reduce(lambda s, y: str(s) + "," + str(y),x)
        query_insert = "INSERT INTO "+table+" ( "+concat(rows)+" ) "+" VALUES ("+concat(values)+")"
        pprint(query_insert)
        self.cursor.execute(query_insert)
    
    def query_all(self, table):
        # Consulta de toda la tabla
        query="SELECT * FROM "+table
        pprint(query)
        return pd.read_sql_query( query, self.connection)
            
    def update_record(self,table, cambio, condicion ):
        #en construccion, necesaria
        query_update = "UPDATE "+table+" SET "+cambio+' where '+condicion
        pprint(query_update)
        self.cursor.execute(query_update)
    
    def execute_query(self,query):
        return pd.read_sql_query( query, self.connection)
    
    def close_connection(self):
        self.cursor.close()
        self.connection.close()
# db_conn.execute_query('SELECT dm_accesses.*, dm_paper_access.* FROM dm_accesses, dm_paper_access where dm_accesses.paper = dm_paper_access."id"')
# db_conn.execute_query('SELECT dm_session.*, dm_accesses.*, dm_paper_access.* FROM dm_session, dm_accesses, dm_paper_access where dm_accesses.paper = dm_paper_access."id" and dm_session."id" = dm_accesses.sessionid')

# DB = db_conn.execute_query('SELECT dm_session.*, dm_accesses.*, dm_paper_access.* FROM dm_session, dm_accesses, dm_paper_access where dm_accesses.paper = dm_paper_access."id" and dm_session."id" = dm_accesses.sessionid')
DB = db_conn.execute_query('SELECT dm_session.*, dm_accesses.*, dm_paper_access.* FROM dm_accesses LEFT OUTER JOIN dm_session ON dm_session."id" = dm_accesses.sessionid LEFT OUTER JOIN dm_paper_access ON dm_paper_access."id" = dm_accesses.paper ORDER BY accessdate') 

# Preprocessing

def unificar_df(df):
    df.columns=pd.io.parsers.ParserBase({'names':df.columns})._maybe_dedup_names(df.columns)
    return df

DB = unificar_df(DB)

def filtra(out_ele, obj):
    return filter(lambda o: o not in out_ele, list(obj))

duplicados = [s for s in list(DB) if "." in s]
duplicados.extend(["id"])
DB = DB[filtra(duplicados,DB)] # eliminamos campos con los que no trabajamos

################# En desarrollo
# como hacer un insert(futuro inset de el scoring en kdd_paperclassenum
# db_conn.insert_record((1,2,'00000000B',4,'NIG',1,9,200),"rdd_paperclassenum")
# print(list(db_conn.query_all("dm_accesses")))

################ Calculo de tiempo transcurrido
# DB['accessdate']
# resta = db_conn.query_all("dm_accesses")['accessdate'][0]- db_conn.query_all("dm_accesses")['accessdate'][0]
# resta.components # Components(days=0, hours=0, minutes=0, seconds=11, milliseconds=994, microseconds=0, nanoseconds=0)


################ Calculo de columnas combinadas
# df=pd.DataFrame({'col0':['auto','auto2','auto3'],'col1':[965046,22501,29672]
#                  ,'col2':[15222,34,10],'col3':[137792670,0.3548,0.04]})
# # Funcion especificada, cambia por el nombre de las columnas    
# def f(x):
#     return round(((x['col2'])/(float(x['col1']))*100),2)
# df['Filtrate%'] = df.apply(f,axis=1)
