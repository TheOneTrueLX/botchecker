import os, stat, mmap, time
from datetime import datetime, timezone
import argparse

# `pip install python-dotenv requests python-dateutil` in order to use this script
from dotenv import load_dotenv
import requests
import dateutil.parser as dt

BLOCKLIST='namelist.txt'

def update_namelist():
    # uses namelist from https://github.com/LinoYeen/Namelists 
    # If the name list is older than MAX_BLOCKLIST_AGE, delete it.
    # Need to do some silly type coersion here because apparently everything from the environment
    # is a string I guess?
    if (time.time() - os.stat(BLOCKLIST)[stat.ST_MTIME]) > int(os.environ.get('MAX_BLOCKLIST_AGE')):
        os.remove(BLOCKLIST)

    # Download the file if it doesn't already exist.  Note that this isn't particularly sophisticated,
    # so if you want a fresh copy, you'll need to delete the existing namelist.txt file before running
    # the script.
    if not os.path.exists(BLOCKLIST):
        response = requests.get('https://raw.githubusercontent.com/LinoYeen/Namelists/main/namelist.txt')
        with open(BLOCKLIST, 'wb') as f:
            f.write(response.content)

def blocklist_lookup(login_name):
    # before doing a blocklist lookup, we'll make sure we have a fresh namelist
    update_namelist()

    # python 3 expects a byte array in mmap.find(), so if you're trying to use this
    # script in python 2, expect none of this to work
    with open(BLOCKLIST, 'rb', 0) as file, mmap.mmap(file.fileno(), 0, access=mmap.ACCESS_READ) as s:
        if s.find(bytearray(login_name.encode())) != -1:
            return True
    
    return False

def twitch_api_auth():
    # get a client auth token - no caching of tokens since I don't really want this script to 
    # have to store secrets locally.
    auth_payload = {
        'client_id': os.environ.get('TWITCH_CLIENT_ID'),
        'client_secret': os.environ.get('TWITCH_CLIENT_SECRET'),
        'grant_type': 'client_credentials',
        'scope': 'user:read:email user:read:broadcast'
    }

    response = requests.post('https://id.twitch.tv/oauth2/token', params=auth_payload)
    client_credentials = response.json()

    # create a session and set the auth headers
    session = requests.Session()
    session.headers.update({'Client-Id': auth_payload['client_id']})
    session.headers.update({'Authorization': 'Bearer {}'.format(client_credentials['access_token'])})

    # return the session
    return session

def get_user_info(session, login_name):
    # return a dict containing the API output from Twitch
    response = session.get('https://api.twitch.tv/helix/users', params={'login': login_name})
    data = response.json()
    if len(data['data']) == 0:
        # the twitch api returns an empty set if a user could not be found... that's not really
        # convenient for us so we test the response object and return None if we see an empty set
        return None
    
    # since we're only looking up a single user, the user data will always been in set position 0
    return data['data'][0]

def get_user_total_follows(session, broadcaster_id):
    # return the total number of accounts that the user being tested currently follows
    response = session.get('https://api.twitch.tv/helix/users/follows', params={'from_id': broadcaster_id})
    return response.json()['total']

def get_user_age(created_at):
    # return the user age in days
    delta = datetime.now(timezone.utc) - dt.parse(created_at)
    return delta.days

def main():
    # do the thing with the environment variables
    load_dotenv()

    # set up some rudimentary command-line help
    parser = argparse.ArgumentParser(
        prog="botchecker.py",
        description="A utility to check if a twitch.tv user is a known bot"
    )

    parser.add_argument('login_name', type=str, help='A twitch.tv username')

    args = parser.parse_args()
    
    if args.login_name is None:
        print('ERROR: no username provided')
        exit()

    # authenticate and get the user info
    # I probably should add some better error checking in the auth routine
    session = twitch_api_auth()
    user = get_user_info(session, args.login_name)
    
    # if we get None back from get_user_info(), the username passed could
    # not be found.  Yay I guess?
    if user is None:
        print('ERROR: username \'{}\' was not found'.format(args.login_name))
        exit()
    
    # a vain attempt at making the output of this program pretty
    print('\nReport for Twitch user id #{}: {}\n-------------------------------------------------------------\n'.format(
        user['id'],
        user['display_name']
    ))

    # check account age... I'm too lazy to format this elegantly right now.
    account_age = get_user_age(user['created_at'])
    print('Account is {} days old'.format(account_age))
    if account_age <= 5:
        print('\tWARNING: NEW ACCOUNT (<= 5 DAYS)')

    if user['broadcaster_type'] == '':
        print('User is neither an affiliate or partner')
    else:
        print('User type = {}'.format(user['broadcaster_type']))

    # check follows
    print('User is following {} people'.format(get_user_total_follows(session, user['id'])))

    # check the username against the blocklist
    if blocklist_lookup(user['login']):
        print("\nALERT: ************************************************************************")
        print("ALERT: {} is on the list of known bot accounts.".format(args.login_name))
        print("ALERT: ************************************************************************")
    
    print('\n\n')

if __name__ == "__main__":
    main()