#!/usr/bin/env bash
cd "$(dirname "$0")"
pip install -r requirements.txt
PORT=${PORT:-8080} python3 server.py
