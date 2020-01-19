
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
#   that describe non-linear interpolations.  The only non-linear
#   interpolations supported are those to get an appropriate interpolation
#   of the path attribute of animateMotion.  (That is to say, if the
#   path specifies a cubic curve, we'll calculate that, rather than, say,
#   do a linear interpolation there.  But if you're animating a color or 
#   something, the only interpolation supported is linear.)
#
# * It doesn't support additive animation.  (This is possibly worth
#   supporting, it wouldn't be too hard, we're just not using it for anything
#
# * xlink:href-type attributes aren't resolved, so only animations nested 
#   in their target element are supported, and for animateMotion the path 
#   needs to be in the "path" attribute.  
#
# * animateColor is not supported, being deprecated in the SVG standard
#   since v1.1.
#
#################

import math
import re
#import svgwrite
import numpy as np
from copy import deepcopy
from lxml import etree as et 
from svg.path import parse_path

NAMESPACE_PREFIX = '{http://www.w3.org/2000/svg}'
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
    if path_str not in PATH_CACHE:
        PATH_CACHE[path_str] = parse_path(path_str, 1e-3)
    return PATH_CACHE[path_str]


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


class Animator:

    def __init__(self, elem, target_id=""):
        self.elem = elem
        self.target_id = target_id 
        self.begin = parse_time(elem.attrib["begin"])
        self.dur = parse_time(elem.attrib["dur"])
        self.fill = self.elem.attrib.get("fill", "")

    def get_target(self, svg):
        
        query = './/*[@id="' + self.target_id + '"]'
        targets = svg.xpath(query)
        if not targets:
            raise Exception("No elements found with id=%s" % self.target_id)
        if len(targets) > 1:
            raise Exception("Multiple elements found with id=%s" % self.target_id)
        return targets[0]

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
        if time_since_begin < 0:
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

    def __init__(self, elem, target_id):
        Animator.__init__(self, elem, target_id)

        if "path" not in elem.attrib:
            raise Exception("Only animateMotion elements with a path attribute are currently supported.")
    
        self.path = parse_path_str(elem.attrib["path"])
        self.attrib_rotate = elem.attrib.get("rotate", "")

    
    def apply(self, svg, t):
        target = self.get_target(svg)

        time_position = self.get_time_position(t)
        if (time_position < 0):
            return

        point = self.path.point(time_position)
        current_x = float(target.attrib.get("x", 0.0))
        current_y = float(target.attrib.get("y", 0.0))
        value_x = "{:.3f}".format(current_x + point.real)
        value_y = "{:.3f}".format(current_y + point.imag)
        target.attrib["x"] = value_x
        target.attrib["y"] = value_y

        if self.attrib_rotate in ["auto", "auto-reverse"]:
            if time_position > 0.999:  # don't want nonsense values if we're at the end,
                current_point = self.path.point(0.999)            # so back up a weee bit
                next_point = point
            else:
                current_point = point
                next_point = self.path.point(time_position + 0.001)
            angle = math.atan2(next_point.imag - current_point.imag, next_point.real - current_point.real)
            angle = math.degrees(angle)
            if self.attrib_rotate == "auto-reverse":
                angle += 180.0
            
            rotate_str = "rotate(" + "{:.3f}".format(angle) + "," + value_x + "," + value_y + ")"
            if "transform" in target.attrib:
                target.attrib["transform"] += " " + rotate_str
            else:
                target.attrib["transform"] = rotate_str

class StaticValueAnimator(Animator):

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
    """ Gives a static SVG element corresponding to 
        an animated SVG element time t """
    global NUM_IDS

    animators = []
    
    if "id" not in elem.attrib:
        elem.attrib["id"] = "svgSnapshotElement" + str(id)

    for child in list(elem):
        if child.tag in ANIMATION_TAGS:
            elem.remove(child)
            animator = make_animator(child, elem.attrib["id"])
            animators.append(animator)
        else:
            animators += get_animators(child)

    return animators

class SnapshotSVG:

    def __init__(self, svg):
        self.svg = svg 
        self.animators = get_animators(svg.getroot())

    def __getitem__(self, t):
        result = deepcopy(self.svg.getroot())
        for animator in self.animators:
            animator.apply(result, t)
        return result