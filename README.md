# ReadAlong-Video
Video rendering capabilities for ReadAlong Studio

ReadAlong Studio creates a variety of output formats (TEI, SMIL, EPUB, etc.), but it would also be nice to render directly to high-quality video, so that users don't have to screen-capture the results to post a video to social media, burn it to a DVD, etc.  

This repository contains some (very experimental) code for rendering RAS outputs to SVG animations and then to MP4 videos.

Usage:

```
tei_to_mp4 <tei_file> <smil_file> <audio_file> <config_file> <output_mp4>
```

To render HD video, you'll need a lot of available ram (5-6 GB at least), disk space, and time (about 18x realtime on my work laptop).  We can probably winnow this down to something more reasonable, but in general video rendering is one of the most computationally expensive things PCs actually do, so it's never going to be completely trivial.

Notes:

* The SVG animation standard is not very well-supported overall, but the nice part about it is that it *is* a standard.  Where an element should be at every time, what color it should be, etc. are all defined by a thorough 3rd-party standard, rather than being dependent on particular imperative code or an under-documented internal format.

    * CSS animation would be another possibility, but stylesheets are only experimentally implemented in the SVG rendering library we're using.

* There does not appear to be any *direct* way to render an SVG animation to video in Python.  (SVG usage in Python tends to be static, like to render data plots.)  

    * However, the basics of the SVG animation standard are not very difficult.  Animations are conceptualized as paths (many of them linear) through a conceptual space (e.g. the coordinate space, or color space), that begin at a certain time and have a certain duration.  The appearance of the animation at any time can be determined by interpolating along that path to get the momentary value each property.  There are many further aspects to the SVG standard, but just implementing this much gives you a substantial sandbox for implementing animations.

    * svg_snapshot.py is the workhorse file that makes this rendering possible.  You give it an SVG animation document and it returns an object, queriable by time, that returns a *static* SVG document representing the state of the animation at that time.

    * This is rendered to a TIFF by svglib (itself a wrapper around reportlab), and a sequence of these is rendered to an MP4 by moviepy.  TIFF is used here because reportlab can't render transparency in PNGs or GIFs, or at least I haven't been successful in figuring out how to do it.  Transparency is nice because it allows us to add high-res backgrounds in moviepy, rather than actually putting them in the SVG, which would take svglib/reportlab forever to render.  
    
        * Unfortunately it's not alpha transparency, so a lot of desirable animation effects like fades are currently off the table.  One way around
        this would be to render two PNGs, one for color information and the other just as a transparency mask.  I just haven't figured out how to get moviepy to do mask compositing properly yet.
