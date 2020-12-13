from lxml import etree as et
#import base64
import unicodedata 
import math
import logging
import argparse

from util import save_xml, parse_time, xpath_default, load_json
from svglib.svglib import _registered_fonts 

from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth, getAscent
from reportlab.pdfbase.ttfonts import TTFont
registerFont(TTFont('NotoSans','./fonts/Noto_Sans_400.ttf'))
_registered_fonts['NotoSans'] = True

registerFont(TTFont('NunitoSemiBold','./fonts/nunito/Nunito-SemiBold.ttf'))
_registered_fonts['NunitoSemiBold'] = True

###################################################################################################
#
# tei_to_svg.py
#
# This module converts the TEI output of ReadAlongs (e.g. the XML with <s>, <w> etc. tags)
# into an SVG animation.
#
# I think this shouldn't be seen as a long-term "right thing to do" with the video component
# of the project; this is still very brittle and involves things like specifying colors, sizes,
# margins, etc. by editing JSON configuration files.  Even if you *can* do that, it's not ideal:
# video rendering can take a long time, and it's annoying to completely re-render the project to 
# see the results of changing the highlight color a little bit.
# 
# Rather, I see the future of the video component as being more tied to a WYSIWYG interface, in which 
# the user is entering/coloring/laying-out the text from the beginning, the client sends that information 
# (including all visual information) to the alignment backend, and the alignment backend just responds 
# with the necessary animation commands to animate the user's visuals appropriately in time to the audio.
#
##################################################################################################




# alternative way to get font metric information, albeit very
# indirectly.  keeping it here as a backup, because I've seen rumors that
# the svglib/reportlab metrics get things wrong for non-Latin/Cyrillic
# writing systems.

#from PIL import Image, ImageFont, ImageDraw
#FONT = ImageFont.truetype("arial.ttf", 64)

#print(width, height)
#im = Image.new("RGBA", (width, height), (0, 0, 0))
#draw = ImageDraw.Draw(im)
#draw.text((0, 0), 'A', (255, 255, 255), font=font)
#im.show('charimg')

from svg.path import parse_path

def get_angle_from_path(path_str, t1, t2):
    path = parse_path(path_str)
    p1 = path.point(t1)
    p2 = path.point(t2)
    angle = math.atan2(p2.imag - p1.imag, p2.real - p1.real)
    angle = math.degrees(angle)
    return angle


HUGE_NUMBER = 10000000000000000.0

class BouncingBallPosition:

    def __init__(self, target_id, x, y, begin_time, end_time):
        self.id = target_id
        self.begin_time = begin_time
        self.end_time = end_time
        assert(end_time >= begin_time)
        self.duration = end_time - begin_time
        self.x = x
        self.y = y

