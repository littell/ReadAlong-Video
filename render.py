from collections import defaultdict 

import os
import argparse
#import math 
from lxml import etree as et 

import moviepy.editor as mp
from svglib.svglib import svg2rlg
from reportlab.graphics import renderPM
from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth

from svg_snapshot import SnapshotSVG

FRAMES_PER_SECOND = 60
SCREEN_WIDTH_480P = 720
SCREEN_WIDTH_480P = 480
SCREEN_WIDTH_HD = 1920
SCREEN_HEIGHT_HD = 1080


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


def make_test_svg(width = SCREEN_WIDTH_HD, height=SCREEN_HEIGHT_HD):

    root = et.Element("svg")
    root.attrib["width"] = str(width)
    root.attrib["height"] = str(height)

    path = et.Element("path")
    path.attrib["d"] = "M 50 50 L 100 100"
    root.append(path)

    rect = et.Element("rect")
    rect.attrib["x"] = "1000"
    rect.attrib["y"] = "500"
    rect.attrib["width"] = "400"
    rect.attrib["height"] = "200"
    rect.attrib["stroke"] = "#6688AA"
    rect.attrib["fill"] = "rgba(0.0, 0.0, 0.0, 0.5)"
    rect.attrib["fill-opacity"] = "0.0"
    root.append(rect)

    return root


def main(input_filename, output_filename):

    #path = [(100,100),(100,200),(200,200),(200,100)]

    #image = svgwrite.Drawing('temp.svg',size=(300,300))

    #rectangle = image.add(image.polygon(path,id ='polygon',stroke="black",fill="white"))
    #rectangle.add(image.animateTransform("translate","transform",id="polygon", from_="0 0", to="200 400",dur="4s",begin="0s",repeatCount="1"))
    #rectangle.add(image.animateTransform("rotate","transform",id="polygon", from_="0 150 150", to="360 150 150",dur="4s",begin="0s",repeatCount="1"))
    #text = image.add(image.text('rectangle1',insert=(150,30),id="text"))
    #text.add(image.animateColor("fill", attributeType="XML",from_="green", to="red",id="text", dur="4s",repeatCount="indefinite"))

    #image.save()

    tree = et.parse(input_filename)
    clips = []

    video_length = 4.0   # in seconds
    frame_duration = 1.0 / FRAMES_PER_SECOND
    current_length = 0

    snapshot_svg = SnapshotSVG(tree)

    while current_length < video_length:
        frozen_svg = snapshot_svg[current_length]
        tempfile_basename = "temp/temp"
        save_xml(tempfile_basename + ".svg", frozen_svg)
        drawing = svg2rlg(tempfile_basename + ".svg")
        renderPM.drawToFile(drawing, tempfile_basename + ".png", fmt="PNG")
        clips.append(mp.ImageClip(tempfile_basename + ".png").set_duration(frame_duration))
        current_length += frame_duration

    concat_clip = mp.concatenate_videoclips(clips, method="compose")
    concat_clip.write_videofile(output_filename, fps=24)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render an SVG animation to MP4 movie')
    parser.add_argument('input', type=str, help='Input .svg file')
    parser.add_argument('output', type=str, help='Output .mp4 file')
    args = parser.parse_args()
    main(args.input, args.output)
