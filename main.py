from fastapi import FastAPI
from app.routers import system


# start server with "uvicorn main:app --reload"

app = FastAPI()

app.include_router(system.router)


# @app - path operation decorator
# .get - path operation
# '/' - the path
@app.get('/')
def index():
    # path operation function
    return {'data': '123'}
