# Analisi Campi Fattura Elettronica (FE versione 1.9 del 1° aprile 2025 vs Database)

Di seguito il riepilogo dettagliato di cosa viene **SALVATO** e cosa resta **FUORI**.

---

## 1. 📂 Header e Dati Trasmissione (`<FatturaElettronicaHeader>`)

| Blocco / Campo Excel | Salvato nel DB? | Nota / Modello DB |
| :--- | :--- | :--- |
| **`DatiTrasmissione`** | ❌ **No** | Intero blocco ignorato |
| └ `IdTrasmittente` | ❌ No | |
| └ `ProgressivoInvio` | ❌ No | |
| └ `FormatoTrasmissione` | ❌ No | |
| └ `CodiceDestinatario` | ❌ No | |
| └ `ContattiTrasmittente` | ❌ No | |
| └ `PECDestinatario` | ❌ No | |

---

## 2. 👤 Anagrafica (`<CedentePrestatore>` e `<CessionarioCommittente>`)

Attualmente il database unifica questi soggetti nel modello `Anagrafica`.

| Campo Excel | Salvato nel DB? | Nota / Modello DB |
| :--- | :--- | :--- |
| `IdFiscaleIVA.IdCodice` | ✅ **Sì** | `Anagrafica.id_fiscale` / `piva` / `cf` |
| `Denominazione` | ✅ **Sì** | `Anagrafica.denominazione` |
| `Indirizzo` | ✅ **Sì** | `Anagrafica.indirizzo` |
| `CAP` | ✅ **Sì** | `Anagrafica.cap` |
| `Comune` | ✅ **Sì** | `Anagrafica.comune` |
| `Nazione` | ✅ **Sì** | `Anagrafica.nazione` |
| `NumeroCivico` | ❌ **No** | Non salvato separatamente |
| `Provincia` | ❌ **No** | Non presente nel modello `Anagrafica` |
| `StabileOrganizzazione` | ❌ **No** | Intero blocco ignorato |
| `IscrizioneREA` | ❌ **No** | Intero blocco ignorato |
| `Contatti` (Tel, Email) | ❌ **No** | Ignorati |
| `RappresentanteFiscale` | ❌ **No** | Ignorato |

---

## 3. 📄 Dati Generali Documento (`<DatiGeneraliDocumento>`)

| Campo Excel | Salvato nel DB? | Nota / Modello DB |
| :--- | :--- | :--- |
| `TipoDocumento` | ✅ **Sì** | `DatiGenerali.tipo_documento` |
| `Divisa` | ✅ **Sì** | `DatiGenerali.divisa` |
| `Data` | ✅ **Sì** | `DatiGenerali.data` |
| `Numero` | ✅ **Sì** | `DatiGenerali.numero` |
| `ImportoTotaleDocumento` | ✅ **Sì** | `DatiGenerali.importo_totale` |
| `Arrotondamento` | ✅ **Sì** | `DatiGenerali.arrotondamento` |
| `Causale` | ✅ **Sì** | `DatiGenerali.causale` |
| `DatiRitenuta` | ❌ **No** | Ignorato |
| `DatiBollo` | ❌ **No** | Ignorato |
| `DatiCassaPrevidenziale` | ❌ **No** | Ignorato |
| `ScontoMaggiorazione` (Testata) | ❌ **No** | Ignorato |
| `Art73` | ❌ **No** | Ignorato |

---

## 4. 🔗 Collegamenti e Riferimenti (`<DatiOrdineAcquisto>`, `<DatiContratto>`, ecc.)

Gestito nel modello `DatiRiferimento`.

| Campo Excel | Salvato nel DB? | Nota / Modello DB |
| :--- | :--- | :--- |
| `IdDocumento` | ✅ **Sì** | `DatiRiferimento.id_documento` |
| `Data` | ✅ **Sì** | `DatiRiferimento.data` |
| `CodiceCommessaConvenzione`| ✅ **Sì** | `DatiRiferimento.codice_commessa` |
| `CodiceCUP` | ✅ **Sì** | `DatiRiferimento.codice_cup` |
| `CodiceCIG` | ✅ **Sì** | `DatiRiferimento.codice_cig` |
| `RiferimentoNumeroLinea` | ✅ **Sì** | `DatiRiferimento.riferimento_numero_linea` |
| `NumItem` | ❌ **No** | Ignorato |

