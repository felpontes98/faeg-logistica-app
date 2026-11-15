import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.orm import declarative_base, sessionmaker

# Carrega a DATABASE_URL do arquivo .env
load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL não encontrada. Verifique se salvou o arquivo .env.")

# Garante compatibilidade com SQLAlchemy 2.0
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# Configura a conexão otimizada para o Neon (serverless)
engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=300
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# Teste rápido de conexão ao rodar este arquivo diretamente
if __name__ == "__main__":
    try:
        with engine.connect() as conn:
            resultado = conn.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public';"))
            tabelas = [linha[0] for linha in resultado]
            print("Conectado ao Neon com sucesso!")
            print(f"Tabelas encontradas ({len(tabelas)}):", tabelas)
    except Exception as e:
        print("Erro ao conectar:", e)