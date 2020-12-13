import os
import argparse
import logging
from tei_to_svg import Slideshow
from svg_to_mp4 import svg_to_mp4
from util import save_xml, load_json, load_xml
from adjust_timing import adjust_timing
import moviepy.editor as mp
from lxml import etree as et


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
    fps = config.get("fps", 60)

    # adjust timing of the SMIL to reflect amplitude
    smil = load_xml(input_smil_path)
    smil_dir = os.path.dirname(input_smil_path)
    bounce_begin = config.get("bounce-begin", 0.1)
    bounce_end = config.get("bounce-end", 0.8)
    smil = adjust_timing(smil, smil_dir, bounce_begin, bounce_end)


    clips = []
    current_time = 0
    fade_duration = 0.5

    # parse the TEI and turn it into a slideshow object
    tree = et.parse(input_tei_path)
    config = load_json(config_path)
    slideshow = Slideshow(tree.getroot(), config)
    slideshow.layout()
    slideshow.add_all_timestamps(smil)
    slideshow.pad_slides(total_duration)
    slide_clip_paths = []
    for slide_idx, slide in enumerate(slideshow.children):
        subslideshow = Slideshow(tree.getroot(), config)
        subslideshow.layout()
        subslideshow.add_all_timestamps(smil)
        subslideshow.pad_slides(total_duration)
        svg = subslideshow.asSVG(slide_idx)
        save_xml(f"temp/slide{slide_idx}.svg", svg)
        slide_clip_path = f"temp/slide.{slide_idx}.mp4"
        svg_to_mp4(svg, "", config_path, slide_clip_path, slide.begin_time, slide.end_time, fade_duration)
        slide_clip_paths.append(slide_clip_path)

    for clip_path in slide_clip_paths:
        clip = mp.VideoFileClip(clip_path) #.crossfadeout(fade_duration)
        if current_time != 0:
            current_time -= fade_duration
            clip = clip.set_start(current_time).crossfadein(fade_duration)
        current_time += clip.duration
        clips.append(clip)
    
    video = mp.CompositeVideoClip(clips)
    video.audio = audio_clip
    video.write_videofile(output_path, fps=fps, codec="png") #, threads=4)


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
