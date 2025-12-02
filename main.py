from fastapi import FastAPI
import uvicorn


app = FastAPI()



if __name__ == "__main__":
    uvicorn.run("main:app", host="localhost", port=8080, reload=True)

