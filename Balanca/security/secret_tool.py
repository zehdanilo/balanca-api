# tools/gen_secrets.py
import os
from cryptography.fernet import Fernet
from Balanca.security.secrets import encrypt

def main():
    if not os.getenv("BALANCA_MASTER_KEY"):
        key = Fernet.generate_key().decode("utf-8")
        print("Defina como variável de ambiente (NÃO no .env em produção):")
        print(f"BALANCA_MASTER_KEY={key}\n")
        os.environ["BALANCA_MASTER_KEY"] = key

    sql_pwd = input("SQLSERVER_PASSWORD (claro): ").strip()
    api_pwd = input("API_PASSWORD (claro): ").strip()

    print("\nCole no .env:")
    print("SQLSERVER_PASSWORD_ENC=" + encrypt(sql_pwd))
    print("API_PASSWORD_ENC=" + encrypt(api_pwd))

if __name__ == "__main__":
    main()
