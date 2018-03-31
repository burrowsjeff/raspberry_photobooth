#!/bin/python

######################################################################
# Raspberry PI powered Photo Booth
######################################################################
# Last updated 20170902 by ericBcreator
#
# This code is free for personal use, not for commercial purposes.
# Please leave this header intact.
#
# contact: ericBcreator@gmail.com
######################################################################
# original by Jack Barker: http://jackbarker.com.au/photo-booth/ 
######################################################################

"""

### auto start ###

to make the script run automatically after booting up, edit the rc.local file:
    sudo nano /etc/rc.local

at the end (but before the exit command) add this line:
    python /home/pi/EB-photo-booth/EB-pb.py &

don't forget the & sign or else the Pi won't boot up but wait until the
script is finished (which - normally - won't happen)

### flashing or continuous arcade led ###

when the positive lead of the led of the arcade button is connected to
pin 2 or 4 (5V) it will be on as long the Pi is powered

when it is connected to pin 7 (or GPIO4, default setup) it will get 3.3V
(so it is less bright) but it will perform flashing functions

"""

#Imports
import datetime
from time import sleep
import os
import time
from PIL import Image

import RPi.GPIO as GPIO
import picamera

from shutil import copy2

#############
### Debug ###
#############
# These options allow you to run a quick test of the app.
# All options must be set to 'False' when running as proper photobooth
TESTMODE_AUTOPRESS_BUTTON = False # Button will be pressed automatically, and app will exit after 1 photo cycle
TESTMODE_FAST             = False # Reduced wait between photos and 2 photos only
                                  # and 10 seconds startup delay
TESTMODE_NO_STARTUP_DELAY = False # Don't delay startup

#####################
### System Config ###
#####################
pin_camera_btn = 17         # pin the arcade button is connected to
pin_arcade_led = 4          # pin the led of the aracade button is connected to

########################
### Variables Config ###
########################
startup_delay = 60
total_pics = 3              # number of pics to be taken
prep_delay = 5              # number of seconds as users prepare to have photo taken
photo_w = 1920              # take photos at this resolution
photo_h = 1152
screen_w = 800              # resolution of the photo booth display
screen_h = 480
blink_speed = 8             # blink speed of 'press the button' overlays
photo_countdown_time = 4    # countdown time before photo is taken
photo_playback_time = 3     # time each photo is shown
timeout_processing = 3      # time the 'processing' screen is shown
backup_photo = True         # when TRUE, saves a backup photo to the default dir on the SD card and the original is stored on a USB drive
arcade_led_flashing = True  # flash the arcade led or not

# BTW: by default, the script will search for a USB drive
# if it finds one, it will create a 'EB-PB-photos' dir and saves to it
# if it doesn't find one, it will default to '/home/pi/EB-photo-booth/EB-PB-photos' on the SD card in the pi

if TESTMODE_FAST:
    total_pics = 2     # number of pics to be taken
    prep_delay = 2     # number of seconds at step 1 as users prep to have photo taken
    startup_delay = 10 # start up delay is just 10 seconds

REAL_PATH = os.path.dirname(os.path.realpath(__file__))

########################
### Helper Functions ###
########################
def print_overlay(string_to_print):
    """
    Writes a string to both [i] the console, and [ii] camera.annotate_text
    """
    #log_print(string_to_print)
    camera.annotate_text = string_to_print

def get_base_filename_for_images():
    """
    For each photo-capture cycle, a common base filename shall be used,
    based on the current timestamp.

    Example:
    ${ProjectRoot}/EB-PB-photos/2017-12-31_23-59-59

    The example above, will later result in:
    ${ProjectRoot}/EB-PB-photos/2017-12-31_23-59-59_1of4.png, being used as a filename.
    """
    base_filename = PHOTO_PATH + str(datetime.datetime.now()).split('.')[0]
    base_filename = base_filename.replace(' ', '_')
    base_filename = base_filename.replace(':', '-')
    return base_filename

def remove_overlay(overlay_id):
    """
    If there is an overlay, remove it
    """
    if overlay_id != -1:
        camera.remove_overlay(overlay_id)

