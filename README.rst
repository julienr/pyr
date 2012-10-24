A quick demo on how to embed R in a web server
==============================================
This is a read–eval–print loop (REPL) for R that uses a web-based GUI.
R runs on the server-side using rpy2. Tornado is used as the web server
and then communication with the HTML interface is done using websockets.

This was hacked together in 3 hours, so it's just a demo.
It uses way too much global variable to be taken seriously :-)

There are also still issues with plotting. To avoid problems, you should
call dev.off() after every plot.

Screenshot
----------
.. image:: https://raw.github.com/julienr/pyr/master/screenshot.png
