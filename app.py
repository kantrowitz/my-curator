from flask import Flask

Configuration.load()

app = Flask(__name__)

if __name__ == "__main__":
    app.run()

