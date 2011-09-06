# Copyright 2011 Matthaeus G. Chajdas. All rights reserved.
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
CONVERT = 'B://Dev//Tools//ImageMagick//convert.exe'
COMPOSITE = 'B://Dev//Tools//ImageMagick//composite.exe'
MONTAGE = 'B://Dev//Tools//ImageMagick//montage.exe'

class Node:
    def __init__(self, name, inputs = [], minInputCount = 0, maxInputCount = 1):
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
    
    def GetStreamSize(self):
        return min([input.GetStreamSize() for input in self.inputs])
    
class ImageSequence(Node):
    """A sequence of images. The image name must contain a valid Python
    format string. The image index is used to generate the final file name.
    For instance, using 'img{0:04}.png' with count=3 and offset=1 will produce
    'img0001.png', 'img0002.png' and 'img0003.png'."""
    def __init__(self, name, format, count, offset = 0):
        super().__init__(name, maxInputCount = 0)
        self.format = format
        self.count = count
        self.offset = offset
        
    def Execute (self, index, target):
        an = [CONVERT, self.format.format (index+self.offset), target]
        subprocess.call(an)
        
        return target
        
    def GetStreamSize(self):
        return self.count
            
class AddLabelNode(Node):
    """Add a label to a node. The corner must be a valid ImageMagick corner."""
    def __init__(self, name, inputs, label, corner="SouthWest"):
        super().__init__(name, inputs)
        self.label = label
        self.corner = corner
        
    def Eval(self, input, output, index):
        an = [CONVERT,
          input, '-fill', 'white', '-undercolor', '#00000080', '-pointsize', '24',
          '-gravity',  self.corner, '-annotate', '+0+5', " {} ".format(self.label),
          output]
        subprocess.call(an)

class CropNode(Node):
    """Crop an image."""
    def __init__(self, name, inputs, hSize, vSize, hOffset = 0, vOffset = 0):
        super().__init__(name, inputs)
        self.format = "{}%x{}%+{}+{}".format (hSize, vSize, hOffset, vOffset)
        
    def Eval(self, input, Output, index):
        an = [CONVERT, input, '-crop', self.format, Output]
        subprocess.call(an)
        
class MergeNode(Node):
    """Merge multiple images."""
    def __init__(self, name, inputs):
        super().__init__(name, inputs, maxInputCount = None)
        
    def Eval(self, input, Output, index):
        an = [CONVERT] + input + ['+append', Output]
        subprocess.call(an)
        
class MergeTiledNode (Node):
    """Merge images in a 2x2 tile."""
    def __init__(self, name, inputs):
        super().__init__(name, inputs, maxInputCount = 4)
        
    def Eval(self, input, Output, index):
        an = [MONTAGE] + input + ['-mode', 'Concatenate', '-tile', '2x2', Output]
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
        an = [CONVERT, '-define', 'png:color-type=2', '-depth', '8', input, 'PNG24:' + Output]
        subprocess.call(an)
        
class SubstreamNode(Node):
    """Extract a substream from an input."""
    def __init__(self, name, inputs, first = 0, last = 0):
        super().__init__(name, inputs)
        self.first = first
        self.last = last
        
    def GetStreamSize (self):
        return self.last - self.first
                
    def Execute (self, index, target):
        self.inputs [0].Execute (index - self.first, target)
        return target
        
class RepeatImageNode(Node):
    """Repeat an image multiple times."""
    def __init__(self, name, image, duration = 24):
        super().__init__(name, maxInputCount = 0)
        self.duration = duration
        self.image = image
        
    def Execute (self, index, target):
        an = [CONVERT, self.image, target]
        subprocess.call(an)
        
        return target
        
    def GetStreamSize(self):
        return self.duration
    
class FadeOutNode(Node):
    """Fade out to black."""
    def __init__(self, name, inputs, fadeOutDuration = 24, blur = False):
        super().__init__(name, inputs)
        self.duration = fadeOutDuration
        self.blur = blur
        self.length = inputs[0].GetStreamSize()
        assert fadeOutDuration <= inputs[0].GetStreamSize()
        self.start = self.length - self.duration
        
    def Eval(self, input, Output, index):
        start = self.length - self.duration
        progress = int ((index - start) / self.duration * 100)
        if index >= self.start:
            b = ['-blur', '0x' + str (int (progress / 100 * 16))] if self.blur else []
            an = [CONVERT, input, '-modulate', str (100 - progress)] + b + [Output]
            subprocess.call(an)
        else:
            an = [CONVERT, input, Output]
            subprocess.call(an)
            
    def GetStreamSize(self):
        return self.length
    
