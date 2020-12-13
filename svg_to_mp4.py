from collections import defaultdict 

import os, sys
import argparse
from lxml import etree as et 
import re
import gc
import logging
import math

import moviepy.editor as mp
from svglib.svglib import svg2rlg #, find_font, _registered_fonts 
from reportlab.graphics import renderPM
#from reportlab.pdfbase.pdfmetrics import registerFont, stringWidth
#from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.colors import toColor

from util import save_xml, load_json
from svg_snapshot import SnapshotSVG

FRAMES_PER_SECOND = 30
SCREEN_WIDTH_480P = 720
SCREEN_HEIGHT_480P = 480
SCREEN_WIDTH_720P = 1280
SCREEN_HEIGHT_720P = 720
SCREEN_WIDTH_HD = 1920
SCREEN_HEIGHT_HD = 1080
FRAMES_PER_CHUNK = 240
CHUNKS_PER_LARGE_CHUNK = 30

def isfloat(x):
    try:
        float(x)
        return True
    except:
        return False

def clamp(x, min_=0, max_=255): 
  return max(min_, min(x, max_))

NUMBER_SPLITTER = re.compile(r'([-+]?\d*\.?\d+|[-+]?\d+)')

def rgb_to_hex(rgb_string):

    parts = NUMBER_SPLITTER.split(rgb_string)
    ints = [ int(float(s)) for s in parts if isfloat(s) ]
    if len(ints) != 3:
        logging.error(f"Error, cannot parse rgb string {rgb_string}")
    r, g, b = ints
    return clamp(b) + 2**8 * clamp(g) + 2**16 * clamp(r)


NUM_MOVIE_CHUNKS = 0
NUM_LARGE_CHUNKS = 0

def write_small_chunk(tiff_paths, background_filename, fps):
    global NUM_MOVIE_CHUNKS
    tempfile_path = "temp/s_chunk_" + str(NUM_MOVIE_CHUNKS) + ".mp4"
    NUM_MOVIE_CHUNKS += 1
    result_clip = mp.ImageSequenceClip(tiff_paths, fps=fps)
    if background_filename:
        bgClip = mp.ImageClip(background_filename).set_duration(result_clip.duration)
        result_clip = mp.CompositeVideoClip([bgClip, result_clip])
    result_clip.write_videofile(tempfile_path, fps=fps, codec="png") #, threads=4) #, codec="mpeg4")
    for tiff_path in tiff_paths:
        os.remove(tiff_path)
    result_clip.close()
    return tempfile_path

def write_large_chunk(clip_paths, fps):
    global NUM_LARGE_CHUNKS
    tempfile_path = "temp/l_chunk_" + str(NUM_LARGE_CHUNKS) + ".mp4"
    NUM_LARGE_CHUNKS += 1
    clips = [mp.VideoFileClip(c) for c in clip_paths]
    result_clip = mp.concatenate_videoclips(clips, method="compose")
    result_clip.write_videofile(tempfile_path, fps=fps, codec="png") #, threads=4) #, codec="mpeg4")
    for clip in clips:
        clip.close()
    for clip_path in clip_paths:
        os.remove(clip_path)
    result_clip.close()
    return tempfile_path

def svg_to_mp4(svg_tree, 
                audio_filename,
                config_filename, 
                output_filename,
                begin_time = 0.0,
                end_time = 3.0, 
                padding_duration = 0.0,
                default_length=4.0):

    #clips = []
    image_paths = []

    if audio_filename:
        audio_clip = mp.AudioFileClip(audio_filename)
        end_time = audio_clip.duration

    if config_filename:
        config = load_json(config_filename)
        background_filename = config.get("bg-image", "")
        fps = config.get("fps", 30)
    else:
        background_filename = ""
        fps = 30

    frame_duration = 1.0 / fps

    start_time_floor = math.floor(begin_time * fps) / fps
    end_time_floor = math.floor(end_time * fps) / fps + padding_duration
    current_time = start_time_floor

    snapshot_svg = SnapshotSVG(svg_tree)


    small_chunk_paths = []
    large_chunk_paths = []

    rgb_str = config.get("bg-color", "rgb(0,0,0)")
    rgb_int = rgb_to_hex(rgb_str)

    frame_idx = 0
    while True:

        if len(image_paths) >= FRAMES_PER_CHUNK:
            small_chunk_path = write_small_chunk(image_paths, background_filename, fps)
            small_chunk_paths.append(small_chunk_path)
            image_paths = []

        if len(small_chunk_paths) >= CHUNKS_PER_LARGE_CHUNK:
            large_chunk_path = write_large_chunk(small_chunk_paths, fps)
            large_chunk_paths.append(large_chunk_path)
            small_chunk_paths = []

        frozen_svg = snapshot_svg[current_time]
        svg_path = f"temp/temp.svg"
        tiff_path = f"temp/temp.{frame_idx}.tiff"

        save_xml(svg_path, frozen_svg)
        drawing = svg2rlg(svg_path)
        renderPM.drawToFile(drawing, tiff_path, fmt="TIFF", bg=rgb_int, configPIL={'transparent': toColor(rgb_str)})

        #imageClip = mp.ImageClip(tempfile_basename + ".png").set_duration(frame_duration)
        #maskClip = mp.ImageClip(tempfile_basename + ".png", ismask=True)
        #imageClip.set_mask(maskClip)
        #renderPM.drawToFile(drawing, tempfile_basename + ".gif", fmt="GIF", bg=0xffff00, configPIL={'transparent': 0xffff00})
        
        #p = renderPM.drawToPIL(drawing, bg=0xffffff, configPIL={'transparent': 0xffffff})
        #p.save(tempfile_basename + ".png")
        #imageClip = mp.ImageClip(tempfile_basename + ".tiff", transparent=True).set_duration(frame_duration)
        
        image_paths.append(tiff_path)
        current_time += frame_duration
        frame_idx += 1

        if current_time >= end_time_floor - 0.000001: # tiny adjustment to avoid doubling a frame due to floating point error
            break

    if image_paths:
        small_chunk_path = write_small_chunk(image_paths, background_filename, fps)
        small_chunk_paths.append(small_chunk_path)

    if small_chunk_paths:
        large_chunk_path = write_large_chunk(small_chunk_paths, fps)
        large_chunk_paths.append(large_chunk_path)

    movie_chunks = [mp.VideoFileClip(c) for c in large_chunk_paths]
    result_clip = mp.concatenate_videoclips(movie_chunks, method="compose").set_duration(end_time_floor - start_time_floor)
    if audio_filename:
        result_clip.audio = audio_clip
    result_clip.write_videofile(output_filename, fps=fps) #, codec="mpeg4")
    for clip in movie_chunks:
        clip.close()
    for path in large_chunk_paths:
        os.remove(path)
    result_clip.close()
    return output_filename


def main(input_filename, audio_filename, config_filename, output_filename):

    svg_tree = et.parse(input_filename)
    svg_to_mp4(svg_tree, audio_filename, config_filename, output_filename, 24)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render an SVG animation to MP4 movie')
    parser.add_argument('input', type=str, help='Input .svg file')
    parser.add_argument('output', type=str, help='Output .mp4 file')
    parser.add_argument('audio', type=str, nargs="?", default="", help='Input .mp3 file')
    parser.add_argument('config', type=str, nargs="?", default="", help="Config JSON file")
    args = parser.parse_args()
    main(args.input, args.audio, args.config, args.output)
