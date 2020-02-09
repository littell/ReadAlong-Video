
#################
#
# This file provides a (very limited) implementation of
# SVG Animations, enough to calculate the "presentation"/"actual"
# state of the animation at a specific point in time, for a 
# very limited class of SVG documents, for the purposes of
# rendering to a video frame.
#
# An SVG animation is potentially quite complex, but 
# it mostly consists of declarations of paths through a conceptual space
# (whether that be coordinate space, color space, etc.) that an object or 
# attribute will travel through beginning at a particular start time and
# continuing for a particular duration (and possibly repeating).  Taking
# a "snapshot" of an SVG at a particular point in time is thus mostly 
# a question of interpolation.  
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
#   that describe non-linear interpolations.  The only non-linear
#   interpolations supported are those to get an appropriate interpolation
#   of the path attribute of animateMotion.  (That is to say, if the
#   path specifies a cubic curve, we'll calculate that, rather than, say,
#   do a linear interpolation there.  But if you're animating a color or 
#   something, the only interpolation supported is linear.)
#
# * It doesn't support additive animation.  (This is possibly worth
#   supporting, it wouldn't be too hard, we're just not using it for anything.)
#
# * animateColor is not supported, being deprecated in the SVG standard
#   since v1.1.
#
# Non-supported features due to missing features in the svglib SVG rendering library:
#
# * The "opacity" attribute is unsupported (but fill-opacity and stroke-
#   opacity are). 
#
# * No support for gradients
#
# * Limited support for masking
#
# Non-supported features due to either undocumented missing features in svglib
# or I just can't figure out how to use them properly:
#
# * It doesn't appear that image elements from an external URL (e.g. 
#   a PNG file) actually work in svglib.  If you need raster images, use
#   a base64 string, e.g. xlink:href="data:image/png;base64,iVBORw0..."
#   Currently I can only get PNGs working this way; I don't know if 
#   that's a problem on my side or theirs.
#
# * Visibility attributes do not appear to be supported. Currently, to
#   make an element invisible, we just move it waaaaaay off to the right.
#   Note that this is not a generally-correct solution to SVG visibility,
#   like invisible text is still supposed to be where it is for the general
#   text layout purposes.  But if works for our purposes.
#
# * PNG and GIF transparency do not appear to work.  TIFF 
#   transparency does, however.
#
#################

import math
import re
import logging
from copy import deepcopy
from lxml import etree as et 
from svg.path import parse_path

from util import parse_time

NAMESPACE_PREFIX = '{http://www.w3.org/2000/svg}'
XLINK_NAMESPACE = '{http://www.w3.org/1999/xlink}'
HREF_TAG = XLINK_NAMESPACE + "href"
MPATH_TAG = "mpath"
MPATH_TAGS = [ NAMESPACE_PREFIX + MPATH_TAG, MPATH_TAG ]

ANIMATE_TRANSFORM_TAG = 'animateTransform'
ANIMATE_TRANSFORM_TAGS = [ ANIMATE_TRANSFORM_TAG, NAMESPACE_PREFIX + ANIMATE_TRANSFORM_TAG]
ANIMATE_TAG = 'animate'
ANIMATE_TAGS = [ ANIMATE_TAG, NAMESPACE_PREFIX + ANIMATE_TAG ]
SET_TAG = 'set'
SET_TAGS = [ SET_TAG, NAMESPACE_PREFIX + SET_TAG ]
MOTION_TAG = 'animateMotion'
MOTION_TAGS = [ MOTION_TAG, NAMESPACE_PREFIX + MOTION_TAG ]
ANIMATION_TAGS = ANIMATE_TRANSFORM_TAGS + ANIMATE_TAGS + SET_TAGS + MOTION_TAGS


PATH_CACHE = {}

def parse_path_str(path_str):
    """ Convenience function for path parsing; caches because path parsing
        can be expensive """

    if path_str not in PATH_CACHE:
        try:
            PATH_CACHE[path_str] = parse_path(path_str, 1e-3)
        except:
            logging.error(f"Cannot parse path: {path_str}")
            return None
    return PATH_CACHE[path_str]


NUMBER_SPLITTER = re.compile(r'([-+]?\d*\.?\d+|[-+]?\d+)')

def interpolate_value_token(s1, s2, pos):
    """ If the values are floats, returns the linear interpolation of them
        at position pos.  If they're strings, but the same, returns the string.
        If they're different, raises an exception. """

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
    """ Takes two strings representing values, like "150 150" and "0 0", or
        "rgb(255,255,0)" and "rgb(255,255,100)", and returns an interpolated version
        like "75 75" or "rgb(255, 255, 50)".  Only linear interpolation is supported. """

    parts1 = NUMBER_SPLITTER.split(s1)
    parts2 = NUMBER_SPLITTER.split(s2)
    if len(parts1) != len(parts2):
        raise Exception("Cannot interpolate between %s and %s", (s1, s2))

    results = [ interpolate_value_token(t1, t2, pos) 
                    for t1, t2 in zip(parts1, parts2) ]
    return "".join(results)