class FadeInNode(Node):
    """Fade in from black."""
    def __init__(self, name, inputs, fadeInDuration = 24, blur = False):
        super().__init__(name, inputs)
        self.duration = fadeInDuration
        self.blur = blur
        self.length = inputs[0].GetStreamSize()
        assert fadeInDuration <= inputs[0].GetStreamSize()
        
    def Eval(self, input, Output, index):
        start = self.length - self.duration
        progress = int ((index - start) / self.duration * 100)
        if index < self.duration:
            b = ['-blur', '0x' + str (int ((100 - progress) / 100 * 16))] if self.blur else []
            an = [CONVERT, input, '-modulate', str (progress)] + b + [Output]
            subprocess.call(an)
        else:
            an = [CONVERT, input, Output]
            subprocess.call(an)
            
    def GetStreamSize(self):
        return self.length

def GetStreamStartIndices(streams, blendFactor):
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
    def __init__(self, name, inputs, crossBlendDuration = 0):
        super().__init__(name, inputs, maxInputCount = None)
        self.parts = [i.GetStreamSize () for i in self.inputs]
        self.prefixSum = [v for v in GetStreamStartIndices (self.parts, crossBlendDuration)]
        self.blend = crossBlendDuration
        
    def GetStreamSize(self):
        return self.prefixSum [-1]
    
    def Execute (self, index, target):
        for i in range(len(self.prefixSum)):
            if index >= self.prefixSum[i] and index < self.prefixSum[i+1]:
                # Check if we need to crossblend
                if (index - self.prefixSum [i] < self.blend):
                    if i == 0:
                        self.inputs [i].Execute (index - self.prefixSum[i], target)
                        break
                                            
                    # Eval both
                    targets = [self.GetTemporary(i) for i in range(2)]
                    
                    leftIndex = index - self.prefixSum[i-1]
                    rightIndex = index - self.prefixSum[i]
                    
                    self.inputs[i-1].Execute (leftIndex, targets [0])
                    self.inputs[i].Execute (rightIndex, targets[1])
                                    
                    inFactor = rightIndex / self.blend
                    blurFactor = 1-abs(inFactor-0.5)*2
                                        
                    an = [COMPOSITE, '-blur', '0x' + str(int(blurFactor * 16)), '-blend', str (int(inFactor*100)) + '%', targets[1], targets[0], target]
                    subprocess.call(an)
                else:                
                    self.inputs [i].Execute (index - self.prefixSum[i], target)
                break
        
        return target

