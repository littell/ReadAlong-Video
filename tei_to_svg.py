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
# see the results of changing the background opacity by 20%.
# 
# Rather, I see the future of the video component as being more tied to a WYSIWYG interface, in which 
# the user is entering/coloring/laying out the text from the beginning, the client sends that information 
# (including all visual information) to the alignment backend, and the alignment backend just responds 
# with the necessary animation commands to animate the user's visuals appropriately in time to the audio.
#
##################################################################################################

'''
failed attempt to use the Adobe Font Metrics inside matplotlib:

from matplotlib import rcParams
import os.path
afm_filename = os.path.join(rcParams['datapath'], 'fonts', 'afm', 'ptmr8a.afm')
from matplotlib.afm import AFM
afm = AFM(open(afm_filename, 'rb'))

def string_width(text):
    return afm.string_width_height(text)

print("Wì", string_width("Wì"))
'''

#from PIL import Image, ImageFont, ImageDraw
#FONT = ImageFont.truetype("arial.ttf", 64)

#print(width, height)
#im = Image.new("RGBA", (width, height), (0, 0, 0))
#draw = ImageDraw.Draw(im)
#draw.text((0, 0), 'A', (255, 255, 255), font=font)
#im.show('charimg')


class RASVComponent:

    def __init__(self, config):
        self.id = ""
        self.children = []
        self.begin_time = 10000000000000000.0
        self.end_time = -1.0
        self.x = 0.0
        self.y = 0.0
        self.config = config

    def setPos(self, x, y):
        deltaX = x - self.x
        deltaY = y - self.y
        self.x = x
        self.y = y
        for child in self.children:
            child.setPos(child.x + deltaX, child.y + deltaY)

    def addTimestamp(self, target_id, begin, end):
        
        if self.id == target_id:
            self.begin_time = begin 
            self.end_time = end
            return True

        for child in self.children:
            if child.addTimestamp(target_id, begin, end):
                self.begin_time = min(begin, self.begin_time)
                self.end_time = max(begin, self.end_time)
                return True

    def asSVG(self):
        result = et.Element("g")
        #result.attrib["data-begin-time"] = "{:.3f}".format(self.begin_time)
        #result.attrib["data-end-time"] = "{:.3f}".format(self.end_time)
        if self.id:
            result.attrib["id"] = self.id
        for token in self.children:
            result.append(token.asSVG())
        return result

class Token(RASVComponent):

    def __init__(self, config, text, id="", isContent=True):
        RASVComponent.__init__(self, config)
        text = unicodedata.normalize("NFC", text)
        self.text = text
        self.id = id
        self.isContent = isContent

    def getFont(self):
        return self.config["font"]

    def getFontSize(self):
        return int(self.config["font-size"])

    def getWidth(self):
        width = stringWidth(self.text, self.getFont(), self.getFontSize())
        return width

    def getHeight(self):
        #return FONT.getsize(self.text)[1]
        height = getAscent(self.getFont(),self.getFontSize())
        return height

    def asSVG(self):
        result = et.Element("text")
        if self.id:
            result.attrib["id"] = self.id
        #result.attrib["data-begin-time"] = "{:.3f}".format(self.begin_time)
        #result.attrib["data-end-time"] = "{:.3f}".format(self.end_time)
        
        original_y = self.y + self.getHeight()
        apparent_y = original_y - 10
        
        result.attrib["x"] = "{:.3f}".format(self.x)
        result.attrib["y"] = "{:.3f}".format(original_y)
        result.attrib["font-size"] = "{:.3f}".format(self.getFontSize())
        result.attrib["font-family"] = self.getFont()
        result.attrib["font-weight"] = "bold"
        if "text-color" in self.config:
            result.attrib["fill"] = self.config["text-color"]
            result.attrib["stroke"] = self.config["text-color"]
        result.text = self.text


        # pre-animation
        pre_animation_begin = self.begin_time - 1.20
        pre_animation_dur = self.begin_time - pre_animation_begin
        original_y = self.y + self.getHeight()
        apparent_y = original_y - 10

        pre_x = self.x + self.config["width"]  # keep it far off screen

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
        
        animation = et.Element("animate")
        animation.attrib["attributeName"] = "fill"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["from"] = self.config["text-color"]
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(pre_animation_begin)
        animation.attrib["dur"] = "{:.3f}s".format(pre_animation_dur)
        result.append(animation)

        animation = et.Element("animate")
        animation.attrib["attributeName"] = "stroke"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["from"] = self.config["text-color"]
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(pre_animation_begin)
        animation.attrib["dur"] = "{:.3f}s".format(pre_animation_dur)
        result.append(animation)

        # animation
        '''
        animation = et.Element("set")
        animation.attrib["attributeName"] = "y"
        animation.attrib["attributeType"] = "XML"
        animation.attrib["to"] = "{:.3f}".format(apparent_y)
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(self.end_time - self.begin_time)
        result.append(animation)
        '''

        animation = et.Element("set")
        animation.attrib["attributeName"] = "fill"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(self.end_time - self.begin_time)
        result.append(animation)

        animation = et.Element("set")
        animation.attrib["attributeName"] = "stroke"
        animation.attrib["attributeType"] = "CSS"
        animation.attrib["to"] = self.config["highlight-color"]
        animation.attrib["begin"] = "{:.3f}s".format(self.begin_time)
        animation.attrib["dur"] = "{:.3f}s".format(self.end_time - self.begin_time)
        result.append(animation)

        # post-animation
        post_animation_dur = 0.2

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
        return result

