from fastapi import FastAPI
from app.routers import apps, bitcoin, system


# start server with "uvicorn main:app --reload"

app = FastAPI()

app.include_router(apps.router)
app.include_router(bitcoin.router)
app.include_router(system.router)


# @app - path operation decorator
# .get - path operation
# '/' - the path
@app.get('/')
def index():
    # path operation function
    return {'data': '123'}