class BouncingBallBounceAnimation:

    def __init__(self, config, position1, invert):
        self.config = config
        self.pos = position1
        self.freeze = False
        self.invert = invert
        self.angle_begin = 0.0   # angles that we begin and end 
        self.angle_end = 0.0     # this animation at, for smooth
                                # transition to adjacent arcs

    def asSVG(self):

        begin_time = self.pos.begin_time
        end_time = self.pos.end_time
        assert(end_time >= begin_time)

        dur = end_time - begin_time
        half_dur = dur / 2
        quarter_dur = half_dur / 2

        ball_radius = self.config.get("ball-radius", 12)
        ball_squash = self.config.get("ball-squish", 1.2)
        ball_squish = 1 / ball_squash

        adjust_x = -ball_radius * (ball_squash - 1)
        if self.invert:
            adjust_x = -adjust_x

        results = []

        #print("begin angle = ", self.angle_begin, ", end angle = ", self.angle_end)
        
        # squish downward
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1 1"
        animation.attrib["to"] = f"{ball_squish} {ball_squash}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)

        # spring back up
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = f"{ball_squish} {ball_squash}"
        animation.attrib["to"] = "1 1"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + half_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        if self.freeze:
            animation.attrib["fill"] = "freeze"
        results.append(animation)
        
        # move the ball slightly down, otherwise the bottom of the
        # ball actually goes *up* during the bounce.  note that
        # we're in a rotated frame of reference, so down=sideways
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["from"] = f"{self.pos.x} {self.pos.y}"
        animation.attrib["to"] = f"{self.pos.x + adjust_x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)        

        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["from"] = f"{self.pos.x + adjust_x} {self.pos.y}"
        animation.attrib["to"] = f"{self.pos.x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + half_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        if self.freeze:
            animation.attrib["fill"] = "freeze"
        results.append(animation)


        angle = 90.0 if self.invert else 270.0
        angle_begin = angle + self.angle_begin  # the full amount is a bit much
        angle_end = angle + self.angle_end 

        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "rotate"
        animation.attrib["from"] = f"{angle} {self.pos.x} {self.pos.y}"
        animation.attrib["to"] = f"{angle} {self.pos.x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(dur)
        results.append(animation)

        '''
        angle = 90.0 if self.invert else 270.0
        angle_begin = angle + self.angle_begin  # the full amount is a bit much
        angle_end = angle + self.angle_end 

        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "rotate"
        animation.attrib["from"] = f"{angle_begin} {self.pos.x} {self.pos.y}"
        animation.attrib["to"] = f"{angle} {self.pos.x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)

        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "rotate"
        animation.attrib["from"] = f"{angle} {self.pos.x} {self.pos.y}"
        animation.attrib["to"] = f"{angle} {self.pos.x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + quarter_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "rotate"
        animation.attrib["from"] = f"{angle} {self.pos.x} {self.pos.y}"
        animation.attrib["to"] = f"{angle_end} {self.pos.x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + half_dur + quarter_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        if self.freeze:
            animation.attrib["fill"] = "freeze"
        results.append(animation)
        '''

        return results

class BouncingBallArcAnimation:

    def __init__(self, config, position1, position2, invert):
        self.config = config
        self.position1 = position1
        self.position2 = position2
        self.invert = invert

        p1_x = "{:.3f}".format(self.position1.x)
        p1_y = "{:.3f}".format(self.position1.y)
        p2_x = "{:.3f}".format(self.position2.x)
        p2_y = "{:.3f}".format(self.position2.y)

        midpoint_x = (self.position1.x + self.position2.x) / 2
        midpoint_y = min(self.position1.y, self.position2.y) -\
                         self.config.get("ball-target-ascent", 20)

        m_x = "{:.3f}".format(midpoint_x)
        m_y = "{:.3f}".format(midpoint_y)

        self.path = f"M{p1_x},{p1_y} Q{m_x},{m_y} {p2_x},{p2_y}"

    def get_angle_in(self):
        return get_angle_from_path(self.path, 0.0, 0.01)

    def get_angle_out(self):
        return get_angle_from_path(self.path, 0.99, 1.0)

    def asSVG(self):

        begin_time = self.position1.end_time
        end_time = self.position2.begin_time
        assert(end_time >= begin_time)

        dur = end_time - begin_time
        half_dur = dur / 2
        quarter_dur = dur / 4

        results = []

        animation = et.Element("animateMotion")
        animation.attrib["rotate"] = "auto-reverse" if self.invert else "auto"
        animation.attrib["path"] = self.path
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(dur)
        results.append(animation)

        ball_squish = self.config.get("ball-squish", 1.2)
        ball_squash = 1 / ball_squish
        ball_squish_mid = (1 + ball_squish)
        ball_squash_mid = (1 + ball_squash)

        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1 1"
        animation.attrib["to"] = f"{ball_squish} {ball_squash}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)
        
        '''
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = f"{ball_squish} {ball_squash}"
        animation.attrib["to"] = f"{ball_squish_mid} {ball_squash_mid}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + quarter_dur)
        animation.attrib["dur"] = "{:.3f}s".format(quarter_dur)
        results.append(animation)
        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = f"{ball_squish_mid} {ball_squash_mid}"
        animation.attrib["to"] = f"{ball_squish} {ball_squash}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + quarter_dur * 2)
        animation.attrib["dur"] = "{:.3f}s".format(quarter_dur)
        results.append(animation)
        '''
        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = f"{ball_squish} {ball_squash}"
        animation.attrib["to"] = "1 1"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + half_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)

        return results



