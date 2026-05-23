#!/bin/bash

   echo "Starting Kiosk Boot Sequence..."
   sleep 5

   #Check for an internet connection
   if ! ping -q -c 1 -W 2 8.8.8.8 >/dev/null 2>&1; then
       echo "No internet detected. Launching Captive Portal..."
       cd /home/seppo/DispLife/
   	/home/seppo/venv/bin/gunicorn -w 1 -b 127.0.0.1:5000 setup:app &
	pid=$!
        sudo wifi-connect
        kill $pid 
   else
        echo "Internet already connected!"
   fi
   echo "Starting server"

   #Start Flask server using virtual environment
   cd /home/seppo/DispLife/
   /home/seppo/venv/bin/gunicorn -w 1 -b 127.0.0.1:5000 server:app
