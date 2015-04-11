# Copyright 2011-2015 Matthaeus G. Chajdas. All rights reserved.
#
# Redistribution and use in source and binary forms, with or without modification, are
# permitted provided that the following conditions are met:
#
#    1. Redistributions of source code must retain the above copyright notice, this list of
#       conditions and the following disclaimer.
#
#    2. Redistributions in binary form must reproduce the above copyright notice, this list
#       of conditions and the following disclaimer in the documentation and/or other materials
#       provided with the distribution.
#
# THIS SOFTWARE IS PROVIDED BY MATTHAEUS G. CHAJDAS ''AS IS'' AND ANY EXPRESS OR IMPLIED
# WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND
# FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL Matthaeus G. Chajdas OR
# CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON
# ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING
# NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF
# ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
#
# The views and conclusions contained in the software and documentation are those of the
# authors and should not be interpreted as representing official policies, either expressed
# or implied, of Matthaeus G. Chajdas.

from multiprocessing import Pool, cpu_count
import os, subprocess, hashlib

# TODO Make this configurable
CONVERT = 'convert'
COMPOSITE = 'composite'
MONTAGE = 'montage'

class Node:
    def __init__ (self, name, inputs = [], minInputCount = 0, maxInputCount = 1):
        self.inputs = inputs
        self.name = name

        assert len(self.inputs) >= minInputCount, "Not enough inputs"
        if (maxInputCount is not None):
            assert len(self.inputs) <= maxInputCount, "Too many inputs"

    def Execute (self, index, target):
        """Process all inputs of this node and then execute the node itself.
        Returns the file name where the output has been written to."""
        targets = [self.GetTemporary (i) for i in range(len(self.inputs))]

        inputs = [self.inputs [i].Execute(index, targets [i]) for i in range (len(self.inputs))]

        self.Eval (inputs, target, index)

        return target

    def GetTemporary (self, index = None):
        thisPid = os.getpid ()
        if index is not None:
            h = hashlib.sha1('{}_{}_{}'.format(thisPid, self.name, index).encode('utf-8')).hexdigest ()
            return '_tmp_AVA__{}.tga'.format(h)
        else:
            h = hashlib.sha1('{}_{}'.format(thisPid, self.name).encode('utf-8')).hexdigest ()
            return '_tmp_AVA__{}.tga'.format(h)

    def GetName (self):
        return self.name

    def GetStreamLength(self):
        return min([input.GetStreamLength() for input in self.inputs])

class ImageSequence(Node):
    """A sequence of images. The image name must contain a valid Python
    format string. The image index is used to generate the final file name.
    For instance, using 'img{0:04}.png' with count=3 and offset=1 will produce
    'img0001.png', 'img0002.png' and 'img0003.png'."""
    def __init__(self, name, format, count, offset = 0):
        super().__init__(name, maxInputCount = 0)
        self._format = format
        self._count = count
        self._offset = offset

    def Execute (self, index, target):
        an = [CONVERT, '-type', 'TrueColor', self._format.format (index+self._offset), target]
        subprocess.call(an)

        return target

    def GetStreamLength(self):
        return self._count

class AddLabelNode(Node):
    """Add a label to a node. The corner must be a valid ImageMagick corner."""
    def __init__(self, name, inputs, label, corner="SouthWest"):
        super().__init__(name, inputs)
        self._label = label
        self._corner = corner

    def Eval(self, input, output, index):
        an = [CONVERT,
          input, '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '24',
          '-gravity',  self._corner, '-annotate', '+0+5', " {} ".format(self._label),
          output]
        subprocess.call(an)

class CropNode(Node):
    """Crop an image."""
    def __init__(self, name, inputs, hSize, vSize, hOffset = 0, vOffset = 0):
        super().__init__(name, inputs)
        self._format = "{}%x{}%+{}+{}".format (hSize, vSize, hOffset, vOffset)

    def Eval(self, input, Output, index):
        an = [CONVERT, input, '-crop', self._format, Output]
        subprocess.call(an)

class MergeNode(Node):
    """Merge multiple images."""
    def __init__(self, name, inputs):
        super().__init__(name, inputs, maxInputCount = None)

    def Eval(self, input, Output, index):
        an = [CONVERT] + input + ['+append', Output]
        subprocess.call(an)

class ResizeNode(Node):
    """Resize an image."""
    def __init__(self, name, inputs, maximumWidth=256, maximumHeight=256):
        super().__init__(name, inputs, maxInputCount = 1)
        self._width = maximumWidth
        self._height = maximumHeight

    def Eval(self, input, Output, index):
        an = [CONVERT] + input + ['-resize', '{}x{}'.format (self._width, self._height), Output]
        subprocess.call(an)

