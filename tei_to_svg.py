from lxml import etree as et
import base64
import unicodedata 
import logging

from util import save_xml, parse_time, xpath_default, load_json

from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth, getAscent
from reportlab.pdfbase.ttfonts import TTFont
registerFont(TTFont('NotoSans','./fonts/Noto_Sans_400.ttf'))

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

    def adjusted_begin_time(self):
        return self.begin_time + self.duration / 3

    def adjusted_end_time(self):
        return self.end_time - self.duration / 3

class BouncingBallBounceAnimation:

    def __init__(self, config, position1):
        self.config = config
        self.pos = position1
        self.freeze = False

    def asSVG(self):

        begin_time = self.pos.adjusted_begin_time()
        end_time = self.pos.adjusted_end_time()
        assert(end_time >= begin_time)

        half_dur = (end_time - begin_time) / 2

        squish_adjust_y = self.pos.y + (self.config.get("ball-radius", 12) * 0.2)

        results = []

        # move the ball slightly down, otherwise the bottom of the
        # ball actually goes *up* during the bounce
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["from"] = f"{self.pos.x} {self.pos.y}"
        animation.attrib["to"] = f"{self.pos.x} {squish_adjust_y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)        

        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "translate"
        animation.attrib["from"] = f"{self.pos.x} {squish_adjust_y}"
        animation.attrib["to"] = f"{self.pos.x} {self.pos.y}"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + half_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        if self.freeze:
            animation.attrib["fill"] = "freeze"
        results.append(animation)        

        # squish downward
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1 1"
        animation.attrib["to"] = "1.2 0.8"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        results.append(animation)

        # spring back up
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1.2 0.8"
        animation.attrib["to"] = "1 1"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + half_dur)
        animation.attrib["dur"] = "{:.3f}s".format(half_dur)
        if self.freeze:
            animation.attrib["fill"] = "freeze"
        results.append(animation)

        return results

class BouncingBallArcAnimation:

    def __init__(self, config, position1, position2):
        self.config = config
        self.position1 = position1
        self.position2 = position2

    def asSVG(self):

        begin_time = self.position1.adjusted_end_time()
        end_time = self.position2.adjusted_begin_time()
        assert(end_time >= begin_time)

        p1_x = "{:.3f}".format(self.position1.x)
        p1_y = "{:.3f}".format(self.position1.y)
        p2_x = "{:.3f}".format(self.position2.x)
        p2_y = "{:.3f}".format(self.position2.y)

        midpoint_x = (self.position1.x + self.position2.x) / 2
        midpoint_y = min(self.position1.y, self.position2.y) -\
                         self.config.get("ball-target-ascent", 20)

        m_x = "{:.3f}".format(midpoint_x)
        m_y = "{:.3f}".format(midpoint_y)

        path = f"M{p1_x},{p1_y} Q{m_x},{m_y} {p2_x},{p2_y}"

        dur = end_time - begin_time
        half_dur = dur / 2
        quarter_dur = dur / 4

        results = []

        animation = et.Element("animateMotion")
        animation.attrib["rotate"] = "auto"
        animation.attrib["path"] = path
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(dur)
        results.append(animation)

        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1 1"
        animation.attrib["to"] = "1.2 0.8"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(quarter_dur)
        results.append(animation)
        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1.2 0.8"
        animation.attrib["to"] = "1.1 0.9"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + quarter_dur)
        animation.attrib["dur"] = "{:.3f}s".format(quarter_dur)
        results.append(animation)
        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1.1 0.9"
        animation.attrib["to"] = "1.2 0.8"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + quarter_dur * 2)
        animation.attrib["dur"] = "{:.3f}s".format(quarter_dur)
        results.append(animation)
        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1.2 0.8"
        animation.attrib["to"] = "1 1"
        animation.attrib["begin"] = "{:.3f}s".format(begin_time + quarter_dur * 3)
        animation.attrib["dur"] = "{:.3f}s".format(quarter_dur)
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

        # make bounce animations
        for time in begin_times:
            self.first_animation_begins = min(time, self.first_animation_begins)
            pos = self.positions[time]
            #self.last_animation_ends = max(pos.end_time, self.last_animation_ends)
            animation = BouncingBallBounceAnimation(self.config, pos)
            self.animations.append(animation)

        # freeze the final bounce animation
        if self.animations: 
            self.animations[-1].freeze = True

        # make arc animations
        for time1, time2 in zip(begin_times, begin_times[1:]):
            pos1 = self.positions[time1]
            pos2 = self.positions[time2]
            animation = BouncingBallArcAnimation(self.config, pos1, pos2)
            self.animations.append(animation)


    def asSVG(self):
        result = et.Element("circle")
        result.attrib["cx"] = "0"
        result.attrib["cy"] = "0"
        result.attrib["r"] = "{:.3f}".format(self.config["ball-radius"])
        if "text-color" in self.config:
            result.attrib["fill"] = self.config["highlight-color"]
            result.attrib["stroke"] = self.config["highlight-color"]

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

        if self.begin_time == HUGE_NUMBER: # don't have a begin time yet    
            previous_sibling = self.getPreviousSibling()
            if previous_sibling:
                self.begin_time = previous_sibling.end_time
            else:
                self.begin_time = parent.begin_time 

            self.end_time = self.begin_time + 0.01  # just a tiny amount, so that it has some duration

            next_sibling = self.getNextSibling()
            if next_sibling and next_sibling.begin_time != HUGE_NUMBER: 
                # if the next sibling has a defined time, extend yourself to fill the gap
                self.end_time = next_sibling.begin_time

        for child in self.children:
            child.addMissingTimestamps()


    def asSVG(self):
        result = et.Element("g")
        result.attrib["data-begin-time"] = "{:.3f}".format(self.begin_time)
        result.attrib["data-end-time"] = "{:.3f}".format(self.end_time)
        if self.id:
            result.attrib["id"] = self.id
        for child in self.children:
            result.append(child.asSVG())
        return result

