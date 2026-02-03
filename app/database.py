from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import os

Base = declarative_base()

class Anagrafica(Base):
    __tablename__ = 'anagrafica'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fiscale = Column(String, unique=True, index=True) # PIVA o CF
    piva = Column(String)
    cf = Column(String)
    denominazione = Column(String)
    indirizzo = Column(String)
    comune = Column(String)
    cap = Column(String)
    nazione = Column(String)

class DatiGenerali(Base):
    __tablename__ = 'dati_generali'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    nome_file = Column(String, unique=True)
    tipo_documento = Column(String)
    divisa = Column(String)
    data = Column(String)
    numero = Column(String)
    
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
    descrizione = Column(String)
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
    tipo = Column(String) # ORDINE, CONTRATTO, CONVENZIONE, FATTURE_COLLEGATE
    
    riferimento_numero_linea = Column(Integer)
    id_documento = Column(String)
    data = Column(String)
    codice_commessa = Column(String)
    codice_cup = Column(String)
    codice_cig = Column(String)
    
    id_riga_db = Column(Integer, ForeignKey('righe_fattura.id'), nullable=True) # Link alla riga specifica nel DB
    
    fattura = relationship("DatiGenerali", back_populates="riferimenti")

class DatiDDT(Base):
    """Gestisce i dati DDT (2.1.8)"""
    __tablename__ = 'dati_ddt'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    numero_ddt = Column(String)
    data_ddt = Column(String)
    riferimento_numero_linea = Column(Integer)
    
    id_riga_db = Column(Integer, ForeignKey('righe_fattura.id'), nullable=True)
    
    fattura = relationship("DatiGenerali", back_populates="ddt")

class DatiRiepilogo(Base):
    """Riepilogo IVA (2.2.2)"""
    __tablename__ = 'dati_riepilogo'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    aliquota_iva = Column(Float)
    natura = Column(String)
    spese_accessorie = Column(Float)
    arrotondamento = Column(Float)
    imponibile_importo = Column(Float)
    imposta = Column(Float)
    esigibilita_iva = Column(String)
    riferimento_normativo = Column(String)
    
    fattura = relationship("DatiGenerali", back_populates="riepilogo")

class DatiPagamento(Base):
    """Condizioni di Pagamento (2.4.1)"""
    __tablename__ = 'dati_pagamento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_fattura = Column(Integer, ForeignKey('dati_generali.id'))
    
    condizioni_pagamento = Column(String)
    
    fattura = relationship("DatiGenerali", back_populates="pagamenti")
    dettagli = relationship("DettaglioPagamento", back_populates="testata_pagamento")

class DettaglioPagamento(Base):
    """Dettagli Pagamento (2.4.2)"""
    __tablename__ = 'dettaglio_pagamento'
    id = Column(Integer, primary_key=True, autoincrement=True)
    id_pagamento = Column(Integer, ForeignKey('dati_pagamento.id'))
    
    modalita_pagamento = Column(String)
    data_scadenza = Column(String)
    importo = Column(Float)
    iban = Column(String)
    abi = Column(String)
    cab = Column(String)
    bic = Column(String)
    
    testata_pagamento = relationship("DatiPagamento", back_populates="dettagli")

# Database SQLite locale - V3 per schema espanso
DB_PATH = "fatture_v3.db"
engine = create_engine(f"sqlite:///{DB_PATH}")
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    Base.metadata.create_all(bind=engine)
