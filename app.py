from flask import Flask
from model import Configuration


Configuration.load()

app = Flask(__name__)

if __name__ == "__main__":
    app.run()