# overlay one image on screen
def overlay_image(image_path, duration=0, layer=3):
    """
    Add an overlay (and sleep for an optional duration).
    If sleep duration is not supplied, then overlay will need to be removed later.
    This function returns an overlay id, which can be used to remove_overlay(id).
    """

    # Load the arbitrarily sized image
    img = Image.open(image_path)
    # Create an image padded to the required size with
    # mode 'RGB'
    pad = Image.new('RGB', (
        ((img.size[0] + 31) // 32) * 32,
        ((img.size[1] + 15) // 16) * 16,
        ))
    # Paste the original image into the padded one
    pad.paste(img, (0, 0))

    # Add the overlay with the padded image as the source,
    # but the original image's dimensions
    o_id = camera.add_overlay(pad.tostring(), size=img.size)
    o_id.layer = layer

    if duration > 0:
        sleep(duration)
        camera.remove_overlay(o_id)
        return -1 # '-1' indicates there is no overlay
    else:
        return o_id # we have an overlay, and will need to remove it later

###############
### Screens ###
###############

def prep_for_photo_screen(photo_number):
    """
    Prompt the user to get ready for the next photo
    """

    #Get ready for the next photo
    get_ready_image = REAL_PATH + "/assets/get_ready_"+str(photo_number)+".png"
    overlay_image(get_ready_image, prep_delay)

def taking_photo(photo_number, filename_prefix):
    """
    This function captures the photo
    """

    #get filename to use
    filename = filename_prefix + '_' + str(photo_number) + 'of'+ str(total_pics)+'.jpg'

    #countdown from #, and display countdown on screen
    for counter in range(photo_countdown_time,0,-1):
        print_overlay("             ..." + str(counter))
        if arcade_led_flashing:
            GPIO.output(pin_arcade_led, 1)
        sleep(.5)

        if arcade_led_flashing:
            GPIO.output(pin_arcade_led, 0)
        sleep(.5)

    #Take still
    if arcade_led_flashing:
        GPIO.output(pin_arcade_led, 1)

    camera.annotate_text = ''
    camera.capture(filename)
    log_print("Photo (" + str(photo_number) + ") saved: " + filename)

    if not PHOTO_PATH_BCK == "":
        filename_bck = PHOTO_PATH_BCK + os.path.basename(filename)
        copy2(filename, filename_bck)
        log_print ("Backup photo: " + filename_bck)

    if arcade_led_flashing:
        GPIO.output(pin_arcade_led, 0)

def playback_screen(filename_prefix):
    """
    Final screen before main loop restarts
    """

    #Processing
    log_print("Processing...")
    processing_image = REAL_PATH + "/assets/processing.png"
    overlay_image(processing_image, timeout_processing)
    
    #Playback
    prev_overlay = False
    for photo_number in range(1, total_pics + 1):
        filename = filename_prefix + '_' + str(photo_number) + 'of'+ str(total_pics)+'.jpg'
        this_overlay = overlay_image(filename, False, 3+total_pics)

        # The idea here, is only remove the previous overlay after a new overlay is added.
        if prev_overlay:
            remove_overlay(prev_overlay)

        sleep(photo_playback_time)
        prev_overlay = this_overlay
    remove_overlay(prev_overlay)
    
    #All done
    log_print("All done!")
    finished_image = REAL_PATH + "/assets/all_done.png"
    overlay_image(finished_image, 5)

#############################################
### Setup Log print function and log file ###
#############################################

def log_print(text):
    print (text)

    with open(REAL_PATH + "/_EB-PB.log", 'a') as logfile:
        logfile.write(str(datetime.datetime.now()).split('.')[0] + " " + text + '\r\n')

### Startup ###################################################################

log_print("logfile opened")

log_print("EB Photo Booth - initializing...")

#Setup GPIO
GPIO.setmode(GPIO.BCM)
GPIO.setup(pin_camera_btn, GPIO.IN, pull_up_down=GPIO.PUD_UP)
GPIO.setup(pin_arcade_led, GPIO.OUT, initial = GPIO.LOW)

#Quit if the button is pressed while starting up
if GPIO.input(pin_camera_btn) == GPIO.LOW:
    log_print("exiting - the button was pressed during start up.")
    raise SystemExit

#Setup Camera
try:
    camera = picamera.PiCamera()
except:
    log_print("error initializing the camera - exiting")
    raise SystemExit
    
camera.rotation = 0
camera.annotate_text_size = 80
camera.resolution = (photo_w, photo_h)
#camera.hflip = True # When preparing for photos, the preview will be flipped horizontally.

#delay startup
if not TESTMODE_NO_STARTUP_DELAY:
    log_print ("Startup delay " + str(startup_delay))

    startup_image_1 = REAL_PATH + "/assets/startup_1.png"
    startup_image_2 = REAL_PATH + "/assets/startup_2.png"
    overlay_startup_1 = overlay_image(startup_image_1, 0, 3)
    overlay_startup_2 = overlay_image(startup_image_2, 0, 4)

    i = 1
    for counter in range(startup_delay,0,-1):
        sleep(1)

        if i == 1:
            overlay_startup_2.alpha = 255
            i = 0
        else:
            overlay_startup_2.alpha = 0
            i = 1
    
    remove_overlay(overlay_startup_1)
    remove_overlay(overlay_startup_2)

################################################################################
### Check if there is a usb drive: if so, set path to it or use default path ###
################################################################################

basedir = '/media/pi/'
CHECK_FILE = '__EB_PB_init.txt'

PHOTO_PATH = ""
for d in os.listdir(basedir):
    PHOTO_PATH = os.path.join(basedir, d) + "/EB-PB-photos/"

    print(PHOTO_PATH)

    # check if '/EB-PB-photos/' path exists and if not, create it
    # if creating the paths generates an error, set path to "" and go for next one
    if not os.path.exists(PHOTO_PATH):
        try:
            os.makedirs(PHOTO_PATH)
        except:
            PHOTO_PATH = ""
            print ("error creating dir")

    # if the path exists, check if the check files exists. if not, try to create it
    # if one of either fails, go for the next path
    if not PHOTO_PATH == "":
        try:
            tmpfile = open(PHOTO_PATH + CHECK_FILE,'a') 
            tmpfile.write(str(datetime.datetime.now()).split('.')[0])
            tmpfile.write ('\r\n')
            tmpfile.close()
            break
        except:
            PHOTO_PATH = ""
    
# no photo_path set so use default
if PHOTO_PATH == "":
    PHOTO_PATH = REAL_PATH + "/EB-PB-photos/"

log_print ("Saving to " + PHOTO_PATH)

PHOTO_PATH_BCK = REAL_PATH + "/EB-PB-photos/"

if PHOTO_PATH == PHOTO_PATH_BCK or not backup_photo:
    PHOTO_PATH_BCK = ""
    log_print ("Not saving backup files")
else:
    log_print ("Saving backup files to " + PHOTO_PATH_BCK)

### main #######################################################################

def main():
    """
    Main program loop
    """

    #Start Program
    log_print("")
    log_print("Welcome to the EB Photo Booth!")
    log_print("Press the button to take a photo")

    #Turn on the arcade led
    GPIO.output(pin_arcade_led, 1)    

    #Start camera preview
    camera.start_preview(resolution=(screen_w, screen_h))
    
    #Display intro screen
    intro_image_1 = REAL_PATH + "/assets/intro_1.png"
    intro_image_2 = REAL_PATH + "/assets/intro_2.png"
    overlay_1 = overlay_image(intro_image_1, 0, 3)
    overlay_2 = overlay_image(intro_image_2, 0, 4)

    #Wait for someone to push the button
    i = 0
    while True:

        #Use falling edge detection to see if button is pushed
        is_pressed = GPIO.wait_for_edge(pin_camera_btn, GPIO.FALLING, timeout=100)

        if TESTMODE_AUTOPRESS_BUTTON:
            is_pressed = True

        #Stay inside loop, until button is pressed
        if is_pressed is None:
            
            #After every # of cycles, alternate the overlay
            i = i+1
            if i==blink_speed:
                overlay_2.alpha = 255
                if arcade_led_flashing:
                    GPIO.output(pin_arcade_led, 1)

            elif i==(2*blink_speed):
                overlay_2.alpha = 0
                i=0
                if arcade_led_flashing:
                    GPIO.output(pin_arcade_led, 0)
            
            #Regardless, restart loop
            continue

        #Button has been pressed!
        filename_prefix = get_base_filename_for_images()
        log_print("Button pressed")
        remove_overlay(overlay_2)
        remove_overlay(overlay_1)

        #Turn off the arcade led
        if arcade_led_flashing:
            GPIO.output(pin_arcade_led, 0)

        for photo_number in range(1, total_pics + 1):
            prep_for_photo_screen(photo_number)
            taking_photo(photo_number, filename_prefix)

        #thanks for playing
        playback_screen(filename_prefix)

        # If we were doing a test run, exit here.
        if TESTMODE_AUTOPRESS_BUTTON:
            break

        # Otherwise, display intro screen again
        overlay_1 = overlay_image(intro_image_1, 0, 3)
        overlay_2 = overlay_image(intro_image_2, 0, 4)
        log_print("Press the button to take a photo")

if __name__ == "__main__":
    try:
        main()

    except KeyboardInterrupt:
        log_print("keyboard interrupt")
        
    except Exception as exception:
        log_print("unexpected error: " + str(exception))

    finally:
        log_print ("logfile closed")
        camera.stop_preview()
        GPIO.cleanup()
