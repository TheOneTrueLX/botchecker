import os, shutil, time
import argparse

from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen, HTTPError
from webbrowser import open_new

from dotenv import load_dotenv
import requests
import dateutil.parser as dt

# This script imports functions from botchecker.py.  You better not've deleted it...
from botchecker import update_namelist

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

def ratelimit_handler(response: requests.Response, *args, **kwargs):

    if response.headers['Ratelimit-Remaining'] == 0:
        # Twitch's API will tell us in the response headers how much time we have
        # to wait until the rate limit token-bucket is refilled.  For some inexplicable
        # reason, though, Twitch decided that they'd return a timestamp in epoch
        # format for when the bucket will reset, instead of, you know, the NUMBER OF
        # SECONDS WE HAVE TO WAIT...
        #
        # So we have to jump through even more hoops to get that number of seconds.
        ratelimit_reset = datetime.fromtimestamp(response.headers['Ratelimit-Reset'])
        current_time = datetime.now()
        delta = ratelimit_reset - current_time

        # Sleepy time
        print('!!! RATE LIMIT REACHED - pausing for {} seconds...'.format(delta.seconds))
        time.sleep(delta.seconds)
    
    return response

def api_health_handler(response: requests.Response, *args, **kwargs):
    # If Twitch's API goes down, it will return a 503 Service Unavailable error, 
    # which we will intercept and respond to gracefully here.
    if response.status_code == "503":
        # Handle API outages "gracefully"
        print("!!! Twitch API shit the bed.  Exiting...")
        exit()
        # Yep... gracefully...

    return response

def main():

    parser = argparse.ArgumentParser(
        description="""
Add known bot accounts to Twitch user blocklist and channel ban list.  By default, accounts are added
to both ban list and block list.  This behavior can be controlled by command line arguments.

The bot list at https://github.com/LinoYeen/Namelists is used by this script.  On the first run, this
entire list is loaded, which may take take well over a day.  
"""
    )

    parser_group = parser.add_mutually_exclusive_group()
    parser_group.add_argument('--only-block', action='store_true', help='Only add bot accounts to block list')
    parser_group.add_argument('--only-ban', action='store_true', help='Only add bot accounts to channel ban list')
    parser_group.add_argument('--only-download', action='store_true', help='Only downloads and parses the namelist - doesn\'t update blocks/bans')

    args = parser.parse_args()

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

        print('**********************************************************************************')
        print('*** WARNING: first run of script detected.  This is going to take a long time. ***')
        print('**********************************************************************************')

    if args.only_download:
        print('--only-download invoked - terminating...')

    # This is where the party starts.
    diff = open(SCRATCH_BLOCKLIST).readline()

    # Most users aren't going to be expecting a brower window to get popped open by
    # a python script, so we should probably explain wtf is about to happen...
    print("""
    This application needs to be authorized with Twitch to allow access to your blocklist and/or
    channel bans.  

    In a few moments, a browser window will open requesting authorization from Twitch. Click the
    "authorize" button to allow this script to continue.

    If you've already authorized this script previously, the 
    """)

    # Do the OAuth dance with Twitch
    access_token = get_access_token()

    session = requests.Session()
    
    # A session lets us automagically include the necessary auth headers
    # for the Twitch API, so we won't need to repeat ourselves.  
    session.headers.update({'Client-Id': os.environ.get('TWITCH_CLIENT_ID')})
    session.headers.update({'Authorization': 'Bearer {}'.format(access_token)})

    # Attach the 
    session.hooks['response'].append(ratelimit_handler)
    session.hooks['response'].append(api_health_handler)

    # This code is only needed if we're doing chat bans
    script_user = None
    if not args.only_blocks:
        # For the chat ban portion of this script, we're going to need to know the script
        # user's channel name (i.e. their login name).  We don't know it now, but we can
        # divine it from the auth token with an API call.
        script_user = session.get(
            'https://api.twitch.tv/helix/users',
        )

    
    for bot in diff:
        # so begins the hoop-jumping... need to get the bot user's ID#
        bot_user = session.get(
            'https://api.twitch.tv/helix/users',
            params={
                'login': bot
            }
        )

        # Sanity check: if the user fetch fails, it's possible that Twitch has already
        # dealt with it, in which case we don't need to proceed any further.
        #
        # Annoyingly this API endpoint always returns 200 Success, so we have to 
        # check the request body itself.
        if len(bot_user.json()['data'] > 0):

            # Process user blocklist API calls
            if not args.only_blocks:
                bot_block = session.put(
                    'https://api.twitch.tv/helix/users/blocks',
                    params={
                        'target_user_id': bot_user.json()['data'][0]['id']
                    }
                )
                
                # Finally an endpoint that does things right...
                if bot_block.status_code == "204":
                    print('+++ {} added to block list.'.format(bot))
                elif bot_block.status_code == '400':
                    print('!!! {} request invalid - {} possibly already exists in block list'.format(bot))
                else:
                    print('*** API Authorization Failure - script cannot continue and will abort')
                    exit()

            # Process channel ban API calls
            if not args.only_bans:
                #TODO: handle chat bans
                pass

        else:
            print('*** User {} not found - likely already killed by Twitch'.format(bot))

        # REMOVING THIS WON'T MAKE THE SCRIPT GO FASTER.  Removing this *WILL* make you
        # hit the API/chat rate limits faster and in the worst case make you unable to
        # chat in any channel while the script is running (which you really shouldn't 
        # be doing anyways)
        time.sleep(0.5)

if __name__ == "__main__":
    main()