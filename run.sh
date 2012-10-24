#!/bin/sh
PYTHONPATH=../:$PYTHONPATH python -m tornado.autoreload -m pyr.main