class ChangeCanvasSizeNode(Node):
    """Change the canvas size for image.

    hShift/vShift can be used to move the image relative to the center of the
    new canvas size."""
    def __init__(self, name, inputs, width=256, height=256, hShift=0, vShift=0):
        super().__init__(name, inputs, maxInputCount = 1)
        self._width = width
        self._height = height
        if hShift >= 0:
            self._hShift = '+{}'.format (hShift)
        else:
            self._hShift = '{}'.format (hShift)

        if vShift >= 0:
            self._vShift = '+{}'.format (vShift)
        else:
            self._vShift = '{}'.format (vShift)

    def Eval(self, input, Output, index):
        an = [CONVERT] + input + ['-gravity', 'center', '-extent',
            '{}x{}{}{}'.format (self._width, self._height, self._hShift, self._vShift), Output]
        subprocess.call(an)

class MergeTiledNode (Node):
    """Merge images in tiled configuration."""
    def __init__(self, name, inputs, columns = 2, rows = 2):
        super().__init__(name, inputs, maxInputCount = rows * columns)
        self._rows = rows
        self._columns = columns

    def Eval(self, input, Output, index):
        an = [MONTAGE] + input + ['-mode', 'Concatenate', '-tile',
            '{}x{}'.format (self._columns, self._rows), Output]
        subprocess.call(an)

class OutputNode(Node):
    """Forward the output. This node ensures that the output is consitent and can
    be easily consumed. By default, some nodes (like AddLabel) might produce
    intermediate outputs with different bit depths which confuse tools like
    VirtualDub. Placing an OutputNode at the end of the processing pipeline
    ensures that all images have the same format."""
    def __init__(self, name, inputs):
        super().__init__(name, inputs)

    def Eval(self, input, Output, index):
        an = [CONVERT, '-type', 'TrueColor', '-depth', '8'] + input + [Output]
        subprocess.call(an)

class SubstreamNode(Node):
    """Extract a substream from an input."""
    def __init__(self, name, inputs, first = 0, last = 0):
        super().__init__(name, inputs)
        self._first = first
        self._last = last

    def GetStreamLength (self):
        return self._last - self._first

    def Execute (self, index, target):
        self.inputs [0].Execute (index - self._first, target)
        return target

class OverlayNode (Node):
    '''Overlay two images.'''
    def __init__ (self, name, inputs, overlay):
        super ().__init__ (name, inputs, maxInputCount = 1)
        self._overlay = overlay

    def Eval(self, input, Output, index):
        an = [COMPOSITE, self._overlay] + input + [Output]
        subprocess.call(an)

class RepeatImageNode(Node):
    """Repeat an image multiple times."""
    def __init__(self, name, image, duration = 24):
        super().__init__(name, maxInputCount = 0)
        self._duration = duration
        self._image = image

    def Execute (self, index, target):
        an = [CONVERT, '-type', 'TrueColor', self._image, target]
        subprocess.call(an)

        return target

    def GetStreamLength (self):
        return self._duration

class RepeatInputNode(Node):
    """Repeat an input multiple times."""
    def __init__ (self, name, inputs, frame, duration = 24):
        super().__init__(name, inputs)
        self._duration = duration
        self._frame = frame

    def Execute (self, index, target):
        self.inputs [0].Execute (self._frame, target)
        return target

    def GetStreamLength (self):
        return self._duration

class FadeOutNode(Node):
    """Fade out to black."""
    def __init__(self, name, inputs, fadeOutDuration = 24, blur = False):
        super().__init__(name, inputs)
        self._duration = fadeOutDuration
        self._blur = blur
        self._length = inputs[0].GetStreamLength()
        assert fadeOutDuration <= inputs[0].GetStreamLength()
        self._start = self._length - self._duration

    def Eval(self, input, Output, index):
        start = self._length - self._duration
        progress = int ((index - start) / self._duration * 100)
        if index >= self._start:
            b = ['-blur', '0x' + str (int (progress / 100 * 16))] if self._blur else []
            an = [CONVERT, input, '-modulate', str (100 - progress)] + b + [Output]
            subprocess.call(an)
        else:
            an = [CONVERT, input, Output]
            subprocess.call(an)

    def GetStreamLength(self):
        return self._length

class FadeInNode(Node):
    """Fade in from black."""
    def __init__(self, name, inputs, fadeInDuration = 24, blur = False):
        super().__init__(name, inputs)
        self._duration = fadeInDuration
        self._blur = blur
        self._length = inputs[0].GetStreamLength()
        assert fadeInDuration <= inputs[0].GetStreamLength()

    def Eval(self, input, Output, index):
        start = self._length - self._duration
        progress = int ((index - start) / self._duration * 100)
        if index < self._duration:
            b = ['-blur', '0x' + str (int ((100 - progress) / 100 * 16))] if self._blur else []
            an = [CONVERT, input, '-modulate', str (progress)] + b + [Output]
            subprocess.call(an)
        else:
            an = [CONVERT, input, Output]
            subprocess.call(an)

    def GetStreamLength(self):
        return self._length