class BouncingBall:

    def __init__(self, config, slideshow):
        self.config = config
        self.slideshow = slideshow
        self.positions = {} # dict of timestamps/positions
        self.animations = []
        self.first_animation_begins = 10000000000000.0
        #self.last_animation_ends = -1.0

    def addTimestamp(self, target_id, begin_time, end_time): 
        ''' the ball uses the timestamps to decide where to be
             at any given moment '''

        target = self.slideshow[target_id]
        if not target:
            logging.warning(f"Cannot find element {target_id}")
            return

        target_x = target.x + target.getWidth() / 2
        target_y = target.y - self.config.get("ball-clearance", 10)

        self.positions[begin_time] = BouncingBallPosition(target_id, 
                                target_x, target_y, 
                                begin_time, end_time)


    def compile(self):
        ''' Turns timestamp/positions into an animation
        path for the ball to follow '''

        begin_times = sorted(list(self.positions.keys()))

        # first make sure nothing goes backwards in time
        for time1, time2 in zip(begin_times, begin_times[1:]):
            pos1 = self.positions[time1]
            if pos1.end_time > time2:
                logging.warning(f"Token {pos1.id} ends after the following token begins.")
                pos1.end_time = time2

        invert = True
        angle_begin = 0.0
        for i in range(len(begin_times)):
            
            invert = not invert

            # make a bounce
            time1 = begin_times[i]
            self.first_animation_begins = min(time1, self.first_animation_begins)
            pos1 = self.positions[time1]
            bounceAnimation = BouncingBallBounceAnimation(self.config, pos1, invert)
            bounceAnimation.angle_begin = angle_begin
            self.animations.append(bounceAnimation)

            if (i+1) >= len(begin_times):
                # this is the last bounce; freeze it and don't make an arc
                bounceAnimation.freeze = True
                #print("freezing")
                continue
                
            # there's a bounce after this one, too; make an arc
            time2 = begin_times[i+1]
            pos2 = self.positions[time2]
            arcAnimation = BouncingBallArcAnimation(self.config, pos1, pos2, invert)
            bounceAnimation.angle_end = arcAnimation.get_angle_in()
            angle_begin = arcAnimation.get_angle_out()
            self.animations.append(arcAnimation)

        '''
        # freeze the final bounce animation
        if self.animations: 
            self.animations[-1].freeze = True

        # make arc animations
        invert = False
        for time1, time2 in zip(begin_times, begin_times[1:]):
            pos1 = self.positions[time1]
            pos2 = self.positions[time2]
            animation = BouncingBallArcAnimation(self.config, pos1, pos2, invert)
            angle_in = animation.get_angle_in()
            print("angle in = ", angle_in)
            angle_out = animation.get_angle_out()
            print("angle out = ", angle_out)
            print()
            self.animations.append(animation)
            invert = not invert
        '''

    def asSVG(self):
        #svg_filename = ''
        svg_filename = self.config.get("ball-image", "")
        radius = float(self.config.get("ball-radius", 12))


        result = et.Element("g")
        result.attrib["id"] = "rasv_ball"
        result.attrib["x"] = "0"
        result.attrib["y"] = "0"

        if not svg_filename:
            circle = et.Element("circle")
            circle.attrib["cx"] = "0"
            circle.attrib["cy"] = "0"
            circle.attrib["r"] = "{:.3f}".format(radius)   
            if "text-color" in self.config:
                circle.attrib["fill"] = self.config["highlight-color"]
                circle.attrib["stroke"] = self.config["highlight-color"]
            result.append(circle)
        else:
            svg = et.parse(svg_filename).getroot()
            if "viewBox" not in svg.attrib:
                logging.error(f"No 'viewBox' attribute in svg file {svg_filename}, cannot determine proper size of svg.")
                return result
            size = svg.attrib["viewBox"].split(" ")
            width, height = float(size[-2]), float(size[-1])
            scale_factor = radius / max(width, height)
            scale = float(self.config.get("ball-image-scale", 1))
            for child in svg:
                translate_str = f"translate(-{width * scale / 2} -{height * scale/ 2})"
                rotate_str = f" rotate(90 {width * scale / 2} {width * scale / 2})"
                scale_str = f" scale({scale} {scale})"
                child.attrib["transform"] = translate_str + rotate_str + scale_str
                result.append(child)


        # get the ball out of the way until the animation starts
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["from"] = "-100000 -100000"
        animation.attrib["to"] = "-100000 -100000"
        animation.attrib["begin"] = "0.0"
        animation.attrib["dur"] = "{:.3f}s".format(self.first_animation_begins)
        result.append(animation)

        for animation in self.animations:
            for subanimation in animation.asSVG():
                result.append(subanimation)
        return result