# Example configuration
graph = [# Load images
         {
          'name' : 'Load-SW-Reference',
          'type' : 'ImageSequence',
          'params' :
            {
                 'format':'ani-output/regular-16-{0:03}.png',
                 'offset' : 1,
                 'count' : 300
            }
          },
         {
          'name' : 'Load-SW-Regular',
          'type' : 'ImageSequence',
          'params' :
            {
                 'format':'ani-output/regular-1-{0:03}.png',
                 'offset' : 1,
                 'count' : 300
            }
          },
         {
          'name' : 'Load-SW-MLAA',
          'type' : 'ImageSequence',
          'params' :
            {
                 'format':'ani-output/mlaa-{0:03}.png',
                 'offset' : 1,
                 'count' : 300
            }
          },
         {
          'name' : 'Load-SW-SRAA',
          'type' : 'ImageSequence',
          'params' :
            {
                 'format':'ani-output/sraa-{0:03}.png',
                 'offset' : 1,
                 'count' : 300
            }
          },
          # add labels
          {
           'name' : 'SW-MLAA-Labeled',
          'type' : 'AddLabel',
          'params': {'label' : 'MLAA', 'corner' : 'SouthWest'},
          'inputs' : ['Load-SW-MLAA']
           },
          {
           'name' : 'SW-Ref-Labeled',
          'type' : 'AddLabel',
          'params': {'label' : 'Reference (16x shading)', 'corner' : 'NorthEast'},
          'inputs' : ['Load-SW-Reference']
           },
          {
           'name' : 'SW-Regular-Labeled',
          'type' : 'AddLabel',
          'params': {'label' : 'Input (1x shading)', 'corner' : 'NorthWest'},
          'inputs' : ['Load-SW-Regular']
           },
          {
           'name' : 'SW-SRAA-Labeled',
          'type' : 'AddLabel',
          'params': {'label' : 'SRAA', 'corner' : 'SouthEast'},
          'inputs' : ['Load-SW-SRAA']
           },
           # tile 4
           {
                'name' : 'SW-Tiled',
                'type' : 'MergeTiled',
                'params' : None,
                'inputs' : ['SW-Regular-Labeled', 'SW-Ref-Labeled', 'SW-MLAA-Labeled', 'SW-SRAA-Labeled']
            },
            # 
         {
          'name' : 'Load-Reference', 'type' : 'ImageSequence',
          'params' :
            {
                 'format':'RefBiasTweaked/capture{0:08}.tga',
                 'offset' : 421,
                 'count' : 700
            }
         },
         {
          'name' : 'Load-SRAA', 'type' : 'ImageSequence',
          'params' :
            {
                 'format':'SRAA/capture{0:08}.png',
                 'offset' : 388,
                 'count' : 700
            }
         },
         {
          'name' : 'Load-MLAA', 'type' : 'ImageSequence',
          'params' :
            {
                 'format':'MLAA/frame{0:08}.png',
                 'offset' : 1,
                 'count' : 700
            }
         },
         {
          'name' : 'Load-Regular', 'type' : 'ImageSequence',
          'params' :
            {
                 'format':'NoMSAA/capture{0:08}.png',
                 'offset' : 363,
                 'count' : 700
            }
         },
         # full-size-label
         {
          'name' : 'SRAA-Fullscreen-Labeled',
          'type' : 'AddLabel',
          'params': {'label' : 'SRAA', 'corner' : 'NorthEast'},
          'inputs' : ['Load-SRAA']
          },
         {
          'name' : 'fullres-label-reg',
          'type' : 'AddLabel',
          'params': {'label' : 'Regular (36 fps)', 'corner' : 'NorthEast'},
          'inputs' : ['Load-Regular']
          },         
         # Cropping
         {
          'name' : 'Crop-ref',
          'type' : 'Crop',
          'params' : { 'hSize' : 25, 'vSize' : 100 },
          'inputs' : ['Load-Reference']
         },
         {
          'name' : 'Crop-mlaa',
          'type' : 'Crop',
          'params' : { 'hSize' : 25, 'vSize' : 100 },
          'inputs' : ['Load-MLAA']
         },
         {
          'name' : 'Crop-regular',
          'type' : 'Crop',
          'params' : { 'hSize' : 25, 'vSize' : 100 },
          'inputs' : ['Load-Regular']
         },
         {
          'name' : 'Crop-sraa',
          'type' : 'Crop',
          'params' : { 'hSize' : 25, 'vSize' : 100 },
          'inputs' : ['Load-SRAA']
         },
         # left-side crops
         
         {
          'name' : 'Crop-mlaa-left',
          'type' : 'Crop',
          'params' : { 'hSize' : 50, 'vSize' : 100 },
          'inputs' : ['Load-MLAA']
         },
         {
          'name' : 'Crop-regular-left',
          'type' : 'Crop',
          'params' : { 'hSize' : 50, 'vSize' : 100 },
          'inputs' : ['Load-Regular']
         },
         {
          'name' : 'Crop-SRAA-50%',
          'type' : 'Crop',
          'params' : { 'hSize' : 50, 'vSize' : 100 },
          'inputs' : ['Load-SRAA']
         },
         {
          'name' : 'Crop-ref-left',
          'type' : 'Crop',
          'params' : { 'hSize' : 50, 'vSize' : 100 },
          'inputs' : ['Load-Reference']
         },
         # Label stuff
         {
          'name' : 'AddLabel-ref',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'Reference'
            },
          'inputs' : ['Crop-ref']
          },
         {
          'name' : 'AddLabel-mlaa',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'MLAA'
            },
          'inputs' : ['Crop-mlaa']
          },
         {
          'name' : 'AddLabel-regular',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'Regular (1x)'
            },
          'inputs' : ['Crop-regular']
          },
         {
          'name' : 'AddLabel-sraa',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'SRAA'
            },
          'inputs' : ['Crop-sraa']
          },
          # large Crop labels
          {
          'name' : 'label-ref-left',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'Reference (1 fps)',
                'corner':'NorthWest'
            },
          'inputs' : ['Crop-ref-left']
          },
         {
          'name' : 'label-mlaa-left',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'MLAA (35 fps)',
                'corner':'NorthWest'
            },
          'inputs' : ['Crop-mlaa-left']
          },
         {
          'name' : 'label-regular-left',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'Regular (36 fps)',
                'corner':'NorthWest'
            },
          'inputs' : ['Crop-regular-left']
          },
         {
          'name' : 'label-sraa-right',
          'type' : 'AddLabel',
          'params' : 
            {
                'label':'SRAA (35 fps)',
                'corner' : 'NorthEast'
            },
          'inputs' : ['Crop-SRAA-50%']
          },
          # Stitch
          {
           'name' : 'Merge-4-side-by-side',
           'type' : 'Merge',
           'params' : None,
           'inputs' : ['AddLabel-regular', 'AddLabel-mlaa', 'AddLabel-sraa', 'AddLabel-ref']
           },
           # stitch 2
           {
            'name' : 'reg-vs-sraa',
            'type' : 'Merge',
            'params' : None,
            'inputs' : ['label-regular-left', 'label-sraa-right']
            },
           {
            'name' : 'mlaa-vs-sraa',
            'type' : 'Merge',
            'params' : None,
            'inputs' : ['label-mlaa-left', 'label-sraa-right']
            },
           {
            'name' : 'ref-vs-sraa',
            'type' : 'Merge',
            'params' : None,
            'inputs' : ['label-ref-left', 'label-sraa-right']
            },
           # Substream of stitch
           {
            'name' : 'Merge-4-side-by-side-short',
            'type' : 'SubSequence',
            'params' : {'first' : 0, 'last' : 224},
            'inputs' : ['Merge-4-side-by-side']
            },
            # SubSequence of fullres regular
            {
            'name' : 'Regular-Fullscreen-Labeled-Short',
            'type' : 'SubSequence',
            'params' : {'first' : 0, 'last' : 224},
            'inputs' : ['fullres-label-reg']
            },
           # title screen
           {
            'name' : 'TitleScreen',
            'type' : 'StillImage',
            'params' : {'image' : 'title.png', 'duration' : 72},
            'inputs' : None
            },
            {
             'name' : 'Titlescreen-FadeOut',
             'type' : 'FadeOut',
             'params' : {'blur' : True},
             'inputs' : ['TitleScreen']
             },
             # Disclaimer screen
             {
            'name' : 'DisclaimerScreen',
            'type' : 'StillImage',
            'params' : {'image' : 'disclaimer.png', 'duration' : 120},
            'inputs' : None
            },
          # Concat
          {
           'name' : 'Concatenate',
           'type' : 'Concatenate',
           'params' : {'crossBlendDuration' : 16 },
           'inputs' : ['Titlescreen-FadeOut' ,'SW-Tiled', 'DisclaimerScreen', 'reg-vs-sraa','mlaa-vs-sraa',
                       'ref-vs-sraa', 'Merge-4-side-by-side-short', 'Regular-Fullscreen-Labeled-Short', 'SRAA-Fullscreen-Labeled']
           },
           # Output
           {
            'name' : 'Output',
            'type' : 'Output',
            'params' : None,
            'inputs' : ['Concatenate']
            }]

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
            params = node['params'] if node['params'] is not None else {}
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
            elif t == 'StillImage':
                n = RepeatImageNode (name, **params)
            elif t == 'SubSequence':
                n = SubstreamNode (name, inputs, **params)
            elif t == 'Output':
                n = OutputNode (name, inputs)
            elif t == 'MergeTiled':
                n = MergeTiledNode (name, inputs, **params)
            g [name] = n
    
        return n
    
def Exec (i):
    root = CreateGraph(graph)
    if i % 100 == 0:
        print(i)
    root.Execute (i, "poutput/test{0:08}.png".format(i))

def DumpGraph(root):
    def _DG(node):
        for i in node.inputs:
            print('"' + i.GetName () + '"', '->', '"' + node.GetName () + '"', ';')
            _DG(i)
    
    print('digraph G {')
    _DG(root)
    print('}')

if __name__=='__main__':
    import glob, sys
    print('Ava node-based video processor')
    root = CreateGraph(graph)

    processCount = cpu_count ()

    # You might want to limit the number of processes depending on the I/O backend
    
    p = Pool(processCount)
    l = root.GetStreamSize ()

    # Dump the graph. Use the dot tool to process the output.
    # DumpGraph(root)
    # sys.exit(1)

    print ('    Processing {} frames on {} processes'.format(l, processCount))
    p.map(Exec, range (l))

    # Remove temporaries
    for f in glob.glob("_tmp_AVA__*.tga"):
        os.remove (f)
