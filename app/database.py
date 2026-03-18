from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text, text, inspect
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os
def load_env(path: str = ".env") -> dict:
    env_data = {}
    if not os.path.exists(path):
         return env_data
    with open(path, "r", encoding="utf-8") as f:
         for line in f:
             line = line.strip()
             if not line or line.startswith("#") or "=" not in line:
                 continue
             k, v = line.split("=", 1)
             env_data[k.strip()] = v.strip()
    return env_data


Base = declarative_base()

class Anagrafica(Base):
    __tablename__ = 'anagrafica'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fiscale = Column(String(255), unique=True, index=True) # PIVA o CF
    piva = Column(String(255))
    cf = Column(String(255))
    denominazione = Column(String(255))
    indirizzo = Column(String(255))
    comune = Column(String(255))
    cap = Column(String(255))
    nazione = Column(String(255))

class DatiGenerali(Base):
    __tablename__ = 'dati_generali'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome_file = Column(String(255), unique=True)
    tipo_documento = Column(String(255))
    divisa = Column(String(255))
    data = Column(String(255))
    numero = Column(String(255))
    data_ricezione = Column(String(255))
    
    # Nuovi campi Fase 7
    importo_totale = Column(Float)
    arrotondamento = Column(Float)
    causale = Column(Text)
    
    # FK e Relazioni
    id_cedente = Column(Integer, ForeignKey('anagrafica.id'))
    id_cessionario = Column(Integer, ForeignKey('anagrafica.id'))
    
    cedente = relationship("Anagrafica", foreign_keys=[id_cedente])
    cessionario = relationship("Anagrafica", foreign_keys=[id_cessionario])
    
    righe = relationship("RigheFattura", back_populates="fattura")
    riferimenti = relationship("DatiRiferimento", back_populates="fattura")
    ddt = relationship("DatiDDT", back_populates="fattura")
    riepilogo = relationship("DatiRiepilogo", back_populates="fattura")
    pagamenti = relationship("DatiPagamento", back_populates="fattura")

class RigheFattura(Base):
    __tablename__ = 'righe_fattura'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    numero_linea = Column(Integer)
    descrizione = Column(Text)
    quantita = Column(Float)
    prezzo_unitario = Column(Float)
    prezzo_totale = Column(Float)
    aliquota_iva = Column(Float)
    
    fattura = relationship("DatiGenerali", back_populates="righe")

class DatiRiferimento(Base):
    """Gestisce Ordine, Contratto, Convenzione, FattureCollegate (2.1.2 - 2.1.6)"""
    __tablename__ = 'dati_riferimento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    tipo = Column(String(255)) # ORDINE, CONTRATTO, CONVENZIONE, FATTURE_COLLEGATE
    
    riferimento_numero_linea = Column(Integer)
    id_documento = Column(String(255))
    data = Column(String(255))
    codice_commessa = Column(String(255))
    codice_cup = Column(String(255))
    codice_cig = Column(String(255))
    
    id_riga_db = Column(Integer, ForeignKey('righe_fattura.id'), nullable=True) # Link alla riga specifica nel DB
    
    fattura = relationship("DatiGenerali", back_populates="riferimenti")

class DatiDDT(Base):
    """Gestisce i dati DDT (2.1.8)"""
    __tablename__ = 'dati_ddt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    numero_ddt = Column(String(255))
    data_ddt = Column(String(255))
    riferimento_numero_linea = Column(Integer)
    
    id_riga_db = Column(Integer, ForeignKey('righe_fattura.id'), nullable=True)
    
    fattura = relationship("DatiGenerali", back_populates="ddt")

class DatiRiepilogo(Base):
    """Riepilogo IVA (2.2.2)"""
    __tablename__ = 'dati_riepilogo'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    aliquota_iva = Column(Float)
    natura = Column(String(255))
    spese_accessorie = Column(Float)
    arrotondamento = Column(Float)
    imponibile_importo = Column(Float)
    imposta = Column(Float)
    esigibilita_iva = Column(String(255))
    riferimento_normativo = Column(String(255))
    
    fattura = relationship("DatiGenerali", back_populates="riepilogo")

class DatiPagamento(Base):
    """Condizioni di Pagamento (2.4.1)"""
    __tablename__ = 'dati_pagamento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    condizioni_pagamento = Column(String(255))
    
    fattura = relationship("DatiGenerali", back_populates="pagamenti")
    dettagli = relationship("DettaglioPagamento", back_populates="testata_pagamento")

class DettaglioPagamento(Base):
    """Dettagli Pagamento (2.4.2)"""
    __tablename__ = 'dettaglio_pagamento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_pagamento = Column(Integer, ForeignKey('dati_pagamento.id'))
    
    modalita_pagamento = Column(String(255))
    data_scadenza = Column(String(255))
    importo = Column(Float)
    iban = Column(String(255))
    abi = Column(String(255))
    cab = Column(String(255))
    bic = Column(String(255))
    
    testata_pagamento = relationship("DatiPagamento", back_populates="dettagli")

# Database Configuration
env = load_env()
db_type = env.get("DB_TYPE", "sqlite").lower()

if db_type == "mysql":
    db_host = env.get("DB_HOST", "localhost")
    db_port = env.get("DB_PORT", "3306")
    db_name = env.get("DB_NAME", "")
    db_user = env.get("DB_USER", "")
    db_pass = env.get("DB_PASS", "")
    connection_string = f"mysql+pymysql://{db_user}:{db_pass}@{db_host}:{db_port}/{db_name}"
else:
    # Default is SQLite
    db_path = env.get("DB_SQLITE_PATH", "fatture_v3.db")
    connection_string = f"sqlite:///{db_path}"

engine = create_engine(connection_string)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
    # Migrazione semplice: aggiunge colonna data_ricezione se manca
    inspector = inspect(engine)
    columns = [c['name'] for c in inspector.get_columns('dati_generali')]
    if "data_ricezione" not in columns:
        with engine.connect() as conn:
            conn.execute(text("ALTER TABLE dati_generali ADD COLUMN data_ricezione TEXT"))
            conn.commit()
