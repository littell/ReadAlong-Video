import os
import argparse
import logging
from tei_to_svg import tei_to_svg
from svg_to_mp4 import svg_to_mp4
from util import save_xml, load_json
import moviepy.editor as mp

def tei_to_mp4(input_tei_path, 
        input_smil_path, 
        input_audio_path, 
        config_path,
        output_path):

    # make sure files exist before going through the trouble of rendering
    for path in [input_tei_path, 
                input_smil_path, 
                input_audio_path, 
                config_path ]:
        if not os.path.exists(path):
            logging.error(f"Input {path} does not exist")
            return

    config = load_json(config_path)
    if "bg-image" in config:
        bg_filename = config["bg-image"]
        if not os.path.exists(bg_filename):
            logging.error(f"Background image {bg_filename} does not exist")
            return 

    # determine some basic parameters like duration and fps
    audio_clip = mp.AudioFileClip(input_audio_path)
    total_duration = audio_clip.duration
    fps = config.get("fps", 24)

    svg = tei_to_svg(input_tei_path, input_smil_path, config_path, total_duration)
    save_xml("output.svg", svg)
    svg_to_mp4(svg, input_audio_path, config_path, output_path, fps)
    
if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render a ReadAlongs TEI to an MP4')
    parser.add_argument('input_tei', type=str, help='Input TEI file')
    parser.add_argument('input_smil', type=str, help='Input SMIL file')
    parser.add_argument('input_audio', type=str, help='Input audio file')
    parser.add_argument('config', type=str, help="Config JSON file")
    parser.add_argument('output', type=str, help='Output MP4 file')
    args = parser.parse_args()
    tei_to_mp4(args.input_tei, 
        args.input_smil, 
        args.input_audio,
        args.config,
        args.output)
