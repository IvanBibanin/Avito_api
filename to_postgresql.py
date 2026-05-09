import pandas as pd
import sqlalchemy


class ToPostgreSQL:
    def __init__(
        self,
        port=None,
        host=None,
        user=None,
        password=None,
        database=None,
        schema=None,
        connect_timeout=30,
        pool_recycle=1800,
        batch_page_size=500,
    ):
        self.schema = schema
        self.batch_page_size = batch_page_size

        db_url = sqlalchemy.engine.URL.create(
            'postgresql+psycopg2',
            username=user,
            password=password,
            host=host,
            port=port,
            database=database,
        )
        self.engine = sqlalchemy.create_engine(
            db_url,
            pool_pre_ping=True,
            pool_recycle=pool_recycle,
            connect_args={'connect_timeout': connect_timeout},
            executemany_mode='values_plus_batch',
            executemany_batch_page_size=batch_page_size,
        )

    @staticmethod
    def _quote_identifier(identifier):
        if not isinstance(identifier, str) or not identifier.strip():
            raise ValueError('SQL identifier cannot be empty')
        return '"' + identifier.replace('"', '""') + '"'

    def _qualified_table(self, table_name):
        return f'{self._quote_identifier(self.schema)}.{self._quote_identifier(table_name)}'

    @staticmethod
    def _validate_data(data):
        if data is None or not isinstance(data, pd.DataFrame):
            raise ValueError('data must be a pandas DataFrame')
        if data.empty:
            raise ValueError('data must not be empty')
        if 'date' not in data.columns:
            raise ValueError('data must contain a date column')

    @staticmethod
    def _normalize_data(data):
        normalized = data.copy()
        normalized['date'] = pd.to_datetime(normalized['date']).dt.date
        normalized = normalized.where(pd.notna(normalized), None)
        return normalized

    @staticmethod
    def _column_type(column_name):
        return 'DATE' if column_name == 'date' else 'TEXT'

    def create_table(self, table_name=None, data=None):
        self._validate_data(data)
        columns_sql = ', '.join(
            f'{self._quote_identifier(column)} {self._column_type(column)}'
            for column in data.columns.tolist()
        )
        table_sql = self._qualified_table(table_name)

        with self.engine.begin() as connection:
            connection.execute(
                sqlalchemy.text(f'CREATE SCHEMA IF NOT EXISTS {self._quote_identifier(self.schema)}')
            )
            connection.execute(
                sqlalchemy.text(f'CREATE TABLE IF NOT EXISTS {table_sql} ({columns_sql})')
            )

        print(f'Таблица {self.schema}.{table_name} готова')
        return True

    def insert_into_table(self, table_name=None, data=None):
        self._validate_data(data)
        data = self._normalize_data(data)

        min_date = data['date'].min()
        max_date = data['date'].max()
        columns = data.columns.tolist()
        columns_sql = ', '.join(self._quote_identifier(column) for column in columns)
        placeholders_sql = ', '.join(f':p{i}' for i in range(len(columns)))
        table_sql = self._qualified_table(table_name)

        rows = [
            {f'p{i}': row.get(column) for i, column in enumerate(columns)}
            for row in data.to_dict(orient='records')
        ]

        delete_sql = sqlalchemy.text(
            f'DELETE FROM {table_sql} WHERE "date" BETWEEN :min_date AND :max_date'
        )
        insert_sql = sqlalchemy.text(
            f'INSERT INTO {table_sql} ({columns_sql}) VALUES ({placeholders_sql})'
        )

        with self.engine.begin() as connection:
            connection.execute(delete_sql, {'min_date': min_date, 'max_date': max_date})
            connection.execute(insert_sql, rows)

        print(f'Записано строк: {len(rows)} в {self.schema}.{table_name}')
        return True