def xpath_id(svg, id):
    """ Convenience function for finding an xml element with a particular id """

    query = './/*[@id="' + id + '"]'
    targets = svg.xpath(query)
    if not targets:
        raise Exception("No elements found with id=%s" % id)
    if len(targets) > 1:
        raise Exception("Multiple elements found with id=%s" % id)
    return targets[0]


class Animator:
    """ Abstract base class of the various animator objects, which interpret animation
        tags like <animate>, <animateTransform>, etc.  Handles parsing of the basic attributes
        and time calculations that are common to all the animation tags. """

    def __init__(self, elem, target_id=""):
        self.elem = elem
        self.begin = parse_time(elem.attrib["begin"])
        self.dur = parse_time(elem.attrib["dur"])
        self.fill = self.elem.attrib.get("fill", "")

        if HREF_TAG in elem.attrib and elem.attrib[HREF_TAG].startswith("#"):
            self.target_id = elem.attrib[HREF_TAG].lstrip("#")
        else:
            self.target_id = target_id 

    def get_target(self, svg, ):
        return xpath_id(svg, self.target_id)

    def get_time_position(self, t):
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

        time_since_begin = t - self.begin
        if time_since_begin < 0 or self.dur <= 0.0:
            return -1

        cycles_since_begin = math.floor(time_since_begin / self.dur) + 1
        

        if "repeatCount" not in self.elem.attrib and \
                "repeatDur" not in self.elem.attrib and \
                time_since_begin > self.dur:
            return 1.0 if self.fill == "freeze" else -1

        if "repeatCount" in self.elem.attrib and self.elem.attrib["repeatCount"] != "indefinite":
            repeat_count = float(self.elem.attrib["repeatCount"])
            if cycles_since_begin > repeat_count:
                return 1.0 if self.fill == "freeze" else -1
        
        if "repeatDur" in self.elem.attrib and self.elem.attrib["repeatDur"] != "indefinite":
            repeat_dur = parse_time(self.elem.attrib["repeatDur"])
            if time_since_begin >= repeat_dur:
                if self.fill == "freeze":
                    return ((repeat_dur - self.begin) % self.dur) / self.dur
                return -1

        time_position = (time_since_begin % self.dur) / self.dur
        return time_position

class TransformAnimator(Animator):
    """ Interprets the <animateTransform> element """
    def __init__(self, elem, target_id):
        Animator.__init__(self, elem, target_id)
        self.attrib_name = elem.attrib["attributeName"]
    
        self.attrib_from = elem.attrib["from"]
        self.attrib_to = elem.attrib["to"]
        self.transform_type = elem.attrib["type"]

    def apply(self, svg, t):

        target = self.get_target(svg)

        time_position = self.get_time_position(t)
        if (time_position < 0):
            return

        result = interpolate_values(self.attrib_from, self.attrib_to, time_position)
        result = self.transform_type + "(" + result + ")"

        if self.attrib_name in target.attrib:
            target.attrib[self.attrib_name] += " " + result
        else:
            target.attrib[self.attrib_name] = result