class RASVComponent:

    def __init__(self, config, parent):
        self.parent = parent
        self.config = config
        self.id = ""
        self.children = []
        self.begin_time = HUGE_NUMBER
        self.end_time = -1.0
        self.x = 0.0
        self.y = 0.0
        self.highlight = True

    def setPos(self, x, y):
        deltaX = x - self.x
        deltaY = y - self.y
        self.x = x
        self.y = y
        for child in self.children:
            child.setPos(child.x + deltaX, child.y + deltaY)

    def getPreviousSibling(self):
        previousChild = None
        result = None
        for child in self.parent.children:
            if child == self:
                return previousChild
            previousChild = child             

    def getNextSibling(self):
        found = False
        for child in self.parent.children:
            if child == self:
                found = True
            elif found:
                return child
        return None

    def __getitem__(self, target_id):

        if self.id == target_id:
            return self
        
        for child in self.children:
            result = child[target_id]
            if result:
                return result
        
        return None

    def addTimestamp(self, target_id, begin, end):
        
        if self.id == target_id:
            self.begin_time = begin 
            self.end_time = end
            return True

        for child in self.children:
            if child.addTimestamp(target_id, begin, end):
                self.begin_time = min(begin, self.begin_time)
                self.end_time = max(end, self.end_time)
                return True

    def addMissingTimestamps(self):

        if not self.highlight:
            return

        if self.begin_time == HUGE_NUMBER: # don't have a begin time yet    
            previous_sibling = self.getPreviousSibling()
            if previous_sibling:
                self.begin_time = previous_sibling.end_time
            else:
                self.begin_time = self.parent.begin_time 

            self.end_time = self.begin_time + 0.01  # just a tiny amount, so that it has some duration

            next_sibling = self.getNextSibling()
            if next_sibling and next_sibling.begin_time != HUGE_NUMBER: 
                # if the next sibling has a defined time, extend yourself to fill the gap
                self.end_time = next_sibling.begin_time

        for child in self.children:
            child.addMissingTimestamps()


    def asSVG(self):
        result = et.Element("g")
        if self.begin_time != HUGE_NUMBER:
            result.attrib["data-begin-time"] = "{:.3f}".format(self.begin_time)
        if self.end_time != -1.0:
            result.attrib["data-end-time"] = "{:.3f}".format(self.end_time)
        if self.id:
            result.attrib["id"] = self.id
        for child in self.children:
            result.append(child.asSVG())
        return result

