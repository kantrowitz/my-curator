from flask import Flask
from model import (
    Configuration, 
    DisplayItem
)


Configuration.load()

app = Flask(__name__)

if __name__ == "__main__":
    app.run()


@app.route('/all_items')
def all_display_items():
    return DisplayItem.get_all_items()

