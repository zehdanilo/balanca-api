from .database.db import SessionLocal
from .models.models import (
    ChemicalSpecCatalog,
    CustomerCatalog,
    DestinationCatalog,
    DriverCatalog,
    HorsePlateCatalog,
    TankPlateCatalog,
    TransporterCatalog,
    WeighingTicket,
)


TANK_PLATES = [
    "HYA1275", "HYW5134", "NRA9G70", "OSL0721", "NTN9562", "PJW5101", "QGV1H57", "DEV0001",
    "HYA1295", "HYA1315", "FJA1041", "NUW9362", "FJA1H10", "HYO5526", "HYV6846", "RQB1G56",
    "QGL9A96", "NYP9184", "QGV1H66", "KGL9A96", "OSL0491", "HXS4854", "NOG8056", "OJV7017",
    "OJV6987", "NOA8007", "OKC4H66", "NOA8A07", "NTN8068", "FJA0H20", "FJA0H21", "HYV-6846",
    "NRA-9G70", "OSD-3277", "HYO-5526", "HXS-4834", "HYA-1295", "HXS-4854", "HYW-5134",
    "HXS-4J14", "HVG-9272", "NUW-9362", "HWG-4063", "HXS-4934", "MNZ-3087", "OJV-6J87",
    "OJS-2618", "OJS-2558", "OJV-7017", "HXS4J14", "HXS4834", "HYV6826", "HXS4934", "NUW9262",
    "HYA-1315", "HYV-6826", "HVE-9272", "HYV-3826", "HSX-4854", "NTN-9F62", "NTN-8068",
    "NYP-9B84", "PKS-5J55", "NTN-8086", "PJK-4J33", "PJK-4933", "NOG-8A66", "OKC-4I06",
    "NOA-8A07", "NOA-7J97", "OKC-4H36", "OKC-4H66", "QGM0E55", "OJS2618", "OKC4H36",
    "OSO-7237", "OSE-7317", "PMJ-2570", "HYA-1275", "POH-2190", "OJS-2F58", "MYV-6826",
    "NTN-8A68", "NTA-8A68", "QGM-0E55", "OSL-0721", "QGB-7C68", "OKC4H3", "OYV2392",
    "NOG8A56", "OJV7A17", "OYV2D92", "NOA7J97", "OMS9D78", "OJV-7A17", "OYV-2392",
    "CUD-4H59", "OSO7237", "HWG4063", "OSE7317", "POH2190", "THS2A31", "PMJ2570", "OJV6J87",
    "NOG8A66", "HVG9272", "OJB7A17", "HDG9272", "HYA6826", "HSX4854", "QGU5B97", "RGN4D13",
    "OCC3B08", "QGB7C88", "OSO3277", "HYL2587", "HYL2617", "XYZ5678", "XYZ8888", "GHI6666",
    "MNO4444", "TUV7777", "ABC9999", "QGB7C68", "OJV7027", "QGK7646", "OJS2F58", "THK3E50",
    "THQ3E50", "QGB7B48", "QGB7C48", "TZB1D59", "THS2F51", "TZD6A97", "PFO1C40",
]


HORSE_PLATES = [
    "PMF9A37", "OII9430", "HXN8658", "RJZ0H36", "OLB7386", "PJK4933", "RGN5D11", "DEV0001",
    "ABC1234", "PMF9137", "SBA1G64", "POG2H73", "SBA1E94", "SBA1I54", "QGU9G77", "ODA9H28",
    "PKT9572", "OVF3D43", "GCB3I99", "NUY7872", "PMF9067", "OYD9B08", "PPA1A39", "KGW4A35",
    "THW4J18", "JHW4J18", "OMS9D78", "PFS5B37", "POS5059", "PGL1G67", "HWN6846", "PKS5264",
    "OII9420", "OSL5718", "OJV6987", "POS5919", "POS-5969", "POS-5059", "OII-9420",
    "POS-8229", "OSL-5238", "POT-6744", "POS-5919", "SBA-1I54", "OSL-5718", "SBA-1E94",
    "POT-6214", "SBA-1G64", "POG-2H73", "POS-5169", "HXN-8658", "POT-6219", "HWN-0817",
    "PMF-9137", "5BA-1E94", "PMF-9067", "THS-3F81", "PMF-9A37", "PEA-9A30", "POU-9F21",
    "KHT-2J95", "KGW-4A35", "CVD-4H59", "OYD-9B08", "CUD-4H59", "PDU-4E19", "PPA-IA39",
    "POS5169", "POT6214", "POG2H28", "SBA1E64", "POS2H73", "POS8229", "SBA1C64", "HYA1295",
    "SBA-1C64", "OII-9430", "SBA-1154", "PMF-3137", "OII-6430", "THS-2A31", "OLB-7386",
    "PJX-2E04", "PKT-9F72", "PKS-5C64", "PJW-5B01", "PKT-9F62", "PKS-5C84", "OMS-9D78",
    "OZL-7B14", "MLN-1B01", "PGL-1G67", "NPX-2E21", "HWN-6846", "NUY-7872", "TID1C39",
    "OZL7B14", "PEA9A30", "THS-2J61", "THS-2F51", "PJK-2E04", "PKT-9E72", "TID-1C39",
    "TIC-8F39", "QYY1B41", "NPX2E21", "OJV6J78", "PJX-2EO4", "QYY-1B41", "PPA-1A39",
    "OJV-7A17", "POT6744", "THS2J61", "OLS5238", "THS3F81", "THS2F51", "THS2A31",
    "MLN1B01", "OZL8A66", "POS599", "OSL5238", "PLN9J98", "PLN9G98", "RLN9J98", "QGU9677",
    "RVM9C48", "RVM9C33", "RVM9C20", "RVM9C08", "PLN9J18", "QYB1B41", "POH2190",
    "OSO7237", "OSE7317", "OSO3277", "PMJ2570", "OSO8239", "SOM1D31", "HYA1315", "TIC8F39",
    "SJU0F10", "ABC9999", "DEF7777", "JKL5555", "QRS6666", "XYZ8888", "CUD4H59", "TSP6E26",
    "QYV1J49", "PNZ8A23", "MTB7J44", "PDU4E19", "GHA7H54", "GIT7C28", "FDB0397", "KGD9E79",
]


