from setuptools import setup

setup(
    name="avito_api",
    version="0.1",
    py_modules=["Avito_Api", "to_postgresql"],
    install_requires=[
        "pandas",
        "requests",
        "sqlalchemy",
        "psycopg2-binary",
    ],
)