---

## 5. 📦 Dati DDT (`<DatiDDT>`)

| Campo Excel | Salvato nel DB? | Nota |
| :--- | :--- | :--- |
| `NumeroDDT` | ✅ **Sì** | `DatiDDT.numero_ddt` |
| `DataDDT` | ✅ **Sì** | `DatiDDT.data_ddt` |
| `RiferimentoNumeroLinea` | ✅ **Sì** | `DatiDDT.riferimento_numero_linea` |

---

## 6. 🛒 Dettaglio Linee (`<DettaglioLinee>`)

Gestito nel modello `RigheFattura`.

| Campo Excel | Salvato nel DB? | Nota / Modello DB |
| :--- | :--- | :--- |
| `NumeroLinea` | ✅ **Sì** | `RigheFattura.numero_linea` |
| `Descrizione` | ✅ **Sì** | `RigheFattura.descrizione` |
| `Quantita` | ✅ **Sì** | `RigheFattura.quantita` |
| `PrezzoUnitario` | ✅ **Sì** | `RigheFattura.prezzo_unitario` |
| `PrezzoTotale` | ✅ **Sì** | `RigheFattura.prezzo_totale` |
| `AliquotaIVA` | ✅ **Sì** | `RigheFattura.aliquota_iva` |
| `TipoCessionePrestazione` | ❌ **No** | Ignorato |
| `CodiceArticolo` | ❌ **No** | Ignorato |
| `UnitaMisura` | ❌ **No** | Ignorato |
| `Date Inizio/Fine Periodo` | ❌ **No** | Ignorati |
| `ScontoMaggiorazione` (Riga) | ❌ **No** | Ignorato |
| `Ritenuta` (Riga) | ❌ **No** | Ignorato |
| `Natura` (Riga) | ❌ **No** | Ignorata sulla riga (salvata solo su Riepilogo) |
| `AltriDatiGestionali` | ❌ **No** | Ignorato |

---

## 7. ⚖️ Riepilogo IVA (`<DatiRiepilogo>`)

| Campo Excel | Salvato nel DB? | Nota |
| :--- | :--- | :--- |
| `AliquotaIVA` | ✅ **Sì** | `DatiRiepilogo.aliquota_iva` |
| `Natura` | ✅ **Sì** | `DatiRiepilogo.natura` |
| `SpeseAccessorie` | ✅ **Sì** | `DatiRiepilogo.spese_accessorie` |
| `Arrotondamento` | ✅ **Sì** | `DatiRiepilogo.arrotondamento` |
| `ImponibileImporto` | ✅ **Sì** | `DatiRiepilogo.imponibile_importo` |
| `Imposta` | ✅ **Sì** | `DatiRiepilogo.imposta` |
| `EsigibilitaIVA` | ✅ **Sì** | `DatiRiepilogo.esigibilita_iva` |
| `RiferimentoNormativo` | ✅ **Sì** | `DatiRiepilogo.riferimento_normativo` |

---

## 8. 💳 Pagamenti (`<DatiPagamento>`)

| Campo Excel | Salvato nel DB? | Nota |
| :--- | :--- | :--- |
| `CondizioniPagamento` | ✅ **Sì** | `DatiPagamento` |
| `ModalitaPagamento` | ✅ **Sì** | `DettaglioPagamento.modalita_pagamento` |
| `DataScadenzaPagamento` | ✅ **Sì** | `DettaglioPagamento.data_scadenza` |
| `ImportoPagamento` | ✅ **Sì** | `DettaglioPagamento.importo` |
| `IBAN` | ✅ **Sì** | `DettaglioPagamento.iban` |
| `ABI` / `CAB` / `BIC` | ✅ **Sì** | Presenti |
| `Beneficiario` | ❌ **No** | Ignorato |
| `GiorniTerminiPagamento` | ❌ **No** | Ignorato |
| `IstitutoFinanziario` | ❌ **No** | Ignorato |

---

## 9. 🚫 Altri Blocchi Totalmente Esclusi
*   **`<DatiTrasporto>`**: non salvato
*   **`<DatiVeicoli>`**: non salvato
*   **`<Allegati>`**: non salvati nel DB (restano solo nei file XML/P7M scaricati)
