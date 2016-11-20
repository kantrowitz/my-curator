import flask
from model import (
    get_one,
    Configuration,
    production_session,
    DisplayItem
)

class Conf(object):
    def __init__(self):
        Configuration.load()
        self.db = production_session()

Conf = Conf()

from flask import Flask
app = Flask(__name__)

if __name__ == "__main__":
    app.run()

@app.route('/all_items')
def all_display_items():
    return flask.jsonify(**DisplayItem.all(Conf.db))

@app.route('/display_item/<major>/<minor>', methods=['GET'])
def get_collection(major, minor):
    item = get_one(
        Conf.db, DisplayItem,
        beacon_major_id=int(major), beacon_minor_id=int(minor)
    )
    return flask.jsonify(**item.json)