class Line(RASVComponent):

    def __init__(self, config):
        RASVComponent.__init__(self, config)
        self.children = []

    def addToken(self, token):
        self.children.append(token)

    def getFontSize(self):
        return 64

    def getWidth(self):
        return sum(t.getWidth() for t in self.children)

    def numTokens(self):
        return len(self.children)

    def getHeight(self):
        return self.getFontSize()

    def layout(self, width):
        margin_x = (width - self.getWidth()) / 2
        current_x = self.x + margin_x
        for token in self.children:
            token.setPos(current_x, self.y)
            current_x += token.getWidth()




class Sentence(RASVComponent):

    def __init__(self, elem, config):
        RASVComponent.__init__(self, config)
        self.width = 0
        self.id = elem.attrib["id"]
        self.tokens = []
        self.children = []

        if elem.text:
            self.tokens.append(Token(config, elem.text, "", False))
        for child in elem:
            child_id = child.attrib["id"]
            self.tokens.append(Token(config, child.text, child_id, True))
            if child.tail:
                self.tokens.append(Token(config, child.tail, "", False))

    def layout(self, width):
        self.width = width
        self.children = []
        current_y = self.y 
        currentLine = Line(self.config)
        currentLine.setPos(self.x, current_y)

        for token in self.tokens:
            tokenWidth = token.getWidth()
            lineWidth = currentLine.getWidth()
            if tokenWidth + lineWidth > width and currentLine.numTokens() > 0 and token.isContent:
                # went over the allowable width
                currentLine.layout(width)
                self.children.append(currentLine)
                current_y += currentLine.getHeight()
                currentLine = Line(self.config)
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

    def __init__(self, elem, config):
        RASVComponent.__init__(self, config)
        self.id = elem.attrib["id"]
        self.children = [ Sentence(s, config) for s in elem.xpath(".//s") ]

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
        result.attrib["fill-opacity"] = "0.1"
        if self.id:
            result.attrib["id"] = self.id
        for token in self.children:
            result.append(token.asSVG())
        return result

class Slideshow(RASVComponent):

    def __init__(self, elem, config):
        RASVComponent.__init__(self, config)
        self.children = [ Slide(p, config) for p in elem.xpath('.//div[@type="page"]') ]
        self.background = ""

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
            break
        return result


def add_timestamps(smil_path, slideshow):
    """ Takes a SMIL file and returns a list of SVG animation elements (e.g.
    animate, animateMotion, etc.) at the appropriate times and targeting the
    appropriate elements via xlink:herf attributes. 
    
    This won't work as coded if there are multiple sound files in the SMIL,
    but at the moment we don't create such SMIL files anyway.
    
    """

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


def tei_to_svg(input_tei_path, input_smil_path, config_path):
    tree = et.parse(input_tei_path)
    config = load_json(config_path)
    slideshow = Slideshow(tree.getroot(), config)
    slideshow.layout()
    add_timestamps(input_smil_path, slideshow)
    return slideshow.asSVG()
