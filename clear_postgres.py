import psycopg2
import sys

DB_NAME = 'hospitoll_db'
DB_USER = 'hospitoll_user'
DB_PASSWORD = 'secure_password_here'
DB_HOST = 'localhost'
DB_PORT = 5432

try:
    conn = psycopg2.connect(dbname=DB_NAME, user=DB_USER, password=DB_PASSWORD, host=DB_HOST, port=DB_PORT)
    conn.autocommit = True
    cur = conn.cursor()
    cur.execute('DROP SCHEMA public CASCADE; CREATE SCHEMA public;')
    cur.close()
    conn.close()
    print('Postgres: public schema dropped and recreated — data removed')
except Exception as e:
    print('ERROR', e)
    sys.exit(1)