class Token(RASVComponent):

    def __init__(self, config, parent, text, id="", isContent=True):
        RASVComponent.__init__(self, config, parent)
        text = unicodedata.normalize("NFC", text)
        self.text = text
        self.id = id
        self.isContent = isContent

    def getFont(self):
        return self.config["font"]

    def getFontSize(self):
        return int(self.config["font-size"])

    def getWidth(self):
        return stringWidth(self.text, self.getFont(), self.getFontSize())

    def getHeight(self):
        return getAscent(self.getFont(),self.getFontSize())

    def asSVG(self):
        result = et.Element("text")
        if self.id:
            result.attrib["id"] = self.id

        result.attrib["data-begin-time"] = "{:.3f}".format(self.begin_time)
        result.attrib["data-end-time"] = "{:.3f}".format(self.end_time)
        
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


        result.attrib["font-size"] = "{:.3f}".format(self.getFontSize())
        result.attrib["font-family"] = self.getFont()
        result.attrib["font-weight"] = "bold"
        if "text-color" in self.config:
            result.attrib["fill"] = self.config["text-color"]
            result.attrib["stroke"] = self.config["text-color"]
        result.text = self.text


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

        third_dur = max(0.05, (self.end_time - self.begin_time) / 3)
        sixth_dur = third_dur / 2

        animation = et.Element("animate")
        animation.attrib["attributeName"] = "fill"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["from"] = self.config["text-color"]
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + third_dur)
        animation.attrib["dur"] = "{:.3f}s".format(third_dur)
        animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                            # want to freeze here.
        result.append(animation)

        animation = et.Element("animate")
        animation.attrib["attributeName"] = "stroke"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["from"] = self.config["text-color"]
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + third_dur)
        animation.attrib["dur"] = "{:.3f}s".format(third_dur)
        animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                            # want to freeze here.
        result.append(animation)

        if self.id:   # whitespace and punctuation doesn't have an identifier

            # squish down and left
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "scale"
            animation.attrib["from"] = "1 1"
            animation.attrib["to"] = "1 0.95"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + third_dur)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)

            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "skewX"
            animation.attrib["from"] = "0"
            animation.attrib["to"] = "-3"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + third_dur)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)

            # hold for a moment
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "scale"
            animation.attrib["from"] = "1 0.95"
            animation.attrib["to"] = "1 0.95"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 3)
            animation.attrib["dur"] = "{:.3f}s".format(third_dur)
            result.append(animation)
    
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "skewX"
            animation.attrib["from"] = "-3"
            animation.attrib["to"] = "-3"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 3)
            animation.attrib["dur"] = "{:.3f}s".format(third_dur)
            result.append(animation)

            # squish down and right as the ball is leaving, bringing skew back to 0
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "scale"
            animation.attrib["from"] = "1 0.95"
            animation.attrib["to"] = "1 0.9"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 5)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)
    
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "skewX"
            animation.attrib["from"] = "-3"
            animation.attrib["to"] = "0"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 5)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)

            
            # squish up and right as a bounce
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "scale"
            animation.attrib["from"] = "1 0.9"
            animation.attrib["to"] = "1 0.95"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 6)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)
    
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "skewX"
            animation.attrib["from"] = "0"
            animation.attrib["to"] = "3"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 6)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)

            # return to normal
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "scale"
            animation.attrib["from"] = "1 0.95"
            animation.attrib["to"] = "1 1"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 7)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)
    
            animation = et.Element("animateTransform")
            animation.attrib["attributeName"] = "transform"
            animation.attrib["type"] = "skewX"
            animation.attrib["from"] = "3"
            animation.attrib["to"] = "0"
            animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + sixth_dur * 7)
            animation.attrib["dur"] = "{:.3f}s".format(sixth_dur)
            result.append(animation)

            # return to normal
            
        '''
        a little bounce after the ball leaves, looks okay but not perfect,
        taking out for now.  Bouncing based on a fraction of the token
        duration leads to some bounces being too rapid and looking jerky.
        Probably this is an animation that, if it's used at all, should 
        be timed to the beat rather than the duration.

        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1 1"
        animation.attrib["to"] = "1 0.9"
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + third_dur * 3)
        animation.attrib["dur"] = "{:.3f}s".format(third_dur)
        result.append(animation)
        
        animation = et.Element("animateTransform")
        animation.attrib["attributeName"] = "transform"
        animation.attrib["type"] = "scale"
        animation.attrib["from"] = "1 0.9"
        animation.attrib["to"] = "1 1"
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time + third_dur * 4)
        animation.attrib["dur"] = "{:.3f}s".format(third_dur)
        result.append(animation)
        '''
        '''
        animation = et.Element("set")
        animation.attrib["attributeName"] = "y"
        animation.attrib["attributeType"] = "XML"
        animation.attrib["to"] = "{:.3f}".format(apparent_y)
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(self.end_time - self.begin_time)
        result.append(animation)
        '''

        '''
        animation = et.Element("set")
        animation.attrib["attributeName"] = "fill"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(self.end_time - self.begin_time)
        animation.attrib["fill"] = "freeze"  # if we were to fade out later, we don't
                                            # want to freeze here.
        result.append(animation)

        animation = et.Element("set")
        animation.attrib["attributeName"] = "stroke"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(self.end_time - self.begin_time)
        animation.attrib["fill"] = "freeze"
        result.append(animation)
        '''
        # post-animation
        #post_animation_dur = 0.2

        '''
        animation = et.Element("animate")
        animation.attrib["attributeName"] = "y"
        animation.attrib["attributeType"] = "XML"
        animation.attrib["from"] = "{:.3f}".format(apparent_y)
        animation.attrib["to"] = "{:.3f}".format(original_y)
        animation.attrib["begin"] = "{:.3f}s".format(self.end_time)
        animation.attrib["dur"] = "{:.3f}s".format(post_animation_dur)
        result.append(animation)
        '''

        '''
        animation = et.Element("animate")
        animation.attrib["attributeName"] = "fill"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["from"] = self.config["highlight-color"]
        animation.attrib["to"] = self.config["text-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.end_time)
        animation.attrib["dur"] = "{:.3f}s".format(post_animation_dur)
        result.append(animation)

        animation = et.Element("animate")
        animation.attrib["attributeName"] = "stroke"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["from"] = self.config["highlight-color"]
        animation.attrib["to"] = self.config["text-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.end_time)
        animation.attrib["dur"] = "{:.3f}s".format(post_animation_dur)
        result.append(animation)
        '''

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
        self.id = elem.attrib["id"]
        self.tokens = []
        self.children = []

        if elem.text:
            self.tokens.append(Token(config, self, elem.text, "", False))
        for child in elem:
            child_id = child.attrib["id"]
            self.tokens.append(Token(config, self, child.text, child_id, True))
            if child.tail:
                self.tokens.append(Token(config, self, child.tail, "", False))

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
        if not self.children:
            return 0
        lineHeight = self.children[0].getHeight()
        result = lineHeight * len(self.children) 
        result += (float(self.config["line-height"]) - 1) * \
                                (len(self.children) - 1)
        return result

    def getSpacingHeight(self):
        if not self.children:
            return 0
        return float(self.config["line-height"] - 1) * self.children[0].getHeight()


