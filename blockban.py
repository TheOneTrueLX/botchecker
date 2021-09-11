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

def get_access_token_from_url(url):
    token = str(urlopen(url).read(), 'utf-8')
    return token.split('=')[1].split('&')[0] #TODO: get the right slice

class HTTPServerHandler(BaseHTTPRequestHandler):
    def __init__(self, request, address, server, client_id, client_secret):
        self.client_id = client_id
        self.client_secret = client_secret
        super().__init__(request, address, server)

    def do_GET(self):
        TWITCH_API_AUTH_URI="https://id.twitch.tv/oauth2/authorize?" 
        + "response_type=token+id_token"
        + "&client_id={}".format(os.environ.get('TWITCH_CLIENT_ID'))
        + "&redirect_uri=http://localhost"
        + "&scope=viewing_activity_read+openid"
        + "&state=c3ab8aa609ea11e793ae92361f002671"
        + "&claims={\"id_token\":{\"email_verified\":null}}"
        
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

        if 'access_token' in self.path:
            self.auth_code = self.path.split('=')[1] #TODO: get the right slice
            self.wfile.write(bytes('<HTML><H1>YOU CAN NOW CLOSE THIS WINDOW</H1></HTML>'), 'utf-8')
            self.server.access_token = get_access_token_from_url(TWITCH_API_AUTH_URI + self.auth_code)

    def log_message(self, format, *args):
        return

class AuthTokenHandler:
    def __init__(self, client_id, client_secret):
        self._client_id = client_id
        self._client_secret = client_secret

    def get_access_token(self):
        httpServer = HTTPServer(('localhost', 8888), HTTPServerHandler)
        httpServer.handle_request()

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

    #TODO: load the contents of diff into both the user's blocklist and channel bans

if __name__ == "__main__":
    main()