DRIVERS = [
    "MÁRCIO GUILHERME DA SILVA",
    "MÁRCIO RICARDO DE MEDEIROS",
    "JOSÉ ARIAN BEZERRA",
    "WESLONE DA SILVA",
    "ANTONIO LUCIO PEREIRA",
    "ANTONIO MARCIO DA SILVA",
    "PAULO HENRIQUE DO NASCIMENTO",
    "DIEGO RODRIGUES NUNES",
    "FRANCISCO HELTON JERONIMO DE SOUSA",
    "WILAMY FAGUNDES DE SOUZA",
    "KELMY GONZAGA CACHINA",
    "LUIZ SOARES DE MELO NETO",
    "LUIZ TESTE",
    "JEAN MEDEIROS DA SILVA",
    "JOSE ANTONIO DA SILVA",
    "FRANCISCO WILLAME RIBEIRO",
    "THALLES HENRIQUE REIS DA COSTA",
    "ANTONIO JUNIOR BARBOSA",
    "RANIERE ALVES LEITE",
    "VALFREDO FERNANDES DE SOUSA",
    "FRANCISCO DAS CHAGAS DE AQUINO JUNIOR",
    "NILSON FARIAS JÚNIOR",
    "IVANILDO FERNANDES DE SOUSA",
    "FRANCISCO ARAÚJO FILHO",
    "ELIALDO SOARES DA COSTA",
    "IVO OLIVEIRA DE MELO",
    "ALISSON PATRICK DE SOUZA",
    "ROBERLINDO FERNANDES DE SOUSA",
    "ANTONIO RISONALDO BARBALHO EVANGELISTA",
    "JOSADAK VIERIA DO NASCIMENTO",
    "ALISSON LEONARDO FERREIRA DE OLIVEIRA",
    "DION CAVALCANTI XAVIER JÚNIOR",
    "EVERTON DIOGO DA SILVA",
    "ALEXANDRE BELARMINO DA SILVA",
    "FRANCISCO SOARES FILHO",
    "JOSE APARECIDO SANTANA",
    "EWERTON MANOEL MARINHO DA SILVA",
    "JOEL PEDRO DA SILVA",
    "NOE VIANA DOS SANTOS",
    "JOSE AUGUSTO ABREU DOS SANTOS",
    "GERALDO OLIVEIRA BATISTA",
    "JOÃO SILVA SANTOS - TESTE API",
    "SSSS",
    "JOSE",
    "FRANCISCO GARCIEL DA SILVA RODRIGUES",
    "ANDRÉ FELIPE ROQUE BATISTA",
    "CLEBSON NUNES DE LIMA",
    "EDER SABINO DE OLIVEIRA COSTA",
    "MOIZES VALERIO DA SILVA JUNIOR",
    "MOTORISTA IMPORTAÇÃO",
    "JOSE WILSON FONSECA OLIVEIRA",
    "JOSE FERREIRA DA SILVA NETO",
    "GILSON DE SOUZA PAIVA",
    "JOSÉ SUEDSON CHAVES",
    "RAMIRO DO NASCIMENTO BEZERRA",
    "FRANCISCO GERMANO DAS NEVES NETO",
    "IVANILDO FERNANDES DE SOUZA",
    "ROBERTO DE SOUZA MELO",
    "DION CAVALCANTE XAVIER JUNIOR",
    "FERNANDO C",
    "FERNANDO CA",
    "FERNANDO CO",
    "CARLOS FERNANDES APARECIDO SANTANA",
    "JOSÉ ABDALA ALVES DA SILVA TORRES",
    "SERVIO VITO DA SILVA",
    "MARCOS AURELIO CANDIDO NOGUEIRA",
    "MIGUEL CIRIACO CONSTANCIO JUNIOR",
    "SEVERINO FERNANDO FERREIRA FILHO",
    "JOAO DA SILVA TESTE",
    "MOTORISTA TESTE PETRO",
    "MOTORISTA TESTE 2",
    "MOTORISTA TESTE 3",
    "MOTORISTA TESTE 4",
    "MOTORISTA TESTE 5",
    "SERVIO VITOR DA SILVA BEZERRA",
    "FLAVIO FERREIRA DA SILVA",
    "DEUZIMAR PAULINO DA SILVA",
    "FRANCISCO CABRAL FERREIRA",
    "HIGO FREIRE CORCINO",
    "JOAO GALDINO DA SILVA",
    "JEAN DE MEDEIROS DA SILVA",
    "THALLES HENRIQUE REIS COSTA",
    "FRANCIKLEBER CARNEIRO ROMAO",
    "ISRAEL LUCAS GOMES FERREIRA",
    "RODRIGO MOURAO ALVIM",
    "ISRAEL DLUCAS GOMES FERREIRA",
]