class Slide(RASVComponent):

    def __init__(self, elem, config, parent):
        RASVComponent.__init__(self, config, parent)
        self.id = elem.attrib["id"]
        self.children = [ Sentence(s, config, self) for s in elem.xpath(".//s") ]

    def layout(self):
        x = float(self.config["margin-left"])
        current_y = 0  #float(self.config["margin-top"])
        width = float(self.config["width"]) - float(self.config["margin-left"]) - float(self.config["margin-right"]) 
        #height = float(self.config["height"]) - float(self.config["margin-top"]) - float(self.config["margin-bottom"]) 
        for sent in self.children:
            sent.setPos(x, current_y)
            sent.layout(width)
            current_y += sent.getHeight() + sent.getSpacingHeight()
        
        height = self.getHeight()
        max_height = float(self.config["height"])
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

        result.attrib["visibility"] = "hidden"

        for token in self.children:
            result.append(token.asSVG())

        faraway_str = "{:.3f} {:.3f}".format(self.config["width"], self.config["height"])

        # get the slide outta the way until it's needed.  workaround
        # for visibility features apparently not being implemented
        # in svglib.  even though this is static throughout the 
        # animation period, this has to be an <animateTransform> and not
        # a <set> because it needs to affect the "transform" attribute.

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
        
        result.append(animation)

        return result

