import os
import argparse
import logging
from tei_to_svg import tei_to_svg
from svg_to_mp4 import svg_to_mp4
from util import save_xml, load_json, load_xml
from adjust_timing import adjust_timing
import moviepy.editor as mp
from lxml import etree as et
from tei_to_svg import Slideshow

def make_cover_svg(input_tei_path, config_path):
    tree = et.parse(input_tei_path)
    config = load_json(config_path)
    slideshow = Slideshow(tree.getroot(), config)
    slideshow.layout()
    return slideshow.asSVG(0)

def main(input_tei_path, config_path, output_path, audio_path):
    svg = make_cover_svg(input_tei_path, config_path)
    svg_to_mp4(svg, audio_path, config_path, output_path, 0.0, 3)

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render a ReadAlongs TEI cover page to an MP4')
    parser.add_argument('input_tei', type=str, help='Input TEI file')   
    parser.add_argument('config', type=str, help="Config JSON file")
    parser.add_argument('output', type=str, help='Output MP4 file')
    parser.add_argument('--audio', type=str, default="", help='Input audio file')
    args = parser.parse_args()
    main(args.input_tei, 
        args.config,
        args.output,
        args.audio)

