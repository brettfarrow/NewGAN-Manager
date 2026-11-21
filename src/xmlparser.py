import re
from xml.sax.saxutils import unescape

_ENTITIES = {"&quot;": '"', "&apos;": "'"}
_COMMENT_REGEX = re.compile(r'<!--.*?-->', re.DOTALL)
# one face mapping: <record from="Ethnicity/Image" to="graphics/pictures/person/r-UID/portrait"/>
_RECORD_REGEX = re.compile(r'<record\s+from="([^"]*)"\s+to="[^"]*?r-([0-9]+)/[^"]*"\s*/>')


def _read_records(path):
    """Return the (image path, UID) pair of every face mapping in a config.xml."""
    with open(path, 'r', encoding="UTF-8", errors="replace") as xml:
        content = xml.read()
    # mappings that are commented out are not active and must not be picked up
    if "<!--" in content:
        content = _COMMENT_REGEX.sub('', content)
    return [(unescape(imgpath, _ENTITIES).strip() if "&" in imgpath else imgpath.strip(), uid)
            for imgpath, uid in _RECORD_REGEX.findall(content)]


class XML_Parser:
    def __init__(self):
        pass

    def parse_xml(self, path):
        result_data = {}
        for imgpath, uid in _read_records(path):
            # the image is the last path component, everything before it is the folder
            eth, sep, img = imgpath.rpartition("/")
            if not sep or not img:
                continue
            result_data[uid] = {"ethnicity": eth, "image": img}
        return result_data

    def get_imgpath_from_uid(self, path, uid):
        uid = str(uid).strip()
        if not uid.isdigit():
            return None
        with open(path, 'r', encoding="UTF-8", errors="replace") as xml:
            content = xml.read()
        # Only look at the records that mention the UID instead of parsing the
        # whole file. Like in parse_xml, the last mapping of a UID wins.
        needle = "r-"+uid+"/"
        pos = content.rfind(needle)
        while pos != -1:
            start = content.rfind("<record", 0, pos)
            commented = content.rfind("<!--", 0, pos) > content.rfind("-->", 0, pos)
            if start != -1 and not commented:
                record = _RECORD_REGEX.match(content, start)
                if record and record.group(2) == uid and record.end() > pos:
                    imgpath = record.group(1)
                    if "&" in imgpath:
                        imgpath = unescape(imgpath, _ENTITIES)
                    return imgpath.strip()
            pos = content.rfind(needle, 0, pos)
        return None