class Slideshow(RASVComponent):

    def __init__(self, elem, config):
        RASVComponent.__init__(self, config, None)
        self.children = [ Slide(p, config, self) for p in elem.xpath('.//div[@type="page"]') ]
        self.background = ""
        self.ball = BouncingBall(config, self)

    def addTimestamp(self, target_id, begin, end):
        ''' Before performing the regular addTimestamp,
         the Slideshow object also forwards the call to
         it's bouncing-ball object '''
        self.ball.addTimestamp(target_id, begin, end)
        return super().addTimestamp(target_id, begin, end)

    def set_background(self, image_path):
        ''' because the only way to use raster images in the SVG
        renderer is as a base64 encoded data URL, actually using this  
        slows down rendering to a crawl.  But it's here if you need it... '''

        extension = image_path.split(".")[-1]
        if extension not in ["png", "jpg"]:
            return

        with open(image_path, "rb") as fin:
            image_data = fin.read()
            png64 = base64.b64encode(image_data).decode()
            self.background = "data:image/{};base64,{}".format(extension, png64) 

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

    def asSVG(self):
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

        for slide in self.children:
            result.append(slide.asSVG())

        self.ball.compile()
        result.append(self.ball.asSVG())

        return result




def add_timestamps(smil_path, slideshow):

    clip_src = ""
    tree = et.parse(smil_path)
    for par_elem in xpath_default(tree, ".//i:par"):
        begin = 10000000000000
        end = -1
        for audio_elem in xpath_default(par_elem, ".//i:audio"):
            clip_src = audio_elem.attrib["src"]
            clip_begin = parse_time(audio_elem.attrib["clipBegin"])
            clip_end = parse_time(audio_elem.attrib["clipEnd"])
            begin = min(clip_begin, begin)
            end = max(clip_end, end)
        for text_elem in xpath_default(par_elem, ".//i:text"):
            src = text_elem.attrib["src"]
            target_id = src.split("#")[-1]
            found = slideshow.addTimestamp(target_id, clip_begin, clip_end)
            if not found:
                logging.warning(f"SMIL file references an element {target_id} that does not exist in the TEI file")

    slideshow.addMissingTimestamps()

def tei_to_svg(input_tei_path, input_smil_path, config_path, total_duration=0.0):
    tree = et.parse(input_tei_path)
    config = load_json(config_path)
    slideshow = Slideshow(tree.getroot(), config)
    slideshow.layout()
    add_timestamps(input_smil_path, slideshow)
    slideshow.pad_slides(total_duration)
    return slideshow.asSVG()
