import argparse
import os
import librosa
import np
from collections import defaultdict
from util import load_xml

class Timespan:
    ''' A collection of timestamps beyond just begin/end, including the 
    ends and beginnings of nearby elements, the beginning and end of an
    amplitude range, etc. '''

    def __init__(self, target_id, clip_src, begin, end):
        self.target_id = target_id
        self.clip_src = clip_src
        self.begin = end
        self.end = end

def get_times(smil_path):
    results = defaultdict(list)
    tree = et.parse(smil_path)
    for par_elem in xpath_default(tree, ".//i:par"):
        begin = np.inf
        end = -np.inf   
        clip_src = ""
        for audio_elem in xpath_default(par_elem, ".//i:audio"):
            clip_src = audio_elem.attrib["src"]
            clip_begin = parse_time(audio_elem.attrib["clipBegin"])
            clip_end = parse_time(audio_elem.attrib["clipEnd"])
            begin = min(clip_begin, begin)
            end = max(clip_end, end)
        for text_elem in xpath_default(par_elem, ".//i:text"):
            src = text_elem.attrib["src"]
            target_id = src.split("#")[-1]
            timespan = Timespan(target_id, clip_src, begin, end)
            results[clip_src].append(timespan)
    return results

def main(input_tei_path, input_smil_path, input_audio_path, output_tei_path):

    tei = load_xml(input_tei_path)
    smil = load_xml

if __name__ == '__main__':
    parser = argparse.ArgumentParser(
        description='Render a ReadAlongs TEI to an MP4')
    parser.add_argument('input_tei', type=str, help='Input TEI file')
    parser.add_argument('input_smil', type=str, help='Input SMIL file')
    parser.add_argument('input_audio', type=str, help='Input audio file')
    parser.add_argument('output_tei', type=str, help='Output TEI file')
    args = parser.parse_args()
    main(args.input_tei, 
        args.input_smil, 
        args.input_audio,
        args.output_tei)
