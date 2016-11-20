import re
import requests
from lxml import etree
from nose.tools import set_trace

from model import (
    get_one_or_create,
    MediaResource,
)

class XEAC(object):

    URL = 'http://data.library.amnh.org:8082/orbeon/xeac/id/amnh'

    PERSON_ENTITY = 'p'
    CORPORATION_ENTITY = 'c'

    PERSON_TYPE               = 1
    EXPEDITION_TYPE           = 2
    DEPARTMENT_TYPE           = 3
    PERMANENT_HALL_TYPE       = 4
    TEMPORARY_EXPEDITION_TYPE = 5

    @classmethod
    def get_resource(cls, _db, identifier, display_item):
        url = cls.URL + identifier + '.xml'
        response = requests.get(url)
        if not response.status_code == 200:
            raise ValueError("Item %s could not be found" % identifier)

        root = etree.fromstring(response.content)
        ns = { 'item' : root.nsmap[None] }
        item = root.find('item:cpfDescription', namespaces=ns)

        title = cls.get_name(item, ns)
        description = cls.get_description(item, ns)
        direct_url = unicode(cls.URL + identifier)
        return get_one_or_create(
            _db, MediaResource,
            title=title,
            description=description,
            direct_url=direct_url,
            display_item=display_item
        )

    @classmethod
    def search_tag(cls, tag_list, ns_key='item'):
        return '/'.join([ns_key+':'+tag for tag in tag_list])

    @classmethod
    def get_name(cls, item, ns):
        name_tag = cls.search_tag(['identity', 'nameEntry[@scriptCode="Latn"]', 'part'])
        name = item.findall(name_tag, namespaces=ns)[-2].text
        return unicode(name)

    @classmethod
    def get_description(cls, item, ns):
        desc_tag = cls.search_tag(['description', 'biogHist'])
        parts = [t.text for t in item.find(desc_tag, namespaces=ns).getchildren()]
        # Remove whitespace
        parts = [p for p in parts if p and p.strip()]
        return unicode("\n\n".join(parts))
