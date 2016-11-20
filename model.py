import contextlib
import json
import logging # Make sure logging is set up properly.
import os
import warnings

from nose.tools import set_trace

from sqlalchemy.orm.session import Session
# from sqlalchemy.engine.url import URL
from sqlalchemy import exc as sa_exc
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import (
    relationship,
    sessionmaker,
)
from sqlalchemy.orm.exc import (
    NoResultFound,
    MultipleResultsFound,
)
from sqlalchemy.ext.associationproxy import (
    association_proxy,
)
from sqlalchemy.exc import (
    IntegrityError
)
from sqlalchemy import (
    create_engine,
    Column,
    ForeignKey,
    Integer,
    String,
    Unicode,
)


Base = declarative_base()


'''
Make postgres database with something like:
CREATE USER amnh_user with password 'test';
simplified_circulation_dev=# create database my_curator_test;
simplified_circulation_dev=# grant all privileges on database my_curator_test to amnh_user;

heroku passwd: amnh_user:abc@
https://amnh-curator.herokuapp.com/ | https://git.heroku.com/amnh-curator.git
'''

def production_session():
    url = Configuration.database_url()
    if url.startswith('"'):
        url = url[1:]
    logging.debug("Database url: %s", url)
    return SessionManager.session(url)


@contextlib.contextmanager
def temp_config(new_config=None, replacement_classes=None):
    old_config = Configuration.instance
    replacement_classes = replacement_classes or [Configuration]
    if new_config is None:
        new_config = copy.deepcopy(old_config)
    try:
        for c in replacement_classes:
            c.instance = new_config
        yield new_config
    finally:
        for c in replacement_classes:
            c.instance = old_config


def get_one(db, model, on_multiple='error', **kwargs):
    q = db.query(model).filter_by(**kwargs)
    try:
        return q.one()
    except MultipleResultsFound, e:
        if on_multiple == 'error':
            raise e
        elif on_multiple == 'interchangeable':
            # These records are interchangeable so we can use
            # whichever one we want.
            #
            # This may be a sign of a problem somewhere else. A
            # database-level constraint might be useful.
            q = q.limit(1)
            return q.one()
    except NoResultFound:
        return None


def get_one_or_create(db, model, create_method='',
                      create_method_kwargs=None,
                      **kwargs):
    one = get_one(db, model, **kwargs)
    if one:
        return one, False
    else:
        __transaction = db.begin_nested()
        try:
            if 'on_multiple' in kwargs:
                # This kwarg is supported by get_one() but not by create().
                del kwargs['on_multiple']
            obj = create(db, model, create_method, create_method_kwargs, **kwargs)
            __transaction.commit()
            return obj
        except IntegrityError, e:
            logging.info(
                "INTEGRITY ERROR on %r %r, %r: %r", model, create_method_kwargs, 
                kwargs, e)
            __transaction.rollback()
            return db.query(model).filter_by(**kwargs).one(), False


def create(db, model, create_method='',
           create_method_kwargs=None,
           **kwargs):
    kwargs.update(create_method_kwargs or {})
    created = getattr(model, create_method, model)(**kwargs)
    db.add(created)
    db.flush()
    return created, True



class Configuration(object):
    INTEGRATIONS = "integrations"
    DATA_DIRECTORY = "data_directory"
    DATABASE_INTEGRATION = "Postgres"
    DATABASE_PRODUCTION_URL = "production_url"
    DATABASE_TEST_URL = "test_url"

    log = logging.getLogger("Configuration file loader")

    instance = None

    @classmethod
    def database_url(cls, test=False):
        if test:
            key = cls.DATABASE_TEST_URL
        else:
            key = cls.DATABASE_PRODUCTION_URL
        return cls.integration(cls.DATABASE_INTEGRATION)[key]

        
    @classmethod
    def data_directory(cls):
        return cls.get(cls.DATA_DIRECTORY)


    @classmethod
    def get(cls, key, default=None):
        if not cls.instance:
            raise ValueError("No configuration file loaded!")
        return cls.instance.get(key, default)


    @classmethod
    def integration(cls, name, required=False):
        """Find an integration configuration by name."""
        integrations = cls.get(cls.INTEGRATIONS, {})
        v = integrations.get(name, {})
        if not v and required:
            raise ValueError(
                "Required integration '%s' was not defined! I see: %r" % (
                    name, ", ".join(sorted(integrations.keys()))
                )
            )
        return v


    @classmethod
    def load(cls):
        #cfv = 'SIMPLIFIED_CONFIGURATION_FILE'
        #if not cfv in os.environ:
        #    print "CannotLoadConfiguration: No configuration file defined in %s." % cfv

        config_path = 'config.json'
        try:
            cls.log.info("Loading configuration from %s", config_path)
            configuration = cls._load(open(config_path).read())
        except Exception, e:
            print "CannotLoadConfiguration: Error loading configuration file %s: %s" % (
                    config_path, e)
            
        cls.instance = configuration
        return configuration


    @classmethod
    def _load(cls, str):
        lines = [x for x in str.split("\n") if not x.strip().startswith("#")]
        try:
            result = json.loads("\n".join(lines))
        except Exception, e:
            print "CannotLoadConfiguration: Error loading configuration file %s: %s" % (e, lines)

        return result

