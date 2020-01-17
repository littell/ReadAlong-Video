
#################
#
# This file provides a (very limited) implementation of
# SVG Animations, enough to calculate the "presentation"/"actual"
# state of the animation at a specific point in time, for a 
# very limited class of SVG documents, for the purposes of
# rendering to a video frame.
#
# Since the SVG animation standard is pretty large, this only
# supports some parts of it that we'll need. 
#
# * It only supports animation elements with single clock-value "begin"
#   and "dur" values; this is for rendering to video so we're not
#   concerned with responding to user events like clicks.  Repetition
#   attributes are supported, as are fill=freeze, but attributes
#   like min and max aren't. Relative clock-values (relative to a 
#   syncbase, like "x.begin+2.0s"), wallclock values, and any other
#   way of specifying time are not supported.  Multiple begin/dur
#   intervals (e.g. begin="0s;2s;4s") are not supported.
#
# * It doesn't support calcMode, keySplines, and other attributes
#   that describe non-linear interpolations.
#
# * It doesn't support additive animation.  (This is possibly worth
#   supporting, it wouldn't be too hard, we're just not using it for anything
#
# * Only animations nested in their target element are supported.  (That is,
#   xlink:href doesn't work.)
#
# * animateColor is not supported (it would be easy to support, but 
#   it's deprecated in any cases)
#
#################

import math
import re
#import svgwrite
from copy import deepcopy
from lxml import etree as et 

NAMESPACE_PREFIX = '{http://www.w3.org/2000/svg}'
ANIMATE_TRANSFORM_TAG = 'animateTransform'
ANIMATE_TRANSFORM_TAGS = [ ANIMATE_TRANSFORM_TAG, NAMESPACE_PREFIX + ANIMATE_TRANSFORM_TAG]
ANIMATE_TAG = 'animate'
ANIMATE_TAGS = [ ANIMATE_TAG, NAMESPACE_PREFIX + ANIMATE_TAG ]
SET_TAG = 'set'
SET_TAGS = [ SET_TAG, NAMESPACE_PREFIX + SET_TAG ]

def parse_time(timestamp):

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

def parse_transform_arg_string(s):
    nums = s.split(" ")
    return [float(n) for n in nums]

NUMBER_SPLITTER = re.compile(r'([-+]?\d*\.?\d+|[-+]?\d+)')

def interpolate_value_token(s1, s2, pos):
    v1, v2 = 0.0, 0.0
    try:
        v1 = float(s1)
        v2 = float(s2)
        return "{:.3f}".format(v1 + pos * (v2 - v1))
    except ValueError:
        if s1 == s2:
            return s1 
        else:
            raise Exception("Cannot interpolate between %s and %s", (s1, s2))


def interpolate_values(s1, s2, pos):

    parts1 = NUMBER_SPLITTER.split(s1)
    parts2 = NUMBER_SPLITTER.split(s2)
    if len(parts1) != len(parts2):
        raise Exception("Cannot interpolate between %s and %s", (s1, s2))

    results = [ interpolate_value_token(t1, t2, pos) 
                    for t1, t2 in zip(parts1, parts2) ]
    return "".join(results)



def interpolate_num_lists(ns1, ns2, pos):
    result = []
    for n1, n2 in zip(ns1, ns2):
        length = n2 - n1 
        result.append(n1 + pos * length)
    return result


def get_time_position(elem, t):
    """ Returns how far along in this animation element is time t, as a
        fraction. For example, if begin=2s and dur=10s, and we're
        at 7s, the result would be 0.5.  
        
        This is for determining the interpolation of values, so it takes 
        into account things like repeatCount="infinite" and fill="freeze".
        E.g. if repeatCount="infinite" in the above situation and we're at
        17, the result would still be 0.5 because that's how far into the 
        second repeat of the animation we are.

        If time t is outside of the animation's duration (including repeats),
        the result is -1.  (The exception to this is fill="freeze", which
        means that the last value of the animation remains as-is, e.g. the 
        rectangle, after moving, stays moved instead of reappearing where 
        it first started.  If time t is after an animation that's frozen,
        then the return value is always 1.0.)
    """

    begin = parse_time(elem.attrib["begin"])
    dur = parse_time(elem.attrib["dur"])
    if t < begin:
        return -1

    time_since_begin = t - begin
    cycles_since_begin = math.floor((t - begin) / dur) + 1
    fill = elem.attrib.get("fill", "")

    if "repeatCount" not in elem.attrib and \
            "repeatDur" not in elem.attrib and \
            time_since_begin > dur:
        return 1.0 if fill == "freeze" else -1

    if "repeatCount" in elem.attrib and elem.attrib["repeatCount"] != "indefinite":
        repeat_count = float(elem.attrib["repeatCount"])
        if cycles_since_begin > repeat_count:
            return 1.0 if fill == "freeze" else -1
    
    if "repeatDur" in elem.attrib and elem.attrib["repeatDur"] != "indefinite":
        repeat_dur = parse_time(elem.attrib["repeatDur"])
        if time_since_begin >= repeat_dur:
            if fill == "freeze":
                return ((repeat_dur - begin) % dur) / dur
            return -1

    time_position = ((t - begin) % dur) / dur
    return time_position

def get_set_at_frame(elem, t):

    attrib_name = elem.attrib.get("attributeName")
    time_position = get_time_position(elem, t)
    if (time_position < 0):
        return attrib_name, ""
    return attrib_name, elem.attrib["to"]

def get_animate_at_frame(elem, t):

    attrib_name = elem.attrib.get("attributeName")
    time_position = get_time_position(elem, t)
    if (time_position < 0):
        return attrib_name, ""

    attrib_from = elem.attrib["from"]
    attrib_to = elem.attrib["to"]

    result = interpolate_values(attrib_from, attrib_to, time_position)
    return attrib_name, result

def get_transform_at_frame(elem, t):

    attrib_name = elem.attrib.get("attributeName", "transform")
    
    assert("type" in elem.attrib)

    transform_type = elem.attrib["type"]

    time_position = get_time_position(elem, t)
    if (time_position < 0):
        return attrib_name, ""

    attrib_from = elem.attrib["from"]
    attrib_to = elem.attrib["to"]

    result = interpolate_values(attrib_from, attrib_to, time_position)
    result = transform_type + "(" + result + ")"

    return attrib_name, result


def get_svg_frame(elem, t):
    """ Gives a static SVG element corresponding to 
        an animated SVG element time t """

    for child in list(elem):
        if child.tag in ANIMATE_TAGS:
            ''' parse the animation elemnet and, if we're at a frame where it's active, 
                change the requested attribute '''

            elem.remove(child)
            attrib_name, value = get_animate_at_frame(child, t)
            if not attrib_name or not value:
                continue
            elem.attrib[attrib_name] = value

        elif child.tag in SET_TAGS:
            ''' same as the above, but a simpler tag '''
            elem.remove(child)
            attrib_name, value = get_set_at_frame(child, t)
            if not attrib_name or not value:
                continue
            elem.attrib[attrib_name] = value

        elif child.tag in ANIMATE_TRANSFORM_TAGS:
            ''' animateTransform elements are slightly more complicated than the above
                because they append to the previous list of transforms, not change them '''
                
            elem.remove(child)
            attrib_name, value = get_transform_at_frame(child, t)

            if not attrib_name or not value:
                continue

            if attrib_name in elem.attrib:
                elem.attrib[attrib_name] += " " + value
            else:
                elem.attrib[attrib_name] = value
        else:
            get_svg_frame(child, t)

    return elem

def get_snapshot(svg, t):
    root = deepcopy(svg.getroot())
    return get_svg_frame(root, t)