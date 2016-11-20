from datetime import (
    datetime,
    timedelta,
)

from nose.tools import (
    eq_, 
    assert_raises,
    assert_raises_regexp,
    set_trace,
)

from model import (
    Collection, 
    Configuration, 
    DisplayItem,
    FulfillmentInfo, 
    get_one_or_create,
    ItemCollection, 
    MediaResource, 
    production_session,
    SessionManager, 
    temp_config, 
)

import logging 
import mock
import model
import os
import shutil
import tempfile
#os.environ['TESTING'] = 'true'

from sqlalchemy.orm.session import Session
from sqlalchemy.ext.declarative import declarative_base


Configuration.load()
Base = declarative_base()


def package_setup():
    """Make sure the database schema is initialized and initial
    data is in place.
    """
    engine, connection = DatabaseTest.get_database_connection()

    # First, recreate the schema.
    #
    # Base.metadata.drop_all(connection) doesn't work here, so we
    # approximate by dropping everything except the materialized
    # views.
    for table in reversed(Base.metadata.sorted_tables):
        if not table.name.startswith('mv_'):
            engine.execute(table.delete())

    Base.metadata.create_all(connection)

    # Initialize basic database data needed by the application.
    _db = Session(connection)
    SessionManager.initialize_data(_db)
    _db.commit()
    connection.close()
    engine.dispose()


class DatabaseTest(object):

    engine = None
    connection = None

    @classmethod
    def get_database_connection(cls):
        url = Configuration.database_url(test=True)
        engine, connection = SessionManager.initialize(url)

        return engine, connection

    @classmethod
    def setup_class(cls):
        # Initialize a temporary data directory.
        cls.engine, cls.connection = cls.get_database_connection()
        cls.old_data_dir = Configuration.data_directory
        cls.tmp_data_dir = tempfile.mkdtemp(dir="/tmp")
        Configuration.instance[Configuration.DATA_DIRECTORY] = cls.tmp_data_dir

        os.environ['TESTING'] = 'true'

    @classmethod
    def teardown_class(cls):
        # Destroy the database connection and engine.
        cls.connection.close()
        cls.engine.dispose()

        if cls.tmp_data_dir.startswith("/tmp"):
            logging.debug("Removing temporary directory %s" % cls.tmp_data_dir)
            shutil.rmtree(cls.tmp_data_dir)
        else:
            logging.warn("Cowardly refusing to remove 'temporary' directory %s" % cls.tmp_data_dir)

        Configuration.instance[Configuration.DATA_DIRECTORY] = cls.old_data_dir
        if 'TESTING' in os.environ:
            del os.environ['TESTING']

    def setup(self):
        # Create a new connection to the database.
        self._db = Session(self.connection)
        self.transaction = self.connection.begin_nested()

        # Start with a high number so it won't interfere with tests that search for an age or grade
        self.counter = 2000

        self.time_counter = datetime(2014, 1, 1)
        self.isbns = ["9780674368279", "0636920028468", "9781936460236"]
        #self.search_mock = mock.patch(model.__name__ + ".ExternalSearchIndex", DummyExternalSearchIndex)
        #self.search_mock.start()

        # TODO:  keeping this for now, but need to fix it bc it hits _isbn, 
        # which pops an isbn off the list and messes tests up.  so exclude 
        # _ functions from participating.
        # also attempt to stop nosetest showing docstrings instead of function names.
        #for name, obj in inspect.getmembers(self):
        #    if inspect.isfunction(obj) and obj.__name__.startswith('test_'):
        #        obj.__doc__ = None


    def teardown(self):
        # Close the session.
        self._db.close()

        # Roll back all database changes that happened during this
        # test, whether in the session that was just closed or some
        # other session.
        self.transaction.rollback()
        #self.search_mock.stop()


    @property
    def _id(self):
        self.counter += 1
        return self.counter



class DummyHTTPClient(object):

    def __init__(self):
        self.responses = []
        self.requests = []

    def queue_response(self, response_code, media_type="text/html",
                       other_headers=None, content=''):
        headers = {}
        if media_type:
            headers["content-type"] = media_type
        if other_headers:
            for k, v in other_headers.items():
                headers[k.lower()] = v
        self.responses.append((response_code, headers, content))

    def do_get(self, url, headers, **kwargs):
        self.requests.append(url)
        return self.responses.pop()



class MockRequestsResponse(object):
    """A mock object that simulates an HTTP response from the
    `requests` library.
    """
    def __init__(self, status_code, headers={}, content=None, url=None):
        self.status_code = status_code
        self.headers = headers
        self.content = content
        self.url = url or "http://url/"

    def json(self):
        return json.loads(self.content)

    @property
    def text(self):
        return self.content.decode("utf8")



class DisplayItemTest(DatabaseTest):

    def test_create_item(self):
        beet_beacon_major_id = '65370'
        beet_beacon_minor_id = '49339'
        beet_beacon_title = 'Beet Beacon'

        lemon_beacon_major_id = '48448'
        lemon_beacon_minor_id = '18544'
        lemon_beacon_title = 'Lemon Tart Beacon'

        item, made_new = get_one_or_create(
            self._db, DisplayItem, create_method_kwargs=dict(
                beacon_major_id=beet_beacon_major_id,
                beacon_minor_id=beet_beacon_minor_id,
                ), id=self._id
        )
        eq_(True, made_new)

        collection, made_new = get_one_or_create(
            self._db, Collection, create_method_kwargs=dict(
                name="Cool Books",
                curator="Jane Curator",
                ), id=self._id
        )
        eq_(True, made_new)

        item.collections.append(collection)
        eq_(collection.id, item.collections[0].id)