class ItemCollection(Base):
    """ Linker for many-to-many relationship between display items and their 
    associated collection (curated experiences). """
    __tablename__ = 'items_collections'
    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey('display_items.id'), index=True)
    collection_id = Column(Integer, ForeignKey('collections.id'), index=True)

    @classmethod
    def from_collection(cls, collection):
        item_coll = ItemCollection()
        item_coll.collection = collection
        return item_coll



class Collection(Base):
    """ A curated experience, involving a bunch of items.  """
    __tablename__ = 'collections'
    id = Column(Integer, primary_key=True)
    name = Column(Unicode)
    curator = Column(Unicode)
    items = association_proxy('item_collections', 'display_item')
    item_collections = relationship("ItemCollection", backref="collection", cascade="all, delete, delete-orphan")



class DisplayItem(Base):
    """
    An item on display, s.a. a book, an item of dress, a photograph, etc..
    """
    __tablename__ = 'display_items'
    id = Column(Integer, primary_key=True)
    beacon_major_id = Column(Integer, index=True)
    beacon_minor_id = Column(Integer, index=True)

    title = Column(Unicode, index=True)
    cover_image = Column(Unicode)

    # an Item can have any number of downloads or streams associated with it.
    media_resources = relationship("MediaResource", backref="display_item")
    # an Item belongs to a curated experience
    collections = association_proxy('item_collections', 'collection', creator=ItemCollection.from_collection)
    item_collections = relationship("ItemCollection", backref="display_item", cascade="all, delete, delete-orphan")

    @classmethod
    def get_all_items(cls):
        items = {}
        items['a'] = 'b'
        set_trace()
        items_string = json.dumps(items)
        json_dict = json.loads(items_string)
        return items_string



class MediaResource(Base):
    """
    A pdf, epub, jpeg, streamed movie, etc..
    """
    __tablename__ = 'media_resources'
    id = Column(Integer, primary_key=True)
    display_item_id = Column(Integer, ForeignKey('display_items.id'), index=True, nullable=False)

    # The name / title that identifies the media resource.
    title = Column(Unicode)

    # A snippet of text from the curator to contribute to the broader story.
    snippet = Column(Unicode)

    # The human-readable URL where this information can be found
    direct_url = Column(Unicode)

    # A longer description of the item (from the source)
    description = Column(Unicode)

    @property
    def json(self):
        return dict(
            title=self.title,
            snippet=self.snippet,
            description=self.description,
            url=self.direct_url
        )

class FulfillmentInfo(object):
    """A record of an attempt to download a media object. """

    def __init__(self, identifier, content_link, content_type):
        """      
        :param identifier Item's unique id.
        :param content_link Either URL to download ACSM file from or URL to streaming content.
        :param content_type Media type of the book version we're getting.  
        """

        self.identifier = identifier
        self.content_link = content_link
        self.content_type = content_type
    


class SessionManager(object):

    # Materialized views need to be created and indexed from SQL
    # commands kept in files. This dictionary maps the views to the
    # SQL files.

    engine_for_url = {}

    @classmethod
    def engine(cls, url=None):
        url = url or Configuration.database_url()
        return create_engine(url, echo=False)

    @classmethod
    def sessionmaker(cls, url=None):
        engine = cls.engine(url)
        return sessionmaker(bind=engine)

    @classmethod
    def initialize(cls, url):
        if url in cls.engine_for_url:
            engine = cls.engine_for_url[url]
            return engine, engine.connect()

        engine = cls.engine(url)
        Base.metadata.create_all(engine)

        base_path = os.path.split(__file__)[0]
        resource_path = os.path.join(base_path, "files")

        connection = None

        if not connection:
            connection = engine.connect()

        if connection:
            connection.close()

        cls.engine_for_url[url] = engine
        return engine, engine.connect()

    @classmethod
    def session(cls, url):
        engine = connection = 0
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=sa_exc.SAWarning)
            engine, connection = cls.initialize(url)
        session = Session(connection)
        cls.initialize_data(session)
        session.commit()
        return session

    @classmethod
    def initialize_data(cls, session):
        pass
