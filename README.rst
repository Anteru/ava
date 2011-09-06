========================================
Ava - Simple graph-based video processor
========================================

:Authors:
	Matthäus G. Chajdas
	
Overview
--------

Ava is a simple graph-based video processing tool which is useful if your
want to batch-process videos. The input is assumed to be one file per frame,
and Ava will also output all frames individually. The actual processing is
done by ImageMagick_.

I'm releasing the tool as it has been used for a bunch of videos I have done.
There's probably quite a bit of stuff that needs to be tweaked, but the code
should be easy to hack.

The core concept is a stream which is produced/consumed by nodes. The last
node in the graph pulls its inputs; so everything is lazily evaluated. Ava
uses the Python multiprocessing module to process each frame individually.

Todo
----

There's a bunch of stuff left if you want to make re-use easier:

* Loading the configuration from an external file (this can be trivially done
	using the JSON)
* GUI for the graph editing
* More useful nodes
* Better integration with dot
* More robust error handling

.. _ImageMagick: http://www.imagemagick.org/