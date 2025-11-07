# Python Image Viewer (zoom, pan, rotate)

This is a fork.
Credit to ImagingSolutions https://github.com/ImagingSolution/PythonImageViewer for the program this is a fork of.

![PythonImageViewer](https://user-images.githubusercontent.com/29155364/106603190-7449bd00-650a-11eb-80f1-b3fe96ba88bf.gif)

# Changes #
Support webp, gif, mp4, webm.
Support thumbnail capability
Use an antialiasing techinique so unzoomed images dont look bad.
Use caching

Without antialiasing, use Nearest as filter.

![python_QUHpf6geqw](https://github.com/user-attachments/assets/e7a61b4e-b34d-4b1d-97df-d4a9740f7427) ![VZEMetR8YX](https://github.com/user-attachments/assets/3f54a56e-0ef8-4395-b345-cf2b4ed7636a)

requires:
psutil
pillow
natsort
send2trash
ultralytics
torch
torchvision
scikit-image
numpy
imageio
pymediainfo
av
pyvips
python-vlc

manual:
vlc (either you need the plugins folder and libvlc.dll, libvlccore.dll) or you can just install the 64-bit version via installer.
pyvips (download the windwos binaries from https://github.com/libvips/libvips/releases. 64-bit web build should be enough)

pyvips can be acquired from https://github.com/libvips/libvips/releases and downloading windows binaries, and vlc can be 

|        |                                |
| ------ | ------------------------------ |
| Zoom   | Mouse wheel up/down            |
| Pan    | Mouse left button drag         |
| Rotate | Mouse wheel up/down + ShiftKey |


