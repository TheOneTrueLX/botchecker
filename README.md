# botchecker.py
This script is an absurdly simple (and probably really badly coded) script that takes a Twitch username as an input and performs some checks using the Twitch API to help determine whether or not the user is a bot.

The party piece of this script is the checks it performs on the Twitch bot blocklist curated by LinoYeen over at https://github.com/LinoYeen/Namelists.  The script downloads a copy of this namelist and checks if the username provided is on that list.

Additionally, this script prints some basic account stats such as the account age and the number of people the account is following.  This might not seems like a big deal, but it saves you the risk of having to look in the suspect user's Twitch page and risk getting your IP leaked through a malicious panel extension.

There will be bugs.  There are always bugs.  Report them to me and I will fix them eventually.

# Install
NOTE: This script requires Python 3.x

 1. Clone this repository
 2. Go to https://dev.twitch.tv/console and get yourself a Twitch API client ID and client secret
 3. Copy `.env-example` to `.env`, then put the client ID and client secret that you just got from Twitch into the proper spots in that file.
 4. Run `pip install -r requirements.txt` to install the prerequisite modules (maybe consider setting up a venv for this)
 5. Run `botchecker.py <twitch_username>` to look up a user

# Notes
 - You can adjust `MAX_BLOCKLIST_AGE` in `.env` to adjust the frequency with which the script checks for a new blocklist file.  Please don't set this to an unreasonable number.
 - If you want to force a re-download of the blocklist, just delete `namelist.txt` and rerun the script.