class Token(RASVComponent):

    def __init__(self, config, parent, text, id="", size="", isContent=True):
        RASVComponent.__init__(self, config, parent)
        text = unicodedata.normalize("NFC", text)
        self.text = text
        self.id = id
        self.size = size
        self.isContent = isContent

    def getFont(self):
        return self.config["font"]

    def getFontSize(self):
        
        if self.size == "small" and "font-size-small" in self.config:
            return int(self.config["font-size-small"])

        if self.size == "large" and "font-size-large" in self.config:
            return int(self.config["font-size-large"])
        
        return int(self.config["font-size"])

    def getWidth(self):
        return stringWidth(self.text, self.getFont(), self.getFontSize())

    def getHeight(self):
        return getAscent(self.getFont(),self.getFontSize())

    def asSVG(self):
        result = et.Element("text")
        if self.id:
            result.attrib["id"] = self.id

        
        original_y = self.y + self.getHeight()
        #apparent_y = original_y - 10
        
        #result.attrib["x"] = "{:.3f}".format(self.x)
        #result.attrib["y"] = "{:.3f}".format(original_y)

        # rather than place the element using x and y attributes,
        # placing it by a transform makes later animation like scaling
        # and rotation easier.

        x_str = "{:.3f}".format(self.x)
        y_str = "{:.3f}".format(original_y)
        result.attrib["x"] = "0.0"
        result.attrib["y"] = "0.0"
        result.attrib["transform"] = f"translate({x_str} {y_str})"


        result.attrib["font-size"] = "{}".format(int(self.getFontSize()))
        result.attrib["font-family"] = self.getFont()
        result.attrib["font-weight"] = "bold"
        if "text-color" in self.config:
            result.attrib["fill"] = self.config["text-color"]
            result.attrib["stroke"] = self.config["text-color"]
        result.text = self.text

        if self.begin_time == HUGE_NUMBER:
            return result

        result.attrib["data-begin-time"] = "{:.3f}".format(self.begin_time)
        result.attrib["data-end-time"] = "{:.3f}".format(self.end_time)

        # lots of playing around here with different effects, don't try too hard
        # to make sense of everything.  eventually this should be factored out into
        # "animators" that encapsulate a reasonable animation that can be applied
        # to elements in the scene.

        # pre-animation
        pre_animation_begin = self.begin_time - 0.2
        pre_animation_dur = self.begin_time - pre_animation_begin
        original_y = self.y + self.getHeight()
        apparent_y = original_y - 10

        #pre_x = self.x + self.config["width"]  # keep it far off screen

        # pre-animation

        '''
        animation = et.Element("set")
        animation.attrib["attributeName"] = "x"
        animation.attrib["attributeType"] = "XML"
        animation.attrib["to"] = "{:.3f}".format(pre_x)
        animation.attrib["begin"] = "0.0s"
        animation.attrib["dur"] = "{:.3f}s".format(pre_animation_begin)
        result.append(animation)
        
        animation = et.Element("animate")
        animation.attrib["attributeName"] = "x"
        animation.attrib["attributeType"] = "XML"
        animation.attrib["from"] = "{:.3f}".format(pre_x)
        animation.attrib["to"] = "{:.3f}".format(self.x)
        animation.attrib["begin"] = "{:.3f}s".format(pre_animation_begin)
        animation.attrib["dur"] = "{:.3f}s".format(pre_animation_dur)
        result.append(animation)
        '''

        dur = self.end_time - self.begin_time
        third_dur = max(0.05, dur / 3)
        sixth_dur = third_dur / 2

        ball_radius = float(self.config.get("ball-radius", 0))
        if ball_radius == 0.0:
            # just highlight

            animation = et.Element("animate")
            animation.attrib["attributeName"] = "fill"
            animation.attrib["attributeType"] = "CSS"
            animation.attrib["from"] = self.config["text-color"]
            animation.attrib["to"] = self.config["highlight-color"]
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time - 0.3)
            animation.attrib["dur"] = "{:.3f}s".format(third_dur + 0.3)
            animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                                # want to freeze here.
            result.append(animation)

            animation = et.Element("animate")
            animation.attrib["attributeName"] = "stroke"
            animation.attrib["attributeType"] = "CSS"
            animation.attrib["from"] = self.config["text-color"]
            animation.attrib["to"] = self.config["highlight-color"]
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time - 0.3)
            animation.attrib["dur"] = "{:.3f}s".format(third_dur * 2 + 0.3)
            animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                                # want to freeze here.
            result.append(animation)

        else:

            animation = et.Element("animate")
            animation.attrib["attributeName"] = "fill"
            animation.attrib["attributeType"] = "CSS"
            animation.attrib["from"] = self.config["text-color"]
            animation.attrib["to"] = self.config["highlight-color"]
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
            animation.attrib["dur"] = "{:.3f}s".format(third_dur)
            animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                                # want to freeze here.
            result.append(animation)

            animation = et.Element("animate")
            animation.attrib["attributeName"] = "stroke"
            animation.attrib["attributeType"] = "CSS"
            animation.attrib["from"] = self.config["text-color"]
            animation.attrib["to"] = self.config["highlight-color"]
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
            animation.attrib["dur"] = "{:.3f}s".format(third_dur)
            animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                                # want to freeze here.
            result.append(animation)

            if self.id:   # whitespace and punctuation doesn't have an identifier

                text_squish = self.config.get("text-squish", 1)
                text_squish_mid = (1 + text_squish) / 2
                text_bend = self.config.get("text-bend", 0)

                # squish down and left
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "scale"
                animation.attrib["from"] = "1 1"
                animation.attrib["to"] = f"1 {text_squish_mid}"
                animation.attrib["begin"] = "{:.3f}s".format(self.begin_time - third_dur)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)

                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "skewX"
                animation.attrib["from"] = "0"
                animation.attrib["to"] = f"-{text_bend}"
                animation.attrib["begin"] = "{:.3f}s".format(self.begin_time - third_dur)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)

                # hold for a moment
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "scale"
                animation.attrib["from"] = f"1 {text_squish_mid}"
                animation.attrib["to"] = f"1 {text_squish_mid}"
                animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
                animation.attrib["dur"] = "{:.3f}s".format(dur)
                result.append(animation)
        
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "skewX"
                animation.attrib["from"] = f"-{text_bend}"
                animation.attrib["to"] = f"-{text_bend}"
                animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
                animation.attrib["dur"] = "{:.3f}s".format(dur)
                result.append(animation)

                # squish down and right as the ball is leaving, bringing skew back to 0
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "scale"
                animation.attrib["from"] = f"1 {text_squish_mid}"
                animation.attrib["to"] = f"1 {text_squish}"
                animation.attrib["begin"] = "{:.3f}s".format(self.end_time)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)
        
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "skewX"
                animation.attrib["from"] = f"-{text_bend}"
                animation.attrib["to"] = "0"
                animation.attrib["begin"] = "{:.3f}s".format(self.end_time)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)
                
                # squish up and right as a bounce
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "scale"
                animation.attrib["from"] = f"1 {text_squish}"
                animation.attrib["to"] = f"1 {text_squish_mid}"
                animation.attrib["begin"] = "{:.3f}s".format(self.end_time + third_dur)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)
        
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "skewX"
                animation.attrib["from"] = "0"
                animation.attrib["to"] = f"{text_bend}"
                animation.attrib["begin"] = "{:.3f}s".format(self.end_time + third_dur)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)

                # return to normal
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "scale"
                animation.attrib["from"] = f"1 {text_squish_mid}"
                animation.attrib["to"] = "1 1"
                animation.attrib["begin"] = "{:.3f}s".format(self.end_time + third_dur * 2)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)
        
                animation = et.Element("animateTransform")
                animation.attrib["attributeName"] = "transform"
                animation.attrib["type"] = "skewX"
                animation.attrib["from"] = f"{text_bend}"
                animation.attrib["to"] = "0"
                animation.attrib["begin"] = "{:.3f}s".format(self.end_time + third_dur * 2)
                animation.attrib["dur"] = "{:.3f}s".format(third_dur)
                result.append(animation)

        return result

