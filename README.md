# Python Image Viewer (zoom, pan, rotate)

This is a fork.
Credit to ImagingSolutions https://github.com/ImagingSolution/PythonImageViewer for the program this is a fork of.

![PythonImageViewer](https://user-images.githubusercontent.com/29155364/106603190-7449bd00-650a-11eb-80f1-b3fe96ba88bf.gif)

# Whats new #
Supports gifs, webp as well as common picture types.
Added: Performance, animation support, options.

Uses "Quick zoom & Panning", essentially much better performance, as we render in NEAREST while on the move, panning or zooming, rendering full quality only when we stop.
Added a "debouncer", a lag-killing mechanism, which allows zooming in and out of large pictures without stalling. Recommended debounce value is 28 (ms), the default.
Tried to also make it as adaptable as possible, so it can be used in python applications. It by default works as a standalone and creates its own prefs file for keeping the settings.

![python_QUHpf6geqw](https://github.com/user-attachments/assets/e7a61b4e-b34d-4b1d-97df-d4a9740f7427) ![VZEMetR8YX](https://github.com/user-attachments/assets/3f54a56e-0ef8-4395-b345-cf2b4ed7636a)


Using modules : 

import tkinter as tk

from tkinter import filedialog

from PIL import Image, ImageTk

import numpy as np

import math

import os

import json

import psutil

import threading

from collections import OrderedDict

from time import perf_counter


|        |                                |
| ------ | ------------------------------ |
| Zoom   | Mouse wheel up/down            |
| Pan    | Mouse left button drag         |
| Rotate | Mouse wheel up/down + ShiftKey |


