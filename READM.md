# P03 Flask API + SQL Server (TCP 9091 / P03 contínuo)

API Flask que:
- Conecta via TCP em um equipamento P03 (frame STX..CR com CS opcional)
- Interpreta leituras (peso/tara + status bytes)
- Persiste no SQL Server
- Expõe endpoints para health/latest/readings/start/stop
- Registra auditoria de consumo dos endpoints (IP, UA, path, status, latência)

## 1) Pré-requisitos

### Windows
- Python 3.10+ recomendado
- Microsoft ODBC Driver 18 for SQL Server (ou 17)

### Linux
- Python 3.11 (x64)
- Driver ODBC (msodbcsql18) e unixODBC

## 2) Instalação

```bash
python -m venv .venv
# Windows:
.venv\Scripts\activate
# Linux/macOS:
source .venv/bin/activate

pip install -r requirements.txt