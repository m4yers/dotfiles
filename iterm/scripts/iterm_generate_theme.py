#!/usr/bin/env python2
# -*- coding: utf-8 -*-

"""
Generate iTerm2 colors from an image.

Original Script: https://gist.github.com/radiosilence/3946121
"""

import sys
import colorsys
from colorz import colorz

from os.path import expanduser
HOME = expanduser("~")

THEME = HOME + "/Library/Application Support/iTerm2/DynamicProfiles/theme.json"

json_before = """
{
  "Profiles": [{
    "Name": "Default.Profile.Theme",
    "Guid": "Default.Profile.Theme",

    "Background Image Location": "/Library/Desktop Pictures/Antelope Canyon.jpg",
    "Background Image Is Tiled": false,
    "Minimum Contrast": 0,
    "Transparency": 0,
    "Blend": 0.11,
    "Blur": false,
"""
json_after = """
  }]
}
"""
json_color="""
    "Ansi {} Color": {{
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""
json_foreground="""
    "Foreground Color": {{
      "Color Space" : "Calibrated",
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""
json_background="""
    "Background Color": {{
      "Color Space" : "Calibrated",
      "Red Component" : {},
      "Green Component" : {},
      "Blue Component" : {}
    }},
"""
json = ""

def clamp(value, min, max):
  if value < min:
    return min
  if value > max:
    return max
  return value

def normalize(rgb, minh=0, maxh=256, mins=0, maxs=256, minv=0, maxv=256):
  h, s, v = colorsys.rgb_to_hsv(*rgb)

  minh = minh / 256.0
  maxh = maxh / 256.0
  mins = mins / 256.0
  maxs = maxs / 256.0
  minv = minv / 256.0
  maxv = maxv / 256.0

  h = clamp(h, minh, maxh)
  s = clamp(s, mins, maxs)
  v = clamp(v, minv, maxv)

  return colorsys.hsv_to_rgb(h, s, v)

COLOR_BLACK = 0
COLOR_RED = 1
COLOR_GREEN = 2
COLOR_YELLOW = 3
COLOR_BLUE = 4
COLOR_MAGENTA = 5
COLOR_CYAN = 6
COLOR_WHITE = 7

if __name__ == '__main__':

  i = 0
  for normal,bright in colorz(sys.argv[1], n=8):
    normal = [x / 256.0 for x in normal]
    bright = [x / 256.0 for x in bright]

    if i == COLOR_WHITE:
      foreground = normalize(normal, mins=30, maxs=40, minv=150, maxv=160)
      json += json_foreground.format(*foreground)
      # normal = normalize(normal, mins=0, maxs=30, minv=200, maxv=220)
      # bright = normalize(bright, mins=0, maxs=50, minv=220, maxv=256)

    if i == COLOR_BLACK:
      background = normalize(normal, mins=0, maxs=25, minv=10, maxv=15)
      json += json_background.format(*background)
      normal = normalize(normal, mins=0, maxs=20, minv=20, maxv=30)
      bright = normalize(bright, mins=0, maxs=40, minv=20, maxv=60)

    json += json_color.format(i, *normal)
    json += json_color.format(i + 8, *bright)
    i += 1

  with open(THEME, 'w') as f:
    f.write(json_before)
    f.write(json[:-2])
    f.write(json_after)
