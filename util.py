import os
from lxml import etree as et

def ensure_dirs(path):
    dirname = os.path.dirname(path)
    if dirname and not os.path.exists(dirname):
        os.makedirs(dirname)

def save_xml(output_path, xml):
    ensure_dirs(output_path)
    with open(output_path, "wb") as fout:
        fout.write(et.tostring(xml, encoding="utf-8", pretty_print = True,
                                  xml_declaration=True))
        fout.write(u'\n'.encode('utf-8'))

        
def xpath_default(xml, query, default_namespace_prefix="i"):
    nsmap = xml.nsmap if hasattr(xml, "nsmap") else xml.getroot().nsmap
    nsmap = dict(((x, y) if x else (default_namespace_prefix, y))
                 for (x, y) in nsmap.items())
    for e in xml.xpath(query, namespaces=nsmap):
        yield e
        
def parse_time(timestamp):
    """ Parses timestamps like 12:34.56 and 2s into seconds """

    if ":" in timestamp:
        parts = timestamp.split(":")
        result = float(parts[-1])
        if len(parts) >= 2:
            result += float(parts[-2]) * 60
        if len(parts) >= 3:
            result += float(parts[-3]) * 3600 
        return result
    elif timestamp.endswith("s"):
        return float(timestamp[:-1])
    elif timestamp.endswith("ms"):
        return float(timestamp[:-2]) / 1000
    elif timestamp.endswith("min"):
        return float(timestamp[:-3]) * 60
    elif timestamp.endswith("h"):
        return float(timestamp[:-1]) * 3600
    return float(timestamp)