TRANSPORTERS = [
    "M. Y. PORDEUS TRANSPORTES DE CARGAS LTDA",
    "MASTER LOCAÇÃO LIMITADA",
    "MARINHO TRANSPORTES DE CARGAS LTDA",
    "FERRAZ TRANSPORTES RODOVIÁRIOS LTDA",
    "BENEL TRANSPORTES E LOGISTICA LTDA",
    "NIOM - TRANSPORTADORA DESENVOLVIMENTO",
    "BENEL",
    "M.Y PORDEUS TRANSPORTES DE CARGAS LTDA",
    "TRANSPORTES TESTE API LTDA",
    "N/A",
    "TRANSPORTADORA RAPIDÃO LTDA",
    "TRANSPORTADORA IMPORTAÇÃO",
    "TRANSPORTADORA TESTE LTDA",
    "TRANSPORTADORA PETRO LTDA",
    "TRANSPORTADORA TESTE 2",
    "TRANSPORTADORA TESTE 3",
    "TRANSPORTADORA TESTE 4",
    "TRANSPORTADORA TESTE 5",
    "MINAS TRADING COMPANY LTDA",
]


def _normalize_text(value):
    return " ".join(str(value).strip().upper().split())


def _unique(values):
    seen = set()
    result = []
    for value in values:
        normalized = _normalize_text(value)
        if normalized and normalized not in seen:
            seen.add(normalized)
            result.append(normalized)
    return result


def _ticket_values(db, column):
    return _unique(value for (value,) in db.query(column).filter(column != "").all())


def seed_catalog_data() -> dict:
    db = SessionLocal()
    try:
        existing_tank_plates = {_normalize_text(placa) for (placa,) in db.query(TankPlateCatalog.placa).all()}
        existing_horse_plates = {_normalize_text(placa) for (placa,) in db.query(HorsePlateCatalog.placa).all()}
        existing_drivers = {_normalize_text(nome) for (nome,) in db.query(DriverCatalog.nome).all()}
        existing_transporters = {_normalize_text(nome) for (nome,) in db.query(TransporterCatalog.nome).all()}
        existing_customers = {_normalize_text(nome) for (nome,) in db.query(CustomerCatalog.nome).all()}
        existing_chemical_specs = {_normalize_text(nome) for (nome,) in db.query(ChemicalSpecCatalog.nome).all()}
        existing_destinations = {_normalize_text(nome) for (nome,) in db.query(DestinationCatalog.nome).all()}

        tank_plates_to_add = [
            TankPlateCatalog(placa=value) for value in _unique(TANK_PLATES) if value not in existing_tank_plates
        ]
        horse_plates_to_add = [
            HorsePlateCatalog(placa=value) for value in _unique(HORSE_PLATES) if value not in existing_horse_plates
        ]
        drivers_to_add = [DriverCatalog(nome=value) for value in _unique(DRIVERS) if value not in existing_drivers]
        transporters_to_add = [
            TransporterCatalog(nome=value) for value in _unique(TRANSPORTERS) if value not in existing_transporters
        ]
        customers_to_add = [
            CustomerCatalog(nome=value)
            for value in _ticket_values(db, WeighingTicket.fornecedor_cliente)
            if value not in existing_customers
        ]
        chemical_specs_to_add = [
            ChemicalSpecCatalog(nome=value)
            for value in _ticket_values(db, WeighingTicket.especificacao_quimico)
            if value not in existing_chemical_specs
        ]
        destinations_to_add = [
            DestinationCatalog(nome=value)
            for value in _ticket_values(db, WeighingTicket.destino_procedencia)
            if value not in existing_destinations
        ]

        db.add_all(
            tank_plates_to_add
            + horse_plates_to_add
            + drivers_to_add
            + transporters_to_add
            + customers_to_add
            + chemical_specs_to_add
            + destinations_to_add
        )
        db.commit()
        return {
            "tank_plates": len(tank_plates_to_add),
            "horse_plates": len(horse_plates_to_add),
            "drivers": len(drivers_to_add),
            "transporters": len(transporters_to_add),
            "customers": len(customers_to_add),
            "chemical_specs": len(chemical_specs_to_add),
            "destinations": len(destinations_to_add),
        }
    finally:
        db.close()
