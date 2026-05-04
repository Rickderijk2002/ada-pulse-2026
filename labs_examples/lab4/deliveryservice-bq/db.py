import os

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy_utils import database_exists, create_database

# The database URL is provided as an env. variable
if 'DB_URL' in os.environ:
    db_url = os.environ['DB_URL']
else:
    db_url = 'sqlite:///delivery.db'
engine = create_engine(db_url)
if not database_exists(engine.url):
    create_database(engine.url)
print(database_exists(engine.url))
Session = sessionmaker(bind=engine)
Base = declarative_base()
