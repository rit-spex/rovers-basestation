import multiprocessing
import multiprocessing.process
import uvicorn
import webview
from fastapi import FastAPI, Response
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse

app = FastAPI()
app.mount("/src", StaticFiles(directory="./rover-code/baseStation/src"), "src")


@app.get("/data")
def test_data():
    return "Got data"


class UvicornServer(multiprocessing.Process):
    def __init__(self, config: uvicorn.Config):
        super().__init__()
        self.server = uvicorn.Server(config=config)
        self.config = config

    def stop(self):
        self.terminate()

    def run(self):
        self.server.run()


if __name__ == "__main__":
    host = "127.0.0.1"
    port = 8000

    config = uvicorn.Config("main:app", host=host, port=port, log_level="debug")
    uvicorn_server = UvicornServer(config)
    uvicorn_server.start()

    webview.create_window("Base Station", url=f"http://{host}:{port}/src/index.html")
    webview.start()