class MotionAnimator(Animator):
    """ Interprets the <animateMotion> element """
    def __init__(self, elem, target_id):
        Animator.__init__(self, elem, target_id)

        self.path = None
        self.path_id = ""

        if "path" in elem.attrib:
            self.path = parse_path_str(elem.attrib["path"])
        else:
            for child in elem:
                if child.tag not in MPATH_TAGS:
                    continue
                if HREF_TAG not in child.attrib:
                    continue 
                self.path_id = child.attrib[HREF_TAG].lstrip("#")
                break

        self.attrib_rotate = elem.attrib.get("rotate", "")

    
    def apply(self, svg, t):
        target = self.get_target(svg)

        time_position = self.get_time_position(t)
        if (time_position < 0):
            return

        if self.path:
            path = self.path
        else:
            path_node = xpath_id(svg, self.path_id)
            if "d" not in path_node.attrib:
                raise Exception("Target of mpath href must have a 'd' attribute.")
            path = parse_path_str(path_node.attrib["d"])
        
        point = path.point(time_position)

        if target.tag == "circle":
            x_label, y_label = "cx", "cy"
        else:
            x_label, y_label = "x", "y"

        if "data-original-x" not in target.attrib:
            target.attrib["data-original-x"] = target.attrib.get(x_label, 0.0)
            target.attrib["data-original-y"] = target.attrib.get(y_label, 0.0)

        current_x = float(target.attrib.get("data-original-x", 0.0))
        current_y = float(target.attrib.get("data-original-y", 0.0))
        value_x = "{:.3f}".format(current_x + point.real)
        value_y = "{:.3f}".format(current_y + point.imag)

        #target.attrib[x_label] = value_x
        #target.attrib[y_label] = value_y

        translate_str = f"translate({value_x} {value_y})"
        
        target.attrib["data-motion-translate"] = translate_str

        #if "transform" in target.attrib:
        #    target.attrib["transform"] += " " + translate_str
        #else:
        #    target.attrib["transform"] = translate_str

        #print(target.attrib["transform"])

        if self.attrib_rotate in ["auto", "auto-reverse"]:
            if time_position > 0.999:  # don't want nonsense values if we're at the end,
                current_point = path.point(0.999)            # so back up a weee bit
                next_point = point
            else:
                current_point = point
                next_point = path.point(time_position + 0.001)
            angle = math.atan2(next_point.imag - current_point.imag, next_point.real - current_point.real)
            angle = math.degrees(angle)
            if self.attrib_rotate == "auto-reverse":
                angle += 180.0
            
            rotate_str = "rotate(" + "{:.3f}".format(angle) + "," + value_x + "," + value_y + ")"
            #if "transform" in target.attrib:
            #    target.attrib["transform"] += " " + rotate_str
            #else:
            #    target.attrib["transform"] = rotate_str

            target.attrib["data-motion-rotate"] = rotate_str

class StaticValueAnimator(Animator):
    """ Interprets the <set> element """

    def __init__(self, elem, target_id):
        Animator.__init__(self, elem, target_id)
        self.attrib_name = elem.attrib.get("attributeName")
        self.attrib_to = elem.attrib["to"]

    def apply(self, svg, t):

        target = self.get_target(svg)
        
        time_position = self.get_time_position(t)
        if (time_position < 0):  # animation doesn't apply right now
            return
        target.attrib[self.attrib_name] = self.attrib_to

        
class ValueAnimator(Animator):
    """ Interprets the <animate> element """

    def __init__(self, elem, target_id):
        Animator.__init__(self, elem, target_id)
        self.attrib_name = elem.attrib.get("attributeName")
        self.attrib_from = elem.attrib["from"]
        self.attrib_to = elem.attrib["to"]
        
    def apply(self, svg, t):

        target = self.get_target(svg)

        time_position = self.get_time_position(t)
        if (time_position < 0): # animation doesn't apply right now
            return
        value = interpolate_values(self.attrib_from, self.attrib_to, time_position)
        target.attrib[self.attrib_name] = value

def make_animator(elem, target):

    if elem.tag in ANIMATE_TAGS:
        return ValueAnimator(elem, target)
    if elem.tag in SET_TAGS:
        return StaticValueAnimator(elem, target)
    if elem.tag in MOTION_TAGS:
        return MotionAnimator(elem, target)
    if elem.tag in ANIMATE_TRANSFORM_TAGS:
        return TransformAnimator(elem, target)

    raise Exception("Invalid tag for animation: %s" % elem.tag)

NUM_IDS = 0

def get_animators(elem):
    global NUM_IDS

    animators = []
    

    for child in list(elem):
        if child.tag in ANIMATION_TAGS: 
            if "id" not in elem.attrib:
                elem.attrib["id"] = "svgSnapshotElement" + str(NUM_IDS)
                NUM_IDS += 1
            elem.remove(child)
            animator = make_animator(child, elem.attrib["id"])
            animators.append(animator)
        else:
            animators += get_animators(child)

    return animators


def motion_compile(elem):

    if "data-motion-translate" in elem.attrib:
        elem.attrib["transform"] = elem.attrib["data-motion-translate"] + \
                                " " +  elem.attrib.get("transform", "") 
    
    if "data-motion-rotate" in elem.attrib:
        elem.attrib["transform"] = elem.attrib["data-motion-rotate"] + \
                                " " +  elem.attrib.get("transform", "") 

    for child in elem:
        motion_compile(child)

class SnapshotSVG:

    def __init__(self, svg):
        self.svg = svg if isinstance(svg, et._Element) else svg.getroot()
        self.animators = get_animators(self.svg)
        self.animators = sorted(self.animators, key=lambda a:a.begin)

    def __getitem__(self, t):    
        """ Gives a static SVG element corresponding to 
        an animated SVG element time t """
        result = deepcopy(self.svg)
        for animator in self.animators:
            animator.apply(result, t)
        motion_compile(result)
        return result