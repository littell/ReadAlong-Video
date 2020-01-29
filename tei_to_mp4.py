import os
import argparse
import logging
from tei_to_svg import tei_to_svg
from svg_to_mp4 import svg_to_mp4
from util import save_xml
def tei_to_mp4(input_tei_path, 
        input_smil_path, 
        input_audio_path, 
        config_path,
        background_image_path, 
        output_path):

    # make sure files exist before going through the trouble of rendering
    for path in [input_tei_path, 
                input_smil_path, 
                input_audio_path, 
                config_path, 
                background_image_path ]:
        if not os.path.exists(path):
            logging.error(f"Input {path} does not exist")
            return

    svg = tei_to_svg(input_tei_path, input_smil_path, config_path)
    save_xml("output.svg", svg)
    svg_to_mp4(svg, input_audio_path, background_image_path, output_path, 60)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render a ReadAlongs TEI to an MP4')
    parser.add_argument('input_tei', type=str, help='Input TEI file')
    parser.add_argument('input_smil', type=str, help='Input SMIL file')
    parser.add_argument('input_audio', type=str, help='Input audio file')
    parser.add_argument('config', type=str, help="Config JSON file")
    parser.add_argument('bg_image', type=str, help='Input raster image for background')
    #parser.add_argument('config', type=str, help='Configuration JSON')
    parser.add_argument('output', type=str, help='Output MP4 file')
    args = parser.parse_args()
    tei_to_mp4(args.input_tei, 
        args.input_smil, 
        args.input_audio,
        args.config,
        args.bg_image,
        args.output)