def GetStreamStartIndices (streams, blendFactor):
    ci = 0
    yield ci
    for stream in streams[:-1]:
        ci += stream
        ci -= blendFactor
        yield ci
    yield ci + streams[-1]

class ConcatNode(Node):
    """Concatenate multiple streams together, optionally with cross-blending
    between them."""
    def __init__(self, name, inputs, crossBlendDuration = 0, blur = True):
        super().__init__(name, inputs, maxInputCount = None)
        inputLengths = [i.GetStreamLength () for i in self.inputs]
        self._prefixSum = [v for v in GetStreamStartIndices (inputLengths, crossBlendDuration)]
        self._blend = crossBlendDuration
        self._blur = blur

    def GetStreamLength(self):
        return self._prefixSum [-1]

    def Execute (self, index, target):
        for i in range(len(self._prefixSum)):
            if index >= self._prefixSum[i] and index < self._prefixSum[i+1]:
                # Check if we need to crossblend
                if (index - self._prefixSum [i] < self._blend):
                    if i == 0:
                        self.inputs [i].Execute (index - self._prefixSum[i], target)
                        break

                    # Eval both
                    targets = [self.GetTemporary(i) for i in range(2)]

                    leftIndex = index - self._prefixSum[i-1]
                    rightIndex = index - self._prefixSum[i]

                    self.inputs[i-1].Execute (leftIndex, targets [0])
                    self.inputs[i].Execute (rightIndex, targets[1])

                    inFactor = rightIndex / self._blend
                    blurFactor = 1-abs(inFactor-0.5)*2

                    an = []
                    if self._blur:
                        an = [COMPOSITE, '-blur', '0x' + str(int(blurFactor * 16)), '-blend', str (int(inFactor*100)) + '%', targets[1], targets[0], target]
                    else:
                        an = [COMPOSITE, '-blend', str (int(inFactor*100)) + '%', targets[1], targets[0], target]
                    subprocess.call(an)
                else:
                    self.inputs [i].Execute (index - self._prefixSum[i], target)
                break

        return target

def CreateGraph(graphDesc):
    g = {}

    def GetInputNodes(g, inputNames):
        if inputNames == None:
            return []
        else:
            return [g[inputName] for inputName in inputNames]

    n = None
    for node in graphDesc:
        name = node ['name']
        params = {}
        if 'params' in node and node['params']:
            params = node ['params']

        inputs = GetInputNodes (g, node['inputs']) if 'inputs' in node else []
        t = node['type']
        if t == 'ImageSequence':
            n = ImageSequence (name, **params)
        elif t == 'Crop':
            n = CropNode (name, inputs, **params)
        elif t == 'AddLabel':
            n = AddLabelNode(name, inputs, **params)
        elif t == 'Merge':
            n = MergeNode(name, inputs, **params)
        elif t == 'Concatenate':
            n = ConcatNode (name, inputs, **params)
        elif t == 'FadeOut':
            n = FadeOutNode (name, inputs, **params)
        elif t == 'StillImage' or t == 'Image':
            n = RepeatImageNode (name, **params)
        elif t == 'EvaluateFrame':
            n = RepeatInputNode (name, inputs, **params)
        elif t == 'SubSequence':
            n = SubstreamNode (name, inputs, **params)
        elif t == 'Output':
            n = OutputNode (name, inputs)
        elif t == 'MergeTiled':
            n = MergeTiledNode (name, inputs, **params)
        elif t == 'Resize':
            n = ResizeNode (name, inputs, **params)
        elif t == 'ChangeCanvasSize':
            n = ChangeCanvasSizeNode (name, inputs, **params)
        elif t == 'Overlay':
            n = OverlayNode (name, inputs, **params)
        else:
            raise Exception('Unknown node type')
        g [name] = n

    return n

def Exec (graph, i, folder = "output", fileprefix = "ani_"):
    root = CreateGraph(graph)
    if i % 100 == 0:
        print(i)
    root.Execute (i, os.path.join (folder, "{0}{1:08}.png".format (fileprefix, i)))

def DumpGraph(root):
    def _DG(node):
        for i in node.inputs:
            print('"' + i.GetName () + '"', '->', '"' + node.GetName () + '"', ';')
            _DG(i)

    print('digraph G {')
    _DG(root)
    print('}')