class Line(RASVComponent):

    def __init__(self, config, parent):
        RASVComponent.__init__(self, config, parent)
        self.children = []

    def addToken(self, token):
        self.children.append(token)
        token.parent = self

    def getWidth(self):
        return sum(t.getWidth() for t in self.children)

    def numTokens(self):
        return len(self.children)

    def getHeight(self):
        if not self.children:
            return 0.0
        return self.children[0].getHeight()

    def layout(self, width):
        margin_x = (width - self.getWidth()) / 2
        current_x = self.x + margin_x
        for token in self.children:
            token.setPos(current_x, self.y)
            current_x += token.getWidth()




class Sentence(RASVComponent):

    def __init__(self, elem, config, parent):
        RASVComponent.__init__(self, config, parent)
        self.width = 0
        self.id = elem.attrib["id"] if "id" in elem.attrib else ""
        self.tokens = []
        self.children = []
        self.size = elem.attrib["size"] if "size" in elem.attrib else ""
        self.highlight = (elem.attrib["highlight"] in ["true", "True", True]) if "highlight" in elem.attrib else True

        if elem.text:
            self.tokens.append(Token(config, self, elem.text, "", self.size, False))
        for child in elem:
            child_id = child.attrib["id"] if "id" in child.attrib else ""
            self.tokens.append(Token(config, self, child.text, child_id, self.size, True))
            if child.tail:
                self.tokens.append(Token(config, self, child.tail, "", self.size, False))

    def layout(self, width):
        self.width = width
        self.children = []
        current_y = self.y 
        currentLine = Line(self.config, self)
        currentLine.setPos(self.x, current_y)

        for token in self.tokens:
            tokenWidth = token.getWidth()
            lineWidth = currentLine.getWidth()
            if tokenWidth + lineWidth > width and currentLine.numTokens() > 0 and token.isContent:
                # went over the allowable width
                currentLine.layout(width)
                self.children.append(currentLine)
                current_y += currentLine.getHeight()
                currentLine = Line(self.config, self)
                currentLine.setPos(self.x, current_y)
            
            currentLine.addToken(token)

        if currentLine.numTokens() > 0:
            currentLine.layout(width)
            self.children.append(currentLine)
            current_y += currentLine.getHeight()

    def getHeight(self):
        result = 0
        lineHeight = 0
        for child in self.children:
            lineHeight = child.getHeight()
            result += lineHeight 
        result += lineHeight * (self.config["line-height"] - 1)
        return result

    def getSpacingHeight(self):
        if not self.children:
            return 0
        return float(self.config["line-height"] - 1) * self.children[0].getHeight()


