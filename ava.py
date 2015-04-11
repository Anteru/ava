import ava
from multiprocessing import Pool, cpu_count
import itertools
import os
import shutil

if __name__=='__main__':
    import glob, sys

    shutil.rmtree ("output", ignore_errors = True)
    os.mkdir ("output")

    # Your processing graph goes in here
    graph = [
        {
            'name' : 'Img_AVA',
            'type' : 'Image',
            'params' : {
                'image' : 'img1.png',
                'duration' : 64
                }
        },
        {
            'name' : 'Img_Sh13',
            'type' : 'Image',
            'params' : {
                'image' : 'img2.png',
                'duration' : 64
                }
        },
        {
            'name' : 'Concat',
            'type' : 'Concatenate',
            'inputs' : ['Img_AVA', 'Img_Sh13'],
            'params' : {
                'crossBlendDuration' : 16
                }
        },
        {
            'name' : 'Output',
            'type' : 'Output',
            'inputs' : ['Concat']
        }
    ]
    root = ava.CreateGraph(graph)

    processCount = cpu_count ()

    # You might want to limit the number of processes depending on the I/O backend
    p = Pool(processCount)
    l = root.GetStreamLength ()

    # Dump the graph. Use the dot tool to process the output.
    # DumpGraph(root)
    # sys.exit(1)

    print ('Processing {} frames on {} processes'.format(l, processCount))
    p.starmap(ava.Exec, zip (itertools.repeat (graph), range (l)))

    # Remove temporaries
    for f in glob.glob("_tmp_AVA__*.tga"):
        os.remove (f)
