from sqlalchemy import create_engine, text
import dlt

engine = create_engine(dlt.secrets["sources.mssql.connection_string"])

def copy_and_edit():
    with engine.begin() as conn:
        
        # tworzenie nowej tabeli
        conn.execute(text("""
            IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'Test')
            EXEC('CREATE SCHEMA Test')
        """))

        # kopiowanie z Production.Product
        conn.execute(text("""
            IF OBJECT_ID('Test.Copied', 'U') IS NOT NULL
                DROP TABLE Test.Copied;

            SELECT *
            INTO Test.Copied
            FROM Production.Product;
        """))

        # modyfikowanie danych
        conn.execute(text("""
            UPDATE Test.Copied
            SET ListPrice = ListPrice * 10.0
            WHERE ListPrice IS NOT NULL;
        """))
        

if __name__ == "__main__":
    copy_and_edit()