class Slide(RASVComponent):

    def __init__(self, elem, config, parent):
        RASVComponent.__init__(self, config, parent)
        self.id = elem.attrib["id"] if "id" in elem.attrib else ""
        self.children = [ Sentence(s, config, self) for s in elem.xpath(".//s") ]

    def layout(self):

        margin_top = float(self.config.get("margin-top", 0))
        margin_bottom = float(self.config.get("margin-bottom", 0))
        margin_left = float(self.config.get("margin-left", 0))
        margin_right = float(self.config.get("margin-right", 0))
        x = margin_left

        current_y = margin_top
        width = float(self.config["width"]) - margin_left - margin_right
        #print(f"total_width = {float(self.config['width'])}, margin_left = {margin_left}, margin_right = {margin_right}, width={width}")
        #height = float(self.config["height"]) - float(self.config["margin-top"]) - float(self.config["margin-bottom"]) 
        for sent in self.children:
            sent.setPos(x, current_y)
            sent.layout(width)
            current_y += sent.getHeight() + sent.getSpacingHeight()
        
        height = self.getHeight()
        max_height = float(self.config["height"]) - margin_top - margin_bottom
        if height < max_height: 
            adjustment_y = (max_height - height) / 2
            for sent in self.children:
                sent.setPos(sent.x, sent.y + adjustment_y)

        return True

    def getHeight(self):
        result = sum(s.getHeight() for s in self.children)
        result += sum(s.getSpacingHeight() for s in self.children[:-1])
        return result

    def asSVG(self):
        result = et.Element("g")
        if self.id:
            result.attrib["id"] = self.id

        #result.attrib["visibility"] = "hidden"

        for token in self.children:
            result.append(token.asSVG())

        if self.begin_time == HUGE_NUMBER:
            return result

        faraway_str = "{:.3f} {:.3f}".format(self.config["width"], self.config["height"])

        # get the slide outta the way until it's needed.  workaround
        # for visibility features apparently not being implemented
        # in svglib.  even though this is static throughout the 
        # animation period, this has to be an <animateTransform> and not
        # a <set> because it needs to affect the "transform" attribute.
        """ 
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["to"] = faraway_str
        animation.attrib["from"] = faraway_str
        animation.attrib["begin"] = "0.0"
        animation.attrib["dur"] = "{:.3f}s".format(self.begin_time)
        result.append(animation)

        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["to"] = faraway_str
        animation.attrib["from"] = faraway_str
        animation.attrib["begin"] = "{:.3f}s".format(self.end_time)
        animation.attrib["dur"] = "{:.3f}s".format(5.0)  
                            # doesn't matter exactly how long because we freeze,
                            # just so long as it's > 0.0
        animation.attrib["fill"] = "freeze"
        
        result.append(animation) """

        return result

