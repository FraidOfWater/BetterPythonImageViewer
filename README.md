# Python Image Viewer (zoom, pan, rotate)

![PythonImageViewer](https://user-images.githubusercontent.com/29155364/106603190-7449bd00-650a-11eb-80f1-b3fe96ba88bf.gif)

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
