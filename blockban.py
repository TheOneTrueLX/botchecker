import os, shutil, mmap
import argparse

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen, HTTPError
from webbrowser import open_new

from dotenv import load_dotenv
import requests
import dateutil.parser as dt

# This script imports functions from botchecker.py.  You better not've deleted it...
from botchecker import update_namelist, twitch_api_auth

# oauth2 implicit auth example used below comes from https://gist.github.com/Blackburn29/126dccf185e4bb2276dc

CURRENT_BLOCKLIST='namelist-current.txt'
WORKING_BLOCKLIST='namelist.txt'
SCRATCH_BLOCKLIST='namelist-scratch.txt'

class HTTPServerHandler(BaseHTTPRequestHandler):
    def __init__(self, request, address, server):
        super().__init__(request, address, server)

    def do_GET(self):
        '''
        Handle callback request from Twitch 
        '''
        # Send a success response code and bare minimum headers back to the
        # user's browser
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if 'access_token' in self.path:
            # Spit out a basic HTML repsonse to the browser
            self.wfile.write(bytes('<HTML><H1>YOU CAN NOW CLOSE THIS WINDOW</H1></HTML>'), 'utf-8')

            # parse out the access token from the query string
            self.server.access_token = self.path.split('=')[1]

    def log_message(self, format, *args):
        # by default, http.server logging is noisy, so we fix that here.
        return

class AuthTokenHandler:
    def get_access_token(self):
        # a note on scopes:
        #   channel:moderate is required to perform moderation actions in the chat API (e.g. banning users)
        #   user:manage:blocked_users is required to manage a user's blocklist
        ACCESS_URI="https://id.twitch.tv/oauth2/authorize"
        + "?client_id={}".format(os.environ.get('TWITCH_CLIENT_ID'))
        + "&redirect_uri=http://{}:{}".format(os.environ.get('CALLBACK_HOST'), os.environ.get('CALLBACK_PORT'))
        + "&response_type=token"
        + "&scope=channel:moderate+user:manage:blocked_users"

        # Pop open the user's browser and open it to the Twitch OAuth URL
        open_new(ACCESS_URI)

        # Open up an HTTP server instance to listen to handle the callback from Twitch
        httpServer = HTTPServer(
            (
                os.environ.get('CALLBACK_HOST'),
                os.environ.get('CALLBACK_PORT')
            ),
            lambda request, address, server: HTTPServerHandler(
                request, address, server
            )
        )
        httpServer.handle_request()
        return httpServer.access_token

def main():
    # load the secrets from .env
    load_dotenv()

    # get a fresh copy of the namelist (see botchecker.py)
    update_namelist()

    # first we generate SCRATCH_BLOCKLIST which is the list of names we will be
    # blocking/banning on Twitch.
    if os.path.isfile(CURRENT_BLOCKLIST):
        # Otherwise, we need to generate a diff between CURRENT_BLOCKLIST
        # and WORKING_BLOCKLIST to extract just the newly-added names, then
        # save that diff to SCRATCH_BLOCKLIST.
        os.remove(SCRATCH_BLOCKLIST)
        left_file = open(CURRENT_BLOCKLIST, "r").readlines()
        right_file = open(WORKING_BLOCKLIST, "r").readlines()
        scratch = list(set(right_file) - set(left_file))
        with open(SCRATCH_BLOCKLIST, 'w') as f:
            for item in scratch:
                f.write('%s' % item)

        # This might not be strictly necessary, but since we're loading two exceptionally
        # large text files into memory, this kinda feels like the right thing to do...
        left_file = None
        right_file = None
        scratch = None
    
    else:
        # If CURRENT_BLOCKLIST doesn't exist, we're going to assume that
        # this is the first run of the script, in which case we need to 
        # process the entire name list.  We do this by simply copying
        # WORKING_BLOCKLIST to both CURRENT_BLOCKLIST and SCRATCH_BLOCKLIST.

        # As long as you don't cock up the text files in the script's
        # working directory, everything should stay gucci.
        shutil.copy(WORKING_BLOCKLIST, CURRENT_BLOCKLIST)
        shutil.copy(WORKING_BLOCKLIST, SCRATCH_BLOCKLIST)

        print('*** WARNING: first run of script detected.  This is going to take a long time.')

    # This is where the party starts.
    diff = open(SCRATCH_BLOCKLIST).readline()

    # Most users aren't going to be expecting a brower window to get popped open by
    # a python script, so we should probably explain wtf is about to happen...
    print("""
    This application needs to be authorized with Twitch to allow access to your blocklist and/or
    channel bans.  

    In a few moments, a browser window will open requesting authorization from Twitch. Click the
    "authorize" button to allow this script to continue.

    If you've already authorized this script previously, 
    """)

    # Do the OAuth dance with Twitch
    twitchauth = AuthTokenHandler()
    access_token = twitchauth.get_access_token()

    #TODO: load the contents of diff into both the user's blocklist and channel bans

if __name__ == "__main__":
    main()