class Slideshow(RASVComponent):

    def __init__(self, elem, config):
        RASVComponent.__init__(self, config, None)
        self.children = [ Slide(p, config, self) for p in elem.xpath('.//div[@type="page"]') ]
        self.background = ""
        self.ball = BouncingBall(config, self)



    def add_all_timestamps(self, smil):

        #clip_src = ""
        for par_elem in xpath_default(smil, ".//i:par"):
            begin = 10000000000000
            end = -1
            for audio_elem in xpath_default(par_elem, ".//i:audio"):
                #clip_src = audio_elem.attrib["src"]
                clip_begin = parse_time(audio_elem.attrib["clipBegin"])
                clip_end = parse_time(audio_elem.attrib["clipEnd"])
                begin = min(clip_begin, begin)
                end = max(clip_end, end)
            for text_elem in xpath_default(par_elem, ".//i:text"):
                src = text_elem.attrib["src"]
                target_id = src.split("#")[-1]
                found = self.addTimestamp(target_id, begin, end)
                if not found:
                    logging.warning(f"SMIL file references an element {target_id} that does not exist in the TEI file")

        self.addMissingTimestamps()


    def addTimestamp(self, target_id, begin, end):
        ''' Before performing the regular addTimestamp,
         the Slideshow object also forwards the call to
         it's bouncing-ball object '''
        self.ball.addTimestamp(target_id, begin, end)
        return super().addTimestamp(target_id, begin, end)

    '''
    def set_background(self, image_path):
        # because the only way to use raster images in the SVG
        #renderer is as a base64 encoded data URL, actually using this  
        # slows down rendering to a crawl.  But it's here if you need it...

        extension = image_path.split(".")[-1]
        if extension not in ["png", "jpg"]:
            return

        with open(image_path, "rb") as fin:
            image_data = fin.read()
            png64 = base64.b64encode(image_data).decode()
            self.background = "data:image/{};base64,{}".format(extension, png64) 
    '''

    def layout(self):
        for slide in self.children:
            slide.layout()

    def pad_slides(self, total_duration):
        if not self.children:
            return

        self.children[0].begin_time = 0.0
        
        if total_duration:
            self.children[-1].end_time = total_duration

        for child1, child2 in zip(self.children, self.children[1:]):
            # step through the children in pairs
            gap = child2.begin_time - child1.end_time
            child1.end_time += gap / 2
            child2.begin_time -= gap / 2

    def asSVG(self, slide_to_render):
        result = et.Element("svg")
        result.attrib["width"] = str(self.config["width"])
        result.attrib["height"] = str(self.config["height"])
        result.attrib["baseProfile"] = "full"
        result.attrib["version"] = "1.1"
        result.attrib["xmlns"] = "http://www.w3.org/2000/svg"
        result.attrib["{http://www.w3.org/2000/svg}ev"] = "http://www.w3.org/2001/xml-events" 
        result.attrib["{http://www.w3.org/2000/svg}xlink"] = "http://www.w3.org/1999/xlink"

        #image = et.Element("image")
        #image.attrib["x"] = "0"
        #image.attrib["y"] = "0"
        #image.attrib["width"] = str(self.config["width"])
        #image.attrib["height"] = str(self.config["height"])
        #image.attrib["href"] = self.config["bg-image"]
        #result.append(image)
        '''
        if self.background:
            image = et.Element("image")
            image.attrib["x"] = "0"
            image.attrib["y"] = "0"
            image.attrib["width"] = str(self.config["width"])
            image.attrib["height"] = str(self.config["height"])
            image.attrib["{http://www.w3.org/1999/xlink}href"] = self.background
            result.append(image)

            if "bg-color" in self.config:
                rect = et.Element("rect")
                rect.attrib["x"] = "0"
                rect.attrib["y"] = "0"
                rect.attrib["width"] = str(self.config["width"])
                rect.attrib["height"] = str(self.config["height"])
                rect.attrib["fill"] = self.config["bg-color"]
                if "bg-color-opacity" in config:
                    rect.attrib["fill-opacity"] = str(self.config["bg-color-opacity"])
                result.append(rect)
        '''

        if slide_to_render >= len(self.children):
            print(f"Warning: tried to render non-existant slide {slide_to_render}")
            return result
            
        slide_svg = self.children[slide_to_render].asSVG()
        result.append(slide_svg)

        ball_radius = float(self.config.get("ball-radius", 0))
        if ball_radius != 0.0:
            self.ball.compile()
            result.append(self.ball.asSVG())

        return result





def tei_to_svg(input_tei_path, smil, config_path, total_duration=0.0):
    tree = et.parse(input_tei_path)
    config = load_json(config_path)
    slideshow = Slideshow(tree.getroot(), config)
    slideshow.layout()
    slideshow.add_all_timestamps(smil)
    slideshow.pad_slides(total_duration)
    return slideshow.asSVG()

